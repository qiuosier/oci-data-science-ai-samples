import logging
import json
import traceback
import datetime
import oci
from ads.jobs import Job, DataScienceJobRun, DataScienceJob
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

    PREFIX = "logs"

    def get_from_service(self, ocid):
        logger.debug("Getting logs from OCI for %s", ocid)
        run = DataScienceJobRun(**get_ds_auth(client="ads")).from_ocid(ocid)
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
        logger.debug("%s - %s log messages.", ocid, str(len(logs)))
        stopped = (
            run.lifecycle_state in DataScienceJobRun.TERMINAL_STATES
            and run.time_finished
            < datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(minutes=5)
        )
        return {
            "ocid": ocid,
            "logs": logs,
            "status": run.lifecycle_state,
            "statusDetails": run.lifecycle_details,
            "stopped": stopped,
        }


class JobKeeper(CacheKeeper):

    PREFIX = "jobs"

    def get_from_service(self, ocid):
        logger.debug("Getting job details from OCI for %s", ocid)
        job = Job(**get_ds_auth(client="ads")).from_datascience_job(ocid)
        data = job.to_dict()
        data["stopped"] = True
        return data


class JobRunKeeper(CacheKeeper):
    PREFIX = "runs"

    def get_from_service(self, ocid):
        logger.debug("Getting job run from OCI for %s", ocid)
        run = DataScienceJobRun(**get_ds_auth(client="ads")).from_ocid(ocid)
        logger.debug(
            "Job Run Status: %s - %s", run.lifecycle_state, run.lifecycle_details
        )
        data = run.to_dict()
        data["stopped"] = run.lifecycle_state in DataScienceJobRun.TERMINAL_STATES
        return data


class ModelKeeper(CacheKeeper):
    PREFIX = "models"

    def get_from_service(self, ocid):
        client = oci.data_science.DataScienceClient(**get_ds_auth())
        model = client.get_model(ocid).data
        data = json.loads(str(model))
        data["stopped"] = True
        return data


class RunListKeeper(CacheKeeper):
    PREFIX = "run_list"

    def __init__(self, cache_location=None) -> None:
        super().__init__(cache_location)
        self.job_keeper = JobKeeper()

    def get_from_service(self, ocid):
        job_dict = self.job_keeper.get(ocid)
        job = Job(**get_ds_auth(client="ads")).from_dict(job_dict)
        job.infrastructure.dsc_job.id = ocid
        runs = job.run_list()
        stopped = all(
            [run.lifecycle_state in DataScienceJobRun.TERMINAL_STATES for run in runs]
        )
        data = {"runs": [run.to_dict() for run in runs], "stopped": stopped}
        return data
    

class ArgsKeeper(CacheKeeper):
    PREFIX = "args"
