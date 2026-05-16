"""Load synthetic Guidewire Parquet into Snowflake Bronze via PUT + COPY INTO.

Mirrors the Snowpipe ingestion pattern from the IBM architecture doc:
  Parquet → STAGE → COPY INTO with MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE.

We use a named internal stage `STAGING.BRONZE_INGEST` rather than auto-Snowpipe
because for the demo we control the source files. In production this would
be `STORAGE_INTEGRATION + AUTO_INGEST = TRUE` against an S3 bucket.

Run: `make load-bronze`
"""

from __future__ import annotations

import subprocess
from pathlib import Path

PARQUET_ROOT = Path("materialized/bronze_parquet")

# (group_dir, source_name, snowflake_table)
TABLES = [
    ("policycenter", "pc_uwcompany", "GW_PC_UWCOMPANY"),
    ("policycenter", "pc_policy", "GW_PC_POLICY"),
    ("policycenter", "pc_policyperiod", "GW_PC_POLICYPERIOD"),
    ("policycenter", "pc_job", "GW_PC_JOB"),
    ("policycenter", "pc_address", "GW_PC_ADDRESS"),
    ("policycenter", "pc_hopolicyline", "GW_PC_HOPOLICYLINE"),
    ("policycenter", "pc_hocoverage", "GW_PC_HOCOVERAGE"),
    ("policycenter", "pc_hodwelling", "GW_PC_HODWELLING"),
    ("billingcenter", "bc_policyperiodpremium", "GW_BC_POLICYPERIODPREMIUM"),
    ("claimcenter", "cc_claim", "GW_CC_CLAIM"),
    ("claimcenter", "cc_exposure", "GW_CC_EXPOSURE"),
    ("claimcenter", "cc_transaction", "GW_CC_TRANSACTION"),
    ("claimcenter", "cc_reserveline", "GW_CC_RESERVELINE"),
    ("claimcenter", "cc_address", "GW_CC_ADDRESS"),
    ("claimcenter", "cc_claim_status_history", "GW_CC_CLAIM_STATUS_HISTORY"),
]


def run_sql(sql: str) -> None:
    """Execute SQL via the snow CLI, raising on failure."""
    result = subprocess.run(
        ["snow", "sql", "-c", "regulai", "-q", sql],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR running SQL:\n{sql}\n---\n{result.stderr}")
        raise SystemExit(1)
    return result.stdout


def main() -> int:
    print("[1/4] Setting up named stage STAGING.BRONZE_INGEST")
    run_sql(
        "USE DATABASE INSURANCE_REGULATORY; "
        "CREATE STAGE IF NOT EXISTS STAGING.BRONZE_INGEST "
        "FILE_FORMAT = (TYPE = PARQUET) "
        "COMMENT = 'Synthetic Guidewire Parquet ingest for demo';"
    )

    print(f"[2/4] Truncating {len(TABLES)} Bronze tables (idempotent reload)")
    for _, _, sf_name in TABLES:
        run_sql(
            "USE DATABASE INSURANCE_REGULATORY; "
            f"TRUNCATE TABLE BRONZE.{sf_name};"
        )

    print("[3/4] PUT Parquet files → stage")
    for group, src, _ in TABLES:
        path = PARQUET_ROOT / group / src / "data.parquet"
        if not path.exists():
            print(f"  ERROR: {path} not found. Run `make build-bronze` first.")
            return 1
        sql = (
            "USE DATABASE INSURANCE_REGULATORY; "
            f"PUT 'file://{path.resolve()}' "
            f"@STAGING.BRONZE_INGEST/{group}/{src}/ "
            "AUTO_COMPRESS=FALSE OVERWRITE=TRUE;"
        )
        run_sql(sql)
        print(f"  ✓ uploaded {group}/{src}/data.parquet")

    print("[4/4] COPY INTO each Bronze table")
    for group, src, sf_name in TABLES:
        sql = (
            "USE DATABASE INSURANCE_REGULATORY; "
            f"COPY INTO BRONZE.{sf_name} "
            f"FROM @STAGING.BRONZE_INGEST/{group}/{src}/ "
            "FILE_FORMAT = (TYPE = PARQUET) "
            "MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE "
            "ON_ERROR = ABORT_STATEMENT;"
        )
        run_sql(sql)
        count_sql = (
            "USE DATABASE INSURANCE_REGULATORY; "
            f"SELECT COUNT(*) FROM BRONZE.{sf_name};"
        )
        out = run_sql(count_sql)
        rows = "?"
        for line in out.strip().splitlines():
            if line.strip().startswith("|") and line.strip()[1:].strip().split("|")[0].strip().isdigit():
                rows = line.strip().split("|")[1].strip()
                break
        print(f"  ✓ {sf_name:<32} {rows} rows")

    print()
    print("Bronze loaded. Run `make demo-join` to see Guidewire ⋈ KG canon.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
