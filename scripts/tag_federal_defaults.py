"""P2.2 — Tag federal-default rules.

Some rules in the TX stat plan are state-specific (ZIP first-digit-7,
reason codes, HB 2067 declination categories). Others are NAIC-level
standards that every state's stat plan re-states (NAIC company-number
format, claim count fields, negative-amount conventions). Tag the latter
as `is_federal_default=True` and re-point their APPLIES_IN edge to the
US Jurisdiction instead of US-TX.

When a second state lands (Phase 3), its canon ingestion can either:
  - Inherit the federal default (no action)
  - Override with a state-specific rule (set `supersedes_federal_rule_id`
    on the new state's rule, link it via SUPERSEDES)

This script is conservative — only ~8 rules and ~1 codelist. Refining
which rules are federal-default is a judgment call that grows as more
states' canon is ingested. The mechanism is what matters here.

Idempotent. Run via:
    uv run python -m scripts.tag_federal_defaults
"""

from __future__ import annotations

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
from packages.core.enums import KGAuditAction


# Federal-default rule numbers. Picked from the TX canon because the
# *concept* is national even if the citation is state-issued. State-specific
# overrides can be added by APPLIES_IN edges to other Jurisdictions.
FEDERAL_DEFAULT_RULES: list[dict[str, str]] = [
    {"rule_number": "22", "reason": "NAIC company-number format (5 digits) is national"},
    {"rule_number": "25", "reason": "NAIC Company Number — definitionally national"},
    {"rule_number": "12", "reason": "Negative-amount encoding is universal stat-plan convention"},
    {"rule_number": "13", "reason": "New Claim Count — NAIC statistical reporting standard"},
    {"rule_number": "14", "reason": "Paid Claim Count — NAIC standard"},
    {"rule_number": "15", "reason": "Reopened Claim Count — NAIC standard"},
    {"rule_number": "16", "reason": "Claim Status — NAIC standard"},
    {"rule_number": "27", "reason": "Claim Identifier — concept standard across states"},
    {"rule_number": "28", "reason": "Designated Statistical Agent — meta-rule every state requires"},
]

# CodeLists that are national in scope.
FEDERAL_DEFAULT_CODELISTS: list[dict[str, str]] = [
    {
        "name_contains": "Line of Business",
        "reason": "NAIC Line of Business codes are national",
    },
]


def tag_federal_defaults() -> dict:
    """Tag rules + codelists, re-point APPLIES_IN to US, record audit."""
    summary = {"rules_tagged": 0, "codelists_tagged": 0, "edges_rewired": 0}

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        # ── Rules ──
        affected_ids = []
        for entry in FEDERAL_DEFAULT_RULES:
            rule_num = entry["rule_number"]
            # Set the flag + jurisdiction_code on every Rule whose
            # rule_number matches (handle both "22" and "A.22" formats).
            r = s.run("""
                MATCH (r:Rule)
                WHERE r.rule_number = $num
                   OR r.rule_number = $alt
                   OR r.name CONTAINS $pat
                SET r.is_federal_default = true,
                    r.jurisdiction_code = 'US'
                RETURN collect(r.id) AS ids
            """, num=rule_num, alt=f"A.{rule_num}", pat=f"Rule A.{rule_num} ").single()
            if r and r["ids"]:
                summary["rules_tagged"] += len(r["ids"])
                affected_ids.extend(r["ids"])

        # ── CodeLists ──
        for entry in FEDERAL_DEFAULT_CODELISTS:
            pat = entry["name_contains"]
            r = s.run("""
                MATCH (cl:CodeList)
                WHERE cl.name CONTAINS $pat
                SET cl.is_federal_default = true,
                    cl.jurisdiction_code = 'US'
                RETURN collect(cl.id) AS ids
            """, pat=pat).single()
            if r and r["ids"]:
                summary["codelists_tagged"] += len(r["ids"])
                affected_ids.extend(r["ids"])

        # ── Re-point APPLIES_IN edges from US-TX to US for the tagged nodes ──
        r = s.run("""
            MATCH (n:GRENode)-[a:APPLIES_IN]->(:Jurisdiction {jurisdiction_code: 'US-TX'})
            WHERE n.is_federal_default = true
            MATCH (us:Jurisdiction {jurisdiction_code: 'US'})
            DELETE a
            WITH n, us
            MERGE (n)-[:APPLIES_IN]->(us)
            RETURN count(n) AS n
        """).single()
        summary["edges_rewired"] = r["n"] if r else 0

    # ── Audit ──
    try:
        with Neo4jGREAdapter() as gre:
            from uuid import UUID
            uuid_ids = []
            for i in affected_ids:
                try:
                    uuid_ids.append(UUID(i))
                except Exception:
                    pass  # legacy non-UUID ids — skip MUTATED_BY linkage
            gre.record_audit_entry(
                action=KGAuditAction.BACKFILL,
                summary=(
                    f"P2.2 federal-default tagging: marked {summary['rules_tagged']} rules + "
                    f"{summary['codelists_tagged']} codelists as is_federal_default=true, "
                    f"re-pointed {summary['edges_rewired']} APPLIES_IN edges from US-TX to US"
                ),
                actor="tag_federal_defaults",
                affected_node_ids=uuid_ids,
            )
    except Exception as e:
        print(f"  ⚠  audit write failed (non-fatal): {e}")

    return summary


def main() -> int:
    print("P2.2 — Tagging federal-default rules + codelists\n")
    summary = tag_federal_defaults()
    print(f"  ✓ Rules tagged is_federal_default=true:     {summary['rules_tagged']}")
    print(f"  ✓ CodeLists tagged is_federal_default=true: {summary['codelists_tagged']}")
    print(f"  ✓ APPLIES_IN edges re-pointed US-TX → US:    {summary['edges_rewired']}")
    print()
    print("Re-run is idempotent (SET + MERGE are no-ops if already in place).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
