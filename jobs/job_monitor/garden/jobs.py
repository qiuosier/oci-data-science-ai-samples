import json
import logging
import os
import traceback

from ads.jobs import DataScienceJobRun
from commons.auth import get_ds_auth

logger = logging.getLogger(__name__)


def format_logs(logs):
    """Reformat logs from job run."""
    for log in logs:
        if str(log["time"]).endswith("Z"):
            log["time"] = log["time"].split(".")[0].replace("T", " ")
        else:
            log["time"] = str(log["time"])
    logs = sorted(logs, key=lambda x: x["time"] if x["time"] else "")
    logs = [str(log["time"]) + " " + log["message"] for log in logs]
    return logs


class CacheManager:

    def __init__(self, cache_location) -> None:
        if not os.path.exists(cache_location):
            os.makedirs(cache_location)
        self.cache_location = cache_location

    def _get_cache_path(self, ocid):
        return os.path.join(self.cache_location, f"{ocid}.json")

    def save_to_cache(self, ocid, context):
        cache_file = self._get_cache_path(ocid)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(context, f)

    def get_from_cache(self, ocid):
        cache_file = self._get_cache_path(ocid)
        if os.path.exists(cache_file):
            logger.debug("Getting from cache for %s", ocid)
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def get_from_service(self, ocid):
        raise NotImplementedError()

    def get(self, ocid):
        context = self.get_from_cache(ocid)
        if context is None:
            context = self.get_from_service(ocid)
            if context.get("stopped"):
                self.save_to_cache(ocid, context)
        return context


class JobLogManager(CacheManager):

    def get_from_service(self, job_run_ocid):
        logger.debug("Getting logs from OCI for %s", job_run_ocid)
        run = DataScienceJobRun(**get_ds_auth(client="ads")).from_ocid(job_run_ocid)
        logger.debug(
            "Job Run Status: %s - %s", run.lifecycle_state, run.lifecycle_details
        )
        if not run.log_id:
            logs = []
        else:
            try:
                logs = run.logs()
                logs = format_logs(logs)
            except Exception:
                traceback.print_exc()
                logs = []
        logger.debug("%s - %s log messages.", job_run_ocid, str(len(logs)))
        return {
            "ocid": job_run_ocid,
            "logs": logs,
            "status": run.lifecycle_state,
            "statusDetails": run.lifecycle_details,
            "stopped": (run.lifecycle_state in DataScienceJobRun.TERMINAL_STATES),
        }
