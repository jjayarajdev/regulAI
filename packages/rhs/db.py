"""Pluggable data-access seam for the RHS pipeline.

Every database call in the backend goes through `query()` here. The engine is
chosen at runtime by the REGULAI_DB env var, so the same code runs against a
managed warehouse or a free local engine with no code changes — the same idea
as the frontend's VITE_API_MODE=mock|live switch.

    REGULAI_DB=snowflake   (default)  → packages.rhs.snowflake_client
    REGULAI_DB=duckdb                 → packages.rhs.duckdb_client  (free, local)
    REGULAI_DB=databricks             → packages.rhs.databricks_client  (planned)

Drivers must expose the same contract:
    query(sql: str, params: tuple | None = None) -> list[dict[str, Any]]
    close() -> None
Rows come back as dicts keyed by lowercase column name.

Default stays `snowflake` so existing deployments are unaffected; demos set
REGULAI_DB=duckdb to run with no warehouse billing or connectivity.
"""

from __future__ import annotations

import os
from typing import Any

_BACKEND = os.environ.get("REGULAI_DB", "snowflake").strip().lower()


def _driver():
    if _BACKEND == "duckdb":
        from packages.rhs import duckdb_client
        return duckdb_client
    if _BACKEND in ("databricks", "dbx"):
        from packages.rhs import databricks_client  # not yet implemented
        return databricks_client
    if _BACKEND in ("snowflake", "sf", ""):
        from packages.rhs import snowflake_client
        return snowflake_client
    raise RuntimeError(
        f"REGULAI_DB={_BACKEND!r} is not a known backend "
        f"(expected one of: snowflake, duckdb, databricks)"
    )


def backend_name() -> str:
    """The active backend identifier (for /health, logging, the UI banner)."""
    return _BACKEND or "snowflake"


def query(sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
    return _driver().query(sql, params)


def close() -> None:
    _driver().close()
