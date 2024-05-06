import json
import re
import traceback
from dataclasses import dataclass, field
from typing import Dict
import fire
from ads.jobs import Job, DataScienceJobRun
from commons.auth import get_ds_auth
from commons.validation import is_valid_ocid
from garden.jobs import JobKeeper, RunListKeeper, ModelKeeper


job_keeper = JobKeeper()
model_keeper = ModelKeeper()
run_list_keeper = RunListKeeper()


def parse_args(**kwargs):
    return kwargs


def make_id(s):
    return re.sub(r"\W+", "-", s)


@dataclass
class FineTuningJob:
    id: str
    name: str
    model: str
    status: str
    shape: str
    replica: int
    batch_size: int
    training_data: str
    val_set_size: float
    sequence_len: int
    # output_dir: str
    # epoch: int
    # learning_rate: float
    image_version: str


class IncompatibleJob(Exception):
    pass


@dataclass
class Card:
    name: str
    rows: list = field(default_factory=list)
    id: str = field(init=False)

    def __post_init__(self):
        self.id = make_id(self.name)


@dataclass
class Accordion:
    name: str
    cards: Dict[str, Card] = field(default_factory=dict)
    id: str = field(init=False)

    def __post_init__(self):
        self.id = make_id(self.name)


class FineTuningReport:
    def __init__(self) -> None:
        self.jobs = []

    @staticmethod
    def get_image_version(job):
        if not hasattr(job.runtime, "image"):
            raise IncompatibleJob()

        image = job.runtime.image
        if ":" not in image:
            raise IncompatibleJob()

        return str(image).split(":", 1)[-1]

    @staticmethod
    def get_model_name(job):
        if "AIP_SMC_FT_ARGUMENTS" not in job.runtime.envs:
            raise IncompatibleJob()
        model_ocid = json.loads(job.runtime.envs["AIP_SMC_FT_ARGUMENTS"])["baseModel"][
            "modelId"
        ]

        if is_valid_ocid("datasciencemodel", model_ocid):
            model = model_keeper.get(model_ocid)
            model_name = model["display_name"]
        else:
            model_name = model_ocid
        return model_name

    @staticmethod
    def parse_cli(job):
        return fire.Fire(parse_args, command=job.runtime.envs["OCI__LAUNCH_CMD"])

    def add_job(self, job: Job):
        image_version = self.get_image_version(job)
        model_name = self.get_model_name(job)
        kwargs = self.parse_cli(job)

        runs = run_list_keeper.get(job.id)["runs"]
        if not runs:
            return
        run = DataScienceJobRun(**get_ds_auth(client="ads")).from_dict(runs[0])
        replica = run.job_configuration_override_details.environment_variables.get(
            "NODE_COUNT", 1
        )
        status = run.lifecycle_state

        self.jobs.append(
            FineTuningJob(
                id=job.id,
                name=job.name,
                model=model_name,
                status=status,
                shape=f"{replica}x{job.infrastructure.shape_name}",
                replica=replica,
                batch_size=kwargs.get("micro_batch_size", -1),
                training_data=kwargs.get("training_data", ""),
                val_set_size=kwargs.get("val_set_size", -1),
                sequence_len=kwargs.get("sequence_len", 2048),
                image_version=image_version,
            )
        )

    @classmethod
    def from_job_summary_list(cls, job_summary_list):
        report = cls()
        for job_summary in job_summary_list:
            job_dict = job_keeper.get(job_summary.id)
            job = Job(**get_ds_auth(client="ads")).from_dict(job_dict)
            job.infrastructure.dsc_job.id = job_summary.id
            try:
                report.add_job(job)
            except Exception:
                traceback.print_exc()
        return report

    def group_by(self, accordion_key, card_key):
        accordions = {}
        accordions: Dict[str, Accordion]
        for job in self.jobs:
            accordion_val = getattr(job, accordion_key)
            accordion = accordions.get(accordion_val, Accordion(accordion_val))

            card_val = getattr(job, card_key)
            card = accordion.cards.get(card_val, Card(card_val))
            card.rows.append(job)
            accordion.cards[card_val] = card

            accordions[accordion_val] = accordion
        # Sort the dicts
        for _, accordion in accordions.items():
            accordion.cards = dict(sorted(accordion.cards.items()))
        return dict(sorted(accordions.items(), reverse=True))
