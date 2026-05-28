"""Phase 2 schema migration — seed jurisdictions + backfill existing nodes.

Idempotent. Run once after Phase 2 schema lands:
    uv run python -m scripts.seed_jurisdictions

What it does:

  1. Creates the canonical Jurisdiction nodes (US federal default + US-TX
     for our current canon). Future states (US-FL, US-CA, ...) get added
     when their canon is ingested.

  2. Creates the Regulator + StatisticalAgent for Texas (TDI, TICO).

  3. Backfills `jurisdiction_code = 'US-TX'` onto every existing pre-Phase-2
     node that lacks it. New nodes set the property at creation time via
     the Pydantic default.

  4. Adds APPLIES_IN edges from every existing Rule, CodeList, CodeValue,
     and RecordLayout to the US-TX Jurisdiction (P2.2 will tag a small
     subset as federal defaults and re-point them to US instead).

  5. Records the migration in the KG audit log.
"""

from __future__ import annotations

import datetime as dt

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
from packages.core.enums import KGAuditAction


# Canonical seed for Phase 2. New states append to this list.
JURISDICTIONS = [
    {
        "id": "jur:US",
        "code": "US",
        "name": "United States (federal default)",
        "kind": "federal",
        "parent": None,
    },
    {
        "id": "jur:US-TX",
        "code": "US-TX",
        "name": "Texas",
        "kind": "state",
        "parent": "US",
    },
]

REGULATORS = [
    {
        "id": "reg:TDI",
        "code": "TDI",
        "name": "Texas Department of Insurance",
        "jurisdiction_code": "US-TX",
        "contact_endpoint": "https://www.tdi.texas.gov",
    },
]

AGENTS = [
    {
        "id": "agent:TICO",
        "code": "TICO",
        "name": "Texas Insurance Checking Office",
        "jurisdiction_code": "US-TX",
        "submission_channel": "ShareFile",
    },
]


def seed() -> dict:
    now_iso = dt.datetime.now(dt.UTC).isoformat()
    summary = {
        "jurisdictions_created": 0,
        "regulators_created": 0,
        "agents_created": 0,
        "nodes_backfilled": 0,
        "applies_in_edges": 0,
    }

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        # ── Step 1: Jurisdiction nodes ─────────────────────────────────────
        for j in JURISDICTIONS:
            r = s.run(
                """
                MERGE (n:GRENode:Jurisdiction {id: $id})
                ON CREATE SET
                    n.type = 'Jurisdiction',
                    n.name = $name,
                    n.jurisdiction_code = $code,
                    n.jurisdiction_name = $name,
                    n.jurisdiction_type = $kind,
                    n.parent_jurisdiction_code = $parent,
                    n.version = 1,
                    n.status = 'approved',
                    n.created_at = $now,
                    n.created_by = 'seed_jurisdictions'
                RETURN CASE WHEN n.created_at = $now THEN 1 ELSE 0 END AS is_new
                """,
                id=j["id"], code=j["code"], name=j["name"], kind=j["kind"],
                parent=j["parent"], now=now_iso,
            ).single()
            if r and r["is_new"]:
                summary["jurisdictions_created"] += 1

        # ── Step 2: Regulator nodes ────────────────────────────────────────
        for reg in REGULATORS:
            r = s.run(
                """
                MERGE (n:GRENode:Regulator {id: $id})
                ON CREATE SET
                    n.type = 'Regulator',
                    n.name = $name,
                    n.regulator_code = $code,
                    n.regulator_name = $name,
                    n.contact_endpoint = $endpoint,
                    n.jurisdiction_code = $jur,
                    n.version = 1,
                    n.status = 'approved',
                    n.created_at = $now,
                    n.created_by = 'seed_jurisdictions'
                WITH n
                MATCH (j:Jurisdiction {jurisdiction_code: $jur})
                MERGE (n)-[:APPLIES_IN]->(j)
                RETURN CASE WHEN n.created_at = $now THEN 1 ELSE 0 END AS is_new
                """,
                id=reg["id"], code=reg["code"], name=reg["name"],
                endpoint=reg["contact_endpoint"], jur=reg["jurisdiction_code"],
                now=now_iso,
            ).single()
            if r and r["is_new"]:
                summary["regulators_created"] += 1

        # ── Step 3: StatisticalAgent nodes ─────────────────────────────────
        for ag in AGENTS:
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
                    n.created_by = 'seed_jurisdictions'
                WITH n
                MATCH (j:Jurisdiction {jurisdiction_code: $jur})
                MERGE (n)-[:APPLIES_IN]->(j)
                RETURN CASE WHEN n.created_at = $now THEN 1 ELSE 0 END AS is_new
                """,
                id=ag["id"], code=ag["code"], name=ag["name"],
                chan=ag["submission_channel"], jur=ag["jurisdiction_code"],
                now=now_iso,
            ).single()
            if r and r["is_new"]:
                summary["agents_created"] += 1

        # ── Step 4: backfill jurisdiction_code on every existing node ─────
        r = s.run(
            """
            MATCH (n:GRENode)
            WHERE n.jurisdiction_code IS NULL
              AND NOT 'Jurisdiction' IN labels(n)
              AND NOT 'KGAuditEntry' IN labels(n)
            SET n.jurisdiction_code = 'US-TX'
            RETURN count(n) AS n
            """
        ).single()
        summary["nodes_backfilled"] = r["n"] if r else 0

        # ── Step 5: APPLIES_IN edges from every jurisdiction-scoped node ──
        # Skip nodes that are themselves jurisdictions or audit entries
        r = s.run(
            """
            MATCH (n:GRENode), (j:Jurisdiction {jurisdiction_code: 'US-TX'})
            WHERE NOT 'Jurisdiction' IN labels(n)
              AND NOT 'KGAuditEntry' IN labels(n)
              AND NOT (n)-[:APPLIES_IN]->(:Jurisdiction)
            MERGE (n)-[:APPLIES_IN]->(j)
            RETURN count(*) AS n
            """
        ).single()
        summary["applies_in_edges"] = r["n"] if r else 0

    # ── Step 6: Audit-log the migration ────────────────────────────────────
    try:
        with Neo4jGREAdapter() as gre:
            gre.record_audit_entry(
                action=KGAuditAction.BACKFILL,
                summary=(
                    f"P2.1 seed: created {summary['jurisdictions_created']} jurisdictions, "
                    f"{summary['regulators_created']} regulators, "
                    f"{summary['agents_created']} agents; backfilled "
                    f"{summary['nodes_backfilled']} nodes with jurisdiction_code='US-TX'; "
                    f"added {summary['applies_in_edges']} APPLIES_IN edges to US-TX"
                ),
                actor="seed_jurisdictions",
            )
    except Exception as e:
        print(f"  ⚠  audit write failed (non-fatal): {e}")

    return summary


def main() -> int:
    print("P2.1 Schema migration — seeding jurisdictions + backfilling existing canon\n")
    summary = seed()
    print(f"  ✓ Jurisdiction nodes created:      {summary['jurisdictions_created']}")
    print(f"  ✓ Regulator nodes created:         {summary['regulators_created']}")
    print(f"  ✓ StatisticalAgent nodes created:  {summary['agents_created']}")
    print(f"  ✓ Existing nodes backfilled:       {summary['nodes_backfilled']}")
    print(f"  ✓ APPLIES_IN edges added:          {summary['applies_in_edges']}")
    print()
    print("Re-run is idempotent — re-running yields zero new nodes/edges.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
