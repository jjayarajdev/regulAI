"""Idempotent restoration of the FL canon scope after rebuild-kg.

The `rebuild-kg` flow replays every cached extraction via the standard
materialize() path, which creates nodes with the GRENodeBase default
of jurisdiction_code='US-TX'. This script:

  1. Ensures Jurisdiction(US-FL) + Regulator(FL-OIR) exist
  2. Looks up every FL node by the names recorded in the cached extraction
  3. Sets jurisdiction_code='US-FL' on each
  4. Re-points its APPLIES_IN edge from US-TX → US-FL

Idempotent — re-running yields the same end state. Belongs in the
conftest re-seed chain after rebuild-kg + seed-jurisdictions so the
demo state survives `make test`.

Usage:
    uv run python -m scripts.seed_florida
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
from packages.core.enums import KGAuditAction


FL_EXTRACTIONS_GLOB = "materialized/extractions/FL_*.extraction.json"
FL_JUR_ID = "jur:US-FL"
FL_REG_ID = "reg:FL-OIR"


def _ensure_fl_scaffolding(gre: Neo4jGREAdapter) -> dict:
    """Create Jurisdiction(US-FL) + Regulator(FL-OIR). Returns counts."""
    now_iso = dt.datetime.now(dt.UTC).isoformat()
    created = {"jurisdiction": 0, "regulator": 0}
    with gre.driver.session(database=gre.database) as s:
        r = s.run(
            """
            MERGE (j:GRENode:Jurisdiction {id: $jid})
            ON CREATE SET
                j.type = 'Jurisdiction',
                j.name = 'Florida',
                j.jurisdiction_code = 'US-FL',
                j.jurisdiction_name = 'Florida',
                j.jurisdiction_type = 'state',
                j.parent_jurisdiction_code = 'US',
                j.version = 1,
                j.status = 'approved',
                j.created_at = $now,
                j.created_by = 'seed_florida',
                j._just_created = true
            RETURN coalesce(j._just_created, false) AS is_new
            """,
            jid=FL_JUR_ID, now=now_iso,
        ).single()
        if r and r["is_new"]:
            created["jurisdiction"] += 1
        s.run("MATCH (j:Jurisdiction {id: $jid}) REMOVE j._just_created", jid=FL_JUR_ID)

        r = s.run(
            """
            MERGE (rg:GRENode:Regulator {id: $rid})
            ON CREATE SET
                rg.type = 'Regulator',
                rg.name = 'FL OIR',
                rg.regulator_code = 'FL-OIR',
                rg.regulator_name = 'Florida Office of Insurance Regulation',
                rg.contact_endpoint = 'https://www.floir.com',
                rg.jurisdiction_code = 'US-FL',
                rg.version = 1,
                rg.status = 'approved',
                rg.created_at = $now,
                rg.created_by = 'seed_florida',
                rg._just_created = true
            WITH rg
            MATCH (j:Jurisdiction {jurisdiction_code: 'US-FL'})
            MERGE (rg)-[:APPLIES_IN]->(j)
            RETURN coalesce(rg._just_created, false) AS is_new
            """,
            rid=FL_REG_ID, now=now_iso,
        ).single()
        if r and r["is_new"]:
            created["regulator"] += 1
        s.run("MATCH (rg:Regulator {id: $rid}) REMOVE rg._just_created", rid=FL_REG_ID)
    return created


def _fl_node_signatures() -> list[tuple[str, str]]:
    """Read every FL_*.extraction.json; return union of [(type, name)]."""
    import glob
    paths = sorted(Path(p) for p in glob.glob(FL_EXTRACTIONS_GLOB))
    sigs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for p in paths:
        data = json.loads(p.read_text(encoding="utf-8"))
        for n in data.get("proposed_nodes", []):
            t = n.get("type")
            nm = n.get("name")
            if not (t and nm):
                continue
            if isinstance(t, dict):
                t = t.get("value") or list(t.values())[0]
            key = (t, nm)
            if key not in seen:
                sigs.append(key)
                seen.add(key)
    return sigs


def _retag_fl_nodes(gre: Neo4jGREAdapter, signatures: list[tuple[str, str]]) -> dict:
    """For every (type, name) in the FL extraction, set jurisdiction_code='US-FL'
    and re-point APPLIES_IN to the FL Jurisdiction."""
    summary = {"matched": 0, "retagged": 0, "edges_rewired": 0}
    if not signatures:
        return summary

    with gre.driver.session(database=gre.database) as s:
        # Use UNWIND to match each signature pair
        r = s.run(
            """
            UNWIND $sigs AS sig
            MATCH (n:GRENode {name: sig[1]})
            WHERE sig[0] IN labels(n)
              AND NOT 'Jurisdiction' IN labels(n)
              AND NOT 'KGAuditEntry' IN labels(n)
            SET n.jurisdiction_code = 'US-FL'
            WITH n
            OPTIONAL MATCH (n)-[old:APPLIES_IN]->(tx:Jurisdiction {jurisdiction_code: 'US-TX'})
            DELETE old
            WITH n
            MATCH (fl:Jurisdiction {jurisdiction_code: 'US-FL'})
            MERGE (n)-[:APPLIES_IN]->(fl)
            RETURN count(DISTINCT n) AS n
            """,
            sigs=[[t, nm] for t, nm in signatures],
        ).single()
        summary["matched"] = summary["retagged"] = summary["edges_rewired"] = r["n"] if r else 0
    return summary


def main() -> int:
    print("Seeding Florida scope (restores P3 state after rebuild-kg)\n")

    with Neo4jGREAdapter() as gre:
        scaffold = _ensure_fl_scaffolding(gre)
        print(f"  ✓ Jurisdiction created/confirmed: +{scaffold['jurisdiction']}")
        print(f"  ✓ Regulator created/confirmed:    +{scaffold['regulator']}")

        sigs = _fl_node_signatures()
        if not sigs:
            print(f"  ⚠  No FL extractions found at {FL_EXTRACTIONS_GLOB}")
            print(f"     Run extract + materialize for an FL document first.")
            return 0
        print(f"  · FL extractions loaded: {len(sigs)} unique node signatures")

        retag = _retag_fl_nodes(gre, sigs)
        print(f"  ✓ Nodes retagged to US-FL: {retag['retagged']}/{len(sigs)}")

        # Audit
        try:
            gre.record_audit_entry(
                action=KGAuditAction.BACKFILL,
                summary=(
                    f"P3 seed_florida: ensured FL scaffolding (+{scaffold['jurisdiction']} jur, "
                    f"+{scaffold['regulator']} reg), retagged {retag['retagged']} extraction nodes to US-FL"
                ),
                actor="seed_florida",
            )
        except Exception:
            pass

    print()
    print("FL canon restored.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
