"""Dagster jobs — composed sequences of ops.

Phase 1: just `full_pipeline_job`. Phase 2 will add validate_only,
bronze_only, etc. as the admin UI grows beyond a single dropdown.

Adding a new pipeline kind requires:
  1. Define a new job here
  2. Add it to ALL_JOBS so dagster_project/definitions.py picks it up
  3. Add its name to PipelineKind in packages/scheduling/__init__.py
  4. The admin UI dropdown reads from that Literal automatically
"""

from dagster import job

from dagster_project.ops import (
    op_detect_anomalies,
    op_load_bronze,
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


ALL_JOBS = [full_pipeline_job]
