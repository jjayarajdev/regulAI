"""Generate rich-markdown variants per DOCS entry using pymupdf4llm.

The "plain" extract_pdfs.py uses PyMuPDF's get_text() — fast, but loses
all structural cues. Headings, tables, lists collapse into a wall of
text. Cited char offsets in the LLM/parser extractions reference THAT
plain text, so we can't replace it without re-extraction.

This script produces a SECOND variant per registry slug, scoped to the
slug's pdf_start_page..pdf_end_page so each section gets its own clean
rich.md without scrolling through the whole 89-page Stat Plan:

   materialized/rich/<slug>.rich.md

The frontend's "Rich Markdown" view loads this on demand. Highlights
in that view use best-effort text search since char offsets refer to
the plain-text variant.

Run: uv run python -m scripts.extract_pdfs_rich
     make extract-rich
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf4llm

from api.registry import DOCS

OUTPUT_DIR = Path("materialized/rich")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = [d for d in DOCS if d.pdf_path is not None and d.pdf_path.exists()]
    if not targets:
        print("No docs with PDFs in the registry.")
        return
    print(f"Generating rich markdown for {len(targets)} registry slug(s)...\n")
    for d in targets:
        out = OUTPUT_DIR / f"{d.slug}.rich.md"
        try:
            # pymupdf4llm.to_markdown accepts a list of 0-indexed pages.
            page_start = (d.pdf_start_page or 1) - 1
            page_end = d.pdf_end_page or page_start + 1
            pages = list(range(page_start, page_end))
            md = pymupdf4llm.to_markdown(
                str(d.pdf_path),
                pages=pages,
                show_progress=False,
            )
        except Exception as e:
            print(f"  ✗ {d.slug}: {e}", file=sys.stderr)
            continue
        # Prepend a small slug header so the page is self-identifying.
        header = f"# {d.label}\n\n*{d.blurb}*\n\n---\n\n"
        out.write_text(header + md, encoding="utf-8")
        print(
            f"  ✓ {d.slug:<35}  →  {out}  ({len(md):,} chars, "
            f"pages {d.pdf_start_page}-{d.pdf_end_page})"
        )
    print(f"\nDone. Rich markdown files in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
