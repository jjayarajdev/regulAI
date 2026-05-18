"""Shared filing registry.

The same record is consumed by:
  - api/rhs_demo.py   — request-time scoping for /validate, /bronze, /audit etc.
  - scripts/run_gold.py — stamps GOLD.*.filing_batch_id during the run

Keep the registry here so both stay in sync. Each entry has multiple
policy_id ranges so curated demo cases (e.g. POL-0011 for the L-companion
storytelling) and bulk synthetic data (POL-2100+) can both belong to the
same filing.
"""

from __future__ import annotations


FILINGS: list[dict] = [
    {
        "id":           "TPA-Q4-2025",
        "plan_name":    "Texas Private Passenger Auto / Homeowners",
        "plan_code":    "TPA",
        # Curated: 2001-2019 (named storytelling cases · POL-0011 L-alone, etc.)
        # Bulk:    2100-2299 (200 distribution-driven synthetic policies)
        "policy_id_ranges": [(2001, 2019), (2100, 2299)],
        "cadence":      "Quarterly",
        "period_start": "2025-10-01",
        "period_end":   "2025-12-31",
        "due_date":     "2026-03-31",
        "channel":      "TICO ShareFile",
        "is_active":    True,
    },
    {
        "id":           "RES-M03-2026",
        "plan_name":    "Residential Property — March 2026",
        "plan_code":    "RES",
        # Curated: 2030-2034.  Bulk: 2300-2399 (100 synthetic residential policies)
        "policy_id_ranges": [(2030, 2034), (2300, 2399)],
        "cadence":      "Monthly",
        "period_start": "2026-03-01",
        "period_end":   "2026-03-31",
        "due_date":     "2026-04-15",
        "channel":      "TICO ShareFile",
        "is_active":    True,
    },
    {
        "id":           "CL-Q4-2025",
        "plan_name":    "Commercial Lines",
        "plan_code":    "CL",
        # Curated: 2050-2053.  Bulk: 2400-2449 (50 synthetic commercial policies)
        "policy_id_ranges": [(2050, 2053), (2400, 2449)],
        "cadence":      "Quarterly",
        "period_start": "2025-10-01",
        "period_end":   "2025-12-31",
        "due_date":     "2026-05-15",
        "channel":      "TICO ShareFile",
        "is_active":    True,
    },
]


def filing_ranges(filing_id: str) -> list[tuple[int, int]]:
    for f in FILINGS:
        if f["id"] == filing_id:
            return list(f["policy_id_ranges"])
    return []


def policy_id_to_filing_case(column: str = "j.policy_id") -> str:
    """SQL CASE expression: maps a Bronze policy_id column to its filing_batch_id.

    Used at Silver→Gold time to stamp filing_batch_id on every record.
    Falls through to NULL for policies outside any known filing.
    """
    branches = []
    for f in FILINGS:
        conds = " OR ".join(f"{column} BETWEEN {lo} AND {hi}" for lo, hi in f["policy_id_ranges"])
        branches.append(f"WHEN {conds} THEN '{f['id']}'")
    return "CASE " + " ".join(branches) + " ELSE NULL END"


def policy_number_to_filing_case(column: str = "s.POLICY_ID") -> str:
    """SQL CASE expression: maps a policy_number column (POL-XXXX) to filing_batch_id.

    Convention from the bronze generator: pid → f'POL-{(pid-2000):04d}'.
    """
    branches = []
    for f in FILINGS:
        pns = []
        for lo, hi in f["policy_id_ranges"]:
            pns.extend(f"'POL-{(pid - 2000):04d}'" for pid in range(lo, hi + 1))
        in_list = ",".join(pns)
        branches.append(f"WHEN {column} IN ({in_list}) THEN '{f['id']}'")
    return "CASE " + " ".join(branches) + " ELSE NULL END"
