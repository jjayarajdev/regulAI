"""Dagster ops — atomic units of work in the pipeline.

Each op wraps an existing scripts/*.py module via subprocess. This is a
deliberate choice for Phase 1: the existing scripts have years of
production-tested SQL + the make targets already know how to invoke
them. Wrapping is ~3 lines per op; refactoring would be days.

When an op needs structured logging, partition awareness, or asset
lineage, promote it to a native Python implementation that imports
the underlying scripts.X.main() directly. Until then: subprocess is
fine. Dagster captures stdout/stderr from subprocess into its run
log, which is enough observability for the admin UI's "show last
run" needs.
"""

from dagster_project.ops.pipeline_ops import (
    op_detect_anomalies,
    op_load_bronze,
    op_run_gold,
    op_run_silver,
    op_validate,
)
from dagster_project.ops.upload_ops import (
    UploadLoadConfig,
    op_load_bronze_from_upload,
    op_mark_upload_done,
)

__all__ = [
    "op_load_bronze",
    "op_run_silver",
    "op_run_gold",
    "op_validate",
    "op_detect_anomalies",
    "op_load_bronze_from_upload",
    "op_mark_upload_done",
    "UploadLoadConfig",
]
