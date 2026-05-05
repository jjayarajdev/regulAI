"""Generate synthetic Guidewire CDC Parquet for Bronze layer.

Mimics what Guidewire Data Platform exports nightly. Same schema as a real
GDP feed — a customer can swap our Parquet stage for their bucket without
changing the medallion pipeline.

Scope of this first cut: the cancellation/nonrenewal/declination flow.
Five Bronze tables, six policies, six jobs. Each job carries the TSPR
reason codes that join to REFERENCE.TSPR_REASON_CODE_MAP.

Six scenarios:
  POL-0001  HO-A renewal             — no cancellation
  POL-0007  Cancellation, reason A   — failure to pay (valid)
  POL-0010  Nonrenewal,   reason LD  — credit+claims (valid: L has companion)
  POL-0011  Declination,  reason L   — INVALID: L alone (§559.052)
  POL-0012  Declination,  reason JD  — INVALID: J must be alone
  POL-0013  Cancellation, reason J   — valid: J alone (market withdrawal)

Output: materialized/bronze_parquet/policycenter/<table>/data.parquet
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

OUTPUT_ROOT = Path("materialized/bronze_parquet/policycenter")

NAIC = "12345"
TICO = "XYZ"
INGEST_TS = dt.datetime(2026, 4, 1, 6, 0, 0)
CDC_TS = dt.datetime(2026, 3, 31, 23, 59, 59)


def _ts(y: int, m: int, d: int, hh: int = 12, mm: int = 0) -> dt.datetime:
    return dt.datetime(y, m, d, hh, mm)


# ─── gw_pc_uwcompany ────────────────────────────────────────────────────────
def uwcompany() -> pa.Table:
    return pa.table({
        "_cdc_operation": ["INSERT"],
        "_cdc_timestamp": [CDC_TS],
        "_cdc_sequence": [1],
        "_ingestion_timestamp": [INGEST_TS],
        "_source_file": ["pc_uwcompany/2026-03-31.parquet"],
        "id": [1001],
        "publicid": ["uw:1001"],
        "code": ["REGULAI_INS"],
        "naiccode": [NAIC],
        "ticocompanynumber": [TICO],
        "createtime": [_ts(2024, 1, 1)],
        "updatetime": [_ts(2024, 1, 1)],
        "retiredvalue": [0],
    })


# ─── gw_pc_policy ───────────────────────────────────────────────────────────
def policy() -> pa.Table:
    rows = [
        {"id": 2001, "publicid": "pol:2001", "policynumber": "POL-0001"},
        {"id": 2007, "publicid": "pol:2007", "policynumber": "POL-0007"},
        {"id": 2010, "publicid": "pol:2010", "policynumber": "POL-0010"},
        {"id": 2011, "publicid": "pol:2011", "policynumber": "POL-0011"},
        {"id": 2012, "publicid": "pol:2012", "policynumber": "POL-0012"},
        {"id": 2013, "publicid": "pol:2013", "policynumber": "POL-0013"},
    ]
    n = len(rows)
    return pa.table({
        "_cdc_operation": ["INSERT"] * n,
        "_cdc_timestamp": [CDC_TS] * n,
        "_cdc_sequence": list(range(1, n + 1)),
        "_ingestion_timestamp": [INGEST_TS] * n,
        "_source_file": ["pc_policy/2026-03-31.parquet"] * n,
        "id": [r["id"] for r in rows],
        "publicid": [r["publicid"] for r in rows],
        "account_id": [3001 + i for i in range(n)],
        "producercode_id": [4001] * n,
        "policynumber": [r["policynumber"] for r in rows],
        "issuedate": [_ts(2025, 1, 1)] * n,
        "originalinceptiondate": [_ts(2025, 1, 1)] * n,
        "createtime": [_ts(2025, 1, 1)] * n,
        "updatetime": [_ts(2026, 3, 1)] * n,
        "retiredvalue": [0] * n,
    })


# ─── gw_pc_policyperiod ─────────────────────────────────────────────────────
def policyperiod() -> pa.Table:
    rows = [
        {"id": 5001, "policy_id": 2001, "status": "Bound", "termtype": "Annual"},
        {"id": 5007, "policy_id": 2007, "status": "Cancelled", "termtype": "Annual"},
        {"id": 5010, "policy_id": 2010, "status": "NonRenewing", "termtype": "Annual"},
        {"id": 5011, "policy_id": 2011, "status": "Declined", "termtype": "Annual"},
        {"id": 5012, "policy_id": 2012, "status": "Declined", "termtype": "Annual"},
        {"id": 5013, "policy_id": 2013, "status": "Cancelled", "termtype": "Annual"},
    ]
    n = len(rows)
    return pa.table({
        "_cdc_operation": ["INSERT"] * n,
        "_cdc_timestamp": [CDC_TS] * n,
        "_cdc_sequence": list(range(1, n + 1)),
        "_ingestion_timestamp": [INGEST_TS] * n,
        "_source_file": ["pc_policyperiod/2026-03-31.parquet"] * n,
        "_partition_month": ["2026-03"] * n,
        "id": [r["id"] for r in rows],
        "publicid": [f"pp:{r['id']}" for r in rows],
        "policy_id": [r["policy_id"] for r in rows],
        "account_id": [3001 + i for i in range(n)],
        "producercode_id": [4001] * n,
        "policycontact_id": [None] * n,
        "uwcompany_id": [1001] * n,
        "policyterm_id": [None] * n,
        "periodstart": [_ts(2026, 1, 1)] * n,
        "periodend": [_ts(2026, 12, 31)] * n,
        "editeffectivedate": [_ts(2026, 1, 1)] * n,
        "modelnumber": [1] * n,
        "modeldate": [_ts(2026, 1, 1)] * n,
        "status": [r["status"] for r in rows],
        "jobtype": ["Submission"] * n,
        "policytype": ["Homeowners"] * n,
        "basestate": ["TX"] * n,
        "branchname": ["Main"] * n,
        "termtype": [r["termtype"] for r in rows],
        "termnum": [1] * n,
        "cancellationdate": [None] * n,
        "cancellationsource": [None] * n,
        "cancellationreason": [None] * n,
        "nonrenewalcode": [None] * n,
        "writtendate": [_ts(2025, 12, 1)] * n,
        "totalpremium": [1500.00] * n,
        "writtenpremium": [1500.00] * n,
        "totalcost": [1500.00] * n,
        "fulltermamount": [1500.00] * n,
        "earnedpremium": [375.00] * n,
        "uwcompanycode": ["REGULAI_INS"] * n,
        "naic_number": [NAIC] * n,
        "tico_company_number": [TICO] * n,
        "createtime": [_ts(2025, 12, 1)] * n,
        "updatetime": [_ts(2026, 3, 31)] * n,
        "retiredvalue": [0] * n,
    })


# ─── gw_pc_job ──────────────────────────────────────────────────────────────
# The cancellation/nonrenewal/declination jobs that carry reason codes.
# Each job's reason code(s) join to REFERENCE.TSPR_REASON_CODE_MAP.
def job() -> pa.Table:
    rows = [
        # POL-0007: cancellation, reason A (failure to pay)
        {
            "id": 7007, "policy_id": 2007, "subtype": "Cancellation",
            "status": "Bound", "cancellationreason": "A",
            "nonrenewalreason": None, "declinereason": None,
            "noticedate": _ts(2026, 2, 15),
            "effectivedate": _ts(2026, 3, 1),
            "cancellationdate": _ts(2026, 3, 1),
            "within60days": False,
        },
        # POL-0010: nonrenewal, reasons L+D (credit + claims) — valid combo
        {
            "id": 7010, "policy_id": 2010, "subtype": "Renewal",
            "status": "NonRenewed", "cancellationreason": None,
            "nonrenewalreason": "LD", "declinereason": None,
            "noticedate": _ts(2026, 3, 1),
            "effectivedate": _ts(2026, 4, 1),
            "cancellationdate": None,
            "within60days": False,
        },
        # POL-0011: declination, reason L alone — INVALID (§559.052)
        {
            "id": 7011, "policy_id": 2011, "subtype": "Submission",
            "status": "Declined", "cancellationreason": None,
            "nonrenewalreason": None, "declinereason": "L",
            "noticedate": _ts(2026, 3, 10),
            "effectivedate": _ts(2026, 3, 10),
            "cancellationdate": None,
            "within60days": False,
        },
        # POL-0012: declination, reasons J+D — INVALID (J must be alone)
        {
            "id": 7012, "policy_id": 2012, "subtype": "Submission",
            "status": "Declined", "cancellationreason": None,
            "nonrenewalreason": None, "declinereason": "JD",
            "noticedate": _ts(2026, 3, 12),
            "effectivedate": _ts(2026, 3, 12),
            "cancellationdate": None,
            "within60days": False,
        },
        # POL-0013: cancellation, reason J alone (market withdrawal) — valid
        {
            "id": 7013, "policy_id": 2013, "subtype": "Cancellation",
            "status": "Bound", "cancellationreason": "J",
            "nonrenewalreason": None, "declinereason": None,
            "noticedate": _ts(2026, 3, 20),
            "effectivedate": _ts(2026, 4, 20),
            "cancellationdate": _ts(2026, 4, 20),
            "within60days": False,
        },
    ]
    n = len(rows)
    return pa.table({
        "_cdc_operation": ["INSERT"] * n,
        "_cdc_timestamp": [CDC_TS] * n,
        "_cdc_sequence": list(range(1, n + 1)),
        "_ingestion_timestamp": [INGEST_TS] * n,
        "_source_file": ["pc_job/2026-03-31.parquet"] * n,
        "id": [r["id"] for r in rows],
        "publicid": [f"job:{r['id']}" for r in rows],
        "policy_id": [r["policy_id"] for r in rows],
        "basedon_id": [None] * n,
        "subtype": [r["subtype"] for r in rows],
        "jobnumber": [f"JOB-{r['id']}" for r in rows],
        "status": [r["status"] for r in rows],
        "createtime": [r["noticedate"] for r in rows],
        "closedate": [r["effectivedate"] for r in rows],
        "effectivedate": [r["effectivedate"] for r in rows],
        "cancellationdate": [r["cancellationdate"] for r in rows],
        "cancellationreason": [r["cancellationreason"] for r in rows],
        "cancellationsource": ["Insurer"] * n,
        "nonrenewalreason": [r["nonrenewalreason"] for r in rows],
        "declinereason": [r["declinereason"] for r in rows],
        "within60days": [r["within60days"] for r in rows],
        "noticedate": [r["noticedate"] for r in rows],
        "noticesource": ["Insurer"] * n,
        "aerialimageused": [False] * n,
        "thirdpartydatauseed": [False] * n,
        "twiadepopulation": [False] * n,
        "retiredvalue": [0] * n,
        "updatetime": [r["noticedate"] for r in rows],
    })


def _coerce_timestamps_us(tbl: pa.Table) -> pa.Table:
    """Force microsecond precision on all timestamp columns.

    Snowflake's COPY INTO interprets Parquet TIMESTAMP_NANOS as if the
    underlying int64 were microseconds, producing dates ~50,000 years out.
    Casting to TIMESTAMP_MICROS at write time avoids the mismatch.
    """
    new_fields = []
    for field in tbl.schema:
        if pa.types.is_timestamp(field.type):
            new_fields.append(field.with_type(pa.timestamp("us")))
        else:
            new_fields.append(field)
    new_schema = pa.schema(new_fields)
    return tbl.cast(new_schema)


def main() -> int:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    tables = {
        "pc_uwcompany": uwcompany(),
        "pc_policy": policy(),
        "pc_policyperiod": policyperiod(),
        "pc_job": job(),
    }

    for name, tbl in tables.items():
        out_dir = OUTPUT_ROOT / name
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "data.parquet"
        # use_deprecated_int96_timestamps writes a 96-bit Julian-day +
        # nanosecond format that Snowflake's COPY INTO interprets correctly
        # without any timestamp scale ambiguity.
        pq.write_table(tbl, out_path, use_deprecated_int96_timestamps=True)
        print(f"  ✓ {out_path}  ({tbl.num_rows} rows, {tbl.num_columns} cols)")

    print()
    print("Job rows (the ones that join to REFERENCE.TSPR_REASON_CODE_MAP):")
    for r in tables["pc_job"].to_pylist():
        reason = (
            r["cancellationreason"]
            or r["nonrenewalreason"]
            or r["declinereason"]
        )
        print(
            f"  POL={r['policy_id']:5d}  "
            f"{r['subtype']:14s}  reason={reason!r:6s}  "
            f"effective={r['effectivedate'].date()}"
        )
    print()
    print("Next: make load-bronze")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
