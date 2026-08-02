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


def backfill_rule_confidence() -> tuple[int, int]:
    """Copy Sentinel extraction confidences onto Rule nodes that lack one.

    Sources materialized/extractions/*.extraction.json (the cached proposals
    that were approved into the canon), matched by exact rule name. Rules with
    no cached proposal (seeds, manual edits) stay confidence-less. Idempotent:
    only touches rules where confidence IS NULL.
    Returns (rules_updated, rules_still_missing).
    """
    import json
    from pathlib import Path

    conf_by_name: dict[str, float] = {}
    for p in sorted(Path("materialized/extractions").glob("*.extraction.json")):
        try:
            d = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for n in d.get("proposed_nodes", []):
            if n.get("type") == "Rule" and n.get("confidence") is not None:
                conf_by_name.setdefault(n["name"], float(n["confidence"]))

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        rows = list(s.run(
            "MATCH (r:Rule) WHERE r.confidence IS NULL RETURN r.id AS id, r.name AS name"
        ))
        updated = 0
        for r in rows:
            c = conf_by_name.get(r["name"])
            if c is None:
                continue
            s.run("MATCH (r:Rule {id: $id}) SET r.confidence = $c", id=r["id"], c=c)
            updated += 1
        return updated, len(rows) - updated


def backfill_rule_cites() -> tuple[int, int]:
    """Link every CITES-less rule to its source document.

    Two cases:
      - r.document_id resolves to a RegulationDocument → MERGE the CITES edge.
      - r.document_id is a phantom (doc never materialized): if any rule in the
        same phantom group references Insurance Code §551 / HB 2067, re-point
        the whole group at the loaded H.B. No. 2067 document.
    Idempotent. Returns (edges_created, rules_repointed).
    """
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        hb = s.run(
            "MATCH (d:RegulationDocument) WHERE d.name STARTS WITH 'H.B. No. 2067' "
            "RETURN d.id AS id LIMIT 1"
        ).single()
        hb_id = hb["id"] if hb else None

        rows = list(s.run(
            "MATCH (r:Rule) WHERE NOT (r)-[:CITES]->() "
            "RETURN r.id AS id, r.name AS name, r.document_id AS doc"
        ))
        # Group by claimed document so phantom groups get one decision.
        by_doc: dict[str, list] = {}
        for r in rows:
            if r["doc"]:
                by_doc.setdefault(r["doc"], []).append(r)

        linked = repointed = 0
        for doc_id, group in by_doc.items():
            exists = s.run(
                "MATCH (d:RegulationDocument {id: $d}) RETURN d.id AS id", d=doc_id
            ).single()
            target = exists["id"] if exists else None
            if target is None and hb_id and any(
                "§551" in (g["name"] or "") or "Insurance Code" in (g["name"] or "")
                for g in group
            ):
                target = hb_id
            if target is None:
                continue
            for g in group:
                s.run(
                    "MATCH (r:Rule {id: $rid}), (d:RegulationDocument {id: $did}) "
                    "MERGE (r)-[:CITES]->(d) SET r.document_id = $did",
                    rid=g["id"], did=target,
                )
                linked += 1
                if target != doc_id:
                    repointed += 1
        return linked, repointed


def link_supersedes() -> int:
    """Materialize rule version chains as (new)-[:SUPERSEDES]->(old).

    Pairs a superseded rule with its successor by matching section +
    rule_number (the stable statute anchor). OVERRIDES stays what it is —
    a bulletin overlaying a rule — SUPERSEDES is version lineage.
    Idempotent via MERGE. Returns edges present after the run.
    """
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        row = s.run("""
            MATCH (old:Rule {status:'superseded'}), (new:Rule)
            WHERE new.section = old.section AND new.rule_number = old.rule_number
              AND new.id <> old.id AND new.status <> 'superseded'
            MERGE (new)-[e:SUPERSEDES]->(old)
            RETURN count(e) AS n
        """).single()
        return row["n"] if row else 0


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

    print("Step 3: Backfill Sentinel confidence onto Rule nodes")
    n_conf, n_missing = backfill_rule_confidence()
    print(f"  ✓ Set confidence on {n_conf} rule(s); {n_missing} have no cached proposal")
    print()

    print("Step 4: Backfill CITES edges for citation-less rules")
    n_cites, n_repointed = backfill_rule_cites()
    print(f"  ✓ Linked {n_cites} rule(s) to their document ({n_repointed} re-pointed off a phantom doc id)")
    print()

    print("Step 5: Materialize SUPERSEDES version chains")
    n_sup = link_supersedes()
    print(f"  ✓ {n_sup} SUPERSEDES edge(s) in place")
    print()

    # Record the hygiene run in the KG audit log
    try:
        with Neo4jGREAdapter() as gre:
            gre.record_audit_entry(
                action=KGAuditAction.BACKFILL,
                summary=(
                    f"KG hygiene: set type on {n_null} NULL-type nodes; "
                    f"propagated CodeList citations to {n_cvs} CodeValues "
                    f"({n_edges} edges added); confidence backfilled on "
                    f"{n_conf} rules; {n_cites} CITES edges backfilled "
                    f"({n_repointed} re-pointed); {n_sup} SUPERSEDES edges"
                ),
                actor="kg_hygiene_script",
            )
        print("  ✓ Audit entry recorded")
    except Exception as e:
        print(f"  ⚠  audit write failed (non-fatal): {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
