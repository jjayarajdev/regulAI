"""P3.2 — Materialize a FL extraction into the KG with jurisdiction_code='US-FL'.

The base materialize() pipeline writes nodes with the GRENodeBase default
of jurisdiction_code='US-TX'. This wrapper:

  1. Ensures the US-FL Jurisdiction + FL-OIR Regulator exist
  2. Snapshots the set of existing node ids BEFORE materialization
  3. Runs the existing materialize() pipeline
  4. Re-tags any newly-created node with jurisdiction_code='US-FL'
  5. Re-points its APPLIES_IN edge from US-TX → US-FL
  6. Records the operation in the KG audit log

Idempotent at the document level — re-running with the same extraction
yields zero new nodes/edges (dedup happens in materialize()).

Usage:
    uv run python -m scripts.materialize_florida_extraction <extraction.json>
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from uuid import UUID

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
from packages.config.settings import settings
from packages.core.enums import KGAuditAction
from packages.lhs.materialization.materialize import materialize
from packages.lhs.sentinel.schema import SentinelExtraction


FL_JUR_ID = "jur:US-FL"
FL_REG_ID = "reg:FL-OIR"


def _ensure_fl_jurisdiction(gre: Neo4jGREAdapter) -> None:
    """Create the US-FL Jurisdiction + FL-OIR Regulator nodes if absent."""
    now_iso = dt.datetime.now(dt.UTC).isoformat()
    with gre.driver.session(database=gre.database) as s:
        s.run(
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
                j.created_by = 'materialize_florida_extraction'
            """,
            jid=FL_JUR_ID, now=now_iso,
        )
        s.run(
            """
            MERGE (r:GRENode:Regulator {id: $rid})
            ON CREATE SET
                r.type = 'Regulator',
                r.name = 'FL OIR',
                r.regulator_code = 'FL-OIR',
                r.regulator_name = 'Florida Office of Insurance Regulation',
                r.contact_endpoint = 'https://www.floir.com',
                r.jurisdiction_code = 'US-FL',
                r.version = 1,
                r.status = 'approved',
                r.created_at = $now,
                r.created_by = 'materialize_florida_extraction'
            WITH r
            MATCH (j:Jurisdiction {jurisdiction_code: 'US-FL'})
            MERGE (r)-[:APPLIES_IN]->(j)
            """,
            rid=FL_REG_ID, now=now_iso,
        )


def _existing_node_ids(gre: Neo4jGREAdapter) -> set[str]:
    """Snapshot of all GRENode ids in the KG (for diffing post-materialize)."""
    with gre.driver.session(database=gre.database) as s:
        return {r["id"] for r in s.run("MATCH (n:GRENode) RETURN n.id AS id")}


def _retag_new_nodes_to_fl(gre: Neo4jGREAdapter, new_ids: set[str]) -> dict:
    """For each newly-created node: set jurisdiction_code='US-FL', re-point
    APPLIES_IN to the FL Jurisdiction (removing the US-TX edge from materialize's
    default tagging via seed_jurisdictions chain)."""
    if not new_ids:
        return {"retagged": 0, "edges_rewired": 0}

    with gre.driver.session(database=gre.database) as s:
        retagged = s.run(
            """
            MATCH (n:GRENode)
            WHERE n.id IN $ids
              AND NOT 'Jurisdiction' IN labels(n)
              AND NOT 'Regulator' IN labels(n)
              AND NOT 'KGAuditEntry' IN labels(n)
            SET n.jurisdiction_code = 'US-FL'
            RETURN count(n) AS n
            """,
            ids=list(new_ids),
        ).single()["n"]

        # If seed_jurisdictions auto-tagged these to US-TX between creation
        # and now, remove that edge and add the US-FL edge.
        edges_rewired = s.run(
            """
            MATCH (n:GRENode)
            WHERE n.id IN $ids
              AND NOT 'Jurisdiction' IN labels(n)
              AND NOT 'KGAuditEntry' IN labels(n)
            OPTIONAL MATCH (n)-[old:APPLIES_IN]->(tx:Jurisdiction {jurisdiction_code: 'US-TX'})
            DELETE old
            WITH n
            MATCH (fl:Jurisdiction {jurisdiction_code: 'US-FL'})
            MERGE (n)-[:APPLIES_IN]->(fl)
            RETURN count(n) AS n
            """,
            ids=list(new_ids),
        ).single()["n"]

    return {"retagged": retagged, "edges_rewired": edges_rewired}


def main(extraction_path_str: str) -> int:
    ext_path = Path(extraction_path_str)
    if not ext_path.exists():
        print(f"✗ Extraction file not found: {ext_path}")
        return 1

    print(f"P3.2 — Materializing Florida extraction: {ext_path}")
    print()

    data = json.loads(ext_path.read_text(encoding="utf-8"))
    extraction = SentinelExtraction.model_validate(data)
    print(f"  Loaded extraction: {len(extraction.proposed_nodes)} nodes, "
          f"{len(extraction.proposed_relationships)} relationships, "
          f"{len(extraction.citations)} citations")

    with Neo4jGREAdapter() as gre:
        # Step 1 — ensure FL scaffolding exists
        _ensure_fl_jurisdiction(gre)
        print(f"  ✓ FL Jurisdiction + FL-OIR Regulator confirmed")

        # Step 2 — snapshot existing node ids
        before = _existing_node_ids(gre)
        print(f"  ✓ Pre-materialize KG size: {len(before)} nodes")

        # Step 3 — run the standard materialize pipeline
        result = materialize(
            extraction,
            gre,
            document_label=ext_path.stem,
            snapshot_dir=Path("materialized/approved"),
        )
        print(f"  ✓ materialize() complete:")
        print(f"      nodes created  : {len(result.nodes_created)}")
        print(f"      nodes reused   : {len(result.nodes_reused)}")
        print(f"      relationships  : {result.relationships_created}")
        print(f"      citations      : {result.citations_created}")
        for s in result.skipped_proposals[:5]:
            print(f"      ✗ skipped {s.type}: {s.name[:60]} ({s.reason[:80]})")

        # Step 4 — re-tag newly created nodes as FL
        after = _existing_node_ids(gre)
        new_ids = after - before
        retag = _retag_new_nodes_to_fl(gre, new_ids)
        print(f"  ✓ FL retagging:")
        print(f"      jurisdiction_code → US-FL: {retag['retagged']} nodes")
        print(f"      APPLIES_IN → US-FL:        {retag['edges_rewired']} edges")

        # Step 5 — audit entry
        try:
            uuid_ids = []
            for i in list(new_ids)[:50]:  # cap to avoid massive audit edge sets
                try:
                    uuid_ids.append(UUID(i))
                except Exception:
                    pass
            gre.record_audit_entry(
                action=KGAuditAction.EXTRACTION,
                summary=(
                    f"P3.1/P3.2 Florida intake: materialized {ext_path.name} → "
                    f"{len(result.nodes_created)} new + {len(result.nodes_reused)} reused, "
                    f"retagged {retag['retagged']} nodes to US-FL"
                ),
                actor="materialize_florida_extraction",
                affected_node_ids=uuid_ids,
                details_json=json.dumps({
                    "document": ext_path.name,
                    "nodes_created": len(result.nodes_created),
                    "nodes_reused": len(result.nodes_reused),
                    "relationships": result.relationships_created,
                    "citations": result.citations_created,
                    "jurisdiction": "US-FL",
                }),
            )
            print(f"  ✓ KG audit entry recorded")
        except Exception as e:
            print(f"  ⚠  audit write failed (non-fatal): {e}")

    print()
    print(f"FL canon now in KG. Verify via:")
    print(f"  cypher-shell> MATCH (n:GRENode)-[:APPLIES_IN]->(:Jurisdiction {{jurisdiction_code: 'US-FL'}}) RETURN labels(n)[1] AS type, count(*) AS n ORDER BY n DESC")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python -m scripts.materialize_florida_extraction <extraction.json>")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
