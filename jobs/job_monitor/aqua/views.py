import json
import re
from dataclasses import dataclass, field
from typing import Dict, Optional
import fire
import oci
from flask import Blueprint, render_template, jsonify
from ads.jobs import Job, DataScienceJob, DataScienceJobRun
from commons.auth import get_ds_auth
from commons.components import base_context_with_compartments
from garden.jobs import JobKeeper, RunListKeeper, ModelKeeper


aqua_views = Blueprint("aqua", __name__, template_folder="templates")

job_keeper = JobKeeper()
model_keeper = ModelKeeper()
run_list_keeper = RunListKeeper()


def make_id(s):
    return re.sub(r"\W+", "-", s)


def parse_args(**kwargs):
    return kwargs


@dataclass
class FineTuningJob:
    name: str
    model: str
    status: str
    shape: str
    replica: int
    batch_size: int
    training_data: str
    val_set_size: float
    # output_dir: str
    # epoch: int
    # learning_rate: float


@dataclass
class ModelReport:
    name: str
    jobs: list = field(default_factory=list)

    def __post_init__(self):
        self.id = make_id(self.name)

    def add_job(self, job: Job):
        kwargs = fire.Fire(parse_args, command=job.runtime.envs["OCI__LAUNCH_CMD"])
        runs = run_list_keeper.get(job.id)["runs"]
        run = DataScienceJobRun(**get_ds_auth(client="ads")).from_dict(runs[0])
        replica = run.job_configuration_override_details.environment_variables.get(
            "NODE_COUNT", 1
        )
        status = run.lifecycle_state
        self.jobs.append(
            FineTuningJob(
                name=job.name,
                model=self.name,
                status=status,
                shape=job.infrastructure.shape_name,
                replica=replica,
                batch_size=kwargs.get("micro_batch_size", -1),
                training_data=kwargs.get("training_data", ""),
                val_set_size=kwargs.get("val_set_size", -1),
            )
        )


@dataclass
class ImageReport:
    """"""

    image: str
    reports: Dict[str, ModelReport] = field(default_factory=dict)
    id: str = field(init=False)

    def __post_init__(self):
        self.id = make_id(self.image)

    @property
    def models(self):
        """A list of model names."""
        names = list(self.reports.keys())
        names.sort()
        return [self.reports[name] for name in names]

    def add_job(self, job: Job):
        if "AIP_SMC_FT_ARGUMENTS" in job.runtime.envs:
            model_ocid = json.loads(job.runtime.envs["AIP_SMC_FT_ARGUMENTS"])[
                "baseModel"
            ]["modelId"]
            model = model_keeper.get(model_ocid)
            model_name = model["display_name"]
        else:
            return
        report = self.reports.get(model_name, ModelReport(name=model_name))
        report.add_job(job)
        self.reports[model_name] = report


class ImageGroup(dict):
    """Mapping image name to ImageReport."""

    def add_job(self, job):
        # Get the image of the job
        image = job.runtime.image
        # Get existing image report or create new one
        image_report = self.get(image, ImageReport(image=image))
        image_report: ImageReport
        image_report.add_job(job)
        self[image] = image_report

    @classmethod
    def from_job_summary_list(cls, job_summary_list):
        group = cls()
        for job_summary in job_summary_list:
            job_dict = job_keeper.get(job_summary.id)
            job = Job(**get_ds_auth(client="ads")).from_dict(job_dict)
            job.infrastructure.dsc_job.id = job_summary.id
            group.add_job(job)
        return group


@aqua_views.route("/fine_tune/report")
def fine_tune_report():
    context = base_context_with_compartments()
    context["title"] = "AQUA FT Jobs"
    compartment_id = context["compartment_id"]
    project_id = context["project_id"]
    if compartment_id and project_id:
        client = oci.data_science.DataScienceClient(**get_ds_auth())
        job_summary_list = client.list_jobs(
            compartment_id=compartment_id,
            project_id=project_id,
            lifecycle_state="ACTIVE",
            limit=10,
        ).data

        context["group"] = ImageGroup.from_job_summary_list(job_summary_list)

    return render_template("aqua_ft_report.html", **context)
