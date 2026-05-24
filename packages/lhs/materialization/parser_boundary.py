"""Hard gate enforcing the parser/LLM boundary at materialize time.

Some documents are owned by the deterministic parser (the TICO Homeowners
record-layout PDF, Stat Plan §C/D/E/G). For these, the parser produces
the authoritative RecordLayout + FieldRequirement nodes. Sentinel's view
of the same document tends to hallucinate variant layouts and orphan
fields whose names don't match the parser's — that produced the
"138 orphan fields" incident in Phase 1.

Existing defenses before Cluster C:
  - scripts/batch_extract.py strips parser-owned types at extraction time
    using packages/lhs/sentinel/filter.py:strip_parser_owned()
  - scripts/rebuild_kg.py skips parser-owned slugs when replaying LLM
    extractions, letting parse_record_layout handle them instead

What was missing:
  - No protection in api/main.py's /approve endpoint — if a user reviews
    and approves a Sentinel extraction of a parser-owned doc through the
    UI, the boundary isn't checked
  - No protection inside materialize() itself; any direct caller (script,
    API, future code) could bypass the boundary silently
  - No CI test verifying the boundary holds

Cluster C adds:
  - A single canonical PARSER_OWNED_SLUGS constant (used by rebuild_kg,
    batch_extract, and materialize)
  - A check_parser_boundary() function that raises ParserBoundaryViolation
    when a parser-owned doc proposes parser-owned-type nodes
  - Invocation at the top of materialize() so every codepath is gated
  - A test that asserts the gate fires

Why raise instead of skip: this shouldn't happen in normal operation.
If it does, it means either Sentinel regressed against its prompt, the
batch_extract filter was bypassed, or someone hand-crafted an extraction
that violates the boundary. All of those are bugs that need investigation,
not silent recovery.
"""

from __future__ import annotations

from packages.core.enums import NodeType
from packages.lhs.sentinel.schema import SentinelExtraction


# Documents where the deterministic parser owns the wire-format schema.
# These slugs must NOT carry Sentinel-extracted RecordLayout or
# FieldRequirement proposals — the parser is the authoritative source.
#
# Single source of truth; rebuild_kg.py and batch_extract.py import from
# here. If you need to declare a new parser-owned doc, add it here.
PARSER_OWNED_SLUGS: frozenset[str] = frozenset({
    "tico-record-layout-homeowners",
    "tico-section-c",
    "tico-section-d",
    "tico-section-e",
    "tico-section-g",
})

# Node types only the parser may produce on parser-owned docs. Sentinel
# may still produce Rules / Documents / Citations on those docs (and we
# want it to — the rule prose lives in the same PDF as the wire layout).
PARSER_OWNED_TYPES: frozenset[NodeType] = frozenset({
    NodeType.RECORD_LAYOUT,
    NodeType.FIELD_REQUIREMENT,
})


class ParserBoundaryViolation(Exception):
    """A Sentinel extraction proposes parser-owned-type nodes on a doc
    the parser owns. This is a structural error — fix the extraction
    (or the slug membership) before continuing."""

    def __init__(self, document_label: str, offenders: list[tuple[str, str]]):
        self.document_label = document_label
        self.offenders = offenders  # list of (type, name)
        names = ", ".join(f"{t}:{n!r}" for t, n in offenders[:5])
        more = f" (+{len(offenders) - 5} more)" if len(offenders) > 5 else ""
        super().__init__(
            f"Parser-owned boundary violation on '{document_label}': "
            f"{len(offenders)} proposed node(s) of parser-owned type — {names}{more}. "
            f"The parser owns this document's wire-format schema; Sentinel "
            f"must not propose RecordLayout / FieldRequirement here. "
            f"Either re-run batch_extract with strip_parser_owned, or remove "
            f"'{document_label}' from PARSER_OWNED_SLUGS if the parser no "
            f"longer owns it."
        )


def check_parser_boundary(
    extraction: SentinelExtraction,
    document_label: str,
) -> None:
    """Raise ParserBoundaryViolation if `extraction` proposes any parser-
    owned-type node and `document_label` is in PARSER_OWNED_SLUGS.

    Pure check — does not mutate the extraction. Safe to call anywhere,
    no DB required."""
    if document_label not in PARSER_OWNED_SLUGS:
        return
    offenders: list[tuple[str, str]] = []
    for n in extraction.proposed_nodes:
        if n.type in PARSER_OWNED_TYPES:
            type_label = n.type.value if hasattr(n.type, "value") else str(n.type)
            offenders.append((type_label, n.name))
    if offenders:
        raise ParserBoundaryViolation(document_label, offenders)
