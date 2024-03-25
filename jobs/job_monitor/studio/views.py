from flask import Blueprint, render_template, jsonify
from ads.jobs import DataScienceJobRun
from commons.auth import get_ds_auth
from commons.components import init_components
from commons.errors import abort_with_json_error, handle_service_exception
from commons.validation import check_ocid


studio_views = Blueprint("studio", __name__, template_folder="templates")


@studio_views.route("/jobs")
@studio_views.route("/jobs/<ocid>")
def view_job(ocid=""):
    if ocid:
        check_ocid(ocid)
    context = init_components()
    context["title"] = "Job"
    context["ocid"] = ocid
    return render_template("view_job.html", **context)


@studio_views.route("/api/runs/<ocid>")
@handle_service_exception
def get_runs(ocid):
    check_ocid(ocid)
    if "datasciencejobrun" in ocid:
        run = DataScienceJobRun(**get_ds_auth(client="ads")).from_ocid(ocid)
        runs = [
            {
                "ocid": run.id,
                "job_ocid": run.job.id,
                "html": render_template("job_run_template.html", run=run, job=run.job),
            }
        ]
        return jsonify({"runs": runs})
    elif "datasciencejob" in ocid:
        from job_monitor import list_job_runs

        return list_job_runs(ocid)
    else:
        abort_with_json_error(404, f"Invalid Job or Job Run OCID: {ocid}")
