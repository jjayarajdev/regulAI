"""Build a local DuckDB warehouse for the RHS demo — a free, zero-billing
stand-in for Snowflake.

Loads BRONZE from the same Parquet that feeds Snowflake
(materialized/bronze_parquet/), seeds REFERENCE validation rules in DuckDB-
native SQL, and creates the GOLD / GOLD_AUDIT tables the API writes to. The
result is a single file (materialized/regulai.duckdb) that the duckdb_client
driver ATTACHes as catalog INSURANCE_REGULATORY.

Run:  uv run python -m scripts.seed_duckdb
Then: REGULAI_DB=duckdb uv run uvicorn api.main:app

Idempotent — safe to re-run; it recreates the file from scratch.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

DB_PATH = Path("materialized/regulai.duckdb")
PARQUET_ROOT = Path("materialized/bronze_parquet")
CATALOG = "INSURANCE_REGULATORY"

# (parquet group, parquet dir, Snowflake/Bronze table name)
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

# Demo validation rules in DuckDB-native SQL (the Snowflake reference table uses
# RLIKE / LISTAGG; here the same intent is expressed in portable SQL). Columns
# verified against the bronze parquet schema.
#  (rule_number, rule_name, target_table, target_id_expr, violation_sql,
#   violation_reason, severity, citation)
VALIDATION_RULES = [
    (
        "A.34", "Reason code L (credit score declination) requires companion",
        "BRONZE.GW_PC_JOB", "j.publicid",
        "j.declinereason = 'L'",
        "L requires companion code", "ERROR",
        "TICO Stat Plan Rule A.34 / Section E",
    ),
    (
        "A.22", "Notice date must precede effective date by 30+ days",
        "BRONZE.GW_PC_JOB", "j.publicid",
        # Egregiously short notice (<10 days) on a declination — a small,
        # believable blocker set rather than every short-notice cancellation.
        "j.subtype = 'Declination' "
        "AND j.noticedate IS NOT NULL AND j.effectivedate IS NOT NULL "
        "AND date_diff('day', CAST(j.noticedate AS DATE), CAST(j.effectivedate AS DATE)) < 10",
        "Insufficient notice period", "ERROR",
        "TICO Stat Plan Rule A.22 / Section E",
    ),
    (
        "A.10", "Written premium must be positive",
        "BRONZE.GW_PC_POLICYPERIOD", "j.publicid",
        "j.writtenpremium IS NOT NULL AND j.writtenpremium <= 0",
        "Non-positive written premium", "ERROR",
        "TICO Stat Plan Rule A.10 / Section C",
    ),
    (
        "B.10", "Loss detail reported within 60 days",
        "BRONZE.GW_CC_CLAIM", "j.claimnumber",
        "j.lossdate IS NOT NULL AND j.reporteddate IS NOT NULL "
        "AND date_diff('day', CAST(j.lossdate AS DATE), CAST(j.reporteddate AS DATE)) > 60",
        "Loss reported late", "WARNING",
        "TICO Stat Plan Rule B.10 / Section D",
    ),
]

# A small valid-reason-code list (the real REFERENCE table is larger).
# (code, description, must_appear_alone, credit_score_companion_required)
# L starts companion-required=TRUE (baseline canon); applying bulletin
# B-2026-Q4-118 flips it FALSE — which is exactly the signal /state reads.
REASON_CODES = [
    ("A", "Failure to pay premium", False, False),
    ("AB", "Failure to pay + increase in hazard", False, False),
    ("C", "Nonrenewal at policy term end", False, False),
    ("D", "Claims history", False, False),
    ("L", "Credit score declination", False, True),
    ("LB", "Credit score + companion", False, False),
    ("LD", "Credit score + claims history", False, False),
    ("Y", "At insured's request", False, False),
]


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    con = duckdb.connect(":memory:")
    con.execute(f"ATTACH '{DB_PATH.as_posix()}' AS {CATALOG}")
    q = lambda sql: con.execute(sql)  # noqa: E731

    for schema in ("BRONZE", "SILVER", "GOLD", "GOLD_AUDIT", "REFERENCE", "STAGING"):
        q(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{schema}")

    # ── BRONZE from parquet ──────────────────────────────────────────
    loaded = 0
    for grp, src, tbl in BRONZE_TABLES:
        p = PARQUET_ROOT / grp / src / "data.parquet"
        if not p.exists():
            print(f"  skip {tbl}: {p} not found")
            continue
        q(f"CREATE OR REPLACE TABLE {CATALOG}.BRONZE.{tbl} AS "
          f"SELECT * FROM read_parquet('{p.as_posix()}')")
        n = con.execute(f"SELECT count(*) FROM {CATALOG}.BRONZE.{tbl}").fetchone()[0]
        print(f"  BRONZE.{tbl}: {n} rows")
        loaded += 1

    # ── REFERENCE.TSPR_VALIDATION_RULES ──────────────────────────────
    q(f"""
        CREATE OR REPLACE TABLE {CATALOG}.REFERENCE.TSPR_VALIDATION_RULES (
            rule_id VARCHAR, rule_number VARCHAR, rule_name VARCHAR,
            section VARCHAR, jurisdiction_code VARCHAR, is_federal_default BOOLEAN,
            target_table VARCHAR, target_id_expr VARCHAR, violation_sql VARCHAR,
            violation_reason VARCHAR, severity VARCHAR, citation VARCHAR,
            validation_version INTEGER, generated_at TIMESTAMP
        )
    """)
    for i, (num, name, tgt, idexpr, vsql, reason, sev, cite) in enumerate(VALIDATION_RULES, 1):
        con.execute(
            f"INSERT INTO {CATALOG}.REFERENCE.TSPR_VALIDATION_RULES VALUES "
            "(?, ?, ?, ?, 'US-TX', FALSE, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)",
            [f"rule-{num}-{i:03d}", num, name, num.split(".")[0], tgt, idexpr, vsql, reason, sev, cite],
        )
    print(f"  REFERENCE.TSPR_VALIDATION_RULES: {len(VALIDATION_RULES)} rules")

    # ── REFERENCE.TSPR_REASON_CODE_MAP ───────────────────────────────
    q(f"""
        CREATE OR REPLACE TABLE {CATALOG}.REFERENCE.TSPR_REASON_CODE_MAP (
            tspr_reason_code VARCHAR, description VARCHAR,
            must_appear_alone BOOLEAN, credit_score_companion_required BOOLEAN
        )
    """)
    for code, desc, alone, companion in REASON_CODES:
        con.execute(
            f"INSERT INTO {CATALOG}.REFERENCE.TSPR_REASON_CODE_MAP VALUES (?, ?, ?, ?)",
            [code, desc, alone, companion],
        )
    print(f"  REFERENCE.TSPR_REASON_CODE_MAP: {len(REASON_CODES)} codes")

    # ── GOLD + GOLD_AUDIT tables the API writes to (start empty) ──────
    q(f"""
        CREATE OR REPLACE TABLE {CATALOG}.GOLD.FILING_BATCH (
            filing_batch_id VARCHAR, filing_id VARCHAR, plan_code VARCHAR, plan_name VARCHAR,
            reporting_period_start DATE, reporting_period_end DATE, cadence VARCHAR,
            due_date DATE, channel VARCHAR, status VARCHAR,
            open_blockers INTEGER DEFAULT 0, last_validated_at TIMESTAMP,
            last_validation_run_id VARCHAR, generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            submitted_at TIMESTAMP, acked_at TIMESTAMP
        )
    """)
    q(f"""
        CREATE OR REPLACE TABLE {CATALOG}.GOLD.FILING_EXCEPTION (
            exception_id VARCHAR, filing_batch_id VARCHAR, source_record_id VARCHAR,
            policy_number VARCHAR, rule_id VARCHAR, rule_number VARCHAR, rule_name VARCHAR,
            severity VARCHAR, violation_reason VARCHAR, citation VARCHAR,
            resolution_status VARCHAR DEFAULT 'open',
            resolution_action VARCHAR, opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, resolved_at TIMESTAMP
        )
    """)
    q(f"""
        CREATE OR REPLACE TABLE {CATALOG}.GOLD.FILING_SUBMISSION (
            submission_id VARCHAR, filing_batch_id VARCHAR, sha256 VARCHAR,
            submitted_at TIMESTAMP, acked_at TIMESTAMP, receipt VARCHAR
        )
    """)
    q(f"""
        CREATE OR REPLACE TABLE {CATALOG}.GOLD.TSPR_ANOMALY_FLAGS (
            anomaly_type VARCHAR, severity VARCHAR, territory_zip VARCHAR,
            cause_of_loss_code VARCHAR, current_month_value DOUBLE, rolling_12m_mean DOUBLE,
            rolling_12m_stddev DOUBLE, std_deviations_from_mean DOUBLE,
            anomaly_description VARCHAR, filing_batch_id VARCHAR, source_records VARCHAR,
            flagged_timestamp TIMESTAMP
        )
    """)
    q(f"""
        CREATE OR REPLACE TABLE {CATALOG}.GOLD_AUDIT.USER_ACTION (
            action_id VARCHAR, filing_batch_id VARCHAR, action_type VARCHAR, actor VARCHAR,
            target_record VARCHAR, target_rule VARCHAR, summary VARCHAR, details VARCHAR,
            acted_at TIMESTAMP
        )
    """)
    q(f"""
        CREATE OR REPLACE TABLE {CATALOG}.GOLD_AUDIT.RULE_MATCH_RESULT (
            match_id VARCHAR, run_id VARCHAR, filing_batch_id VARCHAR, source_record_id VARCHAR,
            policy_number VARCHAR, rule_id VARCHAR, rule_number VARCHAR, rule_name VARCHAR,
            target_table VARCHAR, status VARCHAR, violation_reason VARCHAR, severity VARCHAR,
            citation VARCHAR, evidence VARCHAR, validation_version INTEGER, run_at TIMESTAMP
        )
    """)
    print("  GOLD + GOLD_AUDIT: tables created (empty)")

    con.close()
    print(f"\n✓ {DB_PATH}  ({loaded} bronze tables)\n  run: REGULAI_DB=duckdb uv run uvicorn api.main:app")


if __name__ == "__main__":
    main()
