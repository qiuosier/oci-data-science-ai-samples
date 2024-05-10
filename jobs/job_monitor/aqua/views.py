import oci
from flask import Blueprint, render_template
from commons.auth import get_ds_auth
from commons.components import base_context_with_compartments
from aqua.reports import FineTuningReport


aqua_views = Blueprint("aqua", __name__, template_folder="templates")


@aqua_views.route("/fine_tune/report/images")
def ft_report_images():
    context = base_context_with_compartments()
    context["title"] = "AQUA FT Images"
    compartment_id = context["compartment_id"]
    project_id = context["project_id"]
    if compartment_id and project_id:
        client = oci.data_science.DataScienceClient(**get_ds_auth())
        job_summary_list = client.list_jobs(
            compartment_id=compartment_id,
            project_id=project_id,
            lifecycle_state="ACTIVE",
            limit=50,
        ).data

        context["report"] = FineTuningReport.from_job_summary_list(
            job_summary_list
        ).group_by("image_version", "model")
        context["headers"] = ["shape", "batch_size", "sequence_len"]

    return render_template("aqua/ft_report.html", **context)


@aqua_views.route("/fine_tune/report/models")
def ft_report_models():
    context = base_context_with_compartments()
    context["title"] = "AQUA FT Models"
    compartment_id = context["compartment_id"]
    project_id = context["project_id"]
    if compartment_id and project_id:
        client = oci.data_science.DataScienceClient(**get_ds_auth())
        job_summary_list = client.list_jobs(
            compartment_id=compartment_id,
            project_id=project_id,
            lifecycle_state="ACTIVE",
            limit=75,
        ).data

        report = FineTuningReport.from_job_summary_list(job_summary_list)
        report.save_html("ft_report.html")
        context["report"] = report.group_by("model", "image_version")
        context["headers"] = ["shape", "batch_size", "sequence_len"]

    return render_template("aqua/ft_report.html", **context)
