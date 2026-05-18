"""Anomaly detector — populates GOLD.TSPR_ANOMALY_FLAGS.

Three detectors run against Bronze/Gold:
  1. premium_spike     — ZIPs whose written premium is >3× the all-filing mean.
  2. hail_cluster      — >3 Hail claims in the same ZIP within a 7-day window.
  3. freeze_in_summer  — Freeze-cause claims with loss date in Jun-Sep.

Each anomaly is stamped with its filing_batch_id so the UI can scope properly.
Idempotent: TRUNCATEs the table at the start of each run.

Run via:  uv run python -m scripts.detect_anomalies --month 2026-03
or:       POST /api/rhs/anomalies/detect
"""

from __future__ import annotations

import argparse
import json
import time
import uuid

from packages.rhs.filings import FILINGS, policy_id_to_filing_case
from packages.rhs.snowflake_client import query


def detect_premium_spike(month: str, run_id: str) -> int:
    """ZIPs with anomalously high written premium relative to the all-filing mean."""
    # Per-ZIP per-filing total premium; flag any with > 3× the corpus mean.
    case_expr = policy_id_to_filing_case("pp.policy_id")
    rows = query(f"""
        WITH zip_totals AS (
            SELECT {case_expr}                                AS filing_batch_id,
                   dw.zip                                     AS zip5,
                   SUM(COALESCE(pp.writtenpremium, 0))        AS total_prem,
                   COUNT(DISTINCT pp.policy_id)               AS policy_count
            FROM INSURANCE_REGULATORY.BRONZE.GW_PC_POLICYPERIOD pp
            JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_HOPOLICYLINE l ON l.policy_id = pp.policy_id
            JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_HODWELLING dw ON dw.policyline_id = l.id
            GROUP BY 1, 2
            HAVING filing_batch_id IS NOT NULL
        ),
        stats AS (
            SELECT AVG(total_prem) AS m, STDDEV(total_prem) AS s FROM zip_totals
        )
        SELECT zt.filing_batch_id, zt.zip5, zt.total_prem, zt.policy_count,
               s.m AS mean_prem, s.s AS stddev_prem,
               (zt.total_prem - s.m) / NULLIF(s.s, 0) AS z_score
        FROM zip_totals zt CROSS JOIN stats s
        WHERE zt.total_prem > s.m + 3 * NULLIF(s.s, 0)
        ORDER BY z_score DESC
    """)

    inserted = 0
    for r in rows:
        fbid = r.get("filing_batch_id") or r.get("FILING_BATCH_ID")
        zip5 = r.get("zip5") or r.get("ZIP5")
        total = float(r.get("total_prem") or r.get("TOTAL_PREM") or 0)
        m = float(r.get("mean_prem") or r.get("MEAN_PREM") or 0)
        s = float(r.get("stddev_prem") or r.get("STDDEV_PREM") or 0)
        z = float(r.get("z_score") or r.get("Z_SCORE") or 0)
        desc = (
            f"Written premium ${total:,.0f} in ZIP {zip5} is {z:.1f}σ above corpus "
            f"mean (${m:,.0f}); investigate for misclassification or duplicate-policy ingest."
        )
        query(f"""
            INSERT INTO INSURANCE_REGULATORY.GOLD.TSPR_ANOMALY_FLAGS
                (run_id, accounting_month, naic_company_no, flagged_timestamp,
                 anomaly_type, territory_zip, current_month_value,
                 rolling_12m_mean, rolling_12m_stddev, std_deviations_from_mean,
                 anomaly_description, filing_batch_id, severity)
            VALUES ('{run_id}', '{month}', '12345', CURRENT_TIMESTAMP(),
                    'premium_spike', '{zip5}', {total},
                    {m}, {s}, {z},
                    '{desc.replace("'", "''")}', '{fbid}', 'WARN')
        """)
        inserted += 1
    return inserted


def detect_hail_cluster(month: str, run_id: str) -> int:
    """ZIP × week buckets with >3 Hail claims (rapid-onset hail-storm signature)."""
    case_expr = policy_id_to_filing_case("c.policy_id")
    rows = query(f"""
        SELECT {case_expr}                                AS filing_batch_id,
               ad.postalcode                              AS zip5,
               DATE_TRUNC('WEEK', c.lossdate)             AS week_start,
               COUNT(*)                                   AS n_claims,
               ARRAY_AGG(c.claimnumber)                   AS claim_ids
        FROM INSURANCE_REGULATORY.BRONZE.GW_CC_CLAIM c
        JOIN INSURANCE_REGULATORY.BRONZE.GW_CC_ADDRESS ad ON ad.claim_id = c.id
        WHERE c.losscause = 'Hail'
        GROUP BY 1, 2, 3
        HAVING n_claims > 3 AND filing_batch_id IS NOT NULL
        ORDER BY n_claims DESC
    """)

    inserted = 0
    for r in rows:
        fbid = r.get("filing_batch_id") or r.get("FILING_BATCH_ID")
        zip5 = r.get("zip5") or r.get("ZIP5")
        week = r.get("week_start") or r.get("WEEK_START")
        n = int(r.get("n_claims") or r.get("N_CLAIMS") or 0)
        claim_ids = r.get("claim_ids") or r.get("CLAIM_IDS") or "[]"
        # claim_ids comes back as a JSON-encoded ARRAY from Snowflake
        if isinstance(claim_ids, str):
            try:
                claim_ids_list = json.loads(claim_ids)
            except Exception:
                claim_ids_list = []
        else:
            claim_ids_list = list(claim_ids)
        desc = (
            f"{n} Hail claims clustered in ZIP {zip5} during week of {week}; "
            f"consistent with a localized hailstorm. Cross-check NOAA storm reports."
        )
        # Build the SOURCE_RECORDS VARIANT
        claims_json = json.dumps(claim_ids_list).replace("'", "''")
        query(f"""
            INSERT INTO INSURANCE_REGULATORY.GOLD.TSPR_ANOMALY_FLAGS
                (run_id, accounting_month, naic_company_no, flagged_timestamp,
                 anomaly_type, cause_of_loss_code, territory_zip, current_month_value,
                 anomaly_description, filing_batch_id, source_records, severity)
            SELECT '{run_id}', '{month}', '12345', CURRENT_TIMESTAMP(),
                   'hail_cluster', '30', '{zip5}', {n},
                   '{desc.replace("'", "''")}', '{fbid}',
                   PARSE_JSON('{claims_json}'), 'INFO'
        """.strip())
        inserted += 1
    return inserted


def detect_freeze_in_summer(month: str, run_id: str) -> int:
    """Claims with cause=Freeze and lossdate in Jun-Sep — climatologically improbable."""
    case_expr = policy_id_to_filing_case("c.policy_id")
    rows = query(f"""
        SELECT {case_expr}                          AS filing_batch_id,
               c.claimnumber                         AS claim_id,
               ad.postalcode                         AS zip5,
               c.lossdate                            AS loss_date
        FROM INSURANCE_REGULATORY.BRONZE.GW_CC_CLAIM c
        LEFT JOIN INSURANCE_REGULATORY.BRONZE.GW_CC_ADDRESS ad ON ad.claim_id = c.id
        WHERE c.losscause = 'Freeze'
          AND MONTH(c.lossdate) BETWEEN 6 AND 9
        ORDER BY c.lossdate
    """)

    inserted = 0
    for r in rows:
        fbid = r.get("filing_batch_id") or r.get("FILING_BATCH_ID")
        claim_id = r.get("claim_id") or r.get("CLAIM_ID")
        zip5 = r.get("zip5") or r.get("ZIP5") or ""
        loss_date = r.get("loss_date") or r.get("LOSS_DATE")
        if not fbid or not claim_id:
            continue
        desc = (
            f"Claim {claim_id} reports Freeze cause on {loss_date} "
            f"(June–September). Verify cause-of-loss tagging; freeze losses in TX summer are anomalous."
        )
        source_json = json.dumps([claim_id]).replace("'", "''")
        query(f"""
            INSERT INTO INSURANCE_REGULATORY.GOLD.TSPR_ANOMALY_FLAGS
                (run_id, accounting_month, naic_company_no, flagged_timestamp,
                 anomaly_type, cause_of_loss_code, territory_zip, current_month_value,
                 anomaly_description, filing_batch_id, source_records, severity)
            SELECT '{run_id}', '{month}', '12345', CURRENT_TIMESTAMP(),
                   'freeze_in_summer', '71', '{zip5}', 1,
                   '{desc.replace("'", "''")}', '{fbid}',
                   PARSE_JSON('{source_json}'), 'WARN'
        """)
        inserted += 1
    return inserted


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", default="2026-03")
    args = ap.parse_args()

    run_id = f"anom-{int(time.time())}-{uuid.uuid4().hex[:6]}"

    print(f"Anomaly detection · accounting_month = {args.month} · run_id = {run_id}")
    print()

    # Idempotent: clear flags for this run-context first.
    query("TRUNCATE TABLE INSURANCE_REGULATORY.GOLD.TSPR_ANOMALY_FLAGS")

    n_spike  = detect_premium_spike(args.month, run_id)
    print(f"  ✓ premium_spike      {n_spike} flag(s)")
    n_hail   = detect_hail_cluster(args.month, run_id)
    print(f"  ✓ hail_cluster       {n_hail} flag(s)")
    n_freeze = detect_freeze_in_summer(args.month, run_id)
    print(f"  ✓ freeze_in_summer   {n_freeze} flag(s)")
    print()
    print(f"Total anomalies: {n_spike + n_hail + n_freeze}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
