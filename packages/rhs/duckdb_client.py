"""DuckDB driver for the RHS pipeline — a free, local, zero-billing stand-in
for Snowflake. Same `query()` contract as snowflake_client.

The demo data lives in a single DuckDB file (default
materialized/regulai.duckdb), built by `scripts/seed_duckdb.py` from the same
Parquet that feeds Snowflake. The file is ATTACHed as catalog
INSURANCE_REGULATORY so the codebase's three-part names
(INSURANCE_REGULATORY.BRONZE.GW_PC_JOB) resolve unchanged.

Two compatibility layers let Snowflake-authored SQL run as-is:
  • parameter style — Snowflake's pyformat `%s` placeholders are rewritten to
    DuckDB's `?` (literal `%%` is preserved as `%`).
  • dialect macros — TO_DATE / TO_TIMESTAMP_NTZ / TO_NUMBER / TO_VARCHAR /
    REGEXP_LIKE are installed as DuckDB MACROs, and a few function spellings
    are rewritten textually (CURRENT_TIMESTAMP(), PARSE_JSON()).

Snowflake-only constructs that do NOT appear on the live read path
(LISTAGG WITHIN GROUP, RLIKE, MERGE, INFORMATION_SCHEMA.row_count) are handled
in the seed instead — validation rules are stored with DuckDB-native SQL.
"""

from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from typing import Any

import duckdb

DB_PATH = Path(os.environ.get("REGULAI_DUCKDB_PATH", "materialized/regulai.duckdb"))
CATALOG = "INSURANCE_REGULATORY"

_lock = threading.Lock()
_conn: duckdb.DuckDBPyConnection | None = None


def _install_compat(conn: duckdb.DuckDBPyConnection) -> None:
    """Install Snowflake-compatible scalar functions as DuckDB macros."""
    conn.execute("CREATE OR REPLACE MACRO regexp_like(s, pat) AS regexp_matches(s, pat)")
    conn.execute("CREATE OR REPLACE MACRO to_number(s) AS CAST(s AS DOUBLE)")
    conn.execute("CREATE OR REPLACE MACRO to_date(s) AS CAST(s AS DATE)")
    conn.execute("CREATE OR REPLACE MACRO to_timestamp_ntz(s) AS CAST(s AS TIMESTAMP)")
    # One-arg TO_VARCHAR → string cast (the date-format two-arg form does not
    # appear on the live read path; catalog/pipeline use a seeded meta table).
    conn.execute("CREATE OR REPLACE MACRO to_varchar(x) AS CAST(x AS VARCHAR)")


def get_connection() -> duckdb.DuckDBPyConnection:
    """Process-wide DuckDB connection with INSURANCE_REGULATORY attached."""
    global _conn
    with _lock:
        if _conn is None:
            if not DB_PATH.exists():
                raise RuntimeError(
                    f"DuckDB file {DB_PATH} not found. Build it first:\n"
                    f"    uv run python -m scripts.seed_duckdb"
                )
            conn = duckdb.connect(":memory:")
            conn.execute(f"ATTACH '{DB_PATH.as_posix()}' AS {CATALOG}")
            _install_compat(conn)
            _conn = conn
        return _conn


# Rewrites applied to every SQL string before execution. Ordered, regex-based,
# and deliberately narrow — only the spellings that actually reach this driver.
_CURRENT_TS = re.compile(r"\bCURRENT_TIMESTAMP\s*\(\s*\)", re.IGNORECASE)
_PARSE_JSON = re.compile(r"\bPARSE_JSON\s*\(", re.IGNORECASE)
# Two-arg date format: TO_VARCHAR(<expr>, '<snowflake-fmt>')
_TO_VARCHAR_FMT = re.compile(
    r"\bTO_VARCHAR\s*\(\s*([^,()]+?)\s*,\s*'([^']*)'\s*\)", re.IGNORECASE
)
# Snowflake DATEDIFF(unit, a, b) (bare unit keyword) → DuckDB date_diff('unit', a, b)
_DATEDIFF = re.compile(
    r"\bDATEDIFF\s*\(\s*(day|month|year|week|hour|minute|second|quarter)\s*,",
    re.IGNORECASE,
)
# Snowflake/Databricks address the catalog's information schema three-part
# (CATALOG.INFORMATION_SCHEMA.TABLES); DuckDB only exposes the two-part form.
# One catalog is attached, so dropping the prefix is unambiguous.
_INFO_SCHEMA = re.compile(rf"\b{CATALOG}\.INFORMATION_SCHEMA\.", re.IGNORECASE)

# Snowflake date-format tokens → strftime. Order matters: longer/ambiguous
# tokens first (HH24 before HH, MI before MM-as-minutes isn't an issue since
# MM is months and MI is minutes in Snowflake).
_FMT_TOKENS = [
    ("YYYY", "%Y"), ("YY", "%y"),
    ("HH24", "%H"), ("HH12", "%I"), ("HH", "%H"),
    ("MI", "%M"), ("SS", "%S"),
    ("MM", "%m"), ("MON", "%b"), ("DD", "%d"),
]


def _snow_fmt_to_strftime(fmt: str) -> str:
    out = fmt
    for snow, c in _FMT_TOKENS:
        out = out.replace(snow, c)
    return out


def _translate_sql(sql: str) -> str:
    sql = _CURRENT_TS.sub("CURRENT_TIMESTAMP", sql)
    # PARSE_JSON(x) → (x): DuckDB stores the value as text/JSON directly.
    sql = _PARSE_JSON.sub("(", sql)
    # TO_VARCHAR(expr, 'fmt') → strftime(CAST(expr AS TIMESTAMP), 'duck-fmt')
    sql = _TO_VARCHAR_FMT.sub(
        lambda m: f"strftime(CAST({m.group(1)} AS TIMESTAMP), '{_snow_fmt_to_strftime(m.group(2))}')",
        sql,
    )
    sql = _DATEDIFF.sub(lambda m: f"date_diff('{m.group(1).lower()}',", sql)
    sql = _INFO_SCHEMA.sub("information_schema.", sql)
    return sql


def _translate_params(sql: str) -> str:
    """Snowflake pyformat `%s` → DuckDB `?`, preserving literal `%%` as `%`."""
    if "%" not in sql:
        return sql
    sentinel = "\x00PCT\x00"
    sql = sql.replace("%%", sentinel)
    sql = sql.replace("%s", "?")
    sql = sql.replace(sentinel, "%")
    return sql


def query(sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
    """Run a query, return rows as a list of dicts (lowercase column → value)."""
    conn = get_connection()
    out_sql = _translate_params(_translate_sql(sql))
    with _lock:
        cur = conn.cursor()
        try:
            cur.execute(out_sql, list(params) if params else None)
            if cur.description is None:
                return []
            cols = [d[0].lower() for d in cur.description]
            return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
        finally:
            cur.close()


def close() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None
