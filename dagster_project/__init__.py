"""RegulAI's Dagster project.

This package defines the orchestrated form of the data pipeline that
scripts/ implements as a Makefile-driven sequence. The end-to-end flow:

    Bronze (Guidewire CDC → Snowflake)
        ↓
    Silver (TSPR field-mapped staging)
        ↓
    Gold (submission-ready records + transmittal aggregates)
        ↓
    Validate (run REFERENCE.TSPR_VALIDATION_RULES against Bronze/Gold)
        ↓
    Detect anomalies (Section A.34 reason-code anomalies, etc.)

The ops in dagster_project/ops/ wrap the existing scripts/*.py modules
via subprocess so we don't have to refactor working code to migrate the
orchestrator. Later passes can promote frequently-used ops to native
Python imports for richer logging and structured errors.

How it's run:
    `make dagster`             # dev — webserver on :3000
    via UI at /admin/schedule  # admin sets cron + enabled flag

How the schedule is editable:
    dagster_project/runtime_config.json — the admin UI writes to this
    file; the schedule reads it at every evaluation tick (~30s).
"""

from dagster_project.definitions import defs

__all__ = ["defs"]
