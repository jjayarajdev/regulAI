"""One-shot KG hygiene: drop phantom layouts and orphan field requirements.

A *phantom layout* is a RecordLayout node with no FieldRequirement
connected via CONTAINED_IN. Sentinel produced several of these by
mis-typing prose code-tables (Section B) and reason-code instructions
(Section F) as RecordLayouts. They're harmless but pollute query results
and the UI dropdowns.

An *orphan FieldRequirement* is one with no CONTAINED_IN edge to any
RecordLayout. Same provenance — Sentinel emits them when it can't tell
which layout a field belongs to.

After the deterministic parser runs, these are no longer needed and can
be dropped without losing real provenance: the parser-produced nodes
fully describe each wire format, with PDF citation rects.

Run: uv run python -m scripts.cleanup_kg [--dry-run]
"""

import sys

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

# The only RecordLayout names the system treats as canonical wire-format
# layouts. Anything else is an LLM-extraction artifact (a Sentinel run that
# named the same concept differently) and should be removed in cleanup.
CANONICAL_LAYOUTS = {
    "Premium Record Layout",
    "Loss Record Layout",
    "Notice Record Layout",
    "Notice Count Record Layout",
    "Homeowners Premium Record Layout",
    "Homeowners Loss Record Layout",
}


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    with Neo4jGREAdapter() as gre, gre.driver.session() as s:
        # Phantom RecordLayouts: any layout whose name isn't in the canonical
        # set is an LLM-extraction variant for a concept the parser already
        # owns (e.g. "Residential Property Fixed ASCII Standard Data Format
        # Layout" → Premium/Loss). Drop along with any FieldRequirements
        # exclusively attached to it.
        phantom_layouts = s.run(
            """
            MATCH (l:RecordLayout)
            WHERE NOT l.name IN $canonical
            RETURN l.name AS name, l.id AS id
            ORDER BY l.name
            """,
            canonical=list(CANONICAL_LAYOUTS),
        ).data()

        # Orphan FieldRequirements: not bound to ANY layout via either edge.
        orphans = s.run("""
            MATCH (f:FieldRequirement)
            WHERE NOT (f)-[:CONTAINED_IN]->(:RecordLayout)
              AND NOT (:RecordLayout)-[:REQUIRES]->(f)
            RETURN f.name AS name, f.position_start AS ps, f.id AS id
            ORDER BY coalesce(f.position_start, 9999), f.name
        """).data()

        # Truly unused CodeLists: no FieldRequirement uses them AND no
        # CodeValues are attached. A codelist with HAS_VALUE children is
        # content even if no field is wired up yet (e.g., seed-created
        # "Cause of Loss" pre-bulletin).
        orphan_codelists = s.run("""
            MATCH (cl:CodeList)
            WHERE NOT (cl)<-[:CODED_BY]-(:FieldRequirement)
              AND NOT (cl)-[:HAS_VALUE]->(:CodeValue)
              AND NOT (cl)<-[:OVERRIDES]-(:BulletinOverride)
            RETURN cl.name AS name, cl.id AS id
        """).data()

        # CodeValues with no CodeList parent.
        orphan_codevalues = s.run("""
            MATCH (cv:CodeValue)
            WHERE NOT (cv)<-[:HAS_VALUE]-(:CodeList)
            RETURN cv.name AS name, cv.id AS id
        """).data()

        print(f"Phantom RecordLayouts:      {len(phantom_layouts)}")
        for r in phantom_layouts[:8]:
            print(f"  - {r['name']}")
        if len(phantom_layouts) > 8:
            print(f"  … and {len(phantom_layouts) - 8} more")

        print(f"\nOrphan FieldRequirements:   {len(orphans)}")
        for r in orphans[:8]:
            ps = r["ps"] if r["ps"] is not None else "?"
            print(f"  - col {ps}  {r['name']}")
        if len(orphans) > 8:
            print(f"  … and {len(orphans) - 8} more")

        print(f"\nOrphan CodeLists:           {len(orphan_codelists)}")
        print(f"Orphan CodeValues:          {len(orphan_codevalues)}")

        total = (
            len(phantom_layouts) + len(orphans)
            + len(orphan_codelists) + len(orphan_codevalues)
        )
        if total == 0:
            print("\nNothing to clean.")
            return

        if dry_run:
            print(f"\n[dry-run] {total} nodes would be deleted. Re-run without --dry-run to apply.")
            return

        # DETACH DELETE removes incident relationships too. Same predicates
        # as the discovery queries above so we delete exactly what we listed.
        s.run(
            "MATCH (l:RecordLayout) WHERE NOT l.name IN $canonical DETACH DELETE l",
            canonical=list(CANONICAL_LAYOUTS),
        )
        s.run("""
            MATCH (f:FieldRequirement)
            WHERE NOT (f)-[:CONTAINED_IN]->(:RecordLayout)
              AND NOT (:RecordLayout)-[:REQUIRES]->(f)
            DETACH DELETE f
        """)
        s.run("""
            MATCH (cl:CodeList)
            WHERE NOT (cl)<-[:CODED_BY]-(:FieldRequirement)
              AND NOT (cl)-[:HAS_VALUE]->(:CodeValue)
              AND NOT (cl)<-[:OVERRIDES]-(:BulletinOverride)
            DETACH DELETE cl
        """)
        s.run("""
            MATCH (cv:CodeValue)
            WHERE NOT (cv)<-[:HAS_VALUE]-(:CodeList)
            DETACH DELETE cv
        """)

        print(f"\nDeleted {total} nodes. Re-run validate-kg to confirm.")


if __name__ == "__main__":
    main()
