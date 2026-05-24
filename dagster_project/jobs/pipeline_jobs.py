"""Dagster jobs — composed sequences of ops.

Jobs are the unit the admin UI launches. Two are defined:

  - full_pipeline_job        — scheduled / "Run now" path; reads from
                                the standing materialized/bronze_parquet/.
  - upload_to_gold_job       — admin-upload path (Phase 2A); reads from
                                an uploaded Excel converted to Parquet.

They share the same Silver / Gold / Validate / Anomalies ops. The only
difference is the Bronze-load entry point: `op_load_bronze` for
scheduled runs, `op_load_bronze_from_upload` for admin uploads.
"""

from dagster import job

from dagster_project.ops import (
    op_detect_anomalies,
    op_load_bronze,
    op_load_bronze_from_upload,
    op_mark_upload_done,
    op_run_gold,
    op_run_silver,
    op_validate,
)


@job(
    description=(
        "Full pipeline: Bronze ingest → Silver transform → Gold aggregate → "
        "Validate against KG rules → Detect anomalies. Triggered by the "
        "admin schedule or manually via the admin UI's 'Run now' button."
    ),
)
def full_pipeline_job():
    bronze = op_load_bronze()
    silver = op_run_silver(bronze)
    gold = op_run_gold(silver)
    # Fan-out — validation and anomaly detection both consume gold
    op_validate(gold)
    op_detect_anomalies(gold)


@job(
    description=(
        "Upload pipeline (Phase 2A): admin-uploaded Excel → Bronze → "
        "Silver → Gold → Validate. The first op reads upload_id from "
        "run config; the rest are the same ops as full_pipeline_job."
    ),
)
def upload_to_gold_job():
    bronze = op_load_bronze_from_upload()
    silver = op_run_silver(bronze)
    gold = op_run_gold(silver)
    op_validate(gold)
    op_detect_anomalies(gold)
    # Mark the upload's status to "done" once the gold layer is built.
    # Phase 2 will model this as a sensor instead.
    op_mark_upload_done(upstream_token=gold)


ALL_JOBS = [full_pipeline_job, upload_to_gold_job]
