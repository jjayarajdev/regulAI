"""Thin client over Dagster's GraphQL API.

The FastAPI admin route at /admin/schedule talks to Dagster through
this module. Kept minimal — only the 3 operations the admin UI needs:

  - list_recent_runs(job_name, limit)  → for the history table
  - launch_run(job_name)                → for the "Run now" button
  - is_reachable()                       → for the health badge

The Dagster webserver runs at DAGSTER_URL (default http://localhost:3000).
If Dagster isn't running, every call raises DagsterUnreachable so the
admin route can degrade gracefully — the schedule-config edit path
doesn't need Dagster running (it only writes JSON), but the history
table + Run-now button do.
"""

import os
from dataclasses import dataclass
from typing import Any

import httpx

DAGSTER_URL = os.environ.get("DAGSTER_URL", "http://localhost:3000")
GRAPHQL_ENDPOINT = f"{DAGSTER_URL}/graphql"
DEFAULT_TIMEOUT = 5.0


class DagsterUnreachable(RuntimeError):
    """Dagster webserver isn't accepting GraphQL queries (down, wrong
    URL, network blip). Callers should degrade — e.g., show a placeholder
    'Dagster offline' badge in the admin UI rather than 500."""


@dataclass(frozen=True)
class RunSummary:
    """Trimmed view of a Dagster run — just what the admin UI shows."""
    run_id: str
    status: str            # SUCCESS | FAILURE | STARTED | QUEUED | CANCELED | NOT_STARTED
    job_name: str
    started_at: str | None  # ISO datetime
    ended_at: str | None
    duration_s: float | None


def _gql(query: str, variables: dict[str, Any] | None = None) -> dict:
    """Execute a GraphQL request against the Dagster webserver."""
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            resp = client.post(
                GRAPHQL_ENDPOINT,
                json={"query": query, "variables": variables or {}},
            )
    except httpx.RequestError as e:
        raise DagsterUnreachable(
            f"Cannot reach Dagster at {GRAPHQL_ENDPOINT}: {type(e).__name__}: {e}"
        ) from e

    if resp.status_code >= 500:
        raise DagsterUnreachable(
            f"Dagster GraphQL returned {resp.status_code}: {resp.text[:200]}"
        )

    body = resp.json()
    if body.get("errors"):
        # GraphQL errors are 200 OK with an "errors" array; surface the
        # first one as the message so callers see something useful.
        msg = body["errors"][0].get("message", "Unknown GraphQL error")
        raise RuntimeError(f"Dagster GraphQL error: {msg}")
    return body["data"]


def is_reachable() -> bool:
    """Quick health probe. Used by the admin UI to show a 'connected/
    disconnected' badge without throwing on every page render."""
    try:
        _gql("{ version }")
        return True
    except (DagsterUnreachable, RuntimeError):
        return False


def list_recent_runs(job_name: str = "full_pipeline_job", limit: int = 10) -> list[RunSummary]:
    """Return the most recent runs of `job_name`, newest first."""
    data = _gql(
        """
        query RecentRuns($filter: RunsFilter!, $limit: Int!) {
          runsOrError(filter: $filter, limit: $limit) {
            __typename
            ... on Runs {
              results {
                runId
                status
                pipelineName
                startTime
                endTime
              }
            }
            ... on PythonError { message }
            ... on InvalidPipelineRunsFilterError { message }
          }
        }
        """,
        {"filter": {"pipelineName": job_name}, "limit": limit},
    )
    payload = data.get("runsOrError") or {}
    if payload.get("__typename") != "Runs":
        # No matching pipeline yet, or filter error — return empty list
        # so the UI shows "no runs yet" instead of crashing.
        return []
    out: list[RunSummary] = []
    for r in payload.get("results") or []:
        start = r.get("startTime")
        end = r.get("endTime")
        duration = (end - start) if (start is not None and end is not None) else None
        # Dagster returns timestamps as Unix epoch seconds (floats)
        import datetime as dt
        start_iso = dt.datetime.fromtimestamp(start, tz=dt.UTC).isoformat() if start else None
        end_iso = dt.datetime.fromtimestamp(end, tz=dt.UTC).isoformat() if end else None
        out.append(RunSummary(
            run_id=r["runId"],
            status=r["status"],
            job_name=r["pipelineName"],
            started_at=start_iso,
            ended_at=end_iso,
            duration_s=duration,
        ))
    return out


def launch_run(
    job_name: str = "full_pipeline_job",
    *,
    run_config: dict | None = None,
    tags: dict[str, str] | None = None,
) -> str:
    """Trigger a fresh run of `job_name`. Returns the new run id.

    Args:
      run_config: Dagster run config dict, e.g.
        `{"ops": {"op_X": {"config": {"upload_id": "..."}}}}`. None or
        empty means "no config required" (the job's ops must accept
        empty config in that case).
      tags: arbitrary k/v tags persisted on the run; surfaced in the
        Dagster UI + admin run-history table. Use for provenance
        (e.g. `{"upload.id": "..."}`).

    Repository location/name defaults are fixed by how we load Dagster:
      `dagster dev -m dagster_project`
        → location "dagster_project", repository "__repository__"
    """
    tag_list = [{"key": k, "value": v} for k, v in (tags or {}).items()]
    if not tag_list:
        tag_list = [{"key": "triggered_by", "value": "admin_ui_run_now"}]

    data = _gql(
        """
        mutation LaunchRun($executionParams: ExecutionParams!) {
          launchPipelineExecution(executionParams: $executionParams) {
            __typename
            ... on LaunchRunSuccess { run { runId } }
            ... on RunConfigValidationInvalid { errors { message } }
            ... on PipelineNotFoundError { message }
            ... on InvalidStepError { invalidStepKey }
            ... on PythonError { message }
          }
        }
        """,
        {
            "executionParams": {
                "selector": {
                    "repositoryLocationName": "dagster_project",
                    "repositoryName": "__repository__",
                    "pipelineName": job_name,
                },
                "runConfigData": run_config or {},
                "mode": "default",
                "executionMetadata": {"tags": tag_list},
            }
        },
    )
    result = data.get("launchPipelineExecution") or {}
    if result.get("__typename") != "LaunchRunSuccess":
        raise RuntimeError(
            f"Dagster refused to launch {job_name}: {result.get('message') or result}"
        )
    return result["run"]["runId"]
