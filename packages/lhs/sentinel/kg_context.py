"""Render the current KG state as a context block for Sentinel.

This is the RAG side of the rules-level loop. Before Sentinel reads a new
regulation document we pull a digest of what already exists in the KG —
RegulationDocuments, Rules, RecordLayouts, CodeLists — and inject it into
the user message. With this context the LLM can:

  1. Reference existing entities by their EXACT canonical names (so
     OVERRIDES / SUPERSEDES targets dedupe cleanly on materialization
     instead of creating phantom siblings).
  2. Avoid inventing variants of nodes that already exist.
  3. Express its diff as deltas against known content rather than a
     full self-contained extraction.

The retrieval is name/type based, not vector-based. At our scale (~1.5k
nodes) that's adequate; we can swap to embeddings later without changing
the prompt-augmentation pattern.
"""

from __future__ import annotations

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter


def render_kg_context(*, max_per_type: int = 25) -> str:
    """Return a Sentinel-ready summary of what's already in the KG.

    Caps lists at `max_per_type` to keep prompts compact. Falls back to a
    short note if the KG is empty (e.g. fresh `make migrate` with no seed).
    """
    with Neo4jGREAdapter() as gre, gre.driver.session() as s:
        docs = s.run("""
            MATCH (d:RegulationDocument)
            RETURN d.name AS name, d.kind AS kind
            ORDER BY d.kind, d.name LIMIT $cap
        """, cap=max_per_type).data()

        rules = s.run("""
            MATCH (r:Rule)
            WHERE r.name STARTS WITH "Rule "
            RETURN r.name AS name, r.section AS section
            ORDER BY r.section, r.name LIMIT $cap
        """, cap=max_per_type * 2).data()

        layouts = s.run("""
            MATCH (l:RecordLayout)
            OPTIONAL MATCH (l)<-[:CONTAINED_IN]-(f:FieldRequirement)
            RETURN l.name AS name, count(f) AS field_count
            ORDER BY l.name
        """).data()

        codelists = s.run("""
            MATCH (cl:CodeList)
            OPTIONAL MATCH (cl)-[:HAS_VALUE]->(cv:CodeValue)
            WITH cl, count(cv) AS n_values
            WHERE n_values > 0
            RETURN cl.name AS name, n_values AS values
            ORDER BY values DESC LIMIT $cap
        """, cap=max_per_type).data()

        bulletins = s.run("""
            MATCH (b:BulletinOverride)
            RETURN b.name AS name, b.effective_date AS effective_date
            ORDER BY b.effective_date DESC
        """).data()

    if not (docs or rules or layouts or codelists):
        return "EXISTING KG: empty. This is the first regulation being ingested."

    lines: list[str] = ["EXISTING KG STATE — refer to these by EXACT name where applicable:", ""]
    if docs:
        lines.append("RegulationDocuments:")
        for d in docs:
            lines.append(f"  ({d['kind']}) {d['name']}")
        lines.append("")
    if rules:
        lines.append("Rules (a sample — refer to these by exact name when overriding):")
        for r in rules[:max_per_type]:
            lines.append(f"  {r['name']}")
        if len(rules) > max_per_type:
            lines.append(f"  … and {len(rules) - max_per_type} more rules")
        lines.append("")
    if layouts:
        lines.append("RecordLayouts (canonical — do NOT create variant names):")
        for l in layouts:
            lines.append(f"  {l['name']}  ({l['field_count']} fields)")
        lines.append("")
    if codelists:
        lines.append("CodeLists (top by size):")
        for cl in codelists:
            lines.append(f"  {cl['name']}  ({cl['values']} values)")
        lines.append("")
    if bulletins:
        lines.append("Active BulletinOverrides:")
        for b in bulletins:
            lines.append(f"  {b['name']}  (effective {b['effective_date']})")
        lines.append("")
    lines.append(
        "Guidance: when your extraction targets one of the above (overrides "
        "a Rule, adds a FieldRequirement to a RecordLayout, supersedes a "
        "CodeValue, etc.), use the EXACT name shown so dedup merges your "
        "proposed node with the existing one."
    )
    return "\n".join(lines)
