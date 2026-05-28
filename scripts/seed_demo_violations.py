"""Inject demo-ready Bronze data violations into TPA + CL filings.

By default the synthetic data lands clean in TPA and CL — only RES has
violations because that's where the noise was originally injected. So
the /workstation Kanban looks empty if a demo viewer lands on TPA or
CL first. This script seeds a small set of intentionally-dirty rows
in TPA and CL policy-ID ranges so every filing has visible variety.

Per filing we plant:
  - 2 NAIC mismatches  → Rule A.22 (ERROR — Blocks submission)
  - 1 premium out-of-range → Rule A.30 (ERROR)
  - 1 weird policy term → Rule A.40 (WARNING — Needs review)
  - 1 late loss report → Rule B.14 (WARNING)

Result: every filing's Kanban shows 4-5 tickets across both severity
columns. Demo viewer can click any filing and see violations.

Idempotent — re-runs restore the same dirty values. To clean up:
  make seed-bronze   # regenerates synthetic data from scratch

Run: uv run python -m scripts.seed_demo_violations
"""

from __future__ import annotations

from packages.rhs.snowflake_client import query


# Filing-scoped corruption recipes. Each entry: (filing_id, policy_id_range, recipe)
# Recipes list which rules to violate; pick distinct policy_ids per filing
# so the same row doesn't trip multiple rules (cleaner Kanban presentation).
DEMO_PLAN: list[dict] = [
    {
        "filing": "TPA-Q4-2025",
        "pp_range": (2001, 2019),  # 12 rows available
        "naic_offenders": [2001, 2002],            # → Rule A.22
        "premium_offenders": [(2003, 0)],          # → Rule A.30 (0 < $100)
        "termtype_offenders": [(2004, "Bimonthly")],  # → Rule A.40
        "claim_late_offenders": [(2005, 95)],       # → Rule B.14 (95 days late report)
    },
    {
        "filing": "CL-Q4-2025",
        "pp_range": (2050, 2053),  # only 4 rows — use carefully
        "naic_offenders": [2050],                  # → Rule A.22
        "premium_offenders": [(2051, 99999)],      # → Rule A.30 (above $50k)
        "termtype_offenders": [(2052, "Weekly")],  # → Rule A.40
        "claim_late_offenders": [],
    },
    {
        "filing": "RES-M03-2026",
        "pp_range": (2030, 2034),  # plus 2300..2399, but using narrow window
        "naic_offenders": [2030, 2031],            # → Rule A.22 ×2
        "premium_offenders": [(2032, 50)],         # → Rule A.30 (below $100)
        "termtype_offenders": [(2033, "Quarterly")],  # → Rule A.40
        "claim_late_offenders": [(2034, 120)],     # → Rule B.14 (120 days late)
    },
]


def _update_naic(policy_id: int) -> bool:
    """Corrupt naic_number to a 3-char alphanumeric → fails Rule A.22."""
    r = query(
        f"""UPDATE INSURANCE_REGULATORY.BRONZE.GW_PC_POLICYPERIOD
            SET naic_number = 'ABX'
            WHERE policy_id = {policy_id}"""
    )
    return bool(r)


def _update_premium(policy_id: int, premium: int) -> bool:
    r = query(
        f"""UPDATE INSURANCE_REGULATORY.BRONZE.GW_PC_POLICYPERIOD
            SET writtenpremium = {premium}
            WHERE policy_id = {policy_id}"""
    )
    return bool(r)


def _update_termtype(policy_id: int, termtype: str) -> bool:
    r = query(
        f"""UPDATE INSURANCE_REGULATORY.BRONZE.GW_PC_POLICYPERIOD
            SET termtype = '{termtype}'
            WHERE policy_id = {policy_id}"""
    )
    return bool(r)


def _update_claim_late(policy_id: int, days_late: int) -> bool:
    """Push reporteddate to (lossdate + days_late) so the claim is reported
    `days_late` days after loss — fails Rule B.14 when > 90."""
    r = query(
        f"""UPDATE INSURANCE_REGULATORY.BRONZE.GW_CC_CLAIM
            SET reporteddate = DATEADD(day, {days_late}, lossdate)
            WHERE policyperiod_id IN (
                SELECT id FROM INSURANCE_REGULATORY.BRONZE.GW_PC_POLICYPERIOD
                WHERE policy_id = {policy_id}
            )"""
    )
    return bool(r)


def main() -> int:
    print("Seeding demo violations into TPA + CL filings...\n")
    total = 0
    for plan in DEMO_PLAN:
        print(f"  ── {plan['filing']} (policy_id {plan['pp_range'][0]}..{plan['pp_range'][1]}) ──")
        for pid in plan["naic_offenders"]:
            _update_naic(pid); print(f"    A.22 ERROR    naic_number='ABX' on policy {pid}"); total += 1
        for pid, prem in plan["premium_offenders"]:
            _update_premium(pid, prem); print(f"    A.30 ERROR    writtenpremium={prem} on policy {pid}"); total += 1
        for pid, tt in plan["termtype_offenders"]:
            _update_termtype(pid, tt); print(f"    A.40 WARNING  termtype='{tt}' on policy {pid}"); total += 1
        for pid, days in plan["claim_late_offenders"]:
            _update_claim_late(pid, days); print(f"    B.14 WARNING  claim reported {days}d after loss on policy {pid}"); total += 1
        print()

    print(f"✓ {total} violations seeded across {len(DEMO_PLAN)} filings.")
    print("Open /workstation in the UI; pick TPA-Q4-2025 or CL-Q4-2025 — the Kanban")
    print("should now show tickets in both 'Blocks submission' and 'Needs review' columns.")
    print()
    print("To restore clean data: re-run synthetic generation (`make seed-bronze`).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
