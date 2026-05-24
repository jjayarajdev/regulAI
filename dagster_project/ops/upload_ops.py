"""Upload-driven ops (Phase 2A).

op_load_bronze_from_upload reads the upload_id from Dagster's run
config, validates the upload exists + is in a sane state, and runs
the same Bronze loader that the scheduled path uses — but pointed at
the converted Parquet in materialized/uploads/<id>/parquet/ instead
of the standing materialized/bronze_parquet/ directory.

The op is intentionally chatty in its logs so the operator (or a
debugging engineer) sees exactly what was loaded into Snowflake from
which upload. Telemetry trade-off accepted.
"""

import subprocess
import sys
import time
from pathlib import Path

from dagster import Config, Failure, OpExecutionContext, Out, op

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class UploadLoadConfig(Config):
    """Run-config schema for op_load_bronze_from_upload. Dagster validates
    this against the launchRun call's runConfigData before running the
    op — typos in upload_id surface as a clean validation error, not a
    runtime crash."""
    upload_id: str
    bronze_table: str


@op(
    description=(
        "Bronze — load an admin-uploaded Excel (converted to Parquet) "
        "into BRONZE.GW_*. Reads `upload_id` from run config so the same "
        "op handles every uploaded file."
    ),
    out=Out(str, description="Sentinel value passed to downstream ops."),
)
def op_load_bronze_from_upload(
    context: OpExecutionContext,
    config: UploadLoadConfig,
) -> str:
    from packages.uploads import (
        get_upload,
        parquet_path_for,
        update_upload_status,
    )

    context.log.info(
        f"loading upload upload_id={config.upload_id} "
        f"bronze_table={config.bronze_table}"
    )

    record = get_upload(config.upload_id)
    if record is None:
        raise Failure(
            description=f"Upload {config.upload_id!r} not found in registry.",
            metadata={"upload_id": config.upload_id},
        )
    if record.bronze_table != config.bronze_table:
        raise Failure(
            description=(
                f"Bronze table mismatch — run config says "
                f"{config.bronze_table!r} but upload registry says "
                f"{record.bronze_table!r}."
            ),
        )

    parquet = parquet_path_for(config.upload_id, config.bronze_table)
    if not parquet.exists():
        raise Failure(
            description=(
                f"Converted Parquet not on disk at {parquet}. "
                f"The xlsx→parquet conversion may have been lost; re-upload "
                f"the original file or re-run the conversion."
            ),
            metadata={"expected_parquet": str(parquet)},
        )

    # Run the Bronze loader scoped to this upload. Wrap the whole block
    # in try/except so any failure mode — subprocess.run itself failing
    # (e.g. uv not found in PATH), subprocess crashing with non-zero,
    # network errors during PUT/COPY — all flow back as an
    # `upload.status='failed'` for the admin UI. Without this wrapper,
    # only the proc.returncode != 0 path marked failure; subprocess
    # startup errors left the upload stuck at 'processing' forever.
    started = time.monotonic()
    env_extra = {
        "REGULAI_UPLOAD_PARQUET_DIR": str(parquet.parent),
        "REGULAI_UPLOAD_BRONZE_TABLE": config.bronze_table,
        "REGULAI_UPLOAD_ID": config.upload_id,
    }
    import os
    cmd = [sys.executable, "-m", "scripts.load_bronze_from_upload"]
    context.log.info(f"$ {' '.join(cmd)}")
    try:
        proc = subprocess.run(
            cmd,
            cwd=_REPO_ROOT,
            env={**os.environ, **env_extra},
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as e:
        # subprocess.run itself blew up (e.g. uv not in PATH). Mark the
        # upload as failed before re-raising so the admin UI doesn't
        # show 'processing' forever.
        update_upload_status(
            config.upload_id,
            status="failed",
            error_message=f"Could not invoke Bronze loader: {type(e).__name__}: {e}",
        )
        raise Failure(
            description=f"subprocess.run failed for upload {config.upload_id}",
            metadata={"upload_id": config.upload_id, "error": str(e)},
        ) from e

    elapsed = time.monotonic() - started

    if proc.stdout:
        for line in proc.stdout.rstrip().splitlines():
            context.log.info(line)
    if proc.stderr:
        for line in proc.stderr.rstrip().splitlines():
            context.log.warning(line)

    if proc.returncode != 0:
        update_upload_status(
            config.upload_id,
            status="failed",
            error_message=(
                f"Bronze load exited {proc.returncode}. "
                f"Last stderr: {(proc.stderr or '').rstrip().splitlines()[-1] if proc.stderr else '(no stderr)'}"
            ),
        )
        raise Failure(
            description=f"Bronze load failed for upload {config.upload_id}",
            metadata={
                "returncode": proc.returncode,
                "elapsed_s": elapsed,
                "upload_id": config.upload_id,
            },
        )

    context.log.info(f"✓ Bronze load finished in {elapsed:.1f}s")
    # Don't mark "done" yet — Silver/Gold/Validate still need to run.
    # The upload_to_gold_job's final op marks success/failure.
    return "bronze_loaded_from_upload"


@op(
    description="Marks an upload's status to 'done' once the medallion completes.",
    out=Out(str),
)
def op_mark_upload_done(
    context: OpExecutionContext,
    config: UploadLoadConfig,
    upstream_token: str,
) -> str:
    from packages.uploads import update_upload_status

    update_upload_status(config.upload_id, status="done")
    context.log.info(f"upload {config.upload_id} marked done")
    return "done"
