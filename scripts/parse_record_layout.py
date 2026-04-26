"""Deterministic parser for the TICO Homeowners Record Layout PDF.

This is the *operational* wire format an insurer ships to TICO — a tabular
spec of the 200-char fixed-width record, column-by-column, with all
enumerated code values. Unlike the rulebook (Stat Plan Sections A-G),
this PDF is a regular table that an LLM tends to under-extract from. So
we parse it deterministically with PyMuPDF + a small state machine, and
emit nodes through the same `materialize()` pipeline used for Sentinel
output (dedup, citations, snapshots all reused).

Output (per the closed KG vocabulary):
  - 1 RegulationDocument for the PDF itself
  - 1 RecordLayout per top-level section (PREMIUMS, LOSSES)
  - 1 FieldRequirement per column-position header
  - 1 CodeList per field that has enumerated values
  - 1 CodeValue per listed enumerated value
  - Edges: CONTAINED_IN (field→layout), CODED_BY (field→codelist),
           HAS_VALUE (codelist→codevalue), CITES (every node→source doc)

Run: uv run python -m scripts.parse_record_layout
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import fitz

from api.registry import extraction_path_for, get_doc, rects_path_for
from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
from packages.core.enums import (
    CitationKind,
    DocumentKind,
    NodeType,
    RelationshipType,
)
from packages.lhs.citations.pdf_highlight import compute_rects_bundle
from packages.lhs.materialization.materialize import materialize
from packages.lhs.sentinel.schema import (
    CitationProposal,
    ProposedNode,
    ProposedRelationship,
    SentinelExtraction,
)

DOC_SLUG = "tico-record-layout-homeowners"

# Path to the broader Stat Plan PDF (used for Sections C/D/E/G parsing).
_STAT_PLAN_PDF = Path("references/regulations/TX_Statistical_Plan_Residential_Risks_2026.pdf")
_HO_PDF = Path("references/regulations/tico_recordLayoutHomeOwners.pdf")


@dataclass
class DocInfo:
    """Minimal RegulationDocument metadata for build_extraction."""

    temp_id: str
    name: str
    title: str
    source_url: str
    description: str
    hash: str | None = None  # None → compute from pdf_path


def _layout_key(layout_name: str) -> str:
    """Stable short id for prefixing temp_ids per layout.

    Use up to 28 chars + a 4-char hash so distinct layout names with the
    same prefix (e.g. "Homeowners Premium…" vs "Homeowners Loss…") don't
    collide on temp_id construction.
    """
    cleaned = re.sub(r"[^a-z0-9]+", "", layout_name.lower())
    if not cleaned:
        return "lay"
    h = hashlib.sha256(layout_name.encode()).hexdigest()[:4]
    return f"{cleaned[:28]}{h}"


@dataclass
class ParseTarget:
    """One target = one extraction.json/rects.json file in materialized/.

    A target produces a SentinelExtraction citing exactly one
    RegulationDocument; multiple layouts can live inside it (e.g. HO
    PDF has Premium + Loss). For Stat Plan sections we use one target
    per section so each existing slug (tico-section-c, etc.) gets its
    own files — replacing the prior LLM-extracted output.
    """

    slug: str                                          # registry doc slug
    pdf: Path
    doc: DocInfo
    layouts: list[tuple[str, int, int]]                # (layout_name, page_start, page_end)


# Targets the deterministic parser owns. Each entry produces an
# extraction.json (and rects.json) keyed by its registry slug, and
# materializes through the same pipeline as Sentinel output.
PARSER_TARGETS: list[ParseTarget] = [
    ParseTarget(
        slug="tico-record-layout-homeowners",
        pdf=_HO_PDF,
        doc=DocInfo(
            temp_id="doc-tico-recordlayout-ho",
            name="TICO Wire Layout — Homeowners",
            title="Texas Statistical Plan — Record Layout for Residential Risks - Homeowners",
            source_url="https://www.ticostat.com/ResiDocs/recordLayoutHomeOwners.pdf",
            description="Operational fixed-width record layout for Homeowners — defines what an insurer's premium and loss submissions to TICO must contain, byte-by-byte.",
        ),
        # Page ranges within the HO PDF. None,None lets the running-banner
        # detection pick up section boundaries automatically.
        layouts=[
            ("Homeowners Premium Record Layout", 4, 15),
            ("Homeowners Loss Record Layout", 18, 25),
        ],
    ),
    ParseTarget(
        slug="tico-section-c",
        pdf=_STAT_PLAN_PDF,
        doc=DocInfo(
            temp_id="doc-stat-plan-section-c",
            name="Texas Statistical Plan for Residential Risks (eff. 2026-01-01)",
            title="Texas Statistical Plan for Residential Risks — Section C: Record Layout for Premiums",
            source_url="https://www.tdi.texas.gov/rules/2025/documents/statplanres.pdf",
            description="Section C of the Stat Plan — column-by-column wire format for premium records, all residential lines.",
            hash="tico-tx-stat-plan-2026-01-01",  # matches the seeded RegulationDocument
        ),
        layouts=[("Premium Record Layout", 42, 63)],
    ),
    ParseTarget(
        slug="tico-section-d",
        pdf=_STAT_PLAN_PDF,
        doc=DocInfo(
            temp_id="doc-stat-plan-section-d",
            name="Texas Statistical Plan for Residential Risks (eff. 2026-01-01)",
            title="Texas Statistical Plan for Residential Risks — Section D: Record Layout for Losses",
            source_url="https://www.tdi.texas.gov/rules/2025/documents/statplanres.pdf",
            description="Section D of the Stat Plan — column-by-column wire format for loss records.",
            hash="tico-tx-stat-plan-2026-01-01",
        ),
        layouts=[("Loss Record Layout", 64, 79)],
    ),
    ParseTarget(
        slug="tico-section-e",
        pdf=_STAT_PLAN_PDF,
        doc=DocInfo(
            temp_id="doc-stat-plan-section-e",
            name="Texas Statistical Plan for Residential Risks (eff. 2026-01-01)",
            title="Texas Statistical Plan for Residential Risks — Section E: Record Layout for Notices",
            source_url="https://www.tdi.texas.gov/rules/2025/documents/statplanres.pdf",
            description="Section E of the Stat Plan — wire format for HB 2067 cancellation/nonrenewal/declination notice reports.",
            hash="tico-tx-stat-plan-2026-01-01",
        ),
        layouts=[("Notice Record Layout", 80, 84)],
    ),
    ParseTarget(
        slug="tico-section-g",
        pdf=_STAT_PLAN_PDF,
        doc=DocInfo(
            temp_id="doc-stat-plan-section-g",
            name="Texas Statistical Plan for Residential Risks (eff. 2026-01-01)",
            title="Texas Statistical Plan for Residential Risks — Section G: Record Layout for Counts",
            source_url="https://www.tdi.texas.gov/rules/2025/documents/statplanres.pdf",
            description="Section G of the Stat Plan — wire format for HB 2067 actual cancellation/nonrenewal/declination count reports.",
            hash="tico-tx-stat-plan-2026-01-01",
        ),
        layouts=[("Notice Count Record Layout", 91, 92)],
    ),
]

# Page numbers reset each time we hit one of these section banners.
_SECTION_BANNERS = {
    ("HOMEOWNERS", "PREMIUMS"): "Homeowners Premium Record Layout",
    ("HOMEOWNERS", "LOSSES"): "Homeowners Loss Record Layout",
}

# Lines we always discard (page boilerplate / table headers). Matched
# case-insensitively — the HO record-layout PDF uses ALL CAPS while the
# Stat Plan PDF uses Mixed Case for the same banners.
_NOISE_LINES = {
    s.upper()
    for s in [
        "TEXAS",
        "TEXAS STATISTICAL PLAN",
        "STATISTICAL PLAN",
        "RECORD LAYOUT",
        "RECORD LAYOUT FOR PREMIUMS",
        "RECORD LAYOUT FOR LOSSES",
        "RECORD LAYOUT FOR NOTICES",
        "RECORD LAYOUT FOR COUNTS",
        "RESIDENTIAL RISKS",
        "RESIDENTIAL RISKS - HOMEOWNERS",
        "FOR",
        "HOMEOWNERS",
        "PREMIUMS",
        "LOSSES",
        "NOTICES",
        "COUNTS",
        "COLUMNS",
        "CODES",
        "CODE",
        "TYPE OR DESCRIPTION",
        "SECTION C: RECORD LAYOUT FOR PREMIUMS",
        "SECTION D: RECORD LAYOUT FOR LOSSES",
        "SECTION E: RECORD LAYOUT FOR NOTICES",
        "SECTION G: RECORD LAYOUT FOR COUNTS",
    ]
}

# `1 (SP)`, `3-4 (ACDT)`, `7-16 (POLICY)`, `48 (PSC)`. Code-tag is letters,
# digits, optional `#/&-` (seen in the source). Range separator is hyphen
# in the HO record-layout PDF and en-dash (–) in the Stat Plan PDF.
_FIELD_HEADER_RE = re.compile(r"^(\d+)(?:[–\-](\d+))?\s*\(([A-Z0-9#&\-/]+)\)\s*$")
# `31-33` with no parenthetical → SKIP/reserved fields. Must have the dash:
# a bare `91` is a code value, not a column-range header.
_SKIP_HEADER_RE = re.compile(r"^(\d+)[–\-](\d+)\s*$")


@dataclass
class ParsedField:
    layout_name: str
    short_code: str            # "SP", "RT", "POLICY"
    field_name: str            # "STAT PLAN", "RECORD TYPE", "POLICY NUMBER"
    position_start: int
    position_length: int
    page: int                  # 1-indexed page where the field header appeared
    code_pairs: list[tuple[str, str]] = field(default_factory=list)   # [(code, description)]
    description: str = ""      # for free-form fields ("*" with text)


# A "code line" is a short token that names a code value:
#   - 1-2 alphanumeric chars: "1", "05", "B", "AB"
#   - 3-char ranges: "1-9", "1–9" (covers Jan..Sep style)
#   - footnote-marked: "*1", "**7", "7*" (the * marker is metadata, stripped on store)
#   - special markers: "*", "&", "-"
# Anything else (e.g. "$500", "1/2%", "Greater than 10%") is treated as
# description text. Without this guard the parser flips code/desc pairs in
# fields with dollar/percent enumerations (DEDUCTIBLE TYPE).
_CODE_TOKEN_RE = re.compile(
    r"^(?:\*{1,2}[\dA-Za-z]|[\dA-Za-z]\*{1,2}|[\dA-Za-z]{1,3}|\d+[–\-]\d+|[\*\-&])$"
)


def _is_code_line(line: str) -> bool:
    return bool(_CODE_TOKEN_RE.match(line.strip()))


def _strip_footnote_marker(code: str) -> tuple[str, str]:
    """Remove `*`/`**` footnote markers from a code value.

    Returns (cleaned_code, marker). The marker is preserved so we can keep
    it in the description as metadata. Examples:
       "*1"  → ("1",  "*")
       "**7" → ("7",  "**")
       "7*"  → ("7",  "*")
       "1"   → ("1",  "")
    """
    s = code.strip()
    m = re.match(r"^(\*{1,2})([\dA-Za-z]+)$", s)
    if m:
        return m.group(2), m.group(1)
    m = re.match(r"^([\dA-Za-z]+)(\*{1,2})$", s)
    if m:
        return m.group(1), m.group(2)
    return s, ""


def _is_noise(line: str, *, in_field_body: bool = False) -> bool:
    s = line.strip()
    if not s:
        return True
    if s.upper() in _NOISE_LINES:
        return True
    # Page-number lines like "1", "13" — but ONLY when we haven't yet
    # entered a field's body. Inside a field body, "05" / "06" / "91" are
    # legitimate enumerated codes.
    if not in_field_body and re.fullmatch(r"\d{1,2}", s):
        return True
    return False


def _read_pages(pdf_path: Path) -> list[tuple[int, list[str]]]:
    """Return [(1-indexed page, [stripped non-noise lines])] for every page."""
    out: list[tuple[int, list[str]]] = []
    with fitz.open(pdf_path) as pdf:
        for pno in range(pdf.page_count):
            text = pdf.load_page(pno).get_text()
            lines = [ln.strip() for ln in text.splitlines()]
            out.append((pno + 1, lines))
    return out


def _section_for_page(lines: list[str]) -> str | None:
    """Detect the running banner — pages always start HOMEOWNERS / <SECTION>."""
    head = [ln for ln in lines[:6] if ln]
    if len(head) < 2:
        return None
    key = (head[0], head[1])
    return _SECTION_BANNERS.get(key)


def parse_pdf(
    pdf_path: Path,
    *,
    page_start: int | None = None,
    page_end: int | None = None,
    forced_layout_name: str | None = None,
) -> list[ParsedField]:
    """Walk the PDF (or a page range) and emit one ParsedField per header.

    Args:
        pdf_path:           PDF to parse.
        page_start/page_end:  inclusive 1-indexed range; None = whole PDF.
        forced_layout_name:   when set, every field gets this layout name —
            skips the running-banner detection, used when caller already
            knows which RecordLayout the page range corresponds to.
    """
    pages = _read_pages(pdf_path)
    if page_start is not None or page_end is not None:
        ps = page_start or 1
        pe = page_end or len(pages)
        pages = [(p, lines) for p, lines in pages if ps <= p <= pe]
    fields: list[ParsedField] = []
    current_layout: str | None = forced_layout_name
    current_field: ParsedField | None = None
    pending_name_for: ParsedField | None = None

    for page_num, lines in pages:
        if forced_layout_name is None:
            section = _section_for_page(lines)
            if section is not None:
                current_layout = section

        # Skip cover/TOC/section-divider pages (no layout context).
        if current_layout is None:
            continue

        seen_first_header_this_page = False
        for line in lines:
            if _is_noise(line, in_field_body=seen_first_header_this_page):
                continue

            m = _FIELD_HEADER_RE.match(line)
            skip_m = None
            if not m:
                sm = _SKIP_HEADER_RE.match(line)
                if sm:
                    # Distinguish a column-range SKIP header ("31-33") from
                    # a code abbreviation that uses a dash ("1-9" meaning
                    # values 1..9 for January..September). Codes are always
                    # single-digit; position ranges always include numbers > 9.
                    hi = int(sm.group(2))
                    if hi >= 10:
                        skip_m = sm

            if m:
                seen_first_header_this_page = True
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else start
                short_code = m.group(3)
                pf = ParsedField(
                    layout_name=current_layout,
                    short_code=short_code,
                    field_name="",  # populated by next non-noise line
                    position_start=start,
                    position_length=end - start + 1,
                    page=page_num,
                )
                fields.append(pf)
                current_field = pf
                pending_name_for = pf
                continue

            if skip_m:
                # Skip/reserved column block — single-line entry, no codes.
                seen_first_header_this_page = True
                start = int(skip_m.group(1))
                end = int(skip_m.group(2)) if skip_m.group(2) else start
                pf = ParsedField(
                    layout_name=current_layout,
                    short_code="SKIP",
                    field_name=f"SKIP cols {start}-{end}" if end > start else f"SKIP col {start}",
                    position_start=start,
                    position_length=end - start + 1,
                    page=page_num,
                    description="Reserved/unused columns.",
                )
                fields.append(pf)
                current_field = pf
                pending_name_for = None
                continue

            if pending_name_for is not None:
                pending_name_for.field_name = line
                pending_name_for = None
                continue

            # Otherwise we're in the body of `current_field` — alternating
            # code/description lines. Collect by pairing: odd line = code,
            # even line = description.
            if current_field is None:
                continue

            # A "code line" has to look like one — short and structurally a
            # token, not a phrase like "$500" or "1/2%". Description lines
            # coalesce onto the previous code's description so multi-line
            # descriptions ("New/Renewals…\ninception)") survive.
            is_code = _is_code_line(line)
            if is_code and (current_field.code_pairs == [] or current_field.code_pairs[-1][1] != ""):
                # Start a new code entry awaiting its description. Strip any
                # footnote markers (`*1`, `**7`, `7*`) so the stored code is
                # what an insurer would actually write into the wire format.
                cleaned, _marker = _strip_footnote_marker(line)
                current_field.code_pairs.append((cleaned, ""))
            else:
                if current_field.code_pairs:
                    code, existing_desc = current_field.code_pairs[-1]
                    if existing_desc == "":
                        current_field.code_pairs[-1] = (code, line)
                    else:
                        # Continuation: append to the previous code's description.
                        current_field.code_pairs[-1] = (
                            code,
                            f"{existing_desc} {line}".strip(),
                        )
                else:
                    # Free-form prose for the field as a whole (no enumerated codes).
                    current_field.description = (
                        (current_field.description + " " + line).strip()
                    )

    # Drop fields that ended up with no name (parser glitches).
    fields = [f for f in fields if f.field_name]
    # Promote sub-fields where a parent's code list is actually a header→codes
    # nesting (e.g. ACDT cols 3-4 → MONTH at 3 and YEAR at 4 with their codes).
    fields = _split_sub_fields(fields)
    # Fill gaps so columns 1..target_length are always accounted for.
    fields = _fill_coverage_gaps(fields, target_length=200)
    return fields


def _split_sub_fields(fields: list[ParsedField]) -> list[ParsedField]:
    """If a multi-column field's code list contains sub-field markers
    (single-digit code + ALL-CAPS short description), split it into
    independent sub-FieldRequirements.

    Example: ACDT (cols 3-4) with code_pairs starting with ('3', 'MONTH')
    and ('4', 'YEAR') becomes ACDT (parent) + MONTH (col 3, 1-char) + YEAR
    (col 4, 1-char) with their respective codes. The parent stays so the
    range is still queryable; byte-level validation uses the sub-fields.
    """
    out: list[ParsedField] = []
    for pf in fields:
        if pf.position_length < 2 or not pf.code_pairs:
            out.append(pf)
            continue

        # Identify markers — pairs whose code is a single column number
        # within the parent's range and whose description is ALL-CAPS short.
        marker_indices: list[int] = []
        for i, (code, desc) in enumerate(pf.code_pairs):
            if not code.isdigit():
                continue
            col = int(code)
            if not (pf.position_start <= col <= pf.position_start + pf.position_length - 1):
                continue
            if not desc:
                continue
            if desc.isupper() and len(desc) <= 12 and " " not in desc:
                marker_indices.append(i)

        if len(marker_indices) < 2:
            # Not a sub-field structure — keep parent as-is.
            out.append(pf)
            continue

        # Keep the parent (range view), then build sub-fields from each marker
        # to the next.
        out.append(pf)
        boundaries = marker_indices + [len(pf.code_pairs)]
        for idx, marker_i in enumerate(marker_indices):
            next_i = boundaries[idx + 1]
            sub_code, sub_name = pf.code_pairs[marker_i]
            sub_pairs = pf.code_pairs[marker_i + 1 : next_i]
            sub = ParsedField(
                layout_name=pf.layout_name,
                short_code=f"{pf.short_code}-{sub_name}",
                field_name=sub_name,
                position_start=int(sub_code),
                position_length=1,
                page=pf.page,
                code_pairs=sub_pairs,
                description=f"Sub-field of {pf.short_code}.",
            )
            out.append(sub)
        # The parent's code_pairs are now redundant for byte-level validation;
        # drop them so we don't double-count codes in coverage stats.
        pf.code_pairs = []
        pf.description = (pf.description + " (parent of sub-fields).").strip()
    return out


# Total wire-record length per the TICO Statistical Plan. Anything past the
# parser's last seen column is implicit SKIP/reserved.
_DEFAULT_RECORD_LENGTH = 200


def _fill_coverage_gaps(
    fields: list[ParsedField], *, target_length: int = _DEFAULT_RECORD_LENGTH
) -> list[ParsedField]:
    """Emit explicit SKIP fields for any 1..target_length columns not covered.

    Without this, the KG would silently leave gaps in the wire format. With
    it, every byte of every record has a FieldRequirement node — gaps are
    explicit and queryable, never invisible.
    """
    out: list[ParsedField] = []
    by_layout: dict[str, list[ParsedField]] = {}
    for f in fields:
        by_layout.setdefault(f.layout_name, []).append(f)

    for layout_name, fs in by_layout.items():
        fs_sorted = sorted(fs, key=lambda f: f.position_start)
        # Compute occupied columns
        occupied = set()
        for f in fs_sorted:
            for c in range(f.position_start, f.position_start + f.position_length):
                occupied.add(c)
        out.extend(fs_sorted)
        # Walk 1..target_length and group consecutive missing cols into SKIPs.
        gap_start: int | None = None
        for col in range(1, target_length + 1):
            if col not in occupied:
                if gap_start is None:
                    gap_start = col
            else:
                if gap_start is not None:
                    end = col - 1
                    out.append(_make_implicit_skip(layout_name, gap_start, end))
                    gap_start = None
        if gap_start is not None:
            out.append(_make_implicit_skip(layout_name, gap_start, target_length))

    return out


def _make_implicit_skip(layout_name: str, start: int, end: int) -> ParsedField:
    label = f"SKIP cols {start}-{end}" if end > start else f"SKIP col {start}"
    return ParsedField(
        layout_name=layout_name,
        short_code="SKIP",
        field_name=label,
        position_start=start,
        position_length=end - start + 1,
        page=0,  # synthetic — not bound to a single source page
        description="Reserved/unused columns (gap-filled by parser to make the 200-byte record fully accounted).",
    )


# --- Convert ParsedFields into a SentinelExtraction-shaped proposal -----------


def _hash_pdf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def build_extraction(
    pdf_path: Path,
    text_path: Path,
    parsed_fields: list[ParsedField],
    doc_info: DocInfo,
) -> SentinelExtraction:
    text = text_path.read_text(encoding="utf-8")
    nodes: list[ProposedNode] = []
    rels: list[ProposedRelationship] = []
    citations: list[CitationProposal] = []

    # 1. The source RegulationDocument.
    doc_temp = doc_info.temp_id
    doc_hash = doc_info.hash or _hash_pdf(pdf_path)
    nodes.append(ProposedNode(
        temp_id=doc_temp,
        type=NodeType.REGULATION_DOCUMENT,
        name=doc_info.name,
        confidence=1.0,
        title=doc_info.title,
        kind=DocumentKind.STAT_PLAN,
        hash=doc_hash,
        source_url=doc_info.source_url,
        description=doc_info.description,
    ))

    # 2. One RecordLayout per top-level section seen by the parser.
    layout_temps: dict[str, str] = {}
    for layout_name in sorted({f.layout_name for f in parsed_fields}):
        slug = re.sub(r"[^a-z0-9]+", "-", layout_name.lower()).strip("-")
        tid = f"layout-{slug}"
        layout_temps[layout_name] = tid
        nodes.append(ProposedNode(
            temp_id=tid,
            type=NodeType.RECORD_LAYOUT,
            name=layout_name,
            confidence=1.0,
            layout_name=layout_name,
            record_format="fixed-width-200",
            description=f"Wire-format layout parsed from {pdf_path.name}.",
        ))
        # Layout CITES the source document (whole-doc citation).
        rels.append(ProposedRelationship(
            type=RelationshipType.CITES,
            src_temp_id=tid,
            dst_temp_id=doc_temp,
            char_start=0,
            char_end=min(len(text), 200),
            citation_kind=CitationKind.DEFINES,
        ))

    # 3. FieldRequirement + CodeList + CodeValue per parsed field.
    # Dedup parsed fields that page-break duplicates produced.
    deduped: dict[tuple[str, int, int], ParsedField] = {}
    for pf in parsed_fields:
        key = (pf.layout_name, pf.position_start, pf.position_length)
        if key in deduped:
            # Merge code pairs (later occurrence may complete the list).
            if len(pf.code_pairs) > len(deduped[key].code_pairs):
                deduped[key] = pf
        else:
            deduped[key] = pf
    parsed_fields = list(deduped.values())

    seen_codelist_ids: dict[str, str] = {}
    for i, pf in enumerate(parsed_fields):
        lk = _layout_key(pf.layout_name)
        field_temp = f"field-{lk}-{pf.short_code.lower()}-{pf.position_start}-{pf.position_length}"
        # Compute char span — locate the field-name line in text for CITES provenance.
        anchor = f"({pf.short_code})"
        char_start = text.find(anchor)
        if char_start < 0:
            char_start = 0
        char_end = min(len(text), char_start + 200)

        # FieldRequirement names are scoped to their layout — same column
        # in different layouts (e.g. HO Premium vs Stat-Plan Premium) is
        # NOT the same KG node; their codelists may differ.
        nodes.append(ProposedNode(
            temp_id=field_temp,
            type=NodeType.FIELD_REQUIREMENT,
            name=f"{pf.field_name} ({pf.short_code}) — {pf.layout_name}",
            confidence=1.0,
            field_name=pf.field_name,
            position_start=pf.position_start,
            position_length=pf.position_length,
            format="code" if pf.code_pairs else "free-form",
            is_required=pf.short_code != "SKIP",
            notes=pf.description or None,
        ))

        # CONTAINED_IN: field → its layout
        rels.append(ProposedRelationship(
            type=RelationshipType.CONTAINED_IN,
            src_temp_id=field_temp,
            dst_temp_id=layout_temps[pf.layout_name],
        ))
        # CITES: field → source doc with the spec span
        citations.append(CitationProposal(
            node_temp_id=field_temp,
            char_start=char_start,
            char_end=char_end,
            kind=CitationKind.DEFINES,
        ))

        # CodeList + CodeValues if this field has enumerated codes.
        # Each field gets its own codelist (always field-specific name to
        # avoid collisions). Cross-field canonicalization can come later as
        # an explicit normalization pass.
        if pf.code_pairs:
            cl_name = (
                f"{pf.field_name} ({pf.short_code}) — "
                f"{pf.layout_name} col{pf.position_start}"
            )
            cl_temp = f"codelist-{field_temp}"
            nodes.append(ProposedNode(
                temp_id=cl_temp,
                type=NodeType.CODE_LIST,
                name=cl_name,
                confidence=1.0,
                code_list_name=cl_name,
                description=f"Enumerated values for {pf.field_name} (cols {pf.position_start}+{pf.position_length}).",
            ))
            rels.append(ProposedRelationship(
                type=RelationshipType.CODED_BY,
                src_temp_id=field_temp,
                dst_temp_id=cl_temp,
            ))

            seen_codes_in_list: set[str] = set()
            for j, (code, desc) in enumerate(pf.code_pairs):
                if code in seen_codes_in_list:
                    continue
                seen_codes_in_list.add(code)
                cv_temp = f"{cl_temp}-cv-{j}"
                nodes.append(ProposedNode(
                    temp_id=cv_temp,
                    type=NodeType.CODE_VALUE,
                    name=f"{cl_name} = {code}",
                    confidence=1.0,
                    code=code,
                    notes=desc or None,
                    code_list_temp_id=cl_temp,
                ))
                rels.append(ProposedRelationship(
                    type=RelationshipType.HAS_VALUE,
                    src_temp_id=cl_temp,
                    dst_temp_id=cv_temp,
                ))

    return SentinelExtraction(
        summary=(
            f"Deterministic parse of {pdf_path.name}: "
            f"{len(parsed_fields)} fields across "
            f"{len({f.layout_name for f in parsed_fields})} record layouts."
        ),
        proposed_nodes=nodes,
        proposed_relationships=rels,
        citations=citations,
        uncited_spans=[],
        document_total_chars=len(text),
    )


def _run_target(target: ParseTarget) -> dict:
    """Parse + extract + materialize one target. Returns a stats dict."""
    doc = get_doc(target.slug)
    if doc is None or doc.pdf_path is None or not doc.pdf_path.exists():
        raise SystemExit(f"Cannot find DocEntry {target.slug!r} or its PDF.")

    parsed_all: list[ParsedField] = []
    layout_summaries: list[tuple[str, int, int, int]] = []
    for layout_name, ps_page, pe_page in target.layouts:
        layout_fields = parse_pdf(
            target.pdf,
            page_start=ps_page,
            page_end=pe_page,
            forced_layout_name=layout_name,
        )
        # Restrict to the layout this iteration is responsible for (parser
        # may have detected a layout name internally — override).
        for f in layout_fields:
            f.layout_name = layout_name
        parsed_all.extend(layout_fields)
        n_with_codes = sum(1 for f in layout_fields if f.code_pairs)
        n_codes = sum(len(f.code_pairs) for f in layout_fields)
        layout_summaries.append((layout_name, len(layout_fields), n_with_codes, n_codes))

    extraction = build_extraction(target.pdf, doc.path, parsed_all, target.doc)

    # Persist extraction + rects bundle keyed by the registry slug.
    ext_path = extraction_path_for(doc)
    ext_path.parent.mkdir(parents=True, exist_ok=True)
    ext_path.write_text(
        json.dumps(extraction.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )

    bundle = compute_rects_bundle(
        target.pdf,
        doc.path.read_text(encoding="utf-8"),
        extraction,
        page_start=doc.pdf_start_page,
        page_end=doc.pdf_end_page,
    )
    rects_path_for(doc).write_text(
        json.dumps(bundle.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    located = sum(1 for r in bundle.citation_rects if r)

    with Neo4jGREAdapter() as gre:
        result = materialize(
            extraction, gre, document_label=target.slug, rects_bundle=bundle
        )

    return {
        "slug": target.slug,
        "layouts": layout_summaries,
        "n_nodes_proposed": len(extraction.proposed_nodes),
        "n_rels_proposed": len(extraction.proposed_relationships),
        "n_citations": len(extraction.citations),
        "n_rects_located": located,
        "result": result,
    }


def main() -> None:
    print(f"Running {len(PARSER_TARGETS)} parser targets...\n")
    grand_nodes_created = grand_nodes_reused = grand_rels = 0
    for target in PARSER_TARGETS:
        print(f"━━ {target.slug} ━━")
        stats = _run_target(target)
        for layout, n_fields, n_with_codes, n_codes in stats["layouts"]:
            print(
                f"  {layout:<45}  fields={n_fields:>3}  "
                f"with-codes={n_with_codes:>3}  codes={n_codes:>3}"
            )
        r = stats["result"]
        print(
            f"  → {len(r.nodes_created)} nodes created, {len(r.nodes_reused)} reused, "
            f"{r.relationships_created} rels, {r.citations_created} cites, "
            f"{stats['n_rects_located']}/{stats['n_citations']} rects located"
        )
        print()
        grand_nodes_created += len(r.nodes_created)
        grand_nodes_reused += len(r.nodes_reused)
        grand_rels += r.relationships_created

    print("=" * 60)
    print(
        f"Total: {grand_nodes_created} new nodes, {grand_nodes_reused} reused, "
        f"{grand_rels} relationships."
    )


if __name__ == "__main__":
    main()
