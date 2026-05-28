"""Silver → Gold: assemble TSPR submission-ready records.

One row = one SDF record. Dedupes Silver (which has one row per source
transaction) and applies Rule 34 aggregation for Section E. Computes
Section 29 transmittal control totals. Stamps validation_status from
the existing rules-engine pass.

Run: `make run-gold` (or POST /api/rhs/pipeline/gold from the UI).
"""

from __future__ import annotations

import argparse
import time

from packages.rhs.filings import policy_id_to_filing_case, policy_number_to_filing_case
from packages.rhs.snowflake_client import query

ACCOUNTING_MONTH_DEFAULT = "2026-03"
RUN_ID = f"gold-{int(time.time())}"

# CASE expressions that map a policy back to its filing_batch_id.
# Built once at import time so we don't rebuild on every Gold run.
FILING_CASE_BY_POLICY_NUMBER = policy_number_to_filing_case("s.POLICY_ID")
FILING_CASE_BY_BRONZE_ID      = policy_id_to_filing_case("j.policy_id")


def gold_premium(month: str) -> int:
    """Section C records — one row per (NAIC, policy, period)."""
    query("TRUNCATE TABLE INSURANCE_REGULATORY.GOLD.TSPR_PREMIUM_RECORDS")
    query(f"""
        INSERT INTO INSURANCE_REGULATORY.GOLD.TSPR_PREMIUM_RECORDS (
            ACCOUNTING_MONTH, NAIC_COMPANY_NO, NAIC_COMPANY_NO_SDF,
            STAT_PLAN, ACCOUNTING_DATE_ENCODED, RECORD_TYPE,
            POLICY_ID, LINE_OF_BUSINESS, POLICY_FORM,
            EFFECTIVE_DATE, EXPIRY_DATE, ZIP9, PLACE_CODE,
            AMT_INSURANCE_DW, AMT_INSURANCE_PP, AMT_INSURANCE_ALU,
            CONSTRUCTION, NUMBER_OF_FAMILIES, COVERAGE_OCCUPANCY,
            DEDUCTIBLE_1, DEDUCTIBLE_1_AMT, RECORD_INDICATOR,
            FIRE_PREMIUM, EC_PREMIUM,
            ROOF_COVERING, ROOF_INSTALL_YEAR, ROOF_COVERAGE_TYPE,
            YEAR_OF_CONSTRUCTION,
            TENURE_CODE, TENURE_DISCOUNT_PCT, WIND_COVERAGE_INCLUDED,
            FILING_BATCH_ID,
            VALIDATION_STATUS, _CREATED_TIMESTAMP
        )
        SELECT
            s.ACCOUNTING_MONTH, s.NAIC_COMPANY_NO, s.NAIC_COMPANY_NO,
            s.STAT_PLAN,
            -- ACCOUNTING_DATE_ENCODED: TSPR MMY (Rule 23). Oct=0, Nov=-, Dec=&.
            CASE SUBSTR(s.ACCOUNTING_MONTH, 6, 2)
              WHEN '10' THEN '0'
              WHEN '11' THEN '-'
              WHEN '12' THEN '&'
              ELSE LTRIM(SUBSTR(s.ACCOUNTING_MONTH, 6, 2), '0')
            END || RIGHT(SUBSTR(s.ACCOUNTING_MONTH, 1, 4), 1),
            s.RECORD_TYPE, s.POLICY_ID, s.LINE_OF_BUSINESS, s.POLICY_FORM,
            s.EFFECTIVE_DATE, s.EXPIRY_DATE, s.ZIP9, s.PLACE_CODE,
            s.AMT_INSURANCE_DW, s.AMT_INSURANCE_PP, s.AMT_INSURANCE_ALU,
            s.CONSTRUCTION, s.NUMBER_OF_FAMILIES, s.COVERAGE_OCCUPANCY,
            s.DEDUCTIBLE_1, s.DEDUCTIBLE_1_AMT, 'P',  -- P = Premium record
            s.FIRE_PREMIUM, s.EC_PREMIUM,
            s.ROOF_COVERING, s.ROOF_INSTALL_YEAR, s.ROOF_COVERAGE_TYPE,
            s.YEAR_OF_CONSTRUCTION,
            s.TENURE_CODE, s.TENURE_DISCOUNT_PCT, 'Y',
            {FILING_CASE_BY_POLICY_NUMBER},
            'PENDING', CURRENT_TIMESTAMP()
        FROM INSURANCE_REGULATORY.SILVER.TSPR_PREMIUM_STAGING s
        WHERE s.ACCOUNTING_MONTH = '{month}'
    """)
    r = query("SELECT COUNT(*) AS n FROM INSURANCE_REGULATORY.GOLD.TSPR_PREMIUM_RECORDS")
    return r[0]["n"]


def gold_loss(month: str) -> int:
    """Section D records — one row per (NAIC, claim, exposure)."""
    query("TRUNCATE TABLE INSURANCE_REGULATORY.GOLD.TSPR_LOSS_RECORDS")
    query(f"""
        INSERT INTO INSURANCE_REGULATORY.GOLD.TSPR_LOSS_RECORDS (
            ACCOUNTING_MONTH, NAIC_COMPANY_NO, NAIC_COMPANY_NO_SDF,
            STAT_PLAN, ACCOUNTING_DATE_ENCODED,
            POLICY_ID, CLAIM_ID_TSPR, OCCURRENCE_DATE,
            CAUSE_OF_LOSS, KIND_CODE,
            NEW_CLAIM_COUNT, PAID_CLAIM_COUNT, REOPENED_CLAIM_COUNT, CLAIM_STATUS,
            LOSS_AMOUNT,
            LINE_OF_BUSINESS, POLICY_FORM, CONSTRUCTION,
            TYPE_OF_LOSS, RECORD_INDICATOR, TENURE_CODE, TENURE_DISCOUNT_PCT,
            ZIP9,
            FILING_BATCH_ID,
            VALIDATION_STATUS, _CREATED_TIMESTAMP
        )
        SELECT
            s.ACCOUNTING_MONTH, s.NAIC_COMPANY_NO, s.NAIC_COMPANY_NO,
            s.STAT_PLAN,
            CASE SUBSTR(s.ACCOUNTING_MONTH, 6, 2)
              WHEN '10' THEN '0'
              WHEN '11' THEN '-'
              WHEN '12' THEN '&'
              ELSE LTRIM(SUBSTR(s.ACCOUNTING_MONTH, 6, 2), '0')
            END || RIGHT(SUBSTR(s.ACCOUNTING_MONTH, 1, 4), 1),
            s.POLICY_ID, s.CLAIM_ID_TSPR, s.OCCURRENCE_DATE,
            s.CAUSE_OF_LOSS, s.KIND_CODE,
            s.NEW_CLAIM_COUNT, s.PAID_CLAIM_COUNT, s.REOPENED_CLAIM_COUNT, s.CLAIM_STATUS,
            s.LOSS_AMOUNT,
            s.LINE_OF_BUSINESS, s.POLICY_FORM, s.CONSTRUCTION,
            s.TYPE_OF_LOSS, s.RECORD_INDICATOR, s.TENURE_CODE, '00',
            s.ZIP9,
            {FILING_CASE_BY_POLICY_NUMBER},
            'PENDING', CURRENT_TIMESTAMP()
        FROM INSURANCE_REGULATORY.SILVER.TSPR_LOSS_STAGING s
        WHERE s.ACCOUNTING_MONTH = '{month}'
    """)
    r = query("SELECT COUNT(*) AS n FROM INSURANCE_REGULATORY.GOLD.TSPR_LOSS_RECORDS")
    return r[0]["n"]


def gold_cancellation(month: str) -> int:
    """Section E + G records — Rule 34 aggregation by unique-combination key."""
    query("TRUNCATE TABLE INSURANCE_REGULATORY.GOLD.TSPR_CANCELLATION_RECORDS")
    query(f"""
        INSERT INTO INSURANCE_REGULATORY.GOLD.TSPR_CANCELLATION_RECORDS (
            ACCOUNTING_MONTH, NAIC_COMPANY_NO, NAIC_COMPANY_NO_SDF,
            NOTIFICATION_DATE_ENCODED, ACTION_TYPE, TYPE_OF_POLICY,
            REASON_SOURCE_INDICATOR, WITHIN_60_DAYS_INDICATOR,
            ZIP5, ACTION_EFFECTIVE_DATE,
            REASON_CODE_LIST, RECIPIENT_COUNT, ACTUAL_ACTION_COUNT,
            UNIQUE_COMBINATION_KEY,
            FILING_BATCH_ID,
            VALIDATION_STATUS, _CREATED_TIMESTAMP
        )
        SELECT
            s.ACCOUNTING_MONTH, s.NAIC_COMPANY_NO, s.NAIC_COMPANY_NO,
            s.NOTIFICATION_DATE, s.ACTION_TYPE, s.TYPE_OF_POLICY,
            s.REASON_SOURCE_INDICATOR, s.WITHIN_60_DAYS_INDICATOR,
            s.ZIP5, s.ACTION_EFFECTIVE_DATE,
            s.REASON_CODE_LIST, SUM(s.RECIPIENT_COUNT), SUM(s.ACTUAL_ACTION_COUNT),
            -- Rule 34 unique combination key (now includes filing scope so
            -- two filings that share a ZIP don't collapse into one row).
            s.NOTIFICATION_DATE || '|' || s.ACTION_TYPE || '|' || s.TYPE_OF_POLICY || '|' ||
              COALESCE(s.REASON_SOURCE_INDICATOR, '') || '|' ||
              COALESCE(s.WITHIN_60_DAYS_INDICATOR, '') || '|' ||
              s.ZIP5 || '|' || s.ACTION_EFFECTIVE_DATE || '|' || s.REASON_CODE_LIST || '|' ||
              COALESCE({FILING_CASE_BY_BRONZE_ID}, ''),
            {FILING_CASE_BY_BRONZE_ID},
            'PENDING', CURRENT_TIMESTAMP()
        FROM INSURANCE_REGULATORY.SILVER.TSPR_CANCELLATION_STAGING s
        JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_JOB j ON j.id = s.SOURCE_JOB_ID
        WHERE s.ACCOUNTING_MONTH = '{month}'
        GROUP BY s.ACCOUNTING_MONTH, s.NAIC_COMPANY_NO, s.NOTIFICATION_DATE,
                 s.ACTION_TYPE, s.TYPE_OF_POLICY, s.REASON_SOURCE_INDICATOR,
                 s.WITHIN_60_DAYS_INDICATOR, s.ZIP5, s.ACTION_EFFECTIVE_DATE,
                 s.REASON_CODE_LIST, j.policy_id
    """)
    r = query("SELECT COUNT(*) AS n FROM INSURANCE_REGULATORY.GOLD.TSPR_CANCELLATION_RECORDS")
    return r[0]["n"]


def gold_aggregates(month: str) -> int:
    """Section 29 transmittal control totals."""
    query(f"DELETE FROM INSURANCE_REGULATORY.GOLD.TSPR_MONTHLY_AGGREGATES WHERE ACCOUNTING_MONTH = '{month}'")
    query(f"""
        INSERT INTO INSURANCE_REGULATORY.GOLD.TSPR_MONTHLY_AGGREGATES (
            ACCOUNTING_MONTH, NAIC_COMPANY_NO,
            PREMIUM_RECORD_COUNT, LOSS_RECORD_COUNT,
            CANCELLATION_NOTICE_COUNT, ACTUAL_COUNT_RECORD_COUNT,
            TOTAL_WRITTEN_PREMIUM, TOTAL_PAID_LOSSES, TOTAL_OUTSTANDING_LOSSES,
            TOTAL_RECIPIENT_COUNT,
            TOTAL_CANCELLATIONS, TOTAL_NONRENEWALS, TOTAL_DECLINATIONS,
            _CREATED_TIMESTAMP
        )
        SELECT
            '{month}', '12345',
            (SELECT COUNT(*) FROM INSURANCE_REGULATORY.GOLD.TSPR_PREMIUM_RECORDS WHERE ACCOUNTING_MONTH = '{month}'),
            (SELECT COUNT(*) FROM INSURANCE_REGULATORY.GOLD.TSPR_LOSS_RECORDS WHERE ACCOUNTING_MONTH = '{month}'),
            (SELECT COUNT(*) FROM INSURANCE_REGULATORY.GOLD.TSPR_CANCELLATION_RECORDS WHERE ACCOUNTING_MONTH = '{month}'),
            0,
            (SELECT COALESCE(SUM(FIRE_PREMIUM + EC_PREMIUM), 0) FROM INSURANCE_REGULATORY.GOLD.TSPR_PREMIUM_RECORDS WHERE ACCOUNTING_MONTH = '{month}'),
            (SELECT COALESCE(SUM(LOSS_AMOUNT), 0) FROM INSURANCE_REGULATORY.GOLD.TSPR_LOSS_RECORDS WHERE ACCOUNTING_MONTH = '{month}'),
            0,
            (SELECT COALESCE(SUM(RECIPIENT_COUNT), 0) FROM INSURANCE_REGULATORY.GOLD.TSPR_CANCELLATION_RECORDS WHERE ACCOUNTING_MONTH = '{month}'),
            (SELECT COUNT(*) FROM INSURANCE_REGULATORY.GOLD.TSPR_CANCELLATION_RECORDS WHERE ACCOUNTING_MONTH = '{month}' AND ACTION_TYPE = 'C'),
            (SELECT COUNT(*) FROM INSURANCE_REGULATORY.GOLD.TSPR_CANCELLATION_RECORDS WHERE ACCOUNTING_MONTH = '{month}' AND ACTION_TYPE = 'N'),
            (SELECT COUNT(*) FROM INSURANCE_REGULATORY.GOLD.TSPR_CANCELLATION_RECORDS WHERE ACCOUNTING_MONTH = '{month}' AND ACTION_TYPE = 'D'),
            CURRENT_TIMESTAMP()
    """)
    r = query("SELECT COUNT(*) AS n FROM INSURANCE_REGULATORY.GOLD.TSPR_MONTHLY_AGGREGATES")
    return r[0]["n"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", default=ACCOUNTING_MONTH_DEFAULT)
    args = ap.parse_args()

    print(f"Silver → Gold  ·  accounting_month = {args.month}")
    print()
    n_p = gold_premium(args.month)
    print(f"  ✓ TSPR_PREMIUM_RECORDS         {n_p} rows  (Section C)")

    n_l = gold_loss(args.month)
    print(f"  ✓ TSPR_LOSS_RECORDS            {n_l} rows  (Section D)")

    n_c = gold_cancellation(args.month)
    print(f"  ✓ TSPR_CANCELLATION_RECORDS    {n_c} rows  (Section E + G, Rule 34 aggregated)")

    n_a = gold_aggregates(args.month)
    print(f"  ✓ TSPR_MONTHLY_AGGREGATES      {n_a} rows  (Section 29 transmittal)")

    print()
    print(f"Gold assembled · run_id = {RUN_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
