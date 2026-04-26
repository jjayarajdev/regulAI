"""Strip parser-owned node types from a Sentinel extraction.

For documents the deterministic parser owns (Stat Plan §C/D/E/G, the TICO
Homeowners record-layout PDF), Sentinel's view of the same document tends
to produce phantom variant `RecordLayout`s and orphan `FieldRequirement`s
whose names diverge from the parser's. Even with perfect prompting the
LLM has no incentive to match the parser's exact naming.

The defensive fix: after Sentinel returns, drop any node whose type is
parser-owned, plus any proposed relationship or citation that referenced
those temp_ids. Sentinel keeps the rules, citations, and prose-derived
nodes; the parser owns the tabular schema.
"""

from __future__ import annotations

from packages.core.enums import NodeType
from packages.lhs.sentinel.schema import SentinelExtraction

PARSER_OWNED_TYPES: set[NodeType] = {
    NodeType.RECORD_LAYOUT,
    NodeType.FIELD_REQUIREMENT,
    NodeType.CODE_LIST,
    NodeType.CODE_VALUE,
}


def strip_parser_owned(extraction: SentinelExtraction) -> tuple[SentinelExtraction, dict]:
    """Return (filtered_extraction, stats) with parser-owned types removed.

    Stats counts what was dropped, for the caller to log.
    """
    drop_temp_ids = {
        n.temp_id for n in extraction.proposed_nodes
        if n.type in PARSER_OWNED_TYPES
    }

    new_nodes = [n for n in extraction.proposed_nodes if n.temp_id not in drop_temp_ids]
    new_rels = [
        r for r in extraction.proposed_relationships
        if r.src_temp_id not in drop_temp_ids and r.dst_temp_id not in drop_temp_ids
    ]
    new_cites = [c for c in extraction.citations if c.node_temp_id not in drop_temp_ids]

    stats = {
        "dropped_nodes": len(extraction.proposed_nodes) - len(new_nodes),
        "dropped_relationships": len(extraction.proposed_relationships) - len(new_rels),
        "dropped_citations": len(extraction.citations) - len(new_cites),
        "by_type": {
            t.value: sum(
                1 for n in extraction.proposed_nodes
                if n.type == t and n.temp_id in drop_temp_ids
            )
            for t in PARSER_OWNED_TYPES
        },
    }

    filtered = extraction.model_copy(update={
        "proposed_nodes": new_nodes,
        "proposed_relationships": new_rels,
        "citations": new_cites,
    })
    return filtered, stats
