"""P2.4 — seed FilingObligation nodes from the legacy Python registry.

One-time migration: copy the existing FILINGS list from
`packages/rhs/filings.py` into KG nodes, link them via OBLIGATES (to a
synthetic 'Lone Star Mutual' Insurer) + RECEIVES_SUBMISSION (to the TICO
StatisticalAgent). After this runs, `/api/rhs/filings` reads from KG and
the Python list becomes a bootstrap-only fallback.

Idempotent: MERGE on obligation_code. Re-running yields zero changes
unless someone edits the source list.
"""

from __future__ import annotations

import datetime as dt
import json

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
from packages.core.enums import KGAuditAction
from packages.rhs.filings import FILINGS


# Synthetic carrier — the only carrier in the v1 demo. Future multi-tenant
# will replace this with a real Organization (per customer).
CARRIER_ID = "org:lone-star-mutual"
CARRIER_NAME = "Lone Star Mutual"

# Statistical agents that receive submissions. TICO is created by
# seed_jurisdictions; FHCF (Florida Hurricane Catastrophe Fund) is created
# here so the FL obligation always has a receiving agent.
FHCF_AGENT = {
    "id": "agent:FHCF",
    "code": "FHCF",
    "name": "FL Hurricane Catastrophe Fund",
    "submission_channel": "FHCF Email Submission",
    "jurisdiction_code": "US-FL",
}


def seed() -> dict:
    summary = {
        "carriers_created": 0,
        "obligations_created": 0,
        "obligations_updated": 0,
        "obligates_edges": 0,
        "receives_edges": 0,
        "agents_created": 0,
    }
    now_iso = dt.datetime.now(dt.UTC).isoformat()

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        # ── 1. Carrier Organization (synthetic) ─────────────────────────────
        r = s.run(
            """
            MERGE (o:GRENode:Organization {id: $id})
            ON CREATE SET
                o.type = 'Organization',
                o.name = $name,
                o.org_name = $name,
                o.org_kind = 'Insurer',
                o.jurisdiction_code = 'US-TX',
                o.version = 1,
                o.status = 'approved',
                o.created_at = $now,
                o.created_by = 'seed_filing_obligations'
            WITH o
            MATCH (j:Jurisdiction {jurisdiction_code: 'US-TX'})
            MERGE (o)-[:APPLIES_IN]->(j)
            RETURN CASE WHEN o.created_at = $now THEN 1 ELSE 0 END AS is_new
            """,
            id=CARRIER_ID, name=CARRIER_NAME, now=now_iso,
        ).single()
        if r and r["is_new"]:
            summary["carriers_created"] += 1

        # ── 1b. FHCF StatisticalAgent (idempotent; TICO comes from
        #        seed_jurisdictions) ─────────────────────────────────────────
        r = s.run(
            """
            MERGE (n:GRENode:StatisticalAgent {id: $id})
            ON CREATE SET
                n.type = 'StatisticalAgent',
                n.name = $name,
                n.agent_code = $code,
                n.agent_name = $name,
                n.submission_channel = $chan,
                n.jurisdiction_code = $jur,
                n.version = 1,
                n.status = 'approved',
                n.created_at = $now,
                n.created_by = 'seed_filing_obligations'
            WITH n
            OPTIONAL MATCH (j:Jurisdiction {jurisdiction_code: $jur})
            FOREACH (_ IN CASE WHEN j IS NULL THEN [] ELSE [1] END |
                MERGE (n)-[:APPLIES_IN]->(j))
            RETURN CASE WHEN n.created_at = $now THEN 1 ELSE 0 END AS is_new
            """,
            id=FHCF_AGENT["id"], code=FHCF_AGENT["code"], name=FHCF_AGENT["name"],
            chan=FHCF_AGENT["submission_channel"], jur=FHCF_AGENT["jurisdiction_code"],
            now=now_iso,
        ).single()
        if r and r["is_new"]:
            summary["agents_created"] += 1

        # ── 2. FilingObligation nodes ───────────────────────────────────────
        for f in FILINGS:
            obligation_id = f"fo:{f['id']}"
            ranges_json = json.dumps(f["policy_id_ranges"])
            jurisdiction = f.get("jurisdiction_code") or "US-TX"
            agent_code = "FHCF" if f.get("plan_code") == "FHCF" else "TICO"
            r = s.run(
                """
                MERGE (fo:GRENode:FilingObligation {id: $id})
                ON CREATE SET
                    fo.type = 'FilingObligation',
                    fo.name = $code,
                    fo.obligation_code = $code,
                    fo.plan_code = $plan_code,
                    fo.plan_name = $plan_name,
                    fo.cadence = $cadence,
                    fo.period_start = date($period_start),
                    fo.period_end = date($period_end),
                    fo.due_date = date($due_date),
                    fo.policy_id_ranges_json = $ranges,
                    fo.is_active = $is_active,
                    fo.jurisdiction_code = $jurisdiction,
                    fo.version = 1,
                    fo.status = 'approved',
                    fo.created_at = $now,
                    fo.created_by = 'seed_filing_obligations',
                    fo._just_created = true
                RETURN CASE WHEN coalesce(fo._just_created, false) THEN 1 ELSE 0 END AS is_new
                """,
                id=obligation_id,
                code=f["id"],
                plan_code=f["plan_code"],
                plan_name=f["plan_name"],
                cadence=f["cadence"],
                period_start=f["period_start"],
                period_end=f["period_end"],
                due_date=f["due_date"],
                ranges=ranges_json,
                is_active=f["is_active"],
                jurisdiction=jurisdiction,
                now=now_iso,
            ).single()
            if r and r["is_new"]:
                summary["obligations_created"] += 1
                # Clean up the temp marker so re-runs are accurate
                s.run("MATCH (fo {id: $id}) REMOVE fo._just_created", id=obligation_id)

            # OBLIGATES → carrier
            e = s.run(
                """
                MATCH (fo:FilingObligation {id: $fo_id}), (o:Organization {id: $org_id})
                WHERE NOT (fo)-[:OBLIGATES]->(o)
                MERGE (fo)-[:OBLIGATES]->(o)
                RETURN count(*) AS n
                """,
                fo_id=obligation_id, org_id=CARRIER_ID,
            ).single()
            summary["obligates_edges"] += (e["n"] if e else 0)

            # RECEIVES_SUBMISSION → the plan's StatisticalAgent (TICO or FHCF)
            e = s.run(
                """
                MATCH (fo:FilingObligation {id: $fo_id}), (a:StatisticalAgent {agent_code: $agent_code})
                WHERE NOT (fo)-[:RECEIVES_SUBMISSION]->(a)
                MERGE (fo)-[:RECEIVES_SUBMISSION]->(a)
                RETURN count(*) AS n
                """,
                fo_id=obligation_id, agent_code=agent_code,
            ).single()
            summary["receives_edges"] += (e["n"] if e else 0)

            # APPLIES_IN → the filing's Jurisdiction node
            s.run(
                """
                MATCH (fo:FilingObligation {id: $fo_id}), (j:Jurisdiction {jurisdiction_code: $jurisdiction})
                WHERE NOT (fo)-[:APPLIES_IN]->(j)
                MERGE (fo)-[:APPLIES_IN]->(j)
                """,
                fo_id=obligation_id, jurisdiction=jurisdiction,
            )

    # Audit
    try:
        with Neo4jGREAdapter() as gre:
            gre.record_audit_entry(
                action=KGAuditAction.BACKFILL,
                summary=(
                    f"P2.4 seed: {summary['carriers_created']} carrier, "
                    f"{summary['obligations_created']} obligations created, "
                    f"{summary['obligates_edges']} OBLIGATES + {summary['receives_edges']} RECEIVES_SUBMISSION edges"
                ),
                actor="seed_filing_obligations",
            )
    except Exception as e:
        print(f"  ⚠  audit write failed (non-fatal): {e}")

    return summary


def main() -> int:
    print("P2.4 — seeding FilingObligation nodes from packages/rhs/filings.py\n")
    summary = seed()
    print(f"  ✓ Carrier Organization created:      {summary['carriers_created']}")
    print(f"  ✓ StatisticalAgents created (FHCF):  {summary['agents_created']}")
    print(f"  ✓ FilingObligations created:         {summary['obligations_created']}")
    print(f"  ✓ OBLIGATES edges (FO → carrier):    {summary['obligates_edges']}")
    print(f"  ✓ RECEIVES_SUBMISSION edges (→ agent): {summary['receives_edges']}")
    print()
    print("Re-run is idempotent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
