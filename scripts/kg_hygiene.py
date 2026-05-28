"""KG hygiene migration — Phase 1.5.

Two cleanups that operate independently and idempotently:

1. NULL-type nodes — nodes carrying the right native label (:Rule, :CodeValue,
   etc.) but no `type` property. Caused by raw Cypher writes that didn't set
   the property. We derive `type` from labels(n) excluding 'GRENode'.

2. Citation propagation — CodeValues with no direct CITES edge inherit the
   parent CodeList's first CITES citation, recorded as a new CITES edge with
   `propagated_from='parent_codelist'`.

Both operations are idempotent — re-running is safe. Run via:
    uv run python -m scripts.kg_hygiene
"""

from __future__ import annotations

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
from packages.core.enums import KGAuditAction


def fix_null_type_nodes() -> tuple[int, list[str]]:
    """Set `type` property from native label for any node where type is null.

    Returns (count_fixed, list_of_node_ids).
    """
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        # Find nodes with null type but valid native label
        rows = list(s.run("""
            MATCH (n:GRENode)
            WHERE n.type IS NULL
            RETURN n.id AS id, [l IN labels(n) WHERE l <> 'GRENode'] AS native_labels
        """))
        fixed_ids = []
        for r in rows:
            native = r["native_labels"]
            if not native:
                # Truly unlabeled GRENode — can't auto-fix
                continue
            # Use first non-supertype label as the type
            type_value = native[0]
            s.run("""
                MATCH (n:GRENode {id: $id})
                SET n.type = $type
            """, id=r["id"], type=type_value)
            fixed_ids.append(r["id"])
        return len(fixed_ids), fixed_ids


def propagate_codelist_citations() -> tuple[int, int]:
    """For each CodeValue with no CITES edge, copy the parent CodeList's
    first CITES citation onto the CodeValue.

    Records the propagation source so future audits can distinguish direct
    vs inherited citations. Returns (codevalues_updated, edges_added).
    """
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        # Find CodeValues without direct citations but with a parent that has one
        rows = list(s.run("""
            MATCH (cv:CodeValue)
            WHERE NOT (cv)-[:CITES]->()
            MATCH (cv)<-[:HAS_VALUE]-(cl:CodeList)-[:CITES]->(c)
            WITH cv, head(collect(c)) AS citation, head(collect(cl.id)) AS parent_cl_id
            RETURN cv.id AS cv_id, citation.id AS citation_id, parent_cl_id
        """))
        edges_added = 0
        cvs_updated = set()
        for r in rows:
            cv_id = r["cv_id"]
            cit_id = r["citation_id"]
            parent_id = r["parent_cl_id"]
            if cv_id in cvs_updated:
                continue  # one citation per cv
            # Add the propagated CITES edge with provenance marker
            s.run("""
                MATCH (cv:CodeValue {id: $cv_id}), (c:GRENode {id: $cit_id})
                MERGE (cv)-[r:CITES]->(c)
                ON CREATE SET
                  r.id = randomUUID(),
                  r.propagated_from = 'parent_codelist',
                  r.parent_codelist_id = $parent_id,
                  r.char_start = 0,
                  r.char_end = 0,
                  r.created_at = datetime()
            """, cv_id=cv_id, cit_id=cit_id, parent_id=parent_id)
            edges_added += 1
            cvs_updated.add(cv_id)
        return len(cvs_updated), edges_added


def main() -> int:
    print("KG hygiene migration\n")

    print("Step 1: Fix NULL-type nodes")
    n_null, ids = fix_null_type_nodes()
    if n_null:
        print(f"  ✓ Set `type` on {n_null} node(s) using their native label")
        for i in ids[:5]:
            print(f"    · {i}")
        if n_null > 5:
            print(f"    · ...and {n_null - 5} more")
    else:
        print("  ✓ No NULL-type nodes found")
    print()

    print("Step 2: Propagate CodeList citations to orphan CodeValues")
    n_cvs, n_edges = propagate_codelist_citations()
    if n_cvs:
        print(f"  ✓ Added {n_edges} propagated CITES edges to {n_cvs} CodeValue(s)")
    else:
        print("  ✓ No CodeValues needed propagation (already covered or no parent citation)")
    print()

    # Record the hygiene run in the KG audit log
    try:
        with Neo4jGREAdapter() as gre:
            gre.record_audit_entry(
                action=KGAuditAction.BACKFILL,
                summary=(
                    f"KG hygiene: set type on {n_null} NULL-type nodes; "
                    f"propagated CodeList citations to {n_cvs} CodeValues "
                    f"({n_edges} edges added)"
                ),
                actor="kg_hygiene_script",
            )
        print("  ✓ Audit entry recorded")
    except Exception as e:
        print(f"  ⚠  audit write failed (non-fatal): {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
