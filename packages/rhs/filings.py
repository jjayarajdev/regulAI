"""Shared filing registry.

The same record is consumed by:
  - api/rhs_demo.py   — request-time scoping for /validate, /bronze, /audit etc.
  - scripts/run_gold.py — stamps GOLD.*.filing_batch_id during the run

P2.4 — the canonical registry moved to KG (FilingObligation nodes).
The list below is a fallback used only when:
  - KG is unreachable (boot-time / smoke tests)
  - `make seed-filing-obligations` hasn't run yet

Use `load_filings()` to get the live list, with KG-preferred + Python-fallback
semantics. Both shapes are kept identical so downstream code is unchanged.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


# Fallback / bootstrap registry. Kept for offline tooling (run_gold, etc.)
# and as a safety net if KG is unreachable.
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


# ── P2.4: KG-backed registry ──────────────────────────────────────────────

def _from_kg() -> list[dict]:
    """Read FilingObligation nodes from KG. Returns same shape as FILINGS list.

    Raises any underlying connection error; callers should fall back to the
    Python list when KG is unreachable.
    """
    # Lazy import — keeps this module importable in environments without Neo4j
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    out: list[dict] = []
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        rows = list(s.run(
            """
            MATCH (fo:FilingObligation)
            OPTIONAL MATCH (fo)-[:RECEIVES_SUBMISSION]->(a:StatisticalAgent)
            OPTIONAL MATCH (fo)-[:APPLIES_IN]->(j:Jurisdiction)
            RETURN fo.obligation_code AS id,
                   fo.plan_name AS plan_name,
                   fo.plan_code AS plan_code,
                   fo.cadence AS cadence,
                   fo.period_start AS period_start,
                   fo.period_end AS period_end,
                   fo.due_date AS due_date,
                   fo.is_active AS is_active,
                   fo.policy_id_ranges_json AS ranges_json,
                   coalesce(a.submission_channel, 'TICO ShareFile') AS channel,
                   coalesce(j.jurisdiction_code, 'US-TX') AS jurisdiction_code
            ORDER BY fo.due_date
            """
        ))
    for r in rows:
        try:
            ranges = json.loads(r["ranges_json"]) if r["ranges_json"] else []
            # JSON gives lists; the rest of the code uses tuples.
            ranges = [tuple(rg) for rg in ranges]
        except (json.JSONDecodeError, TypeError):
            ranges = []
        out.append({
            "id":              r["id"],
            "plan_name":       r["plan_name"],
            "plan_code":       r["plan_code"],
            "policy_id_ranges": ranges,
            "cadence":         r["cadence"],
            "period_start":    str(r["period_start"]) if r["period_start"] else None,
            "period_end":      str(r["period_end"]) if r["period_end"] else None,
            "due_date":        str(r["due_date"]) if r["due_date"] else None,
            "channel":         r["channel"],
            "is_active":       bool(r["is_active"]),
            "jurisdiction_code": r["jurisdiction_code"],
        })
    return out


def load_filings() -> list[dict]:
    """Get the live filings list.

    Prefers KG (FilingObligation nodes). Falls back to the in-file FILINGS
    list when KG is unreachable or empty (e.g. fresh seed). Same shape as
    the legacy list so callers don't need to branch.
    """
    try:
        kg = _from_kg()
        if kg:
            return kg
        logger.info("filings.load_filings: KG has no FilingObligation nodes — using Python fallback")
    except Exception as e:
        logger.warning("filings.load_filings: KG unreachable (%s) — using Python fallback", e)
    return FILINGS
