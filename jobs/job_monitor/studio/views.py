from flask import Blueprint, render_template
from commons.components import init_components


studio_views = Blueprint("studio", __name__, template_folder="templates")


@studio_views.route("/jobs/<ocid>")
def view_job(ocid):
    context = init_components()
    context["title"] = "Job"
    return render_template("view_job.html", **context)
