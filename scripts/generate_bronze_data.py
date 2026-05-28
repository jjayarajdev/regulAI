"""Generate synthetic Guidewire CDC Parquet for Bronze layer.

Mimics what Guidewire Data Platform exports nightly. Same schema as a real
GDP feed — a customer can swap our Parquet stage for their bucket without
changing the medallion pipeline.

Section E (cancellations/nonrenewals/declinations):
  POL-0001  HO-A renewal             — no cancellation
  POL-0007  Cancellation, reason A   — failure to pay (valid)
  POL-0010  Nonrenewal,   reason LD  — credit+claims (valid: L has companion)
  POL-0011  Declination,  reason L   — INVALID: L alone (§559.052, A.34 L-companion)
  POL-0012  Declination,  reason JD  — INVALID: J must be alone (A.34 J-alone)
  POL-0013  Cancellation, reason J   — valid: J alone (market withdrawal)
  POL-0014  Cancellation, reason K   — valid: K alone (location of risk)
  POL-0015  Nonrenewal,   reason LM  — valid: L + M companion (roof condition)
  POL-0016  Declination,  reason LJ  — INVALID: combines L with J (J-alone rule)
  POL-0017  Nonrenewal,   reason LK  — valid: L + K companion (location of risk)
  POL-0018  Cancellation, reason DG  — valid: claims + wind/hail exposure
  POL-0019  Declination,  reason IO  — INVALID: I and O are not valid TSPR codes

Other intentional data-quality quirks (exercise rules outside A.34):
  POL-0017  naic_number = "ABC45"        — INVALID per A.22 (must be 5 digits)
  POL-0014  writtenpremium = $50         — INVALID per A.30 (out of range)
  POL-0015  termtype = "Custom"          — WARNING per A.40 (not a standard term)
  POL-0010  job.noticedate = NULL        — INVALID per A.42 (notice date required)

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
# Guidewire CDA emits timestamp + fingerprint as folder-name strings,
# not row-level TIMESTAMPs. Match real CDA shape: timestampfolder is
# the snapshot folder (e.g. "1711929599000" — epoch ms) and
# fingerprintfolder is a diagnostic identifier.
_CDC_EPOCH_MS = int(dt.datetime(2026, 3, 31, 23, 59, 59).timestamp() * 1000)
CDC_TIMESTAMP_FOLDER = str(_CDC_EPOCH_MS)
CDC_FINGERPRINT_FOLDER = "fp-synth-20260331-235959"

def _hex_seq(i: int) -> str:
    """Mirror Guidewire's gwcbi___seqval_hex: zero-padded hex string."""
    return f"{i:016x}"

import random as _rng_module

# Deterministic seed — change to regenerate, keep fixed for reproducible demos.
BULK_RANDOM_SEED = 20260515

# Bulk policy counts per filing (layered on top of the curated set)
BULK_COUNTS = {"TPA": 200, "RES": 100, "CL": 50}

# Texas metro ZIP pool with population weights — bulk policies sample from this
# so we get realistic geo distribution (Houston/Dallas heavy, smaller cities thin).
_TX_ZIP_POOL = [
    # zip,    city,             county,        weight
    ("77002", "Houston",        "Harris",      6),
    ("77024", "Houston",        "Harris",      4),
    ("77019", "Houston",        "Harris",      3),
    ("77018", "Houston",        "Harris",      3),
    ("75201", "Dallas",         "Dallas",      4),
    ("75205", "Dallas",         "Dallas",      3),
    ("75001", "Addison",        "Dallas",      2),
    ("78701", "Austin",         "Travis",      4),
    ("78704", "Austin",         "Travis",      3),
    ("78745", "Austin",         "Travis",      3),
    ("78712", "Austin",         "Travis",      2),
    ("78216", "San Antonio",    "Bexar",       4),
    ("78215", "San Antonio",    "Bexar",       2),
    ("76101", "Fort Worth",     "Tarrant",     3),
    ("76001", "Arlington",      "Tarrant",     2),
    ("76012", "Arlington",      "Tarrant",     2),
    ("75070", "McKinney",       "Collin",      2),
    ("78415", "Corpus Christi", "Nueces",      1),
    ("76301", "Wichita Falls",  "Wichita",     1),
    ("79101", "Amarillo",       "Potter",      1),
    ("76710", "Waco",           "McLennan",    1),
]

# Reason-code distributions per filing — weighted so violations are rare-but-present
_REASON_DIST = {
    # (reason_code or None, weight) · None = no cancellation (in-force policy)
    "TPA": [
        (None, 50),
        ("A", 30), ("LD", 12), ("LK", 8), ("LM", 6),
        ("K", 8), ("M", 4), ("DG", 4), ("J", 3), ("D", 3),
        # Violations — rare but present so each rule has fresh blockers
        ("L", 2.5), ("JD", 1.5), ("LJ", 1), ("IO", 0.5),
    ],
    "RES": [
        (None, 65),
        ("A", 22), ("LD", 10), ("M", 8), ("K", 6), ("N", 4), ("LK", 4),
        ("DG", 2),
        ("L", 1.5), ("JD", 0.5),
    ],
    "CL": [
        (None, 45),
        ("A", 20), ("DG", 12), ("J", 10), ("H", 8), ("K", 6),
        ("M", 3), ("D", 5),
        ("L", 1),
    ],
}

# Subtype heuristic: how is the cancellation/nonrenewal/declination reported?
_SUBTYPE_FOR_REASON = {
    # Most A-coded events are cancellations (failure to pay)
    "A": "Cancellation",
    # L alone or invalid → typically declinations (initial application rejected)
    "L": "Submission", "IO": "Submission", "LJ": "Submission",
    "JD": "Submission",
    # J alone → market withdrawal, typically a cancellation
    "J": "Cancellation",
    # Multi-letter combinations are typically nonrenewals
    "LD": "Renewal", "LK": "Renewal", "LM": "Renewal", "M": "Renewal", "N": "Renewal", "K": "Renewal",
    "DG": "Cancellation", "D": "Cancellation", "H": "Cancellation",
}

# Status that follows from subtype
_STATUS_FOR_SUBTYPE = {
    "Cancellation": "Cancelled",
    "Renewal":      "NonRenewed",
    "Submission":   "Declined",
}


def _bulk_synth_policies() -> dict[int, dict]:
    """Generate bulk synthetic policy details (ids 2100..2299 TPA / 2300..2399 RES / 2400..2449 CL).

    Layered on top of the curated POLICY_DETAILS — the curated cases keep their
    role as the demo narrative (POL-0011 is always The L-Alone Case, etc.),
    while these add distributional realism for screenshots and stress tests.
    """
    rng = _rng_module.Random(BULK_RANDOM_SEED)
    bulk: dict[int, dict] = {}
    # Note: Silver's POLICY_FORM column is VARCHAR(1) — must use single-char codes
    plans = [
        # plan_code, id_range,            form_pool,        cov_a_range_k, tenure_max
        ("TPA", range(2100, 2300), ["A","B","3"], ( 180,  600), 30),
        ("RES", range(2300, 2400), ["3","5","6"], ( 180,  850), 25),
        ("CL",  range(2400, 2450), ["6"],         ( 500, 5000), 40),
    ]
    for _plan_code, id_range, form_pool, (cov_lo, cov_hi), tenure_max in plans:
        zip_choices  = [z[0] for z in _TX_ZIP_POOL]
        zip_weights  = [z[3] for z in _TX_ZIP_POOL]
        for pid in id_range:
            zipcode = rng.choices(zip_choices, weights=zip_weights, k=1)[0]
            year_built = rng.randint(1970, 2024)
            tenure = rng.randint(0, tenure_max)
            # triangular distribution gives a "mostly-medium, occasional high" cov_a shape
            cov_a = int(rng.triangular(cov_lo, cov_hi, (cov_lo + cov_hi) * 0.5) * 1000)
            bulk[pid] = {
                "pol":          f"POL-{pid - 2000:04d}",
                "territory":    rng.choice(["10","20","30","40","50","60"]),
                "zip":          zipcode,
                "construction": str(rng.choices([1, 2, 3], weights=[7, 2, 1])[0]),
                "year_built":   year_built,
                "form":         rng.choice(form_pool),
                "cov_a":        cov_a,
                "tenure_years": tenure,
            }
    return bulk


# ── Bulk synthetic CLAIMS ─────────────────────────────────────────────────
# Mirrors the pattern used for policies: layer realistic-distribution claims
# on top of the 4 curated narrative claims (CLM-001, 002, 005, 009).

# Loss-cause distribution weighted to match Texas HO historical patterns
_LOSS_CAUSE_DIST = [
    # (cause, subtype, weight, typical_indemnity_K, cat_pct)
    ("Wind",        "Wind",         25, ( 3,  35),  3),
    ("Hail",        "Hail",         15, ( 4,  45), 18),  # most CAT events
    ("WaterDamage", "WaterDamage",  18, ( 4,  25),  0),
    ("Theft",       "Theft",         6, ( 1,  12),  0),
    ("Fire",        "FireExternal",  6, (12, 180),  0),
    ("Liability",   "Liability",     4, ( 5,  50),  0),
    ("Vandalism",   "Vandalism",     4, ( 1,   8),  0),
    ("Lightning",   "Lightning",     3, ( 2,  20),  0),
    ("Freeze",      "Freeze",        5, ( 4,  30),  8),  # winter storm Uri-style
    ("Other",       "Other",        14, ( 1,  20),  0),
]


def _bulk_synth_claims() -> list[dict]:
    """Generate ~150 synthetic claims, one per policy with a sampled-frequency
    multiplier. Each claim's loss-cause + amount + dates are drawn from realistic
    distributions; CAT-flagged claims cluster on Hail/Freeze.
    """
    rng = _rng_module.Random(BULK_RANDOM_SEED + 2)
    bulk: list[dict] = []
    next_id = 61000
    next_claim_num = 100

    causes  = [c[0] for c in _LOSS_CAUSE_DIST]
    weights = [c[2] for c in _LOSS_CAUSE_DIST]

    # Per-filing target count: ~80 TPA, ~50 RES, ~20 CL
    target = {"TPA": 80, "RES": 50, "CL": 20}

    for plan_code, count in target.items():
        # Sample policies in this filing that get claims (some get >1)
        eligible_pids = [pid for pid, pc in POLICY_FILING.items() if pc == plan_code]
        rng.shuffle(eligible_pids)
        # Pick claims-per-policy: weighted so some get 2, rare 3
        produced = 0
        for pid in eligible_pids:
            if produced >= count:
                break
            # 65% 1 claim, 25% 2, 10% 3
            n_claims = rng.choices([1, 2, 3], weights=[65, 25, 10], k=1)[0]
            pd = POLICY_DETAILS.get(pid, {})
            zipcode = pd.get("zip", "78701")
            for _ in range(n_claims):
                if produced >= count:
                    break
                idx = rng.choices(range(len(_LOSS_CAUSE_DIST)), weights=weights, k=1)[0]
                cause, subtype, _, (lo_k, hi_k), cat_pct = _LOSS_CAUSE_DIST[idx]
                # Loss amount: triangular log-shaped — mode at low end, long tail high
                indemnity = int(rng.triangular(lo_k, hi_k, lo_k * 1.8) * 1000)
                # Pattern: 40% pure reserve, 50% paid+reserve, 10% paid only
                pattern = rng.choices(["reserve_only", "paid_and_reserve", "paid_only"], weights=[40, 50, 10], k=1)[0]
                if pattern == "reserve_only":
                    indemnity_paid, indemnity_reserve = 0, indemnity
                elif pattern == "paid_only":
                    indemnity_paid, indemnity_reserve = indemnity, 0
                else:
                    paid_frac = rng.uniform(0.3, 0.8)
                    indemnity_paid = int(indemnity * paid_frac)
                    indemnity_reserve = indemnity - indemnity_paid
                lae_paid = int(indemnity_paid * rng.uniform(0.02, 0.10)) if indemnity_paid else 0
                rc_estimate = int(indemnity * rng.uniform(1.1, 1.6)) if cause in ("Wind", "Hail") and rng.random() < 0.45 else 0
                acv_paid = indemnity_paid if rc_estimate else 0
                is_cat = rng.random() < (cat_pct / 100.0)
                is_roof = cause in ("Wind", "Hail") and rng.random() < 0.55

                # Dates within Q3-Q4 2025 / Q1 2026 (clustered seasonally)
                month = rng.choices([3, 6, 7, 8, 9, 10, 11, 12, 1, 2],
                                    weights=[5, 6, 8, 10, 12, 14, 10, 8, 9, 8], k=1)[0]
                year = 2025 if month >= 6 else 2026
                day = rng.randint(1, 28)
                lossdate = dt.datetime(year, month, day)
                # Reported 0-3 days later, occasionally up to 60
                lag = rng.choices([0, 1, 2, 3, 7, 14, 30, 60], weights=[15, 25, 20, 10, 8, 5, 4, 2], k=1)[0]
                reporteddate = lossdate + dt.timedelta(days=lag)

                claim_id = next_id
                claim_num = f"CLM-{next_claim_num:03d}"
                next_id += 1
                next_claim_num += 1

                bulk.append({
                    "id": claim_id,
                    "publicid": f"clm:{claim_id}",
                    "claimnumber": claim_num,
                    "policy_id": pid,
                    "policy_number": pd.get("pol", f"POL-{pid - 2000:04d}"),
                    "lossdate": lossdate,
                    "reporteddate": reporteddate,
                    "losscause": cause,
                    "subtype": subtype,
                    "indemnity_paid": indemnity_paid,
                    "lae_paid": lae_paid,
                    "indemnity_reserve": indemnity_reserve,
                    "salvage": 0,
                    "subrogation": 0,
                    "rc_estimate": rc_estimate,
                    "acv_paid": acv_paid,
                    "is_roof_loss": is_roof,
                    "previously_closed": False,
                    "claim_id_tspr": f"{(claim_id % 100):02d}",
                    "city": "Houston",  # populated by address lookup post-merge
                    "zip": zipcode,
                    "is_cat": is_cat,
                })
                produced += 1

    # ── Inject deliberate violations so the new Section B/D rules fire ──
    # B.11: 2 claims with a loss cause NOT in the TSPR set
    for c in bulk[:2]:
        c["losscause"] = "Earthquake"  # not a valid TSPR cause
    # B.14: 3 claims with extreme reporting lag (>100 days)
    for c in bulk[2:5]:
        c["reporteddate"] = c["lossdate"] + dt.timedelta(days=rng.randint(100, 180))
    # D.12: pick 2 hail/freeze claims, ensure they're high-severity and mark
    # them to receive NULL isintwiazone in cc_claim() below
    hail_freeze = sorted(
        [c for c in bulk if c["losscause"] in ("Hail", "Freeze")],
        key=lambda c: -(c["indemnity_paid"] + c["indemnity_reserve"]),
    )
    for c in hail_freeze[:2]:
        c["indemnity_paid"] = max(c["indemnity_paid"], 35000)
        c["needs_cat_zone_null"] = True

    return bulk


def _bulk_jobs_for(policy_id: int, plan_code: str, rng: _rng_module.Random) -> list[dict] | None:
    """Sample 0 or 1 cancellation/nonrenewal/declination job for a bulk policy."""
    dist = _REASON_DIST[plan_code]
    choices = [d[0] for d in dist]
    weights = [d[1] for d in dist]
    reason = rng.choices(choices, weights=weights, k=1)[0]
    if reason is None:
        return None  # no job — policy is in-force
    subtype = _SUBTYPE_FOR_REASON.get(reason, "Cancellation")
    status  = _STATUS_FOR_SUBTYPE.get(subtype, "Bound")
    job_id  = 7000 + policy_id - 2000   # 7100..7299 for TPA bulk, etc.
    # Notice/effective dates fall within reporting period
    month = rng.randint(1, 3) if plan_code != "RES" else 3   # RES bulk is March 2026
    day   = rng.randint(1, 28)
    notice_date = dt.datetime(2026, month, day)
    eff_date    = notice_date + dt.timedelta(days=rng.choice([14, 21, 30]))
    return [{
        "id": job_id, "policy_id": policy_id, "subtype": subtype,
        "status": status,
        "cancellationreason": reason if subtype == "Cancellation" else None,
        "nonrenewalreason":   reason if subtype == "Renewal"      else None,
        "declinereason":      reason if subtype == "Submission"   else None,
        "noticedate":     notice_date,
        "effectivedate":  eff_date,
        "cancellationdate": eff_date if subtype == "Cancellation" else None,
        "within60days": False,
    }]


# Policy → (territory, ZIP, construction, year_built, form, coverageA)
# Three filings:
#   POL-0001..0019  TPA curated      |  POL-0100..0299  TPA bulk synthetic
#   POL-0030..0034  RES curated      |  POL-0300..0399  RES bulk synthetic
#   POL-0050..0053  CL curated       |  POL-0400..0449  CL bulk synthetic
POLICY_DETAILS = {
    # ── TPA filing (existing) ──
    2001: {"pol": "POL-0001", "territory": "30", "zip": "78701", "construction": "1", "year_built": 2010, "form": "A", "cov_a": 250000, "tenure_years": 5},
    2007: {"pol": "POL-0007", "territory": "20", "zip": "75001", "construction": "1", "year_built": 1995, "form": "A", "cov_a": 220000, "tenure_years": 3},
    2010: {"pol": "POL-0010", "territory": "10", "zip": "76001", "construction": "1", "year_built": 2005, "form": "B", "cov_a": 320000, "tenure_years": 7},
    2011: {"pol": "POL-0011", "territory": "30", "zip": "77001", "construction": "1", "year_built": 2018, "form": "A", "cov_a": 180000, "tenure_years": 1},
    2012: {"pol": "POL-0012", "territory": "30", "zip": "77002", "construction": "1", "year_built": 2020, "form": "A", "cov_a": 200000, "tenure_years": 0},
    2013: {"pol": "POL-0013", "territory": "20", "zip": "75201", "construction": "2", "year_built": 1980, "form": "B", "cov_a": 180000, "tenure_years": 12},
    2014: {"pol": "POL-0014", "territory": "40", "zip": "75070", "construction": "1", "year_built": 2015, "form": "A", "cov_a": 275000, "tenure_years": 4},
    2015: {"pol": "POL-0015", "territory": "50", "zip": "78415", "construction": "1", "year_built": 2008, "form": "B", "cov_a": 195000, "tenure_years": 8},
    2016: {"pol": "POL-0016", "territory": "60", "zip": "76301", "construction": "1", "year_built": 2021, "form": "A", "cov_a": 165000, "tenure_years": 0},
    2017: {"pol": "POL-0017", "territory": "40", "zip": "79101", "construction": "2", "year_built": 1998, "form": "B", "cov_a": 210000, "tenure_years": 6},
    2018: {"pol": "POL-0018", "territory": "20", "zip": "78216", "construction": "1", "year_built": 2012, "form": "A", "cov_a": 305000, "tenure_years": 9},
    2019: {"pol": "POL-0019", "territory": "60", "zip": "76710", "construction": "1", "year_built": 2019, "form": "A", "cov_a": 245000, "tenure_years": 2},
    # ── RES filing (residential monthly) ──
    2030: {"pol": "POL-0030", "territory": "10", "zip": "75205", "construction": "1", "year_built": 2014, "form": "3", "cov_a": 410000, "tenure_years": 6},
    2031: {"pol": "POL-0031", "territory": "10", "zip": "78704", "construction": "1", "year_built": 2007, "form": "3", "cov_a": 295000, "tenure_years": 11},
    2032: {"pol": "POL-0032", "territory": "30", "zip": "77024", "construction": "1", "year_built": 2019, "form": "3", "cov_a": 525000, "tenure_years": 2},
    2033: {"pol": "POL-0033", "territory": "20", "zip": "76012", "construction": "1", "year_built": 2002, "form": "5", "cov_a": 215000, "tenure_years": 14},
    2034: {"pol": "POL-0034", "territory": "10", "zip": "78712", "construction": "1", "year_built": 2022, "form": "3", "cov_a": 365000, "tenure_years": 1},
    # ── CL filing (commercial lines quarterly) ──
    2050: {"pol": "POL-0050", "territory": "10", "zip": "78701", "construction": "1", "year_built": 1998, "form": "6", "cov_a": 1250000, "tenure_years": 15},
    2051: {"pol": "POL-0051", "territory": "30", "zip": "77002", "construction": "2", "year_built": 2010, "form": "6", "cov_a": 850000, "tenure_years": 8},
    2052: {"pol": "POL-0052", "territory": "20", "zip": "75201", "construction": "1", "year_built": 2016, "form": "6", "cov_a": 2100000, "tenure_years": 5},
    2053: {"pol": "POL-0053", "territory": "10", "zip": "78216", "construction": "1", "year_built": 2003, "form": "6", "cov_a": 680000, "tenure_years": 22},
}

# Filing membership — used to scope queries by current filing context.
# Includes both curated and bulk-synthetic ranges.
POLICY_FILING = {
    **{pid: "TPA" for pid in list(range(2001, 2020)) + list(range(2100, 2300))},
    **{pid: "RES" for pid in list(range(2030, 2035)) + list(range(2300, 2400))},
    **{pid: "CL"  for pid in list(range(2050, 2054)) + list(range(2400, 2450))},
}

# Merge the bulk synthetic policies into POLICY_DETAILS — this is what every
# generator function iterates, so all 15 Bronze tables auto-extend with bulk
# data. The curated 21 keep their explicit definitions; bulk policies follow.
POLICY_DETAILS.update(_bulk_synth_policies())


def _ts(y: int, m: int, d: int, hh: int = 12, mm: int = 0) -> dt.datetime:
    return dt.datetime(y, m, d, hh, mm)


# ─── gw_pc_uwcompany ────────────────────────────────────────────────────────
def uwcompany() -> pa.Table:
    return pa.table({
        "gwcbi___operation": ["INSERT"],
        "gwcdac___timestampfolder": [CDC_TIMESTAMP_FOLDER],
        "gwcdac___fingerprintfolder": [CDC_FINGERPRINT_FOLDER],
        "gwcbi___seqval_hex": [_hex_seq(1)],
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
        {"id": pid, "publicid": f"pol:{pid}", "policynumber": d["pol"]}
        for pid, d in POLICY_DETAILS.items()
    ]
    n = len(rows)
    return pa.table({
        "gwcbi___operation": ["INSERT"] * n,
        "gwcdac___timestampfolder": [CDC_TIMESTAMP_FOLDER] * n,
        "gwcdac___fingerprintfolder": [CDC_FINGERPRINT_FOLDER] * n,
        "gwcbi___seqval_hex": [_hex_seq(i) for i in range(1, n + 1)],
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
    # Map each policy_id to its period status. Period id = policy id + 3000.
    POLICY_STATUS = {
        # TPA curated
        2001: "Bound",
        2007: "Cancelled",
        2010: "NonRenewing",
        2011: "Declined",
        2012: "Declined",
        2013: "Cancelled",
        2014: "Cancelled",
        2015: "NonRenewing",
        2016: "Declined",
        2017: "NonRenewing",
        2018: "Cancelled",
        2019: "Declined",
        # RES curated
        2030: "Cancelled",
        2031: "NonRenewing",
        2032: "Declined",
        2033: "NonRenewing",
        2034: "Bound",
        # CL curated
        2050: "Cancelled",
        2051: "Cancelled",
        2052: "Cancelled",
        2053: "Bound",
    }
    # For bulk-synthetic policies, default to Bound (status gets overridden later
    # by the job() function if the policy gets a cancellation/nonrenewal/declination)
    def _status_for(pid):
        if pid in POLICY_STATUS:
            return POLICY_STATUS[pid]
        return "Bound"

    rows = [
        {
            "id": 3000 + pid,
            "policy_id": pid,
            "status": _status_for(pid),
            # Termtype: TPA-specific quirk for POL-0015; RES is monthly cadence;
            # bulk policies follow their filing's cadence.
            "termtype":
                "Custom"    if pid == 2015
                else "Monthly" if (pid in range(2030, 2035) or pid in range(2300, 2400))
                else "Annual",
        }
        for pid in POLICY_DETAILS
    ]
    n = len(rows)
    return pa.table({
        "gwcbi___operation": ["INSERT"] * n,
        "gwcdac___timestampfolder": [CDC_TIMESTAMP_FOLDER] * n,
        "gwcdac___fingerprintfolder": [CDC_FINGERPRINT_FOLDER] * n,
        "gwcbi___seqval_hex": [_hex_seq(i) for i in range(1, n + 1)],
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
        # POL-0014 (TPA) gets a tiny premium → A.30 violation
        "writtenpremium": [50.00 if r["policy_id"] == 2014 else 1500.00 for r in rows],
        "totalcost": [1500.00] * n,
        "fulltermamount": [1500.00] * n,
        "earnedpremium": [375.00] * n,
        "uwcompanycode": ["REGULAI_INS"] * n,
        # NAIC quirks: POL-0017 (TPA) → bad alphanumeric. POL-0052 (CL) → 4-digit
        "naic_number": [
            "ABC45" if r["policy_id"] == 2017 else
            "9876"  if r["policy_id"] == 2052 else
            NAIC
            for r in rows
        ],
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
        # POL-0010: nonrenewal, reasons L+D — valid combo, BUT noticedate is missing
        # (intentional gap → triggers A.42 notice-date-required rule)
        {
            "id": 7010, "policy_id": 2010, "subtype": "Renewal",
            "status": "NonRenewed", "cancellationreason": None,
            "nonrenewalreason": "LD", "declinereason": None,
            "noticedate": None,
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
        # POL-0014: cancellation, reason K (location of risk) — valid alone
        {
            "id": 7014, "policy_id": 2014, "subtype": "Cancellation",
            "status": "Bound", "cancellationreason": "K",
            "nonrenewalreason": None, "declinereason": None,
            "noticedate": _ts(2026, 1, 18),
            "effectivedate": _ts(2026, 2, 18),
            "cancellationdate": _ts(2026, 2, 18),
            "within60days": False,
        },
        # POL-0015: nonrenewal, reason L+M (credit + roof condition) — valid
        {
            "id": 7015, "policy_id": 2015, "subtype": "Renewal",
            "status": "NonRenewed", "cancellationreason": None,
            "nonrenewalreason": "LM", "declinereason": None,
            "noticedate": _ts(2026, 2, 5),
            "effectivedate": _ts(2026, 3, 5),
            "cancellationdate": None,
            "within60days": False,
        },
        # POL-0016: declination, reason L+J — INVALID (J must be alone)
        {
            "id": 7016, "policy_id": 2016, "subtype": "Submission",
            "status": "Declined", "cancellationreason": None,
            "nonrenewalreason": None, "declinereason": "LJ",
            "noticedate": _ts(2026, 2, 22),
            "effectivedate": _ts(2026, 2, 22),
            "cancellationdate": None,
            "within60days": False,
        },
        # POL-0017: nonrenewal, reason L+K (credit + location) — valid
        {
            "id": 7017, "policy_id": 2017, "subtype": "Renewal",
            "status": "NonRenewed", "cancellationreason": None,
            "nonrenewalreason": "LK", "declinereason": None,
            "noticedate": _ts(2026, 3, 2),
            "effectivedate": _ts(2026, 4, 2),
            "cancellationdate": None,
            "within60days": False,
        },
        # POL-0018: cancellation, reason D+G (claims + wind/hail) — valid combo
        {
            "id": 7018, "policy_id": 2018, "subtype": "Cancellation",
            "status": "Bound", "cancellationreason": "DG",
            "nonrenewalreason": None, "declinereason": None,
            "noticedate": _ts(2026, 1, 28),
            "effectivedate": _ts(2026, 2, 28),
            "cancellationdate": _ts(2026, 2, 28),
            "within60days": False,
        },
        # POL-0019: declination, reason I+O — INVALID (codes not in plan)
        {
            "id": 7019, "policy_id": 2019, "subtype": "Submission",
            "status": "Declined", "cancellationreason": None,
            "nonrenewalreason": None, "declinereason": "IO",
            "noticedate": _ts(2026, 3, 7),
            "effectivedate": _ts(2026, 3, 7),
            "cancellationdate": None,
            "within60days": False,
        },

        # ─── RES filing (residential monthly · POL-0030..0034) ───
        # POL-0030: cancellation, reason A — pass
        {
            "id": 7030, "policy_id": 2030, "subtype": "Cancellation",
            "status": "Bound", "cancellationreason": "A",
            "nonrenewalreason": None, "declinereason": None,
            "noticedate": _ts(2026, 2, 12),
            "effectivedate": _ts(2026, 3, 12),
            "cancellationdate": _ts(2026, 3, 12),
            "within60days": False,
        },
        # POL-0031: nonrenewal, reason M (roof condition) — pass
        {
            "id": 7031, "policy_id": 2031, "subtype": "Renewal",
            "status": "NonRenewed", "cancellationreason": None,
            "nonrenewalreason": "M", "declinereason": None,
            "noticedate": _ts(2026, 2, 28),
            "effectivedate": _ts(2026, 3, 28),
            "cancellationdate": None,
            "within60days": False,
        },
        # POL-0032: declination, reason L alone — FAILS A.34 L-companion
        {
            "id": 7032, "policy_id": 2032, "subtype": "Submission",
            "status": "Declined", "cancellationreason": None,
            "nonrenewalreason": None, "declinereason": "L",
            "noticedate": _ts(2026, 3, 4),
            "effectivedate": _ts(2026, 3, 4),
            "cancellationdate": None,
            "within60days": False,
        },
        # POL-0033: nonrenewal, reason LD — pass (L has D companion)
        {
            "id": 7033, "policy_id": 2033, "subtype": "Renewal",
            "status": "NonRenewed", "cancellationreason": None,
            "nonrenewalreason": "LD", "declinereason": None,
            "noticedate": _ts(2026, 3, 6),
            "effectivedate": _ts(2026, 4, 6),
            "cancellationdate": None,
            "within60days": False,
        },
        # POL-0034: in-force, no cancellation — passive
        # (no job row; policy is just active during reporting period)

        # ─── CL filing (commercial lines quarterly · POL-0050..0053) ───
        # POL-0050: cancellation, reason A (failure to pay) — pass
        {
            "id": 7050, "policy_id": 2050, "subtype": "Cancellation",
            "status": "Bound", "cancellationreason": "A",
            "nonrenewalreason": None, "declinereason": None,
            "noticedate": _ts(2026, 1, 22),
            "effectivedate": _ts(2026, 2, 22),
            "cancellationdate": _ts(2026, 2, 22),
            "within60days": False,
        },
        # POL-0051: cancellation, reason DG (claims + wind/hail) — pass
        {
            "id": 7051, "policy_id": 2051, "subtype": "Cancellation",
            "status": "Bound", "cancellationreason": "DG",
            "nonrenewalreason": None, "declinereason": None,
            "noticedate": _ts(2026, 2, 8),
            "effectivedate": _ts(2026, 3, 8),
            "cancellationdate": _ts(2026, 3, 8),
            "within60days": False,
        },
        # POL-0052: cancellation, reason H (concentration of risk) — passes A.34
        # but policyperiod has bad NAIC '9876' → fails A.22
        {
            "id": 7052, "policy_id": 2052, "subtype": "Cancellation",
            "status": "Bound", "cancellationreason": "H",
            "nonrenewalreason": None, "declinereason": None,
            "noticedate": _ts(2026, 1, 30),
            "effectivedate": _ts(2026, 2, 28),
            "cancellationdate": _ts(2026, 2, 28),
            "within60days": False,
        },
        # POL-0053: in-force, no cancellation — passive
    ]

    # ── Append bulk-synthetic jobs (sampled per filing's reason-code distribution) ──
    _bulk_rng = _rng_module.Random(BULK_RANDOM_SEED + 1)
    for pid in POLICY_DETAILS:
        # Skip curated ids — they've already been handled above
        if pid < 2100:
            continue
        plan_code = POLICY_FILING.get(pid)
        if plan_code is None:
            continue
        bulk_jobs = _bulk_jobs_for(pid, plan_code, _bulk_rng)
        if bulk_jobs:
            rows.extend(bulk_jobs)

    n = len(rows)
    return pa.table({
        "gwcbi___operation": ["INSERT"] * n,
        "gwcdac___timestampfolder": [CDC_TIMESTAMP_FOLDER] * n,
        "gwcdac___fingerprintfolder": [CDC_FINGERPRINT_FOLDER] * n,
        "gwcbi___seqval_hex": [_hex_seq(i) for i in range(1, n + 1)],
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
        # Most jobs report "Insurer"; a few have noticesource missing so rule
        # F.0 (reason-source-indicator-required) has something to fire on.
        "noticesource": [(None if r["policy_id"] in (2010, 2012) else "Insurer") for r in rows],
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
    # Build cities/counties from the bulk ZIP pool (covers all bulk + curated ZIPs)
    cities = {z[0]: z[1] for z in _TX_ZIP_POOL}
    counties = {z[0]: z[2] for z in _TX_ZIP_POOL}
    # Curated ZIPs not in the bulk pool — fill from explicit mapping
    cities.update({
        "78701": "Austin",   "75001": "Addison",      "76001": "Arlington",
        "77001": "Houston",  "75201": "Dallas",
        "75070": "McKinney", "78415": "Corpus Christi","76301": "Wichita Falls",
        "79101": "Amarillo", "78216": "San Antonio",  "76710": "Waco",
        "75205": "Dallas",   "78704": "Austin",       "77024": "Houston",
        "76012": "Arlington","78712": "Austin",
    })
    counties.update({
        "78701": "Travis",   "75001": "Dallas",       "76001": "Tarrant",
        "77001": "Harris",   "75201": "Dallas",
        "75070": "Collin",   "78415": "Nueces",       "76301": "Wichita",
        "79101": "Potter",   "78216": "Bexar",        "76710": "McLennan",
        "75205": "Dallas",   "78704": "Travis",       "77024": "Harris",
        "76012": "Tarrant",  "78712": "Travis",
    })
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
        "gwcbi___operation": ["INSERT"] * n,
        "gwcdac___timestampfolder": [CDC_TIMESTAMP_FOLDER] * n,
        "gwcdac___fingerprintfolder": [CDC_FINGERPRINT_FOLDER] * n,
        "gwcbi___seqval_hex": [_hex_seq(i) for i in range(1, n + 1)],
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
        "gwcbi___operation": ["INSERT"] * n,
        "gwcdac___timestampfolder": [CDC_TIMESTAMP_FOLDER] * n,
        "gwcdac___fingerprintfolder": [CDC_FINGERPRINT_FOLDER] * n,
        "gwcbi___seqval_hex": [_hex_seq(i) for i in range(1, n + 1)],
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
        "gwcbi___operation": ["INSERT"] * n,
        "gwcdac___timestampfolder": [CDC_TIMESTAMP_FOLDER] * n,
        "gwcdac___fingerprintfolder": [CDC_FINGERPRINT_FOLDER] * n,
        "gwcbi___seqval_hex": [_hex_seq(i) for i in range(1, n + 1)],
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
        "gwcbi___operation": ["INSERT"] * n,
        "gwcdac___timestampfolder": [CDC_TIMESTAMP_FOLDER] * n,
        "gwcdac___fingerprintfolder": [CDC_FINGERPRINT_FOLDER] * n,
        "gwcbi___seqval_hex": [_hex_seq(i) for i in range(1, n + 1)],
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
        # POL-0014 ZIP intentionally non-TX (out-of-state 90210) so rule B.18 fires.
        "zip": [('90210' if p == 2014 else POLICY_DETAILS[p]["zip"]) for p in policy_ids],
        "ziplus4": ["1234"] * n,
        "state": ["TX"] * n,
        "constructiontype": [POLICY_DETAILS[p]["construction"] for p in policy_ids],
        "yearbuilt": [POLICY_DETAILS[p]["year_built"] for p in policy_ids],
        # Deliberate B.6 violation: POL-0007 dwelling has 5 families (out of 1-4 HO range).
        # Deliberate B.18 violation: POL-0014 dwelling overridden to a non-TX ZIP below.
        "numberoffamilies": [(5 if p == 2007 else 1) for p in policy_ids],
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
        "gwcbi___operation": ["INSERT"] * n,
        "gwcdac___timestampfolder": [CDC_TIMESTAMP_FOLDER] * n,
        "gwcdac___fingerprintfolder": [CDC_FINGERPRINT_FOLDER] * n,
        "gwcbi___seqval_hex": [_hex_seq(i) for i in range(1, n + 1)],
        "_ingestion_timestamp": [INGEST_TS] * n,
        "_source_file": ["bc_policyperiodpremium/2026-03-31.parquet"] * n,
        "id": [9300 + i for i in range(n)],
        "publicid": [f"bcpp:{9300+i}" for i in range(n)],
        "policyperiod_id": [3000 + pid for pid in POLICY_DETAILS],
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

# Append bulk synthetic claims so all the cc_* table generators auto-extend.
# Each bulk claim mirrors the curated dict shape so no downstream code changes.
CLAIMS.extend(_bulk_synth_claims())


def cc_claim() -> pa.Table:
    n = len(CLAIMS)
    return pa.table({
        "gwcbi___operation": ["INSERT"] * n,
        "gwcdac___timestampfolder": [CDC_TIMESTAMP_FOLDER] * n,
        "gwcdac___fingerprintfolder": [CDC_FINGERPRINT_FOLDER] * n,
        "gwcbi___seqval_hex": [_hex_seq(i) for i in range(1, n + 1)],
        "_ingestion_timestamp": [INGEST_TS] * n,
        "_source_file": ["cc_claim/2026-03-31.parquet"] * n,
        "_partition_month": ["2026-03"] * n,
        "id": [c["id"] for c in CLAIMS],
        "publicid": [c["publicid"] for c in CLAIMS],
        "claimnumber": [c["claimnumber"] for c in CLAIMS],
        "policy_id": [c["policy_id"] for c in CLAIMS],
        "policynumber": [c["policy_number"] for c in CLAIMS],
        # Policy period id uses our 3000+pid scheme; falls back to 5001 for legacy curated rows
        "policyperiod_id": [
            (5001 if c["policy_id"] == 2001 else 5010) if c["policy_id"] in (2001, 2010)
            else 3000 + c["policy_id"]
            for c in CLAIMS
        ],
        "uwcompany_id": [1001] * n,
        "naic_number": [NAIC] * n,
        "lossdate": [c["lossdate"] for c in CLAIMS],
        "losslocation_id": [70000 + i for i in range(n)],
        "reporteddate": [c["reporteddate"] for c in CLAIMS],
        "losscause": [c["losscause"] for c in CLAIMS],
        # CLM-001 / CLM-002 deliberately miss their subtype so rule D.13
        # (Wind/Hail attribution required) has demo violations to fire on.
        "losscausesubtype": [(None if c["claimnumber"] in ("CLM-001", "CLM-002") else c["subtype"]) for c in CLAIMS],
        "lobtypecode": ["HO"] * n,
        "coveragecategory": ["Dwelling"] * n,
        "state": ["TX"] * n,
        "closedate": [None] * n,
        "reopendate": [_ts(2026, 1, 5) if c["claimnumber"] == "CLM-009" else None for c in CLAIMS],
        "hasindemnity": [c["indemnity_paid"] > 0 for c in CLAIMS],
        "totalincurred": [c["indemnity_paid"] + c["lae_paid"] + c["indemnity_reserve"] for c in CLAIMS],
        "subrogationamount": [c["subrogation"] for c in CLAIMS],
        "salvageamount": [c["salvage"] for c in CLAIMS],
        # Most claims explicitly False; bulk-flagged D.12 demo claims get NULL
        "isintwiazone": [None if c.get("needs_cat_zone_null") else False for c in CLAIMS],
        "createtime": [c["reporteddate"] for c in CLAIMS],
        "updatetime": [_ts(2026, 3, 31)] * n,
        "retiredvalue": [0] * n,
    })


def cc_exposure() -> pa.Table:
    n = len(CLAIMS)
    return pa.table({
        "gwcbi___operation": ["INSERT"] * n,
        "gwcdac___timestampfolder": [CDC_TIMESTAMP_FOLDER] * n,
        "gwcdac___fingerprintfolder": [CDC_FINGERPRINT_FOLDER] * n,
        "gwcbi___seqval_hex": [_hex_seq(i) for i in range(1, n + 1)],
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
        "gwcbi___operation": ["INSERT"] * n,
        "gwcdac___timestampfolder": [CDC_TIMESTAMP_FOLDER] * n,
        "gwcdac___fingerprintfolder": [CDC_FINGERPRINT_FOLDER] * n,
        "gwcbi___seqval_hex": [_hex_seq(i) for i in range(1, n + 1)],
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
        "gwcbi___operation": ["INSERT"] * n,
        "gwcdac___timestampfolder": [CDC_TIMESTAMP_FOLDER] * n,
        "gwcdac___fingerprintfolder": [CDC_FINGERPRINT_FOLDER] * n,
        "gwcbi___seqval_hex": [_hex_seq(i) for i in range(1, n + 1)],
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
        "gwcbi___operation": ["INSERT"] * n,
        "gwcdac___timestampfolder": [CDC_TIMESTAMP_FOLDER] * n,
        "gwcdac___fingerprintfolder": [CDC_FINGERPRINT_FOLDER] * n,
        "gwcbi___seqval_hex": [_hex_seq(i) for i in range(1, n + 1)],
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
