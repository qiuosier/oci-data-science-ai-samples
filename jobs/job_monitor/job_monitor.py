import datetime

import json
import os
import re
import subprocess
import traceback
import urllib.parse
import uuid

import ads
import oci
import requests
import yaml

from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    render_template_string,
    redirect,
    session,
)


from ads.common.oci_datascience import OCIDataScienceMixin
from ads.common.oci_resource import OCIResource
from ads.jobs import DataScienceJobRun, Job, DataScienceJob
from ads.model.datascience_model import DataScienceModel
from ads.common.object_storage_details import ObjectStorageDetails

import metric_query
from commons.auth import get_authentication, load_oci_config, load_profiles
from commons.logs import logger
from commons.errors import abort_with_json_error, handle_service_exception
from commons.config import CONFIG_MAP
from studio import jobs as studio_jobs
from studio.models import StudioModel


SERVICE_METRICS_NAMESPACE = "oci_datascience_jobrun"
SERVICE_METRICS_DIMENSION = "resourceId"
CUSTOM_METRICS_NAMESPACE_ENV = "OCI__METRICS_NAMESPACE"
CUSTOM_METRICS_DIMENSION = metric_query.CUSTOM_METRIC_OCID_DIMENSION


# Load config
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, encoding="utf-8") as f:
        config = json.load(f)
else:
    config = {}
YAML_DIR = os.path.join(os.path.dirname(__file__), config.get("yaml_dir", None))


global_tenancy_id = None


# Flask templates location
app = Flask(
    __name__, template_folder=os.path.join(os.path.dirname(__file__), "templates")
)
# Use hardware address as secret key so it will likely be unique for each computer.
app.secret_key = str(uuid.getnode())


def check_ocid(ocid):
    if not re.match(r"ocid[0-9].[a-z]+.oc[0-9].[a-z-]+.[a-z0-9]+", ocid):
        abort_with_json_error(404, f"Invalid OCID: {ocid}")


def check_project_id(project_id):
    if not re.match(
        r"ocid[0-9].datascienceproject.oc[0-9].[a-z-]+.[a-z0-9]+", project_id
    ):
        abort_with_json_error(404, f"Invalid Project OCID: {project_id}")


def check_compartment_id(compartment_id):
    if not re.match(
        r"ocid[0-9].(compartment|tenancy).oc[0-9]..[a-z0-9]+", compartment_id
    ):
        abort_with_json_error(404, f"Invalid Compartment OCID: {compartment_id}")


def is_valid_ocid(resource_type, ocid):
    if re.match(r"ocid[0-9]." + resource_type + r".oc[0-9].[a-z-]+.[a-z0-9]+", ocid):
        return True
    if re.match(r"ocid[0-9]." + resource_type + r"int.oc[0-9].[a-z-]+.[a-z0-9]+", ocid):
        return True
    return False


def check_compartment_project(compartment_id, project_id):
    if str(project_id).lower() == "all":
        project_id = None
    else:
        check_project_id(project_id)
        # Lookup compartment when project ID is valid but no compartment is given.
        if not compartment_id:
            compartment_id = OCIResource.get_compartment_id(project_id)
    check_compartment_id(compartment_id)
    return compartment_id, project_id


def check_endpoint():
    endpoint = request.args.get("endpoint")
    if endpoint:
        OCIDataScienceMixin.kwargs = {"service_endpoint": endpoint}
        os.environ["OCI_ODSC_SERVICE_ENDPOINT"] = endpoint
    else:
        OCIDataScienceMixin.kwargs = None
        os.environ.pop("OCI_ODSC_SERVICE_ENDPOINT", None)
    return endpoint


def check_limit():
    limit = request.args.get("limit", 10)
    if isinstance(limit, str) and not limit.isdigit():
        abort_with_json_error(400, "limit parameter must be an integer.")
    return limit


def list_all_sub_compartments(client: oci.identity.IdentityClient, compartment_id):
    compartments = oci.pagination.list_call_get_all_results(
        client.list_compartments,
        compartment_id=compartment_id,
        compartment_id_in_subtree=True,
        access_level="ANY",
    ).data
    return compartments


def list_all_child_compartments(client: oci.identity.IdentityClient, compartment_id):
    compartments = oci.pagination.list_call_get_all_results(
        client.list_compartments,
        compartment_id=compartment_id,
    ).data
    return compartments


def get_tenancy_ocid(auth):
    if auth["config"]:
        if "TENANCY_OCID" in os.environ:
            tenancy_id = os.environ["TENANCY_OCID"]
        elif "override_tenancy" in auth["config"]:
            tenancy_id = auth["config"]["override_tenancy"]
        else:
            tenancy_id = auth["config"]["tenancy"]
    else:
        tenancy_id = getattr(auth["signer"], "tenancy_id", None)
    return tenancy_id


def init_components():
    compartment_id = request.args.get("c")
    project_id = request.args.get("p")
    limit = request.args.get("limit", 10)
    endpoint = check_endpoint()

    if project_id:
        compartment_id, project_id = check_compartment_project(
            compartment_id, project_id
        )
    else:
        compartment_id = None

    auth = get_authentication()
    global global_tenancy_id
    tenancy_ocid = request.args.get("t")
    if not tenancy_ocid:
        tenancy_ocid = get_tenancy_ocid(auth)
    global_tenancy_id = tenancy_ocid
    logger.debug("Tenancy ID: %s", global_tenancy_id)
    client = oci.identity.IdentityClient(**auth)
    compartments = []
    error = None
    # User may not have permissions to list compartment.
    try:
        compartments.extend(
            list_all_sub_compartments(client, compartment_id=global_tenancy_id)
        )
    except oci.exceptions.ServiceError:
        traceback.print_exc()
        error = (
            f"ERROR: Unable to list all sub compartment in tenancy {global_tenancy_id}."
        )
        try:
            compartments.append(
                list_all_child_compartments(client, compartment_id=global_tenancy_id)
            )
        except oci.exceptions.ServiceError:
            traceback.print_exc()
            error = f"ERROR: Unable to list all child compartment in tenancy {global_tenancy_id}."
    try:
        root_compartment = client.get_compartment(global_tenancy_id).data
        compartments.insert(0, root_compartment)
    except oci.exceptions.ServiceError:
        traceback.print_exc()
        error = (
            f"ERROR: Unable to get details of the root compartment {global_tenancy_id}."
        )
        if compartments:
            compartments.insert(
                0,
                oci.identity.models.Compartment(
                    id=global_tenancy_id, name=" ** Root - Name N/A **"
                ),
            )
    context = dict(
        compartment_id=compartment_id,
        project_id=project_id,
        compartments=compartments,
        limit=limit,
        service_endpoint=endpoint,
        error=error,
    )
    return context


@app.route("/favicon.ico")
def favicon():
    return redirect("https://www.oracle.com/favicon.ico")


@app.route("/")
def job_monitor():
    context = init_components()
    return render_template("job_monitor.html", **context)


@app.route("/compartments")
def list_compartments():
    context = init_components()
    compartments = [compartment.id for compartment in context["compartments"]]
    return jsonify({"compartments": compartments, "error": context["error"]})


@app.route("/jobs/<compartment_id>/<project_id>")
@handle_service_exception
def list_jobs(compartment_id, project_id):
    compartment_id, project_id = check_compartment_project(compartment_id, project_id)
    limit = check_limit()
    endpoint = check_endpoint()
    job_list = []

    # Calling OCI API here instead of ADS API is faster :)
    jobs = (
        oci.data_science.DataScienceClient(
            service_endpoint=endpoint, **get_authentication()
        )
        .list_jobs(
            compartment_id=compartment_id,
            project_id=project_id,
            lifecycle_state="ACTIVE",
            sort_by="timeCreated",
            sort_order="DESC",
            limit=int(limit) + 5,
        )
        .data[: int(limit)]
    )

    for job in jobs:
        job_data = dict(
            name=job.display_name,
            id=job.id,
            ocid=job.id,
            time_created=job.time_created.timestamp(),
            html=render_template("job_accordion.html", job=job),
        )
        job_list.append(job_data)
    return jsonify({"limit": limit, "jobs": job_list, "error": None})


@app.route("/job_runs/<job_id>")
def list_job_runs(job_id):
    check_ocid(job_id)
    check_endpoint()
    job = Job.from_datascience_job(job_id)
    runs = job.run_list()
    run_list = []
    for run in runs:
        if run.status == "DELETED":
            continue
        run_data = {
            "ocid": run.id,
            "job_ocid": job.id,
            "html": render_template("job_run_template.html", run=run, job=job),
        }
        run_list.append(run_data)
    return jsonify({"runs": run_list})


@app.route("/projects/<compartment_id>")
def list_projects(compartment_id):
    endpoint = check_endpoint()
    logger.debug(f"Getting projects in compartment {compartment_id}")
    ds_client = oci.data_science.DataScienceClient(
        service_endpoint=endpoint, **get_authentication()
    )
    projects = oci.pagination.list_call_get_all_results(
        ds_client.list_projects, compartment_id=compartment_id, sort_by="displayName"
    ).data
    # projects = sorted(projects, key=lambda x: x.display_name)
    logger.debug(f"{len(projects)} projects")
    context = {
        "compartment_id": compartment_id,
        "projects": [
            {"display_name": project.display_name, "ocid": project.id}
            for project in projects
        ],
    }
    return jsonify(context)


def format_logs(logs):
    for log in logs:
        if str(log["time"]).endswith("Z"):
            log["time"] = log["time"].split(".")[0].replace("T", " ")
        else:
            log["time"] = str(log["time"])
    logs = sorted(logs, key=lambda x: x["time"] if x["time"] else "")
    logs = [str(log["time"]) + " " + log["message"] for log in logs]
    return logs


@app.route("/logs/<job_run_ocid>")
def get_logs(job_run_ocid):
    logger.debug(f"Getting logs for {job_run_ocid}...")
    run = DataScienceJobRun.from_ocid(job_run_ocid)
    logger.debug(f"Job Run Status: {run.lifecycle_state} - {run.lifecycle_details}")
    if not run.log_id:
        logs = []
    else:
        logs = run.logs()
        logs = format_logs(logs)
    logger.debug(f"{job_run_ocid} - {len(logs)} log messages.")
    context = {
        "ocid": job_run_ocid,
        "logs": logs,
        "status": run.lifecycle_state,
        "statusDetails": run.lifecycle_details,
        "stopped": (
            True if run.lifecycle_state in DataScienceJobRun.TERMINAL_STATES else False
        ),
    }
    return jsonify(context)


@app.route("/delete/<ocid>")
def delete_resource(ocid):
    check_endpoint()
    if is_valid_ocid("datasciencejob", ocid):
        job = Job.from_datascience_job(ocid)
        try:
            job.delete()
            error = None
            logger.info("Deleted Job: %s", ocid)
        except oci.exceptions.ServiceError as ex:
            error = ex.message

    elif is_valid_ocid("datasciencejobrun", ocid):
        run = DataScienceJobRun.from_ocid(ocid)
        try:
            if run.status not in run.TERMINAL_STATES:
                run.cancel()
                logger.info("Cancelled Job Run: %s", ocid)
            run.delete()
            error = None
            logger.info("Deleted Job Run: %s", ocid)
        except oci.exceptions.ServiceError as ex:
            error = ex.message

    elif is_valid_ocid("datasciencemodel", ocid):
        resource = DataScienceModel.from_id(ocid)
        try:
            resource.delete()
            error = None
            logger.info("Deleted Model: %s", ocid)
        except oci.exceptions.ServiceError as ex:
            error = ex.message
    else:
        error = "Not supported"

    return jsonify({"ocid": ocid, "error": error})


@app.route("/download/url/<path:url>")
def download_from_url(url):
    res = requests.get(url)
    return res.content


def load_yaml_list(uri):
    yaml_files = []
    if not uri:
        return {"yaml": yaml_files}
    for filename in os.listdir(uri):
        if filename.endswith(".yaml") or filename.endswith(".yml"):
            yaml_files.append({"filename": filename})
    yaml_files.sort(key=lambda x: x.get("filename"))
    return {"yaml": yaml_files}


@app.route("/yaml")
@app.route("/yaml/<filename>")
def load_yaml(filename=None):
    if not filename:
        return jsonify(load_yaml_list(YAML_DIR))
    with open(os.path.join(YAML_DIR, filename), encoding="utf-8") as f:
        content = f.read()
    return jsonify({"filename": filename, "content": content})


@app.route("/run", methods=["POST"])
def run_workload():
    oci_auth = get_authentication()
    check_endpoint()
    # The following config check is added for security reason.
    # When the app is started with resource principal or instance principal,
    # this will restrict the app to only monitor job runs and status.
    # Without the following restriction, anyone have access to the website could use it to run large workflow.
    if not oci_auth["config"]:
        abort_with_json_error(
            403,
            "Starting a workflow is only available when you launch the app locally with OCI API key.",
        )
    try:
        yaml_string = urllib.parse.unquote(request.data[5:].decode())
        yaml_string = render_template_string(yaml_string, **load_oci_config())
        workflow = yaml.safe_load(yaml_string)

        if workflow.get("kind") == "job":
            job = Job.from_dict(workflow)
            job.create()
            logger.info("Created Job: %s", job.id)
            job_run = job.run()
            logger.info("Created Job Run: %s", job_run.id)
            job_id = job.id
        else:
            # Running an opctl workflow require additional dependencies for ADS
            from ads.opctl.cmds import run as opctl_run

            kwargs = {}
            kwargs["tag"] = None
            kwargs["registry"] = None
            kwargs["dockerfile"] = None
            kwargs["source_folder"] = None
            kwargs["nobuild"] = 1
            kwargs["backend"] = None
            kwargs["auto_increment"] = None
            kwargs["nopush"] = 1
            kwargs["dry_run"] = None
            kwargs["job_info"] = None
            info = opctl_run(workflow, **kwargs)
            job_id = info[0].id

        return jsonify(
            {
                "job": job_id,
            }
        )
    except Exception as ex:
        traceback.print_exc()
        abort_with_json_error(500, str(ex))


def get_custom_metrics_namespace(job_run):
    job_envs = job_run.job.runtime.envs
    return job_envs.get(CUSTOM_METRICS_NAMESPACE_ENV)


def get_metrics_list(ocid):
    job_run = DataScienceJobRun.from_ocid(ocid)
    custom_metric_namespace = get_custom_metrics_namespace(job_run)
    client = oci.monitoring.MonitoringClient(**get_authentication())
    service_metrics = metric_query.list_job_run_metrics(
        job_run, SERVICE_METRICS_NAMESPACE, SERVICE_METRICS_DIMENSION, client
    )
    if custom_metric_namespace:
        custom_metrics = metric_query.list_job_run_metrics(
            job_run,
            custom_metric_namespace,
            metric_query.CUSTOM_METRIC_OCID_DIMENSION,
            client,
        )
    else:
        custom_metrics = []
    metrics = service_metrics + custom_metrics
    if "gpu.gpu_utilization" in metrics and "GpuUtilization" in metrics:
        metrics.remove("GpuUtilization")
    metric_display_name = {
        "CpuUtilization": "CPU Utilization (%)",
        "GpuUtilization": "GPU Utilization (%)",
        "DiskUtilization": "Disk Utilization (%)",
        "MemoryUtilization": "Memory Utilization (%)",
        "NetworkBytesIn": "Network Bytes In",
        "NetworkBytesOut": "Network Bytes Out",
        "gpu.gpu_utilization": "GPU Utilization (%)",
        "gpu.memory_usage": "GPU Memory (%)",
        "gpu.power_draw": "GPU Power (W)",
        "gpu.temperature": "GPU Temperature (&#8451;)",
    }
    return [
        {"key": metric, "display": metric_display_name.get(metric, metric)}
        for metric in metrics
    ]


@app.route("/metrics/<ocid>")
def list_metrics(ocid):
    return jsonify(
        {
            "metrics": get_metrics_list(ocid),
        }
    )


@app.route("/metrics/<name>/<ocid>")
def get_metrics(name, ocid):
    job_run = DataScienceJobRun.from_ocid(ocid)
    if name.startswith("gpu"):
        metric_namespace = get_custom_metrics_namespace(job_run)
        dimension = CUSTOM_METRICS_DIMENSION
    else:
        metric_namespace = "oci_datascience_jobrun"
        dimension = SERVICE_METRICS_DIMENSION
    run_metrics = []
    if metric_namespace and job_run.time_started:
        client = oci.monitoring.MonitoringClient(**get_authentication())
        metric_query_args = {
            "job_run": job_run,
            "name": name,
            "namespace": metric_namespace,
            "ocid_dimension": dimension,
            "monitoring_client": client,
            "start": job_run.time_started,
            "end": (
                job_run.time_finished
                if job_run.time_finished
                else datetime.datetime.now(datetime.timezone.utc)
            ),
        }
        results = metric_query.get_metric_values(**metric_query_args)

        if results:
            for result in results:
                run_metrics.append(
                    [
                        {"timestamp": p.timestamp, "value": p.value}
                        for p in result.aggregated_datapoints
                    ]
                )

    timestamps = set()
    datasets = []
    for metric in run_metrics:
        timestamps.update([p["timestamp"] for p in metric])
        datasets.append({p["timestamp"]: p["value"] for p in metric})
    timestamps = list(timestamps)
    timestamps.sort()
    values = []
    for dataset in datasets:
        values.append([dataset.get(timestamp) for timestamp in timestamps])
    datasets = [{"label": f"#{i}", "data": v} for i, v in enumerate(values, start=1)]
    return jsonify(
        {
            "metrics": get_metrics_list(ocid),
            "timestamps": timestamps,
            "datasets": datasets,
        }
    )


@app.route("/shapes/<compartment_ocid>")
@handle_service_exception
def supported_shapes(compartment_ocid):
    shapes = [
        shape.name
        for shape in DataScienceJob.instance_shapes(compartment_id=compartment_ocid)
    ]
    fast_launch_shapes = [
        shape.shape_name
        for shape in DataScienceJob.fast_launch_shapes(compartment_id=compartment_ocid)
    ]
    return jsonify(
        {
            "supported_shapes": shapes,
            "fast_launch_shapes": fast_launch_shapes,
        }
    )


@app.route("/profiles", methods=["GET"])
def list_profiles():
    profiles = list(load_profiles().keys())
    return jsonify(
        {"profiles": profiles, "selected": session.get("profile", profiles[0])}
    )


@app.route("/profiles", methods=["POST"])
def select_profile():
    data = request.get_json()
    if "profile" in data:
        session["profile"] = data["profile"]
    return jsonify({})


@app.route("/authenticate/token/<profile>")
def authenticate_with_token(profile):
    """Authenticate with security token."""
    auth = get_authentication(profile_name=profile)
    cmd = f"oci session authenticate --profile-name {profile}"
    region = auth.get("config", {}).get("region")
    if region:
        cmd += f" --region {region}"
    try:
        subprocess.check_output(f"{cmd}", shell=True)
        error = None
    except subprocess.CalledProcessError as ex:
        error = ex.output
    return jsonify({"error": str(error)})


@app.route("/storage/buckets")
def storage_namespace():
    tenancy_id = request.args.get("t", global_tenancy_id)
    compartment_id = request.args.get("c", tenancy_id)
    auth = get_authentication()
    client = oci.object_storage.ObjectStorageClient(**auth)
    namespace = client.get_namespace(compartment_id=tenancy_id).data
    buckets = oci.pagination.list_call_get_all_results(
        client.list_buckets, namespace, compartment_id
    ).data
    return jsonify(
        {"namespace": namespace, "buckets": [bucket.name for bucket in buckets]}
    )


@app.route("/studio")
def studio_dashboard():
    context = init_components()
    return render_template("studio.html", **context)


def model_metadata_to_dict(model):
    if not isinstance(model, dict):
        model = model.to_dict()["spec"]
    metadata = {
        item["key"]: item["value"] for item in model["customMetadataList"]["data"]
    }
    if metadata.get("base_model", "").startswith("ocid"):
        metadata["is_base_model"] = False
    else:
        metadata["is_base_model"] = True
    return metadata


@app.route("/studio/models", methods=["GET"])
def studio_list_models():
    compartment_id = request.args.get("c")
    project_id = request.args.get("p")
    models = DataScienceModel.list(
        compartment_id=compartment_id, project_id=project_id, lifecycle_state="ACTIVE"
    )
    models = [m.to_dict()["spec"] for m in models]
    models.reverse()
    for model in models:
        model["metadata"] = model_metadata_to_dict(model)
    context = {"models": models}
    context["html"] = render_template("row_models.html", **context)
    return jsonify(context)


@app.route("/studio/models", methods=["POST"])
def studio_add_model():
    data = request.get_json()
    data.update(config)

    required_settings = ["subnet_id", "log_group_id", "log_id", "hf_token", "conda_env"]
    for key in required_settings:
        if key not in data:
            abort_with_json_error(
                400, f"Please set {key} in config.json and restart the app."
            )
    # Create the model
    model = StudioModel().create(**data)
    # Create job to download the model files
    if data["download_files"]:
        studio_jobs.start_downloading_model(data)
    return jsonify(model.dsc_model.to_dict())


@app.route("/studio/verify/<ocid>")
def verify_model(ocid):
    model = DataScienceModel.from_id(ocid)
    metadata = model_metadata_to_dict(model)
    os_uri = ObjectStorageDetails.from_path(
        os.path.join(metadata["model_path"], studio_jobs.DOWNLOAD_STATUS_FILENAME)
    )
    auth = get_authentication()
    os_client = oci.object_storage.ObjectStorageClient(**auth)
    try:
        response = os_client.get_object(
            namespace_name=os_uri.namespace,
            bucket_name=os_uri.bucket,
            object_name=os_uri.filepath,
        )
        metadata["download_status"] = json.loads(response.data.text)
    except oci.exceptions.ServiceError:
        metadata["download_status"] = {}

    job_run_id = metadata["download_status"].get("job_run_ocid")
    if job_run_id:
        run = DataScienceJobRun.from_ocid(job_run_id)
        metadata["download_status"]["job_run_status"] = run.status
    return jsonify(metadata)
