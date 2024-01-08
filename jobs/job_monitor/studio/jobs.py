import json
import os
import tempfile
import oci
from flask import render_template
from ads.common.auth import default_signer
from ads.common.object_storage_details import ObjectStorageDetails
from ads.jobs import Job


DOWNLOAD_STATUS_FILENAME = "oci_download.json"


def start_downloading_model(context):
    """Run a job to download the model files"""
    context["script_path"] = os.path.join(os.path.dirname(__file__), "download_model.py")
    context["output_dir"] = "/home/datascience/outputs"
    context["local_dir"] = os.path.join(context["output_dir"], context["model_path"])
    job_yaml_string = render_template("job_download_model.yaml", **context)
    job = Job.from_string(job_yaml_string).create()
    run = job.run()
    os_uri = ObjectStorageDetails.from_path(context["object_storage_path"])
    with tempfile.TemporaryDirectory() as temp_dir:
        filename = os.path.join(temp_dir, DOWNLOAD_STATUS_FILENAME)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                "job_ocid": job.id,
                "job_run_ocid": run.id
            }, f)
        with open(filename, 'r', encoding="utf-8") as f:
            oci.object_storage.ObjectStorageClient(**default_signer()).put_object(
                namespace_name=os_uri.namespace,
                bucket_name=os_uri.bucket,
                object_name=os.path.join(os_uri.filepath, DOWNLOAD_STATUS_FILENAME),
                put_object_body=f
            )
