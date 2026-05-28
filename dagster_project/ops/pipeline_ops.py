"""Subprocess-wrapped pipeline ops.

Pattern for each op:

    @op
    def op_X(context):
        _run_module(context, "scripts.X")

`_run_module` shells out to `uv run python -m scripts.X`, streams stdout
into Dagster's run log, and raises `Failure` if the script exits
non-zero. That gives the Dagster UI per-op status + per-line logs +
clean retry semantics without touching the underlying scripts.

The ops form a fan-in chain:

    load_bronze ─► run_silver ─► run_gold ─► validate
                                          └► detect_anomalies

In a Dagster job (see dagster_project/jobs/full_pipeline.py) the deps
are expressed via `op(input)` wiring; here, each op is a standalone
unit that returns a token ("OK") so it can be plumbed as an input
to the next op without leaking implementation details.
"""

import subprocess
import sys
import time
from pathlib import Path

from dagster import Failure, In, OpExecutionContext, Out, op

# Resolved once at module load — Dagster's working dir is repo root when
# launched via `make dagster`, but be explicit for safety.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _run_module(context: OpExecutionContext, module: str, *args: str) -> None:
    """Run `uv run python -m <module> <args...>` and stream output.

    Raises Dagster's `Failure` on non-zero exit so the op fails loudly
    with the actual script's error message in the run log.
    """
    cmd = ["uv", "run", "python", "-m", module, *args]
    context.log.info(f"$ {' '.join(cmd)}")
    started = time.monotonic()
    proc = subprocess.run(
        cmd,
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = time.monotonic() - started

    # Stream both streams into Dagster's structured log
    if proc.stdout:
        for line in proc.stdout.rstrip().splitlines():
            context.log.info(line)
    if proc.stderr:
        for line in proc.stderr.rstrip().splitlines():
            context.log.warning(line)

    if proc.returncode != 0:
        raise Failure(
            description=(
                f"{module} exited with code {proc.returncode} after {elapsed:.1f}s. "
                f"Last stderr line: {(proc.stderr or '').rstrip().splitlines()[-1] if proc.stderr else '(no stderr)'}"
            ),
            metadata={"module": module, "returncode": proc.returncode, "elapsed_s": elapsed},
        )

    context.log.info(f"✓ {module} finished in {elapsed:.1f}s")


@op(
    description="Bronze — load Guidewire CDC Parquet → Snowflake BRONZE schema",
    out=Out(str, description="Sentinel value passed downstream to express dependency."),
)
def op_load_bronze(context: OpExecutionContext) -> str:
    _run_module(context, "scripts.load_bronze_to_snowflake")
    return "bronze_loaded"


@op(
    description="Silver — transform BRONZE → SILVER TSPR staging tables",
    ins={"bronze_token": In(str)},
    out=Out(str),
)
def op_run_silver(context: OpExecutionContext, bronze_token: str) -> str:
    _run_module(context, "scripts.run_silver")
    return "silver_done"


@op(
    description="Gold — aggregate SILVER → GOLD submission-ready records",
    ins={"silver_token": In(str)},
    out=Out(str),
)
def op_run_gold(context: OpExecutionContext, silver_token: str) -> str:
    _run_module(context, "scripts.run_gold")
    return "gold_done"


@op(
    description="Validate — run REFERENCE.TSPR_VALIDATION_RULES against BRONZE/GOLD",
    ins={"gold_token": In(str)},
    out=Out(str),
)
def op_validate(context: OpExecutionContext, gold_token: str) -> str:
    # The validate endpoint is exposed via the API; here we re-run via
    # the build script which writes the reference SQL. Customers can
    # also hit /api/rhs/validate directly; this op exists so a scheduled
    # run leaves a Dagster artifact in the timeline.
    _run_module(context, "scripts.build_validation_rules_reference")
    return "validate_done"


@op(
    description="Detect anomalies — Section A.34 reason-code patterns, etc.",
    ins={"gold_token": In(str)},
    out=Out(str),
)
def op_detect_anomalies(context: OpExecutionContext, gold_token: str) -> str:
    # Anomaly detection runs for the current accounting month by default.
    # Phase 2: make month a Dagster config or partition.
    _run_module(context, "scripts.detect_anomalies")
    return "anomalies_done"
