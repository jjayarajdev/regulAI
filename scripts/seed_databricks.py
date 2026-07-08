"""Build the RHS demo warehouse in Databricks (Unity Catalog) — the cloud
engine for client demos.

Loads BRONZE from the same Parquet that feeds Snowflake/DuckDB, seeds
REFERENCE validation rules in Databricks-native SQL, and creates the GOLD /
GOLD_AUDIT tables the API writes to. Connection comes from the same env the
runtime driver uses (DATABRICKS_*; see .env.example).

Run (after setting DATABRICKS_* env):
    uv run python -m scripts.seed_databricks
Then:
    REGULAI_DB=databricks uv run uvicorn api.main:app

Data is tiny (~3k rows total) so tables are created with inferred schema and
filled with chunked INSERTs over the SQL connector — no cloud-storage Volume
or COPY INTO permissions required. Idempotent: CREATE OR REPLACE per table.
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb

from scripts.seed_duckdb import REASON_CODES  # dialect-neutral reference data

PARQUET_ROOT = Path("materialized/bronze_parquet")

BRONZE_TABLES = [
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

# Databricks-native validation rules (Spark SQL: date_diff(DAY, a, b) with an
# unquoted unit keyword). Same intent as the DuckDB seed; columns verified
# against the bronze parquet schema.
VALIDATION_RULES = [
    ("A.34", "Reason code L (credit score declination) requires companion",
     "BRONZE.GW_PC_JOB", "j.publicid",
     # Canon-flag driven so the bulletin's effect is one portable UPDATE (see
     # /bulletin/apply): L-alone violates only while the reason-code map still
     # requires a companion.
     "j.declinereason = 'L' AND EXISTS ("
     "SELECT 1 FROM INSURANCE_REGULATORY.REFERENCE.TSPR_REASON_CODE_MAP m "
     "WHERE m.tspr_reason_code = 'L' AND m.credit_score_companion_required)",
     "L requires companion code", "ERROR", "TICO Stat Plan Rule A.34 / Section E"),
    ("A.22", "Notice date must precede effective date by 30+ days",
     "BRONZE.GW_PC_JOB", "j.publicid",
     "j.subtype = 'Declination' AND j.noticedate IS NOT NULL AND j.effectivedate IS NOT NULL "
     "AND date_diff(DAY, CAST(j.noticedate AS DATE), CAST(j.effectivedate AS DATE)) < 10",
     "Insufficient notice period", "ERROR", "TICO Stat Plan Rule A.22 / Section E"),
    ("A.10", "Written premium must be positive",
     "BRONZE.GW_PC_POLICYPERIOD", "j.publicid",
     "j.writtenpremium IS NOT NULL AND j.writtenpremium <= 0",
     "Non-positive written premium", "ERROR", "TICO Stat Plan Rule A.10 / Section C"),
    ("B.10", "Loss detail reported within 60 days",
     "BRONZE.GW_CC_CLAIM", "j.claimnumber",
     "j.lossdate IS NOT NULL AND j.reporteddate IS NOT NULL "
     "AND date_diff(DAY, CAST(j.lossdate AS DATE), CAST(j.reporteddate AS DATE)) > 60",
     "Loss reported late", "WARNING", "TICO Stat Plan Rule B.10 / Section D"),
]

# DuckDB type → Databricks (Spark) type for inferred bronze schemas.
_TYPE_MAP = {
    "BOOLEAN": "BOOLEAN", "TINYINT": "TINYINT", "SMALLINT": "SMALLINT",
    "INTEGER": "INT", "BIGINT": "BIGINT", "HUGEINT": "DECIMAL(38,0)",
    "FLOAT": "FLOAT", "DOUBLE": "DOUBLE", "DATE": "DATE",
    "TIMESTAMP": "TIMESTAMP", "TIMESTAMP_NS": "TIMESTAMP", "TIME": "STRING",
    "VARCHAR": "STRING", "BLOB": "STRING",
}


def _dbx_type(duck_type: str) -> str:
    t = duck_type.upper()
    if t.startswith("DECIMAL"):
        return t
    return _TYPE_MAP.get(t, "STRING")


def _q(cur, sql: str):
    cur.execute(sql)


def main() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    from databricks import sql as dbx_sql

    CATALOG = os.environ.get("DATABRICKS_CATALOG", "INSURANCE_REGULATORY")
    conn = dbx_sql.connect(
        server_hostname=os.environ["DATABRICKS_SERVER_HOSTNAME"],
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DATABRICKS_TOKEN"],
        use_inline_params=True,  # codebase emits %s markers
    )
    local = duckdb.connect()  # reads parquet, infers schema
    cur = conn.cursor()

    # Catalog may already exist / require admin — tolerate failure and proceed
    # with whatever catalog the user pointed us at.
    try:
        _q(cur, f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
    except Exception as e:
        print(f"  (CREATE CATALOG skipped: {str(e)[:80]} — using existing {CATALOG})")
    for schema in ("BRONZE", "SILVER", "GOLD", "GOLD_AUDIT", "REFERENCE", "STAGING"):
        _q(cur, f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{schema}")

    # ── BRONZE from parquet ──────────────────────────────────────────
    loaded = 0
    for grp, src, tbl in BRONZE_TABLES:
        p = PARQUET_ROOT / grp / src / "data.parquet"
        if not p.exists():
            print(f"  skip {tbl}: {p} not found")
            continue
        schema = local.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{p.as_posix()}')"
        ).fetchall()
        cols = [(r[0], _dbx_type(r[1])) for r in schema]
        col_ddl = ", ".join(f"`{c}` {t}" for c, t in cols)
        _q(cur, f"DROP TABLE IF EXISTS {CATALOG}.BRONZE.{tbl}")
        _q(cur, f"CREATE TABLE {CATALOG}.BRONZE.{tbl} ({col_ddl})")

        rows = local.execute(f"SELECT * FROM read_parquet('{p.as_posix()}')").fetchall()
        if rows:
            ph = "(" + ", ".join(["%s"] * len(cols)) + ")"
            CHUNK = 200
            for i in range(0, len(rows), CHUNK):
                chunk = rows[i:i + CHUNK]
                values = ", ".join([ph] * len(chunk))
                flat = [v for row in chunk for v in row]
                cur.execute(f"INSERT INTO {CATALOG}.BRONZE.{tbl} VALUES {values}", flat)
        print(f"  BRONZE.{tbl}: {len(rows)} rows")
        loaded += 1

    # ── REFERENCE.TSPR_VALIDATION_RULES ──────────────────────────────
    _q(cur, f"DROP TABLE IF EXISTS {CATALOG}.REFERENCE.TSPR_VALIDATION_RULES")
    _q(cur, f"""
        CREATE TABLE {CATALOG}.REFERENCE.TSPR_VALIDATION_RULES (
            rule_id STRING, rule_number STRING, rule_name STRING, section STRING,
            jurisdiction_code STRING, is_federal_default BOOLEAN, target_table STRING,
            target_id_expr STRING, violation_sql STRING, violation_reason STRING,
            severity STRING, citation STRING, validation_version INT, generated_at TIMESTAMP
        )
    """)
    for i, (num, name, tgt, idexpr, vsql, reason, sev, cite) in enumerate(VALIDATION_RULES, 1):
        cur.execute(
            f"INSERT INTO {CATALOG}.REFERENCE.TSPR_VALIDATION_RULES VALUES "
            "(%s, %s, %s, %s, 'US-TX', false, %s, %s, %s, %s, %s, %s, 1, CURRENT_TIMESTAMP())",
            [f"rule-{num}-{i:03d}", num, name, num.split(".")[0], tgt, idexpr, vsql, reason, sev, cite],
        )
    print(f"  REFERENCE.TSPR_VALIDATION_RULES: {len(VALIDATION_RULES)} rules")

    # ── REFERENCE.TSPR_REASON_CODE_MAP ───────────────────────────────
    _q(cur, f"DROP TABLE IF EXISTS {CATALOG}.REFERENCE.TSPR_REASON_CODE_MAP")
    _q(cur, f"""
        CREATE TABLE {CATALOG}.REFERENCE.TSPR_REASON_CODE_MAP (
            tspr_reason_code STRING, description STRING,
            must_appear_alone BOOLEAN, credit_score_companion_required BOOLEAN
        )
    """)
    for code, desc, alone, companion in REASON_CODES:
        cur.execute(
            f"INSERT INTO {CATALOG}.REFERENCE.TSPR_REASON_CODE_MAP VALUES (%s, %s, %s, %s)",
            [code, desc, alone, companion],
        )
    print(f"  REFERENCE.TSPR_REASON_CODE_MAP: {len(REASON_CODES)} codes")

    # ── GOLD + GOLD_AUDIT tables the API writes to (start empty) ──────
    ddl = {
        "GOLD.FILING_BATCH": (
            "filing_batch_id STRING, filing_id STRING, plan_code STRING, plan_name STRING, "
            "reporting_period_start DATE, reporting_period_end DATE, cadence STRING, "
            "due_date DATE, channel STRING, status STRING, open_blockers INT, "
            "last_validated_at TIMESTAMP, last_validation_run_id STRING, generated_at TIMESTAMP, "
            "submitted_at TIMESTAMP, acked_at TIMESTAMP"
        ),
        "GOLD.FILING_EXCEPTION": (
            "exception_id STRING, filing_batch_id STRING, source_record_id STRING, "
            "policy_number STRING, rule_id STRING, rule_number STRING, rule_name STRING, "
            "severity STRING, violation_reason STRING, citation STRING, resolution_status STRING, "
            "resolution_action STRING, opened_at TIMESTAMP, resolved_at TIMESTAMP"
        ),
        "GOLD.FILING_SUBMISSION": (
            "submission_id STRING, filing_batch_id STRING, sha256 STRING, "
            "submitted_at TIMESTAMP, acked_at TIMESTAMP, receipt STRING"
        ),
        "GOLD.TSPR_ANOMALY_FLAGS": (
            "anomaly_type STRING, severity STRING, territory_zip STRING, cause_of_loss_code STRING, "
            "current_month_value DOUBLE, rolling_12m_mean DOUBLE, rolling_12m_stddev DOUBLE, "
            "std_deviations_from_mean DOUBLE, anomaly_description STRING, filing_batch_id STRING, "
            "source_records STRING, flagged_timestamp TIMESTAMP"
        ),
        "GOLD_AUDIT.USER_ACTION": (
            "action_id STRING, filing_batch_id STRING, action_type STRING, actor STRING, "
            "target_record STRING, target_rule STRING, summary STRING, details STRING, acted_at TIMESTAMP"
        ),
        "GOLD_AUDIT.RULE_MATCH_RESULT": (
            "match_id STRING, run_id STRING, filing_batch_id STRING, source_record_id STRING, "
            "policy_number STRING, rule_id STRING, rule_number STRING, rule_name STRING, "
            "target_table STRING, status STRING, violation_reason STRING, severity STRING, "
            "citation STRING, evidence STRING, validation_version INT, run_at TIMESTAMP"
        ),
    }
    for name, cols in ddl.items():
        _q(cur, f"DROP TABLE IF EXISTS {CATALOG}.{name}")
        _q(cur, f"CREATE TABLE {CATALOG}.{name} ({cols})")
    print("  GOLD + GOLD_AUDIT: tables created (empty)")

    cur.close()
    conn.close()
    print(f"\n✓ Databricks catalog {CATALOG} seeded ({loaded} bronze tables)\n"
          f"  run: REGULAI_DB=databricks uv run uvicorn api.main:app")


if __name__ == "__main__":
    main()
