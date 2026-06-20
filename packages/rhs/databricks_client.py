"""Databricks SQL driver for the RHS pipeline — the cloud-warehouse engine for
client demos. Same `query()` contract as snowflake_client / duckdb_client.

Connects to a Databricks SQL Warehouse over the official
`databricks-sql-connector`. Config comes from env (see .env.example):

    DATABRICKS_SERVER_HOSTNAME   adb-xxxx.azuredatabricks.net  (no https://)
    DATABRICKS_HTTP_PATH         /sql/1.0/warehouses/<id>
    DATABRICKS_TOKEN             dapi… personal access token
    DATABRICKS_CATALOG           Unity Catalog catalog (default INSURANCE_REGULATORY)
    DATABRICKS_SCHEMA            optional default schema

Unity Catalog uses the same three-part naming the codebase already emits
(catalog.schema.table). When DATABRICKS_CATALOG is not INSURANCE_REGULATORY,
the driver rewrites the hardcoded `INSURANCE_REGULATORY.` prefix to the
configured catalog — so you can demo in an existing catalog (e.g. `main`)
without needing CREATE CATALOG rights.

Snowflake → Databricks SQL (Spark SQL) translations live here; the seed
(`scripts/seed_databricks.py`) writes validation rules in Databricks-native
SQL, so RLIKE/LISTAGG never reach this layer.

NOTE: the read path mirrors the verified DuckDB driver, but the live
connection has not been exercised against a real warehouse yet — expect a
short first-connect shakedown (param marker style and a function spelling or
two are the usual suspects; both are isolated to this file).
"""

from __future__ import annotations

import os
import re
import threading
from typing import Any

def _catalog() -> str:
    # Read at call time, not import — .env is loaded by the db.py seam, which
    # may run after this module is first imported.
    return os.environ.get("DATABRICKS_CATALOG", "INSURANCE_REGULATORY")


_lock = threading.Lock()
_conn = None


def _load_config() -> dict[str, str]:
    host = os.environ.get("DATABRICKS_SERVER_HOSTNAME")
    path = os.environ.get("DATABRICKS_HTTP_PATH")
    token = os.environ.get("DATABRICKS_TOKEN")
    missing = [k for k, v in [
        ("DATABRICKS_SERVER_HOSTNAME", host),
        ("DATABRICKS_HTTP_PATH", path),
        ("DATABRICKS_TOKEN", token),
    ] if not v]
    if missing:
        raise RuntimeError(
            "Databricks backend selected (REGULAI_DB=databricks) but missing "
            f"env: {', '.join(missing)}. See .env.example."
        )
    return {"host": host, "path": path, "token": token}  # type: ignore[return-value]


def get_connection():
    """Process-wide Databricks SQL connection (lazily opened)."""
    global _conn
    with _lock:
        if _conn is None:
            try:
                from databricks import sql as dbx_sql  # lazy import
            except ModuleNotFoundError as e:
                raise RuntimeError(
                    "databricks-sql-connector is not installed. "
                    "Run: uv sync --extra databricks"
                ) from e

            cfg = _load_config()
            _conn = dbx_sql.connect(
                server_hostname=cfg["host"],
                http_path=cfg["path"],
                access_token=cfg["token"],
                catalog=_catalog(),
                schema=os.environ.get("DATABRICKS_SCHEMA"),
                # The codebase emits Snowflake-style %s markers; inline params
                # restore that (v3 connector defaults to native ? otherwise).
                use_inline_params=True,
            )
        return _conn


# ── Snowflake → Databricks SQL translations (runtime read path only) ──────
_CURRENT_TS = re.compile(r"\bCURRENT_TIMESTAMP\s*\(\s*\)", re.IGNORECASE)
_PARSE_JSON = re.compile(r"\bPARSE_JSON\s*\(", re.IGNORECASE)
_TO_VARCHAR_FMT = re.compile(
    r"\bTO_VARCHAR\s*\(\s*([^,()]+?)\s*,\s*'([^']*)'\s*\)", re.IGNORECASE
)
_TO_VARCHAR_1 = re.compile(r"\bTO_VARCHAR\s*\(\s*([^,()]+?)\s*\)", re.IGNORECASE)
_TO_DATE = re.compile(r"\bTO_DATE\s*\(", re.IGNORECASE)
_DATEDIFF = re.compile(
    r"\bDATEDIFF\s*\(\s*(day|month|year|week|hour|minute|second|quarter)\s*,",
    re.IGNORECASE,
)

# Snowflake date-format tokens → Spark date_format (java.time) patterns.
_FMT_TOKENS = [
    ("YYYY", "yyyy"), ("YY", "yy"),
    ("HH24", "HH"), ("HH12", "hh"), ("HH", "HH"),
    ("MI", "mm"), ("SS", "ss"),
    ("MM", "MM"), ("MON", "MMM"), ("DD", "dd"),
]


def _snow_fmt_to_spark(fmt: str) -> str:
    out = fmt
    for snow, spark in _FMT_TOKENS:
        out = out.replace(snow, spark)
    return out


def _translate_sql(sql: str) -> str:
    catalog = _catalog()
    if catalog != "INSURANCE_REGULATORY":
        sql = sql.replace("INSURANCE_REGULATORY.", f"{catalog}.")
    sql = _CURRENT_TS.sub("CURRENT_TIMESTAMP()", sql)
    sql = _PARSE_JSON.sub("(", sql)  # store JSON as string
    sql = _TO_VARCHAR_FMT.sub(
        lambda m: f"date_format(CAST({m.group(1)} AS TIMESTAMP), '{_snow_fmt_to_spark(m.group(2))}')",
        sql,
    )
    sql = _TO_VARCHAR_1.sub(lambda m: f"CAST({m.group(1)} AS STRING)", sql)
    sql = _TO_DATE.sub("to_date(", sql)
    sql = _DATEDIFF.sub(lambda m: f"date_diff({m.group(1).upper()},", sql)
    return sql


def query(sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
    """Run a query, return rows as a list of dicts (lowercase column → value).

    The connector accepts Snowflake-style `%s` markers with a parameter
    sequence, so the SQL passes through unchanged on that axis.
    """
    conn = get_connection()
    out_sql = _translate_sql(sql)
    with _lock:
        with conn.cursor() as cur:
            cur.execute(out_sql, list(params) if params else None)
            if cur.description is None:
                return []
            cols = [d[0].lower() for d in cur.description]
            return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def close() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None
