"""Load a single uploaded Parquet into Snowflake's BRONZE schema.

Invoked by Dagster's op_load_bronze_from_upload via subprocess. Env vars:

  REGULAI_UPLOAD_PARQUET_DIR — abs path containing exactly one .parquet
                                file for the target table.
  REGULAI_UPLOAD_BRONZE_TABLE — e.g. "gw_pc_policy". Determines:
                                 - target Snowflake table
                                 - the stage subdirectory PUT writes to.
  REGULAI_UPLOAD_ID — provenance; echoed in COPY INTO metadata.

Mirrors the structure of scripts/load_bronze_to_snowflake.py but
scoped to one table + one parquet file. The full loader is kept for
the synthetic-data path (rebuild-kg, seed); this script is the
upload path.

The script is intentionally narrow: PUT one file, COPY INTO one table,
print one summary line. Verifies row count after load to give the
admin UI useful feedback.
"""

import os
import sys
from pathlib import Path

from packages.rhs.snowflake_client import query


def _env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise SystemExit(f"Missing required env var: {name}")
    return v


def main() -> int:
    parquet_dir = Path(_env("REGULAI_UPLOAD_PARQUET_DIR"))
    bronze_table = _env("REGULAI_UPLOAD_BRONZE_TABLE")
    upload_id = _env("REGULAI_UPLOAD_ID")

    parquet_files = list(parquet_dir.glob("*.parquet"))
    if not parquet_files:
        raise SystemExit(f"No .parquet files in {parquet_dir}")
    if len(parquet_files) > 1:
        print(f"WARNING: {len(parquet_files)} parquet files in dir; using {parquet_files[0].name}")
    parquet = parquet_files[0]

    target_qualified = f"INSURANCE_REGULATORY.BRONZE.{bronze_table.upper()}"
    stage = f"@INSURANCE_REGULATORY.STAGING.BRONZE_INGEST/uploads/{upload_id}"

    print(f"Loading {parquet.name} → {target_qualified}")
    print(f"  upload_id : {upload_id}")
    print(f"  stage     : {stage}")
    print(f"  rows in source parquet: ", end="", flush=True)

    # Quick local row-count via pyarrow before touching Snowflake
    import pyarrow.parquet as pq
    parquet_rows = pq.read_metadata(parquet).num_rows
    print(parquet_rows)

    # Make sure the stage subdirectory is clean — re-runs shouldn't
    # double-load the same upload's data.
    try:
        query(f"REMOVE {stage};")
    except Exception:
        pass  # stage didn't exist yet; fine

    # PUT — uses Snowflake's auto-compress; auto_compress=false because
    # parquet is already columnar+compressed and Snowflake would just
    # gzip a parquet file (wasteful).
    query(
        f"PUT 'file://{parquet.as_posix()}' {stage} "
        f"AUTO_COMPRESS=FALSE OVERWRITE=TRUE;"
    )

    # COPY INTO — TRUNCATE first so each upload replaces the table
    # contents for `bronze_table`. Multi-upload accumulate is a Phase
    # 2B concern; for the demo path we keep it deterministic.
    query(f"TRUNCATE TABLE {target_qualified};")
    copy_sql = f"""
        COPY INTO {target_qualified}
        FROM {stage}
        FILE_FORMAT = (TYPE = PARQUET)
        MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
        ON_ERROR = ABORT_STATEMENT
        PURGE = FALSE;
    """
    rows = query(copy_sql)
    print(f"COPY INTO result: {rows}")

    # Verify
    count_row = query(f"SELECT COUNT(*) AS n FROM {target_qualified};")
    n = count_row[0]["N"] if count_row else 0
    print(f"✓ {target_qualified} now has {n} rows (uploaded: {parquet_rows})")

    if n != parquet_rows:
        print(
            f"WARNING: loaded row count ({n}) != parquet row count ({parquet_rows}). "
            f"This usually means some rows were rejected during COPY INTO "
            f"(check Snowflake's INFORMATION_SCHEMA.LOAD_HISTORY for details).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
