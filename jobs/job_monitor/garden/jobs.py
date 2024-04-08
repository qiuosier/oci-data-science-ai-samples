
import logging
import traceback

from ads.jobs import DataScienceJobRun
from commons.auth import get_ds_auth
from garden.cache import CacheKeeper

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


class JobLogKeeper(CacheKeeper):

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
