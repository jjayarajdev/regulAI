"""Back-fill position_start / position_length on FieldRequirement proposals.

Sentinel sometimes extracts a FieldRequirement's name and format but leaves
position_start/length null — typically when the source document describes
the field in prose ("The RISK_ZIP field is a 5-digit ZIP code") rather
than a column-numbered table ("| 21–25 | RISK_ZIP | NUMERIC(5) |").

This resolver runs *after* extraction and *before* materialize(). It
scans the source text for column-position markers near each unresolved
field's anchor (short_code or field_name) and back-fills positions.

Hits expected on FL FHCF (table-shaped) and the OIR memo (mixed). No-op
on TX wire-layouts (parser-owned, never has nulls).

This is best-effort — fields it can't resolve stay null. The audit script
will still report them as low-confidence, but they won't be rejected.
"""

from __future__ import annotations

import re

from packages.core.enums import NodeType
from packages.lhs.sentinel.schema import ProposedNode, SentinelExtraction


# Patterns we recognize, in priority order:
#   "Cols 21–25" / "Cols 21-25" / "Columns 21 to 25"   → start=21, end=25
#   "Col 135" / "Column 135" / "Position 60"           → start=135, length=1
#   "21–25" inside a markdown table cell               → start=21, end=25
_RANGE_RE = re.compile(
    r"(?:Cols?|Columns?|Positions?)\s+(\d+)\s*(?:[-–—]|to)\s*(\d+)",
    re.IGNORECASE,
)
_SINGLE_RE = re.compile(
    r"(?:Cols?|Columns?|Positions?)\s+(\d+)\b",
    re.IGNORECASE,
)
# Bare table-cell range like "| 21–25 | RISK_ZIP |" — used as fallback,
# more permissive so apply it only inside a table row containing the field.
_BARE_RANGE_RE = re.compile(r"(\d+)\s*[-–—]\s*(\d+)")


def _resolve_one(p: ProposedNode, source_text: str) -> bool:
    """Try to back-fill positions on a single FieldRequirement. Returns True
    if anything was resolved. Modifies `p` in place."""
    if p.position_start is not None:
        return False
    if not p.field_name:
        return False

    # Find every occurrence of field_name in source; pick the one whose row
    # contains a position marker.
    needle = p.field_name
    idx = 0
    while True:
        anchor = source_text.find(needle, idx)
        if anchor < 0:
            break
        # Bound by row: previous newline → next newline.
        row_start = source_text.rfind("\n", 0, anchor) + 1
        row_end = source_text.find("\n", anchor)
        if row_end < 0:
            row_end = len(source_text)
        row = source_text[row_start:row_end]

        m = _RANGE_RE.search(row)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            if end >= start:
                p.position_start = start
                p.position_length = end - start + 1
                return True

        m = _SINGLE_RE.search(row)
        if m:
            p.position_start = int(m.group(1))
            p.position_length = 1
            return True

        # Markdown table cell — "| 21–25 |" — only if the row begins with
        # a pipe (so we don't accidentally match a year range like "1900–2000").
        if row.lstrip().startswith("|"):
            m = _BARE_RANGE_RE.search(row)
            if m:
                start, end = int(m.group(1)), int(m.group(2))
                if end >= start and end - start < 500:  # sanity: layouts are <=500 cols
                    p.position_start = start
                    p.position_length = end - start + 1
                    return True

        idx = anchor + len(needle)

    return False


def resolve_positions(
    extraction: SentinelExtraction,
    source_text: str,
) -> tuple[SentinelExtraction, int]:
    """Back-fill positions on every FieldRequirement proposal that lacks one.

    Returns (mutated_extraction, num_resolved). The extraction is mutated
    in place; the return value is for convenience + count.
    """
    resolved = 0
    for p in extraction.proposed_nodes:
        if p.type != NodeType.FIELD_REQUIREMENT:
            continue
        if _resolve_one(p, source_text):
            resolved += 1
    return extraction, resolved
