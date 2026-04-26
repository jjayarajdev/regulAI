"""Pixel-perfect citation rectangles for PDF highlighting.

Sentinel produces citations as char offsets into the *extracted* source text.
That text differs from the PDF text layer (markdown headers, page markers,
text-layer reflow), so frontend fuzzy-matching is unreliable. Instead, at
extraction time we use PyMuPDF (fitz) to look up the actual rectangles for
each citation and persist them — the UI then just overlays them, no search.

Coordinates are in PDF points (72 DPI), top-left origin (y increases
downward), matching the convention PDF.js exposes via viewport.
"""

from __future__ import annotations

import re
from pathlib import Path

import fitz  # PyMuPDF
from pydantic import BaseModel, ConfigDict, Field

from packages.lhs.sentinel.schema import SentinelExtraction


class CitationRect(BaseModel):
    """One rectangle on one PDF page, in PDF points (top-left origin)."""

    model_config = ConfigDict(extra="forbid")

    page: int = Field(description="1-indexed PDF page number.")
    x0: float
    y0: float
    x1: float
    y1: float
    matched_text: str = Field(
        default="",
        description="The actual text fragment that fitz matched (for diagnostics).",
    )


class PageDimensions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    width: float
    height: float


class CitationRectsBundle(BaseModel):
    """Companion data for a SentinelExtraction. Persisted alongside it.

    `citation_rects` is parallel to `SentinelExtraction.citations` — index i
    holds the rects for citation i. An empty list at index i means we could
    not locate that citation in the PDF (UI should fall back to text-layer
    search or simply jump to the section's page range).
    """

    model_config = ConfigDict(extra="forbid")

    citation_rects: list[list[CitationRect]]
    page_dimensions: dict[int, PageDimensions] = Field(
        default_factory=dict,
        description="1-indexed page number → {width, height} in PDF points.",
    )


# Progressive prefix lengths to try when the full snippet doesn't match.
# Longer prefixes are most distinctive; shorter ones survive PDF text reflow.
_PREFIX_LENGTHS = [200, 140, 100, 70, 50, 35]


def _clean_snippet_for_pdf_search(snippet: str) -> str:
    """Strip artifacts that appear in the extracted text but NOT in the PDF.

    - Markdown heading hashes (`#`, `##`)
    - Markdown emphasis (`*`, `_`, backtick)
    - `(eff. YYYY-MM-DD)` parentheticals our section files prepend
    - `# Source: ...` metadata lines
    - `===== PAGE N =====` page markers
    - Collapse whitespace.
    """
    s = snippet
    s = re.sub(r"={3,}\s*PAGE\s+\d+\s*={3,}", " ", s)
    s = re.sub(r"^#\s*Source:[^\n]*$", " ", s, flags=re.MULTILINE | re.IGNORECASE)
    s = re.sub(r"\(eff\.\s*\d{4}-\d{2}-\d{2}\)", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"^#+\s*", " ", s, flags=re.MULTILINE)
    s = re.sub(r"[*_`]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _trim_to_word_boundary(s: str) -> str:
    """Drop the trailing partial word so a prefix doesn't end mid-token."""
    return re.sub(r"\s+\S*$", "", s).strip() or s


def _candidate_prefixes(cleaned: str) -> list[str]:
    """Generate progressively-shorter prefixes plus a few suffix windows.

    The full text is always tried first (most distinctive). Suffixes catch
    cases where the snippet starts with a heading that's been re-laid-out
    in the PDF.
    """
    out: list[str] = []
    seen: set[str] = set()

    def add(c: str) -> None:
        c = c.strip()
        if len(c) < 12:
            return
        key = c.lower()
        if key in seen:
            return
        seen.add(key)
        out.append(c)

    add(cleaned)
    for n in _PREFIX_LENGTHS:
        if len(cleaned) > n:
            add(_trim_to_word_boundary(cleaned[:n]))
    # Suffix windows — if the snippet starts with a wrapped heading, the
    # tail might land cleanly in the PDF body.
    for n in (140, 80):
        if len(cleaned) > n + 20:
            add(_trim_to_word_boundary(cleaned[-n:]))
    return out


def _search_page(page: fitz.Page, candidate: str) -> list[fitz.Rect]:
    """Return all rects where `candidate` was found on `page`.

    PyMuPDF's `search_for` is whitespace/newline tolerant and returns one
    rect per visual line a match occupies (line-wrapped matches yield 2+ rects).
    """
    try:
        # quads=False → rects only, which is what we want for axis-aligned overlays.
        return page.search_for(candidate, quads=False) or []
    except Exception:
        return []


def find_citation_rects(
    pdf_doc: fitz.Document,
    snippet: str,
    page_start: int,
    page_end: int | None,
) -> list[CitationRect]:
    """Locate `snippet` in pages [page_start..page_end] (1-indexed, inclusive).

    Tries candidate prefixes in order; returns rects for the first candidate
    that matches anywhere in the page range. Empty list = not located.
    """
    cleaned = _clean_snippet_for_pdf_search(snippet)
    if len(cleaned) < 12:
        return []

    candidates = _candidate_prefixes(cleaned)
    if not candidates:
        return []

    # Convert to 0-indexed inclusive range, clamped to actual pages.
    p_start = max(1, page_start) - 1
    p_end = (page_end if page_end is not None else pdf_doc.page_count) - 1
    p_end = min(p_end, pdf_doc.page_count - 1)
    if p_start > p_end:
        return []

    for candidate in candidates:
        hits: list[CitationRect] = []
        for pno in range(p_start, p_end + 1):
            page = pdf_doc.load_page(pno)
            for r in _search_page(page, candidate):
                hits.append(
                    CitationRect(
                        page=pno + 1,
                        x0=float(r.x0),
                        y0=float(r.y0),
                        x1=float(r.x1),
                        y1=float(r.y1),
                        matched_text=candidate[:80],
                    )
                )
        if hits:
            return hits
    return []


def extract_page_dimensions(
    pdf_doc: fitz.Document,
    page_start: int = 1,
    page_end: int | None = None,
) -> dict[int, PageDimensions]:
    """Return {1-indexed page → {width, height}} in PDF points for the range."""
    p_start = max(1, page_start) - 1
    p_end = (page_end if page_end is not None else pdf_doc.page_count) - 1
    p_end = min(p_end, pdf_doc.page_count - 1)
    out: dict[int, PageDimensions] = {}
    for pno in range(p_start, p_end + 1):
        rect = pdf_doc.load_page(pno).rect
        out[pno + 1] = PageDimensions(width=float(rect.width), height=float(rect.height))
    return out


def compute_rects_bundle(
    pdf_path: Path,
    source_text: str,
    extraction: SentinelExtraction,
    page_start: int = 1,
    page_end: int | None = None,
) -> CitationRectsBundle:
    """For each citation in `extraction`, look up its rects in the PDF.

    `source_text` is the exact text Sentinel was given (so char offsets line up).
    Returns a CitationRectsBundle parallel to `extraction.citations`.
    """
    citation_rects: list[list[CitationRect]] = []
    with fitz.open(pdf_path) as pdf_doc:
        page_dims = extract_page_dimensions(pdf_doc, page_start, page_end)
        for cite in extraction.citations:
            start = max(0, cite.char_start)
            end = min(len(source_text), cite.char_end)
            snippet = source_text[start:end]
            rects = find_citation_rects(pdf_doc, snippet, page_start, page_end)
            citation_rects.append(rects)
    return CitationRectsBundle(
        citation_rects=citation_rects,
        page_dimensions=page_dims,
    )
