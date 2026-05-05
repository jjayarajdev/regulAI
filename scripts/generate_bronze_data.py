"""Generate synthetic Guidewire CDC Parquet for Bronze layer.

Mimics what Guidewire Data Platform exports nightly. Same schema as a real
GDP feed — a customer can swap our Parquet stage for their bucket without
changing the medallion pipeline.

Section E (cancellations/nonrenewals/declinations):
  POL-0001  HO-A renewal             — no cancellation
  POL-0007  Cancellation, reason A   — failure to pay (valid)
  POL-0010  Nonrenewal,   reason LD  — credit+claims (valid: L has companion)
  POL-0011  Declination,  reason L   — INVALID: L alone (§559.052)
  POL-0012  Declination,  reason JD  — INVALID: J must be alone
  POL-0013  Cancellation, reason J   — valid: J alone (market withdrawal)

Section D (claims) — four scenarios that exercise the loss flow:
  CLM-001   Wind, reserve only          (KIND=7, NCC=1, no payment)
  CLM-002   Hail roof, ACV paid + RC    (KIND=6/7, DEPREC populated)
  CLM-005   Fire partial payment        (LAE flagged, excluded from net loss)
  CLM-009   Reopened mid-period         (RCC=1, Rule 15 demonstration)

Output: materialized/bronze_parquet/policycenter/<table>/data.parquet
        materialized/bronze_parquet/claimcenter/<table>/data.parquet
        materialized/bronze_parquet/billingcenter/<table>/data.parquet
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

OUTPUT_ROOT = Path("materialized/bronze_parquet")
PC_ROOT = OUTPUT_ROOT / "policycenter"
CC_ROOT = OUTPUT_ROOT / "claimcenter"
BC_ROOT = OUTPUT_ROOT / "billingcenter"

NAIC = "12345"
TICO = "XYZ"
INGEST_TS = dt.datetime(2026, 4, 1, 6, 0, 0)
CDC_TS = dt.datetime(2026, 3, 31, 23, 59, 59)

# Policy → (territory, ZIP, construction, year_built, form, coverageA)
POLICY_DETAILS = {
    2001: {"pol": "POL-0001", "territory": "30", "zip": "78701", "construction": "1", "year_built": 2010, "form": "A", "cov_a": 250000, "tenure_years": 5},
    2007: {"pol": "POL-0007", "territory": "20", "zip": "75001", "construction": "1", "year_built": 1995, "form": "A", "cov_a": 220000, "tenure_years": 3},
    2010: {"pol": "POL-0010", "territory": "10", "zip": "76001", "construction": "1", "year_built": 2005, "form": "B", "cov_a": 320000, "tenure_years": 7},
    2011: {"pol": "POL-0011", "territory": "30", "zip": "77001", "construction": "1", "year_built": 2018, "form": "A", "cov_a": 180000, "tenure_years": 1},
    2012: {"pol": "POL-0012", "territory": "30", "zip": "77002", "construction": "1", "year_built": 2020, "form": "A", "cov_a": 200000, "tenure_years": 0},
    2013: {"pol": "POL-0013", "territory": "20", "zip": "75201", "construction": "2", "year_built": 1980, "form": "B", "cov_a": 180000, "tenure_years": 12},
}


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


def address() -> pa.Table:
    """Risk-location addresses (one per policy)."""
    n = len(POLICY_DETAILS)
    cities = {"78701": "Austin", "75001": "Addison", "76001": "Arlington",
              "77001": "Houston", "77002": "Houston", "75201": "Dallas"}
    counties = {"78701": "Travis", "75001": "Dallas", "76001": "Tarrant",
                "77001": "Harris", "77002": "Harris", "75201": "Dallas"}
    rows = []
    for i, (pid, d) in enumerate(POLICY_DETAILS.items()):
        rows.append({
            "id": 8000 + i,
            "publicid": f"addr:{8000+i}",
            "addressline1": f"{1000+i*10} Main St",
            "city": cities.get(d["zip"], "Houston"),
            "county": counties.get(d["zip"], "Harris"),
            "state": "TX",
            "postalcode": d["zip"],
            "postalcodeplus4": "1234",
            "fipscodefull": "48000",
            "countyfipscode": "48201",
        })
    return pa.table({
        "_cdc_operation": ["INSERT"] * n,
        "_cdc_timestamp": [CDC_TS] * n,
        "_cdc_sequence": list(range(1, n + 1)),
        "_ingestion_timestamp": [INGEST_TS] * n,
        "_source_file": ["pc_address/2026-03-31.parquet"] * n,
        "id": [r["id"] for r in rows],
        "publicid": [r["publicid"] for r in rows],
        "addressline1": [r["addressline1"] for r in rows],
        "city": [r["city"] for r in rows],
        "county": [r["county"] for r in rows],
        "state": [r["state"] for r in rows],
        "postalcode": [r["postalcode"] for r in rows],
        "postalcodeplus4": [r["postalcodeplus4"] for r in rows],
        "fipscodefull": [r["fipscodefull"] for r in rows],
        "countyfipscode": [r["countyfipscode"] for r in rows],
        "createtime": [_ts(2025, 1, 1)] * n,
        "updatetime": [_ts(2025, 1, 1)] * n,
        "retiredvalue": [0] * n,
    })


def hopolicyline() -> pa.Table:
    """HO line characteristics: form, occupancy, roof, tenure, RV codes."""
    n = len(POLICY_DETAILS)
    policy_ids = list(POLICY_DETAILS.keys())
    return pa.table({
        "_cdc_operation": ["INSERT"] * n,
        "_cdc_timestamp": [CDC_TS] * n,
        "_cdc_sequence": list(range(1, n + 1)),
        "_ingestion_timestamp": [INGEST_TS] * n,
        "_source_file": ["pc_hopolicyline/2026-03-31.parquet"] * n,
        "id": [9000 + i for i in range(n)],
        "publicid": [f"hopl:{9000+i}" for i in range(n)],
        "branchid": [1] * n,
        "policy_id": policy_ids,
        "policylinepatterncodeidentifier": ["HOLine"] * n,
        "linecategory": ["HO"] * n,
        "effectivedate": [_ts(2026, 1, 1)] * n,
        "expirationdate": [_ts(2026, 12, 31)] * n,
        "holineform": [POLICY_DETAILS[p]["form"] for p in policy_ids],
        "numberofunits": [1] * n,
        "occupancytype": ["OwnerOccupied"] * n,
        "roofcoveringtype": ["A"] * n,        # A = composition shingle
        "roofcoveringcreditclass": [1] * n,
        "roofinstallationyear": [POLICY_DETAILS[p]["year_built"] for p in policy_ids],
        "cosmeticdamageexclusion": [False] * n,
        "roofcoveragetype": ["RC"] * n,
        "dwellingcoveragetype": ["RC"] * n,
        "personalpropertycovtype": ["RC"] * n,
        "priorclaimscount": [0] * n,
        "priorclaimsused": [True] * n,
        "rv_alarm": ["1"] * n,
        "rv_age_of_home": ["1"] * n,
        "rv_sprinkler": ["5"] * n,
        "rv_claims_experience": ["1"] * n,
        "rv_companion_policy": ["5"] * n,
        "rv_credit_score": ["1"] * n,
        "rv_senior_citizen": ["5"] * n,
        "rv_smart_home": ["5"] * n,
        "rv_new_home": ["5"] * n,
        "rv_additional_surcharges": ["5"] * n,
        "tenurewithinsurer": [POLICY_DETAILS[p]["tenure_years"] for p in policy_ids],
        "tenurediscountpct": [3.0] * n,
        "tenureusedforrating": [True] * n,
        "tenureusedfortiering": [True] * n,
        "privatefloodcoverage": [False] * n,
        "lawordcompct": ["10"] * n,
        "createtime": [_ts(2026, 1, 1)] * n,
        "updatetime": [_ts(2026, 1, 1)] * n,
        "retiredvalue": [0] * n,
        "_partition_month": ["2026-01"] * n,
    })


def hocoverage() -> pa.Table:
    """HO coverage limits (Coverage A/B/C/D) and deductibles."""
    n = len(POLICY_DETAILS)
    policy_ids = list(POLICY_DETAILS.keys())
    return pa.table({
        "_cdc_operation": ["INSERT"] * n,
        "_cdc_timestamp": [CDC_TS] * n,
        "_cdc_sequence": list(range(1, n + 1)),
        "_ingestion_timestamp": [INGEST_TS] * n,
        "_source_file": ["pc_hocoverage/2026-03-31.parquet"] * n,
        "id": [9100 + i for i in range(n)],
        "publicid": [f"hocov:{9100+i}" for i in range(n)],
        "branchid": [1] * n,
        "fixedid": [9100 + i for i in range(n)],
        "policyline_id": [9000 + i for i in range(n)],
        "coveragepatterncode": ["HODW_Cov_HOE"] * n,
        "coveragecategory": ["Dwelling"] * n,
        "coveragetype": ["A"] * n,
        "coverageamount": [POLICY_DETAILS[p]["cov_a"] for p in policy_ids],
        "personalpropertylimit": [int(POLICY_DETAILS[p]["cov_a"] * 0.5) for p in policy_ids],
        "lossofuselimit": [int(POLICY_DETAILS[p]["cov_a"] * 0.2) for p in policy_ids],
        "lossofusepct": [20.0] * n,
        "deductibletype": ["Dollar"] * n,
        "allperilsdeductible": [1000] * n,
        "windhailddeductible": [2500] * n,
        "windhailddeductiblepct": [None] * n,
        "tropicalcyclonedeductible": [None] * n,
        "tropicalcyclonedeductibletype": [None] * n,
        "windexcluded": [False] * n,
        "optionalcovcode": [None] * n,
        "optionalcovamount": [None] * n,
        "writtenpremium": [1500.0] * n,
        "ecpremium": [200.0] * n,
        "effectivedate": [_ts(2026, 1, 1)] * n,
        "expirationdate": [_ts(2026, 12, 31)] * n,
        "createtime": [_ts(2026, 1, 1)] * n,
        "updatetime": [_ts(2026, 1, 1)] * n,
        "retiredvalue": [0] * n,
        "_partition_month": ["2026-01"] * n,
    })


def hodwelling() -> pa.Table:
    """Physical property facts: territory, ZIP, construction, year built."""
    n = len(POLICY_DETAILS)
    policy_ids = list(POLICY_DETAILS.keys())
    return pa.table({
        "_cdc_operation": ["INSERT"] * n,
        "_cdc_timestamp": [CDC_TS] * n,
        "_cdc_sequence": list(range(1, n + 1)),
        "_ingestion_timestamp": [INGEST_TS] * n,
        "_source_file": ["pc_hodwelling/2026-03-31.parquet"] * n,
        "id": [9200 + i for i in range(n)],
        "publicid": [f"hodw:{9200+i}" for i in range(n)],
        "branchid": [1] * n,
        "policyline_id": [9000 + i for i in range(n)],
        "policyaddress_id": [8000 + i for i in range(n)],
        "territory": [POLICY_DETAILS[p]["territory"] for p in policy_ids],
        "countyfips": ["48201"] * n,
        "placecodetdi": ["999"] * n,
        "zip": [POLICY_DETAILS[p]["zip"] for p in policy_ids],
        "ziplus4": ["1234"] * n,
        "state": ["TX"] * n,
        "constructiontype": [POLICY_DETAILS[p]["construction"] for p in policy_ids],
        "yearbuilt": [POLICY_DETAILS[p]["year_built"] for p in policy_ids],
        "numberoffamilies": [1] * n,
        "ppccode": ["3"] * n,
        "ppccodesplit": ["3W"] * n,
        "buildingcodecredit": [None] * n,
        "intwiazone": [False] * n,
        "coastalterritory": [False] * n,
        "createtime": [_ts(2026, 1, 1)] * n,
        "updatetime": [_ts(2026, 1, 1)] * n,
        "retiredvalue": [0] * n,
    })


def policyperiodpremium() -> pa.Table:
    """BillingCenter tenure & premium summary, one row per period."""
    n = len(POLICY_DETAILS)
    policy_ids = list(POLICY_DETAILS.keys())
    return pa.table({
        "_cdc_operation": ["INSERT"] * n,
        "_cdc_timestamp": [CDC_TS] * n,
        "_cdc_sequence": list(range(1, n + 1)),
        "_ingestion_timestamp": [INGEST_TS] * n,
        "_source_file": ["bc_policyperiodpremium/2026-03-31.parquet"] * n,
        "id": [9300 + i for i in range(n)],
        "publicid": [f"bcpp:{9300+i}" for i in range(n)],
        "policyperiod_id": [5001, 5007, 5010, 5011, 5012, 5013],
        "policy_id": policy_ids,
        "writtenpremium": [1500.0] * n,
        "earnedpremium": [375.0] * n,
        "unearnedpremium": [1125.0] * n,
        "tenureyears": [POLICY_DETAILS[p]["tenure_years"] for p in policy_ids],
        "tenurediscountpct": [3.0] * n,
        "tenureusedforrating": [True] * n,
        "tenureusedfortiering": [True] * n,
        "transactiontype": ["NewBusiness"] * n,
        "transactiondate": [_ts(2026, 1, 1)] * n,
        "createtime": [_ts(2026, 1, 1)] * n,
        "updatetime": [_ts(2026, 3, 31)] * n,
        "retiredvalue": [0] * n,
        "_partition_month": ["2026-01"] * n,
    })


# ─── Claim scenarios ────────────────────────────────────────────────────────
# Four claims chosen to exercise distinct TSPR Section D rules.
CLAIMS = [
    {  # CLM-001 — wind on POL-0001, reserve only (KIND=7)
        "id": 60001, "publicid": "clm:60001", "claimnumber": "CLM-001",
        "policy_id": 2001, "policy_number": "POL-0001",
        "lossdate": _ts(2026, 2, 12), "reporteddate": _ts(2026, 2, 14),
        "losscause": "Wind", "subtype": "Wind",
        "indemnity_paid": 0, "lae_paid": 0, "indemnity_reserve": 8500,
        "salvage": 0, "subrogation": 0, "rc_estimate": 0, "acv_paid": 0,
        "is_roof_loss": True, "previously_closed": False, "claim_id_tspr": "01",
        "city": "Austin", "zip": "78701",
    },
    {  # CLM-002 — hail roof on POL-0001, paid + RC depreciation
        "id": 60002, "publicid": "clm:60002", "claimnumber": "CLM-002",
        "policy_id": 2001, "policy_number": "POL-0001",
        "lossdate": _ts(2026, 1, 22), "reporteddate": _ts(2026, 1, 23),
        "losscause": "Hail", "subtype": "Hail",
        "indemnity_paid": 6800, "lae_paid": 250, "indemnity_reserve": 0,
        "salvage": 0, "subrogation": 0, "rc_estimate": 12000, "acv_paid": 6800,
        "is_roof_loss": True, "previously_closed": False, "claim_id_tspr": "02",
        "city": "Austin", "zip": "78701",
    },
    {  # CLM-005 — fire partial pay on POL-0010, LAE excluded
        "id": 60005, "publicid": "clm:60005", "claimnumber": "CLM-005",
        "policy_id": 2010, "policy_number": "POL-0010",
        "lossdate": _ts(2026, 2, 3), "reporteddate": _ts(2026, 2, 4),
        "losscause": "Fire", "subtype": "FireExternal",
        "indemnity_paid": 18500, "lae_paid": 1200, "indemnity_reserve": 4500,
        "salvage": 0, "subrogation": 0, "rc_estimate": 0, "acv_paid": 0,
        "is_roof_loss": False, "previously_closed": False, "claim_id_tspr": "05",
        "city": "Arlington", "zip": "76001",
    },
    {  # CLM-009 — reopened claim on POL-0001 (Rule 15 RCC=1 demo)
        "id": 60009, "publicid": "clm:60009", "claimnumber": "CLM-009",
        "policy_id": 2001, "policy_number": "POL-0001",
        "lossdate": _ts(2025, 11, 5), "reporteddate": _ts(2025, 11, 7),
        "losscause": "Wind", "subtype": "Wind",
        "indemnity_paid": 4200, "lae_paid": 0, "indemnity_reserve": 1500,
        "salvage": 0, "subrogation": 0, "rc_estimate": 0, "acv_paid": 0,
        "is_roof_loss": True, "previously_closed": True, "claim_id_tspr": "09",
        "city": "Austin", "zip": "78701",
    },
]


def cc_claim() -> pa.Table:
    n = len(CLAIMS)
    return pa.table({
        "_cdc_operation": ["INSERT"] * n,
        "_cdc_timestamp": [CDC_TS] * n,
        "_cdc_sequence": list(range(1, n + 1)),
        "_ingestion_timestamp": [INGEST_TS] * n,
        "_source_file": ["cc_claim/2026-03-31.parquet"] * n,
        "_partition_month": ["2026-03"] * n,
        "id": [c["id"] for c in CLAIMS],
        "publicid": [c["publicid"] for c in CLAIMS],
        "claimnumber": [c["claimnumber"] for c in CLAIMS],
        "policy_id": [c["policy_id"] for c in CLAIMS],
        "policynumber": [c["policy_number"] for c in CLAIMS],
        "policyperiod_id": [5001 if c["policy_id"] == 2001 else 5010 for c in CLAIMS],
        "uwcompany_id": [1001] * n,
        "naic_number": [NAIC] * n,
        "lossdate": [c["lossdate"] for c in CLAIMS],
        "losslocation_id": [70000 + i for i in range(n)],
        "reporteddate": [c["reporteddate"] for c in CLAIMS],
        "losscause": [c["losscause"] for c in CLAIMS],
        "losscausesubtype": [c["subtype"] for c in CLAIMS],
        "lobtypecode": ["HO"] * n,
        "coveragecategory": ["Dwelling"] * n,
        "state": ["TX"] * n,
        "closedate": [None] * n,
        "reopendate": [_ts(2026, 1, 5) if c["claimnumber"] == "CLM-009" else None for c in CLAIMS],
        "hasindemnity": [c["indemnity_paid"] > 0 for c in CLAIMS],
        "totalincurred": [c["indemnity_paid"] + c["lae_paid"] + c["indemnity_reserve"] for c in CLAIMS],
        "subrogationamount": [c["subrogation"] for c in CLAIMS],
        "salvageamount": [c["salvage"] for c in CLAIMS],
        "isintwiazone": [False] * n,
        "createtime": [c["reporteddate"] for c in CLAIMS],
        "updatetime": [_ts(2026, 3, 31)] * n,
        "retiredvalue": [0] * n,
    })


def cc_exposure() -> pa.Table:
    n = len(CLAIMS)
    return pa.table({
        "_cdc_operation": ["INSERT"] * n,
        "_cdc_timestamp": [CDC_TS] * n,
        "_cdc_sequence": list(range(1, n + 1)),
        "_ingestion_timestamp": [INGEST_TS] * n,
        "_source_file": ["cc_exposure/2026-03-31.parquet"] * n,
        "_partition_month": ["2026-03"] * n,
        "id": [70000 + i for i in range(n)],
        "publicid": [f"exp:{70000+i}" for i in range(n)],
        "claim_id": [c["id"] for c in CLAIMS],
        "claimnumber": [c["claimnumber"] for c in CLAIMS],
        "coveragetype": ["A"] * n,
        "coveragesegment": ["Dwelling"] * n,
        "coveragesubtype": ["Building"] * n,
        "losstype": ["1"] * n,        # 1 = basic
        "isenhancementendorsement": [False] * n,
        "state": ["TX"] * n,
        "closedate": [None] * n,
        "reopendate": [_ts(2026, 1, 5) if c["claimnumber"] == "CLM-009" else None for c in CLAIMS],
        "previouslyclosed": [c["previously_closed"] for c in CLAIMS],
        "claimidentifier": [c["claim_id_tspr"] for c in CLAIMS],
        "isroofloss": [c["is_roof_loss"] for c in CLAIMS],
        "rooflosscauseoftype": ["RoofRepair" if c["is_roof_loss"] else None for c in CLAIMS],
        "totalincurred": [c["indemnity_paid"] + c["lae_paid"] + c["indemnity_reserve"] for c in CLAIMS],
        "totalpaid": [c["indemnity_paid"] + c["lae_paid"] for c in CLAIMS],
        "totaloutstanding": [c["indemnity_reserve"] for c in CLAIMS],
        "createtime": [c["reporteddate"] for c in CLAIMS],
        "updatetime": [_ts(2026, 3, 31)] * n,
        "retiredvalue": [0] * n,
    })


def cc_transaction() -> pa.Table:
    """One row per payment / reserve event. Drives the loss flow in Silver."""
    rows = []
    seq = 1
    for ci, c in enumerate(CLAIMS):
        # Indemnity payment (if any)
        if c["indemnity_paid"]:
            rows.append({
                "id": 80000 + seq, "publicid": f"txn:{80000+seq}", "claim_id": c["id"],
                "exposure_id": 70000 + ci, "claimnumber": c["claimnumber"],
                "subtype": "Payment", "transactiontype": "Payment",
                "costtype": "claimcost", "costcategory": "indemnity",
                "isindemnity": True, "islae": False, "isreinsurancerecovery": False,
                "issalvage": False, "issubrogation": False,
                "amount": c["indemnity_paid"], "currency": "USD",
                "transactiondate": c["reporteddate"] + dt.timedelta(days=14),
                "paymentdate": c["reporteddate"] + dt.timedelta(days=14),
                "accountingdate": c["reporteddate"] + dt.timedelta(days=14),
                "isreversal": False, "isreserve": False,
                "rc_estimate": c["rc_estimate"], "acv_paid": c["acv_paid"],
            })
            seq += 1
        # LAE payment (if any)
        if c["lae_paid"]:
            rows.append({
                "id": 80000 + seq, "publicid": f"txn:{80000+seq}", "claim_id": c["id"],
                "exposure_id": 70000 + ci, "claimnumber": c["claimnumber"],
                "subtype": "Payment", "transactiontype": "Payment",
                "costtype": "claimcost", "costcategory": "lae",
                "isindemnity": False, "islae": True, "isreinsurancerecovery": False,
                "issalvage": False, "issubrogation": False,
                "amount": c["lae_paid"], "currency": "USD",
                "transactiondate": c["reporteddate"] + dt.timedelta(days=14),
                "paymentdate": c["reporteddate"] + dt.timedelta(days=14),
                "accountingdate": c["reporteddate"] + dt.timedelta(days=14),
                "isreversal": False, "isreserve": False,
                "rc_estimate": 0, "acv_paid": 0,
            })
            seq += 1
        # Reserve (if any)
        if c["indemnity_reserve"]:
            rows.append({
                "id": 80000 + seq, "publicid": f"txn:{80000+seq}", "claim_id": c["id"],
                "exposure_id": 70000 + ci, "claimnumber": c["claimnumber"],
                "subtype": "Reserve", "transactiontype": "Reserve",
                "costtype": "claimcost", "costcategory": "indemnity",
                "isindemnity": True, "islae": False, "isreinsurancerecovery": False,
                "issalvage": False, "issubrogation": False,
                "amount": 0, "currency": "USD",
                "transactiondate": c["reporteddate"] + dt.timedelta(days=2),
                "paymentdate": None,
                "accountingdate": c["reporteddate"] + dt.timedelta(days=2),
                "isreversal": False, "isreserve": True,
                "rc_estimate": 0, "acv_paid": 0,
            })
            seq += 1
    n = len(rows)
    return pa.table({
        "_cdc_operation": ["INSERT"] * n,
        "_cdc_timestamp": [CDC_TS] * n,
        "_cdc_sequence": list(range(1, n + 1)),
        "_ingestion_timestamp": [INGEST_TS] * n,
        "_source_file": ["cc_transaction/2026-03-31.parquet"] * n,
        "_partition_month": ["2026-03"] * n,
        "id": [r["id"] for r in rows],
        "publicid": [r["publicid"] for r in rows],
        "claim_id": [r["claim_id"] for r in rows],
        "exposure_id": [r["exposure_id"] for r in rows],
        "claimnumber": [r["claimnumber"] for r in rows],
        "subtype": [r["subtype"] for r in rows],
        "transactiontype": [r["transactiontype"] for r in rows],
        "costtype": [r["costtype"] for r in rows],
        "costcategory": [r["costcategory"] for r in rows],
        "isindemnity": [r["isindemnity"] for r in rows],
        "islae": [r["islae"] for r in rows],
        "isreinsurancerecovery": [r["isreinsurancerecovery"] for r in rows],
        "issalvage": [r["issalvage"] for r in rows],
        "issubrogation": [r["issubrogation"] for r in rows],
        "amount": [float(r["amount"]) for r in rows],
        "currency": [r["currency"] for r in rows],
        "transactiondate": [r["transactiondate"] for r in rows],
        "paymentdate": [r["paymentdate"] for r in rows],
        "accountingdate": [r["accountingdate"] for r in rows],
        "linkedtransaction_id": [None] * n,
        "isreversal": [r["isreversal"] for r in rows],
        "isreserve": [r["isreserve"] for r in rows],
        "reserveamount": [None] * n,
        "reserveline": [None] * n,
        "replacementcostestimate": [float(r["rc_estimate"]) if r["rc_estimate"] else None for r in rows],
        "actualcashvaluepaid": [float(r["acv_paid"]) if r["acv_paid"] else None for r in rows],
        "createtime": [r["transactiondate"] for r in rows],
        "updatetime": [r["transactiondate"] for r in rows],
    })


def cc_reserveline() -> pa.Table:
    """Month-end reserve snapshot per claim (March 2026 cycle)."""
    n = len(CLAIMS)
    return pa.table({
        "_cdc_operation": ["INSERT"] * n,
        "_cdc_timestamp": [CDC_TS] * n,
        "_cdc_sequence": list(range(1, n + 1)),
        "_ingestion_timestamp": [INGEST_TS] * n,
        "_source_file": ["cc_reserveline/2026-03-31.parquet"] * n,
        "_partition_month": ["2026-03"] * n,
        "id": [85000 + i for i in range(n)],
        "publicid": [f"rl:{85000+i}" for i in range(n)],
        "claim_id": [c["id"] for c in CLAIMS],
        "exposure_id": [70000 + i for i in range(n)],
        "claimnumber": [c["claimnumber"] for c in CLAIMS],
        "totalreserve": [float(c["indemnity_reserve"]) for c in CLAIMS],
        "indemnitypaid": [float(c["indemnity_paid"]) for c in CLAIMS],
        "indemnityreserve": [float(c["indemnity_reserve"]) for c in CLAIMS],
        "laepaid": [float(c["lae_paid"]) for c in CLAIMS],
        "laereserve": [0.0] * n,
        "asofdate": [_ts(2026, 3, 31)] * n,
        "accountingmonth": ["2026-03"] * n,
        "createtime": [_ts(2026, 3, 31)] * n,
        "updatetime": [_ts(2026, 3, 31)] * n,
    })


def cc_address() -> pa.Table:
    """Loss-location addresses, one per claim."""
    n = len(CLAIMS)
    return pa.table({
        "_cdc_operation": ["INSERT"] * n,
        "_cdc_timestamp": [CDC_TS] * n,
        "_cdc_sequence": list(range(1, n + 1)),
        "_ingestion_timestamp": [INGEST_TS] * n,
        "_source_file": ["cc_address/2026-03-31.parquet"] * n,
        "id": [86000 + i for i in range(n)],
        "publicid": [f"caddr:{86000+i}" for i in range(n)],
        "claim_id": [c["id"] for c in CLAIMS],
        "addresstype": ["LossLocation"] * n,
        "addressline1": [f"{1000 + i*10} Main St" for i in range(n)],
        "city": [c["city"] for c in CLAIMS],
        "county": ["Travis"] * n,
        "state": ["TX"] * n,
        "postalcode": [c["zip"] for c in CLAIMS],
        "postalcodeplus4": ["1234"] * n,
        "fipscodefull": ["48000"] * n,
        "createtime": [c["reporteddate"] for c in CLAIMS],
        "updatetime": [c["reporteddate"] for c in CLAIMS],
        "retiredvalue": [0] * n,
    })


def cc_claim_status_history() -> pa.Table:
    """Append-only status events. Drives the SCD-2 claim state machine."""
    rows = []
    for ci, c in enumerate(CLAIMS):
        # Initial open
        rows.append({
            "claim_id": c["id"], "claimnumber": c["claimnumber"],
            "exposure_id": 70000 + ci,
            "status_from": None, "status_to": "open",
            "status_change_timestamp": c["reporteddate"],
            "accounting_month": f"{c['reporteddate'].year}-{c['reporteddate'].month:02d}",
            "has_indemnity_payment": False, "cumulative_paid": 0,
            "is_close_event": False, "is_reopen_event": False, "is_new_event": True,
        })
        # CLM-009 had a prior-period close + a Jan 2026 reopen
        if c["claimnumber"] == "CLM-009":
            rows.append({
                "claim_id": c["id"], "claimnumber": c["claimnumber"],
                "exposure_id": 70000 + ci,
                "status_from": "open", "status_to": "closed",
                "status_change_timestamp": _ts(2025, 12, 20),
                "accounting_month": "2025-12",
                "has_indemnity_payment": True,
                "cumulative_paid": float(c["indemnity_paid"]),
                "is_close_event": True, "is_reopen_event": False, "is_new_event": False,
            })
            rows.append({
                "claim_id": c["id"], "claimnumber": c["claimnumber"],
                "exposure_id": 70000 + ci,
                "status_from": "closed", "status_to": "open",
                "status_change_timestamp": _ts(2026, 1, 5),
                "accounting_month": "2026-01",
                "has_indemnity_payment": True,
                "cumulative_paid": float(c["indemnity_paid"]),
                "is_close_event": False, "is_reopen_event": True, "is_new_event": False,
            })
    n = len(rows)
    return pa.table({
        "_ingestion_timestamp": [INGEST_TS] * n,
        "_source_file": ["cc_claim_status_history/2026-03-31.parquet"] * n,
        "_partition_month": [r["accounting_month"] for r in rows],
        "claim_id": [r["claim_id"] for r in rows],
        "claimnumber": [r["claimnumber"] for r in rows],
        "exposure_id": [r["exposure_id"] for r in rows],
        "status_from": [r["status_from"] for r in rows],
        "status_to": [r["status_to"] for r in rows],
        "status_change_timestamp": [r["status_change_timestamp"] for r in rows],
        "accounting_month": [r["accounting_month"] for r in rows],
        "has_indemnity_payment": [r["has_indemnity_payment"] for r in rows],
        "cumulative_paid": [r["cumulative_paid"] for r in rows],
        "is_close_event": [r["is_close_event"] for r in rows],
        "is_reopen_event": [r["is_reopen_event"] for r in rows],
        "is_new_event": [r["is_new_event"] for r in rows],
    })


def main() -> int:
    PC_ROOT.mkdir(parents=True, exist_ok=True)
    CC_ROOT.mkdir(parents=True, exist_ok=True)
    BC_ROOT.mkdir(parents=True, exist_ok=True)

    pc_tables = {
        "pc_uwcompany": uwcompany(),
        "pc_policy": policy(),
        "pc_policyperiod": policyperiod(),
        "pc_job": job(),
        "pc_address": address(),
        "pc_hopolicyline": hopolicyline(),
        "pc_hocoverage": hocoverage(),
        "pc_hodwelling": hodwelling(),
    }
    cc_tables = {
        "cc_claim": cc_claim(),
        "cc_exposure": cc_exposure(),
        "cc_transaction": cc_transaction(),
        "cc_reserveline": cc_reserveline(),
        "cc_address": cc_address(),
        "cc_claim_status_history": cc_claim_status_history(),
    }
    bc_tables = {
        "bc_policyperiodpremium": policyperiodpremium(),
    }

    for root, label, tables in [(PC_ROOT, "PC", pc_tables), (CC_ROOT, "CC", cc_tables), (BC_ROOT, "BC", bc_tables)]:
        for name, tbl in tables.items():
            out_dir = root / name
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / "data.parquet"
            pq.write_table(tbl, out_path, use_deprecated_int96_timestamps=True)
            print(f"  ✓ [{label}] {out_path.relative_to(OUTPUT_ROOT)}  ({tbl.num_rows} rows, {tbl.num_columns} cols)")

    print()
    print(f"Total: {sum(len(t) for t in [pc_tables, cc_tables, bc_tables])} tables across "
          f"{sum(len(t.values()) for t in [pc_tables, cc_tables, bc_tables])} files")
    print()
    print("Next: make load-bronze")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
