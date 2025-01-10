import os
import shutil
import tempfile
from dataclasses import asdict
from typing import List

import fsspec
import pandas as pd
import plotly.express as px
import report_creator as rc
from jinja2 import Template

from commons.auth import get_authentication
from garden.jobs import JobLogKeeper
from .reports import Accordion, FineTuningJob
from .logs import METRIC_MAPPINGS, get_log_metric


log_keeper = JobLogKeeper()

TABLE_TEMPLATE = Template(
    """
    <table width="100%">
    <tr>
        {% for key in keys %}
        <th>{{ key }}</th>
        {% endfor %}
    </tr>
    <tr>
        {% for val in values %}
        <td>{{ val }}</td>
        {% endfor %}
    </tr>
    </table>
    """
)


class FineTuningReportCreator:

    def job_stats(self, jobs: List[FineTuningJob]):
        single_node_count = 0
        multi_node_count = 0
        succeeded_count = 0
        failed_count = 0
        for job in jobs:
            if job.status == "SUCCEEDED":
                succeeded_count += 1
            elif job.status == "FAILED":
                failed_count += 1

            if job.replica == 1:
                single_node_count += 1
            else:
                multi_node_count += 1

        total_count = len(jobs)
        return rc.Group(
            rc.Metric("Total Test Jobs", total_count),
            rc.Metric("Single Node", single_node_count),
            rc.Metric("Multi Node", multi_node_count),
            rc.Metric("Succeeded", succeeded_count),
            rc.Metric("Failed", failed_count),
            rc.Metric("In Progress", total_count - failed_count - succeeded_count),
            label="Jobs",
        )

    def job_metric_plot(self, job: FineTuningJob):
        blocks = []
        for key in METRIC_MAPPINGS.keys():
            x, y = get_log_metric(ocid=job.run_id, name=key)
            if not y:
                continue
            x = ["{:.4f}".format(p) for p in x]
            y = {p["label"]: p["data"] for p in y}
            y["epoch"] = x
            blocks.append(
                rc.Widget(
                    px.line(
                        pd.melt(pd.DataFrame(y), id_vars=["epoch"]),
                        x="epoch",
                        y="value",
                        color="variable",
                    ),
                    label=key,
                )
            )
        if not blocks:
            return None
        return rc.Select(blocks)

    def job_config_table(self, job: FineTuningJob):
        '<table width="100%"><th></th></table>'

    def save_table(self, jobs: List[FineTuningJob], filename: str):
        data = [asdict(job) for job in jobs]

        with rc.ReportCreator("AQUA FT Tests Report") as report:
            view = rc.Block(rc.DataTable(data))
            report.save(view, filename)

    def save_version_report(self, version: str, accordion: Accordion, filename: str):
        jobs: List[FineTuningJob] = []
        succeeded_count = 0
        failed_count = 0

        model_blocks = []
        data_table = []
        total_count = len(accordion.cards.keys())

        for model_name, card in accordion.cards.items():
            jobs.extend(card.rows)
            model_table = []
            # Model test is considered as succeeded if there is a successful job.
            has_succeeded = False
            has_failed = False
            job: FineTuningJob
            for job in card.rows:
                if job.status == "SUCCEEDED":
                    has_succeeded = True
                    emoji = "✅"
                elif job.status == "FAILED":
                    has_failed = True
                    emoji = "❌"
                else:
                    emoji = "☕️"
                model_table.append(
                    {
                        "Model": job.model,
                        "Status": (
                            f"{emoji} {job.status}"
                            + (f" Code={job.exit_code}" if job.exit_code else "")
                        ),
                        "Job ID": job.id[-12:],
                        "Shape": job.shape,
                        "Batch Size": job.batch_size,
                        "Sequence Length": job.sequence_len,
                        "Duration (mins)": job.duration,
                        "Dataset": str(job.training_data).rsplit("/", 1)[-1],
                    }
                )
            data_table.extend(model_table)
            if has_succeeded:
                succeeded_count += 1
                emoji = "✅"
            elif has_failed:
                failed_count += 1
                emoji = "❌"
            else:
                emoji = "☕️"

            blocks = []
            for job_config in model_table:
                blocks.extend(
                    [
                        rc.Separator(),
                        rc.Html(
                            TABLE_TEMPLATE.render(
                                keys=job_config.keys(), values=job_config.values()
                            )
                        ),
                    ]
                )
                plot = self.job_metric_plot(card.rows[0])
                if plot:
                    blocks.append(plot)

            model_blocks.append(
                rc.Collapse(
                    *blocks,
                    label=f"{emoji} {model_name}",
                )
            )

        model_tab = rc.Block(
            rc.Text(
                "Test on a model is considered as succeeded "
                "if there is at least one successful test job. "
                "Fine-tuning the same model may still fail "
                "on some parameters/datasets if they are not supported.",
                label="Tested Models",
            ),
            rc.Group(
                rc.Metric("Tested Models", total_count),
                rc.Metric("Succeeded", succeeded_count),
                rc.Metric("Failed", failed_count),
                rc.Metric("In Progress", total_count - failed_count - succeeded_count),
            ),
            *model_blocks,
            label="Tested Models",
        )

        job_tab = rc.Block(
            self.job_stats(jobs),
            rc.DataTable(pd.DataFrame(data_table)),
            label="Test Jobs",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            basename = os.path.basename(filename)
            temp_report = os.path.join(temp_dir, basename)
            with rc.ReportCreator(
                f"AQUA Fine-Tuning {version}", logo="oracle"
            ) as report:
                view = rc.Block(rc.Select([model_tab, job_tab]))
                report.save(view, temp_report)
            if filename.startswith("oci://"):
                fs = fsspec.filesystem("oci", **get_authentication())
                fs.put(temp_report, filename)
            else:
                shutil.copy(temp_report, filename)
