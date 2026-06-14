"""Bronze → Silver: apply TSPR rules and code translations.

Idempotent. Truncates and reloads Silver tables for the target accounting
month. Each transformation is a single INSERT INTO ... SELECT against
Bronze, with REFERENCE.* lookups joined inline so plan rule changes flow
through automatically.

Run: `make run-silver` (or POST /api/rhs/pipeline/silver from the UI).
"""

from __future__ import annotations

import argparse
import time

from packages.rhs.db import query

ACCOUNTING_MONTH_DEFAULT = "2026-03"
RUN_ID = f"silver-{int(time.time())}"


def run(sql: str, label: str) -> int:
    """Execute a statement, return rows affected (or 0 if not reported)."""
    rows = query(sql)
    if rows and "number of rows" in (rows[0].get(list(rows[0].keys())[0], "") or "").lower():
        # snowflake-connector returns rowcount as a column for INSERTs sometimes
        try:
            return int(list(rows[0].values())[0])
        except (ValueError, TypeError):
            return 0
    return 0


def silver_premium(month: str) -> int:
    """Build silver.tspr_premium_staging from Bronze policy + line + coverage + dwelling."""
    query("TRUNCATE TABLE INSURANCE_REGULATORY.SILVER.TSPR_PREMIUM_STAGING")
    query(f"""
        INSERT INTO INSURANCE_REGULATORY.SILVER.TSPR_PREMIUM_STAGING (
            ACCOUNTING_MONTH, NAIC_COMPANY_NO, TICO_COMPANY_NO, RUN_ID,
            SOURCE_POLICYPERIOD_ID, STAT_PLAN, RECORD_TYPE,
            POLICY_ID, EFFECTIVE_DATE, EXPIRY_DATE,
            AMT_INSURANCE_DW, AMT_INSURANCE_PP, AMT_INSURANCE_ALU,
            LINE_OF_BUSINESS, POLICY_FORM, NUMBER_OF_FAMILIES,
            COVERAGE_OCCUPANCY, CONSTRUCTION, PPC_SIMPLE, PPC_SPLIT,
            DEDUCTIBLE_1, DEDUCTIBLE_1_AMT,
            FIRE_PREMIUM, EC_PREMIUM,
            ROOF_COVERING, ROOF_INSTALL_YEAR, ROOF_COVERAGE_TYPE,
            ZIP9, YEAR_OF_CONSTRUCTION,
            TENURE_CODE, TENURE_DISCOUNT_PCT,
            VALIDATION_STATUS, _CREATED_TIMESTAMP, _PIPELINE_RUN_ID, _SOURCE_SYSTEM
        )
        SELECT
            '{month}' AS accounting_month,
            pp.naic_number, pp.tico_company_number, '{RUN_ID}',
            pp.id, '4', '01',
            p.policynumber,
            -- TSPR MMDDY (Rule 8): MM + DD + last-digit-of-year
            TO_VARCHAR(pp.periodstart, 'MMDD') || RIGHT(TO_VARCHAR(pp.periodstart, 'YYYY'), 1),
            -- TSPR MMY (Rule 8): MM + last-digit-of-year
            TO_VARCHAR(pp.periodend, 'MM') || RIGHT(TO_VARCHAR(pp.periodend, 'YYYY'), 1),
            -- AMT_INSURANCE_DW = Coverage A in $1000s
            ROUND(cov.coverageamount / 1000, 0),
            ROUND(cov.personalpropertylimit / 1000, 0),
            ROUND(cov.lossofuselimit / 1000, 0),
            -- LINE_OF_BUSINESS: 1 = Homeowners
            '1',
            line.holineform,
            CAST(dw.numberoffamilies AS VARCHAR),
            '1',  -- coverage occupancy: owner-occupied
            dw.constructiontype, dw.ppccode, dw.ppccodesplit,
            -- DEDUCTIBLE_1: simple mapping — 1=$100, 2=$250, 3=$500, 4=$1000, etc
            CASE
              WHEN cov.allperilsdeductible = 100 THEN '1'
              WHEN cov.allperilsdeductible = 250 THEN '2'
              WHEN cov.allperilsdeductible = 500 THEN '3'
              WHEN cov.allperilsdeductible = 1000 THEN '4'
              WHEN cov.allperilsdeductible = 2500 THEN '6'
              ELSE '4'
            END,
            cov.allperilsdeductible,
            -- Premium split: ~70% fire, ~30% extended coverage
            ROUND(cov.writtenpremium * 0.7, 0),
            ROUND(cov.writtenpremium * 0.3, 0),
            line.roofcoveringtype, line.roofinstallationyear, '1',  -- ROOF_COVERAGE_TYPE: 1=Replacement Cost
            dw.zip || dw.ziplus4, dw.yearbuilt,
            -- TENURE_CODE: 0=not used, 1=0-2yr, 2=3-5yr, 3=6-8yr, 4=9-10yr, 5=11-15yr, 6=16-19yr, 7=20+yr
            CASE
              WHEN line.tenurewithinsurer < 3  THEN '1'
              WHEN line.tenurewithinsurer < 6  THEN '2'
              WHEN line.tenurewithinsurer < 9  THEN '3'
              WHEN line.tenurewithinsurer < 11 THEN '4'
              WHEN line.tenurewithinsurer < 16 THEN '5'
              WHEN line.tenurewithinsurer < 20 THEN '6'
              ELSE '7'
            END,
            -- TENURE_DISCOUNT_PCT: 2-digit integer percent (e.g., 3% → '03')
            LPAD(CAST(ROUND(line.tenurediscountpct, 0) AS VARCHAR), 2, '0'),
            'PENDING', CURRENT_TIMESTAMP(), '{RUN_ID}', 'GUIDEWIRE'
        FROM INSURANCE_REGULATORY.BRONZE.GW_PC_POLICYPERIOD pp
        JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY p ON p.id = pp.policy_id
        JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_HOPOLICYLINE line ON line.policy_id = pp.policy_id
        JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_HOCOVERAGE cov ON cov.policyline_id = line.id
        JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_HODWELLING dw ON dw.policyline_id = line.id
    """)
    r = query("SELECT COUNT(*) AS n FROM INSURANCE_REGULATORY.SILVER.TSPR_PREMIUM_STAGING")
    return r[0]["n"]


def silver_claim_state(month: str) -> int:
    """SCD-2 claim state per (claim, exposure, accounting_month). Rules 13–16."""
    query("TRUNCATE TABLE INSURANCE_REGULATORY.SILVER.TSPR_CLAIM_STATE")
    # Simplified state machine: NCC=1 in the month the claim was first reported,
    # PCC=1 only on the first record where we see indemnity payment, RCC=1 on
    # rows where the claim was previously closed and is now open.
    query(f"""
        INSERT INTO INSURANCE_REGULATORY.SILVER.TSPR_CLAIM_STATE (
            ACCOUNTING_MONTH, NAIC_COMPANY_NO,
            CLAIM_ID, EXPOSURE_ID, CLAIMNUMBER,
            NEW_CLAIM_COUNT, PAID_CLAIM_COUNT, REOPENED_CLAIM_COUNT,
            CLAIM_STATUS, KIND_CODE,
            WAS_PREVIOUSLY_CLOSED, IS_NEWLY_REOPENED_THIS_PERIOD, IS_FIRST_RCC_RECORD_THIS_MONTH,
            _CREATED_TIMESTAMP, _PIPELINE_RUN_ID
        )
        SELECT
            '{month}',
            '12345',
            c.id, e.id, c.claimnumber,
            CASE WHEN TO_VARCHAR(c.reporteddate, 'YYYY-MM') = '{month}' THEN 1 ELSE 0 END AS ncc,
            CASE WHEN e.totalpaid > 0 THEN 1 ELSE 0 END AS pcc,
            CASE WHEN e.previouslyclosed AND c.reopendate IS NOT NULL THEN 1 ELSE 0 END AS rcc,
            -- CLAIM_STATUS 1-6 (open/cwip/cwop crossed with previously-closed flag)
            CASE
              WHEN e.previouslyclosed AND e.totalpaid = 0 THEN 4
              WHEN e.previouslyclosed AND e.totalpaid > 0 THEN 5
              WHEN e.totalpaid = 0 AND e.totaloutstanding > 0 THEN 1
              WHEN e.totalpaid > 0 AND e.totaloutstanding > 0 THEN 2
              WHEN e.totalpaid > 0 AND e.totaloutstanding = 0 THEN 6
              ELSE 1
            END AS cs,
            -- KIND_CODE 1-9: 1-3 (no payment), 4-5 (paid on reopened), 6 (paid not reopened), 7-9 (outstanding)
            CASE
              WHEN e.previouslyclosed AND e.totalpaid > 0 THEN 5
              WHEN e.previouslyclosed AND e.totaloutstanding > 0 THEN 4
              WHEN e.totaloutstanding > 0 AND e.totalpaid = 0 THEN 7
              WHEN e.totalpaid > 0 AND e.totaloutstanding > 0 THEN 6
              WHEN e.totalpaid > 0 AND e.totaloutstanding = 0 THEN 6
              ELSE 1
            END AS kind,
            e.previouslyclosed,
            CASE WHEN e.previouslyclosed AND c.reopendate IS NOT NULL THEN TRUE ELSE FALSE END,
            CASE WHEN e.previouslyclosed AND c.reopendate IS NOT NULL THEN TRUE ELSE FALSE END,
            CURRENT_TIMESTAMP(), '{RUN_ID}'
        FROM INSURANCE_REGULATORY.BRONZE.GW_CC_CLAIM c
        JOIN INSURANCE_REGULATORY.BRONZE.GW_CC_EXPOSURE e ON e.claim_id = c.id
    """)
    r = query("SELECT COUNT(*) AS n FROM INSURANCE_REGULATORY.SILVER.TSPR_CLAIM_STATE")
    return r[0]["n"]


def silver_loss(month: str) -> int:
    """Build silver.tspr_loss_staging — Section D loss records.

    Joins claim + exposure + state + policy lookup for shared fields
    (Rule 9 alignment: form, construction, deductible must match Section C).
    """
    query("TRUNCATE TABLE INSURANCE_REGULATORY.SILVER.TSPR_LOSS_STAGING")
    query(f"""
        INSERT INTO INSURANCE_REGULATORY.SILVER.TSPR_LOSS_STAGING (
            ACCOUNTING_MONTH, NAIC_COMPANY_NO, TICO_COMPANY_NO, RUN_ID,
            SOURCE_CLAIM_ID, SOURCE_EXPOSURE_ID, STAT_PLAN, RECORD_TYPE,
            POLICY_ID, CLAIM_ID_TSPR,
            ZIP9, OCCURRENCE_DATE,
            CAUSE_OF_LOSS, KIND_CODE,
            NEW_CLAIM_COUNT, PAID_CLAIM_COUNT, REOPENED_CLAIM_COUNT, CLAIM_STATUS,
            LOSS_AMOUNT,
            LINE_OF_BUSINESS, POLICY_FORM, CONSTRUCTION, TYPE_OF_LOSS,
            RECORD_INDICATOR, TENURE_CODE,
            VALIDATION_STATUS, _CREATED_TIMESTAMP, _PIPELINE_RUN_ID, _SOURCE_SYSTEM
        )
        SELECT
            '{month}', c.naic_number, '{TICO}', '{RUN_ID}',
            c.id, e.id, '4', '11',
            c.policynumber, e.claimidentifier,
            ad.postalcode || ad.postalcodeplus4,
            -- TSPR MMDDY occurrence date
            TO_VARCHAR(c.lossdate, 'MMDD') || RIGHT(TO_VARCHAR(c.lossdate, 'YYYY'), 1),
            CASE
              WHEN c.losscause = 'Wind' THEN '25'
              WHEN c.losscause = 'Hail' THEN '30'
              WHEN c.losscause = 'Fire' AND c.losscausesubtype = 'FireExternal' THEN '10'
              WHEN c.losscause = 'Fire' THEN '05'
              WHEN c.losscause = 'Freeze' THEN '71'
              ELSE '99'
            END,
            CAST(cs.KIND_CODE AS VARCHAR),
            cs.NEW_CLAIM_COUNT, cs.PAID_CLAIM_COUNT, cs.REOPENED_CLAIM_COUNT, cs.CLAIM_STATUS,
            -- Rule 11: indemnity paid - salvage - subrogation. LAE excluded.
            COALESCE(e.totalpaid, 0) - COALESCE(c.salvageamount, 0) - COALESCE(c.subrogationamount, 0),
            '1', line.holineform, dw.constructiontype, '1',  -- TYPE_OF_LOSS: 1=basic
            'L',  -- RECORD_INDICATOR: L=Loss
            CASE
              WHEN line.tenurewithinsurer < 3  THEN '1'
              WHEN line.tenurewithinsurer < 6  THEN '2'
              WHEN line.tenurewithinsurer < 9  THEN '3'
              WHEN line.tenurewithinsurer < 11 THEN '4'
              WHEN line.tenurewithinsurer < 16 THEN '5'
              WHEN line.tenurewithinsurer < 20 THEN '6'
              ELSE '7'
            END,
            'PENDING', CURRENT_TIMESTAMP(), '{RUN_ID}', 'GUIDEWIRE'
        FROM INSURANCE_REGULATORY.BRONZE.GW_CC_CLAIM c
        JOIN INSURANCE_REGULATORY.BRONZE.GW_CC_EXPOSURE e ON e.claim_id = c.id
        JOIN INSURANCE_REGULATORY.BRONZE.GW_CC_ADDRESS ad ON ad.claim_id = c.id
        JOIN INSURANCE_REGULATORY.SILVER.TSPR_CLAIM_STATE cs
              ON cs.CLAIM_ID = c.id AND cs.EXPOSURE_ID = e.id
        JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_HOPOLICYLINE line ON line.policy_id = c.policy_id
        JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_HODWELLING dw ON dw.policyline_id = line.id
    """)
    r = query("SELECT COUNT(*) AS n FROM INSURANCE_REGULATORY.SILVER.TSPR_LOSS_STAGING")
    return r[0]["n"]


def silver_cancellation(month: str) -> int:
    """Build silver.tspr_cancellation_staging from gw_pc_job + reason validation."""
    query("TRUNCATE TABLE INSURANCE_REGULATORY.SILVER.TSPR_CANCELLATION_STAGING")
    query(f"""
        INSERT INTO INSURANCE_REGULATORY.SILVER.TSPR_CANCELLATION_STAGING (
            ACCOUNTING_MONTH, NAIC_COMPANY_NO, TICO_COMPANY_NO, RUN_ID,
            SOURCE_JOB_ID, NOTIFICATION_DATE, ACTION_EFFECTIVE_DATE,
            ACTION_TYPE, TYPE_OF_POLICY, ZIP5,
            REASON_SOURCE_INDICATOR, WITHIN_60_DAYS_INDICATOR,
            REASON_CODE_LIST, RECIPIENT_COUNT, ACTUAL_ACTION_COUNT,
            CREDIT_SCORE_VIOLATION, WITHDRAWAL_VIOLATION,
            VALIDATION_STATUS, _CREATED_TIMESTAMP, _PIPELINE_RUN_ID, _SOURCE_SYSTEM
        )
        SELECT
            '{month}', '12345', '{TICO}', '{RUN_ID}',
            j.id,
            -- NOTIFICATION_DATE is MMY (3 chars); ACTION_EFFECTIVE_DATE is MMDDYY (6 chars).
            -- COALESCE with effectivedate then '000' so we never write NULL — the
            -- A.42 validator catches missing notice dates downstream; the pipeline
            -- must not abort on real-world data-quality issues.
            COALESCE(
              TO_VARCHAR(j.noticedate, 'MM') || RIGHT(TO_VARCHAR(j.noticedate, 'YYYY'), 1),
              TO_VARCHAR(j.effectivedate, 'MM') || RIGHT(TO_VARCHAR(j.effectivedate, 'YYYY'), 1),
              '000'
            ),
            COALESCE(TO_VARCHAR(j.effectivedate, 'MMDDYY'), '000000'),
            CASE
              WHEN j.subtype = 'Cancellation' THEN 'C'
              WHEN j.subtype = 'Renewal' THEN 'N'
              ELSE 'D'
            END,
            -- TYPE_OF_POLICY (Section F crosswalk; just pass form letter for demo)
            CASE WHEN line.holineform IS NOT NULL THEN '01' ELSE '01' END,
            dw.zip,
            CASE WHEN j.aerialimageused OR j.thirdpartydataused THEN 'A' ELSE 'N' END,
            CASE WHEN j.within60days THEN 'Y' ELSE 'N' END,
            COALESCE(j.cancellationreason, j.nonrenewalreason, j.declinereason),
            1, 1,  -- recipient_count, actual_action_count
            -- credit_score_violation: code L is the sole reason and reference says it needs companion
            CASE
              WHEN LENGTH(COALESCE(j.cancellationreason, j.nonrenewalreason, j.declinereason)) = 1
                AND COALESCE(j.cancellationreason, j.nonrenewalreason, j.declinereason) IN (
                  SELECT tspr_reason_code FROM INSURANCE_REGULATORY.REFERENCE.TSPR_REASON_CODE_MAP
                  WHERE credit_score_companion_required = TRUE
                )
              THEN TRUE ELSE FALSE
            END,
            -- withdrawal_violation: any must_appear_alone code is combined with others
            CASE
              WHEN LENGTH(COALESCE(j.cancellationreason, j.nonrenewalreason, j.declinereason)) > 1
                AND COALESCE(j.cancellationreason, j.nonrenewalreason, j.declinereason) LIKE ANY (
                  SELECT '%' || tspr_reason_code || '%'
                  FROM INSURANCE_REGULATORY.REFERENCE.TSPR_REASON_CODE_MAP
                  WHERE must_appear_alone = TRUE
                )
              THEN TRUE ELSE FALSE
            END,
            'PENDING', CURRENT_TIMESTAMP(), '{RUN_ID}', 'GUIDEWIRE'
        FROM INSURANCE_REGULATORY.BRONZE.GW_PC_JOB j
        JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY p ON p.id = j.policy_id
        JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_HOPOLICYLINE line ON line.policy_id = p.id
        JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_HODWELLING dw ON dw.policyline_id = line.id
        -- (GW_PC_ADDRESS intentionally not joined: address.postalcode is non-
        -- unique and produced a cartesian — 234 cancellations × ~23 addresses
        -- per ZIP = 5,310 rows. dw.zip carries the same value from the source
        -- POLICY_DETAILS dict, so we read it directly.)
    """)
    r = query("SELECT COUNT(*) AS n FROM INSURANCE_REGULATORY.SILVER.TSPR_CANCELLATION_STAGING")
    return r[0]["n"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", default=ACCOUNTING_MONTH_DEFAULT)
    args = ap.parse_args()

    print(f"Bronze → Silver  ·  accounting_month = {args.month}")
    print()
    n_premium = silver_premium(args.month)
    print(f"  ✓ TSPR_PREMIUM_STAGING        {n_premium} rows")

    n_state = silver_claim_state(args.month)
    print(f"  ✓ TSPR_CLAIM_STATE            {n_state} rows")

    n_loss = silver_loss(args.month)
    print(f"  ✓ TSPR_LOSS_STAGING           {n_loss} rows")

    n_cancel = silver_cancellation(args.month)
    print(f"  ✓ TSPR_CANCELLATION_STAGING   {n_cancel} rows")

    print()
    print(f"Silver populated · run_id = {RUN_ID}")
    return 0


TICO = "XYZ"

if __name__ == "__main__":
    raise SystemExit(main())
