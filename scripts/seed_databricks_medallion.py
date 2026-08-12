"""Create the SILVER + statistical-GOLD tables on Databricks — the layers the
base `seed_databricks.py` doesn't build.

`seed_databricks.py` only loads BRONZE, seeds REFERENCE, and creates the
*operational* GOLD tables (FILING_BATCH, FILING_EXCEPTION, …). The canonical
SILVER staging (`SILVER.TSPR_*`) and the *statistical* GOLD records
(`GOLD.TSPR_*_RECORDS`, aggregates) are never created — so `run_silver` /
`run_gold` have nothing to write into and SILVER stays empty. On Snowflake these
tables came from the `references/files -Snowflake/*.sql` DDL; this script ports
that same DDL to Delta so Databricks reaches parity (all three medallion layers).

It reads the Snowflake CREATE TABLE blocks, translates the column types
(VARCHAR→STRING, NUMBER(p,s)→DECIMAL/BIGINT, TIMESTAMP_NTZ→TIMESTAMP, VARIANT→
STRING) and drops Snowflake-only clauses (DEFAULT, COMMENT, CLUSTER BY, tags),
then issues `CREATE TABLE IF NOT EXISTS` through the same `query()` seam the app
uses (which maps the catalog name).

Run:  REGULAI_DB=databricks uv run python -m scripts.seed_databricks_medallion
Then: REGULAI_DB=databricks uv run python -m scripts.run_silver
      REGULAI_DB=databricks uv run python -m scripts.run_gold
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from packages.rhs.db import query

# Delta-specific DDL only applies on Databricks. On DuckDB (the free local
# stopgap) we emit plain CREATE TABLE and skip the Delta column-mapping renames
# (seed_duckdb already writes the corrected Bronze column names).
_ENGINE = os.environ.get("REGULAI_DB", "databricks").strip().lower()
_IS_DELTA = _ENGINE == "databricks"

SNOW_DIR = Path("references/files -Snowflake")
# The DDL files + the schema each of their CREATE TABLEs belongs to.
DDL_FILES = [
    ("01_silver_tspr_staging.sql", "SILVER"),
    ("01_gold_tspr_records.sql", "GOLD"),
]

_CREATE = re.compile(r"CREATE TABLE IF NOT EXISTS\s+(\w+)\.(\w+)\s*\(", re.IGNORECASE)
_SKIP_PREFIX = ("--", "comment", "cluster", "primary", "constraint", "unique", "foreign")

# Columns run_gold writes that the (stale) Snowflake DDL file lacks — the real
# Snowflake tables gained these after that file was written. Add them so the
# Silver→Gold transform's INSERT column list resolves on Databricks too.
_SUPPLEMENTAL_COLS = {
    "GOLD.TSPR_PREMIUM_RECORDS": ["filing_batch_id STRING"],
    "GOLD.TSPR_LOSS_RECORDS": ["filing_batch_id STRING"],
    "GOLD.TSPR_CANCELLATION_RECORDS": ["filing_batch_id STRING", "unique_combination_key STRING"],
}

# Bronze column names that came in misspelled from the Parquet fixtures. Snowflake
# corrected them in its hand-written DDL; the Databricks seed builds Bronze from
# the Parquet schema, so it inherits the typo. Normalize to the canonical name the
# shared transforms use. (Requires Delta column-mapping, enabled here.)
_BRONZE_RENAMES = [
    ("BRONZE.GW_PC_JOB", "thirdpartydatauseed", "thirdpartydataused"),
]


def _delta_type(raw: str) -> str:
    """Translate a Snowflake column type token to its Delta/Spark equivalent."""
    t = raw.upper()
    if t.startswith(("VARCHAR", "CHAR", "STRING", "TEXT")):
        return "STRING"
    if t.startswith(("NUMBER", "DECIMAL", "NUMERIC")):
        m = re.match(r"[A-Z]+\((\d+)\s*,\s*(\d+)\)", t)
        if m:
            p, s = int(m.group(1)), int(m.group(2))
            return f"DECIMAL({p},{s})" if s > 0 else ("BIGINT" if p <= 18 else f"DECIMAL({p},0)")
        m1 = re.match(r"[A-Z]+\((\d+)\)", t)
        if m1:
            p = int(m1.group(1))
            return "BIGINT" if p <= 18 else f"DECIMAL({p},0)"
        return "BIGINT"
    if t.startswith(("INT", "BIGINT", "SMALLINT", "TINYINT")):
        return "BIGINT"
    if t.startswith(("FLOAT", "DOUBLE", "REAL")):
        return "DOUBLE"
    if t.startswith("TIMESTAMP") or t == "DATETIME":
        return "TIMESTAMP"
    if t == "DATE":
        return "DATE"
    if t in ("BOOLEAN", "BOOL"):
        return "BOOLEAN"
    if t in ("VARIANT", "OBJECT", "ARRAY"):
        return "STRING"
    return "STRING"


def _parse_columns(lines: list[str], start: int) -> tuple[list[tuple[str, str]], int]:
    """From the line after `CREATE TABLE (`, collect (name, delta_type) pairs
    until the closing `)`. Returns (columns, index_of_close)."""
    cols: list[tuple[str, str]] = []
    i = start
    while i < len(lines):
        s = lines[i].strip()
        i += 1
        if not s:
            continue
        if s.startswith(")"):
            return cols, i
        low = s.lower()
        if low.startswith(_SKIP_PREFIX):
            continue
        toks = s.split()
        if len(toks) < 2:
            continue
        name = toks[0].strip(",")
        cols.append((name, _delta_type(toks[1].strip(","))))
    return cols, i


def _tables_from(path: Path, schema: str) -> list[tuple[str, list[tuple[str, str]]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    i = 0
    while i < len(lines):
        m = _CREATE.search(lines[i])
        if m:
            table = m.group(2)
            cols, j = _parse_columns(lines, i + 1)
            out.append((table, cols))
            i = j
        else:
            i += 1
    return out


def main() -> int:
    for schema in ("SILVER", "GOLD"):
        query(f"CREATE SCHEMA IF NOT EXISTS INSURANCE_REGULATORY.{schema}")

    created = 0
    for fname, schema in DDL_FILES:
        path = SNOW_DIR / fname
        if not path.exists():
            print(f"  skip {fname}: not found")
            continue
        for table, cols in _tables_from(path, schema):
            if not cols:
                print(f"  skip {schema}.{table}: no columns parsed")
                continue
            col_ddl = ",\n  ".join(f"{n} {t}" for n, t in cols)
            fq = f"INSURANCE_REGULATORY.{schema}.{table.upper()}"
            using = " USING DELTA" if _IS_DELTA else ""
            try:
                query(f"CREATE TABLE IF NOT EXISTS {fq} (\n  {col_ddl}\n){using}")
                print(f"  ✓ {schema}.{table.upper()}  ({len(cols)} cols)")
                created += 1
            except Exception as e:  # noqa: BLE001 — report + continue
                print(f"  ✗ {schema}.{table.upper()}: {str(e)[:160]}")

    # ── FL FHCF medallion tables (populated by scripts.run_fhcf) ──────────
    # Shared portable DDL from the transform module; the databricks client
    # translates length-less VARCHAR → STRING, so no Snowflake-file parsing
    # is needed here (these tables never existed in the Snowflake DDL set).
    from scripts.run_fhcf import FHCF_GOLD_DDL, FHCF_SILVER_DDL
    for label, ddl in (("SILVER.FHCF_EXPOSURE_STAGING", FHCF_SILVER_DDL),
                       ("GOLD.FHCF_EXPOSURE_RECORDS", FHCF_GOLD_DDL)):
        try:
            query(ddl + (" USING DELTA" if _IS_DELTA else ""))
            print(f"  ✓ {label}")
            created += 1
        except Exception as e:  # noqa: BLE001 — report + continue
            print(f"  ✗ {label}: {str(e)[:160]}")

    # ── supplemental gold columns (run_gold is ahead of the DDL file) ──────
    for fq, cols in _SUPPLEMENTAL_COLS.items():
        for col in cols:
            # Databricks: ADD COLUMNS (a T, b T);  DuckDB: ADD COLUMN a T
            add = f"ADD COLUMNS ({col})" if _IS_DELTA else f"ADD COLUMN {col}"
            try:
                query(f"ALTER TABLE INSURANCE_REGULATORY.{fq} {add}")
                print(f"  + {fq}.{col.split()[0]}")
            except Exception as e:  # noqa: BLE001 — already-exists is fine on re-run
                if "already exists" not in str(e).lower():
                    print(f"  ! {fq}.{col.split()[0]}: {str(e)[:100]}")

    # ── normalize misspelled Bronze columns from the Parquet fixtures ──────
    # Delta-only (column mapping). DuckDB's seed_duckdb already writes the
    # corrected name, so nothing to rename there.
    for fq, old, new in ([] if not _IS_DELTA else _BRONZE_RENAMES):
        try:
            query(f"ALTER TABLE INSURANCE_REGULATORY.{fq} SET TBLPROPERTIES "
                  "('delta.minReaderVersion'='2','delta.minWriterVersion'='5','delta.columnMapping.mode'='name')")
            query(f"ALTER TABLE INSURANCE_REGULATORY.{fq} RENAME COLUMN {old} TO {new}")
            print(f"  ~ {fq}: {old} → {new}")
        except Exception as e:  # noqa: BLE001 — already-renamed / missing is fine
            low = str(e).lower()
            if "cannot be resolved" not in low and "does not exist" not in low:
                print(f"  ! rename {fq}.{old}: {str(e)[:100]}")

    print(f"\n✓ {created} tables ensured + supplemental columns + Bronze normalized.")
    print("  Next: REGULAI_DB=databricks uv run python -m scripts.run_silver && "
          "uv run python -m scripts.run_gold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
