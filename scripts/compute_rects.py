"""Backfill citation_rects for every cached extraction.

For each extraction in materialized/extractions/*.extraction.json, look up the
matching DocEntry in the registry, run PyMuPDF over the source PDF, and write
a companion `<stem>.rects.json` next to the extraction.

Idempotent: skips when a rects file is already present and newer than the
extraction. Use `--force` to recompute everything.

Run: uv run python -m scripts.compute_rects [--force]
"""

import json
import sys
import time
from pathlib import Path

from api.registry import DOCS, extraction_path_for, rects_path_for
from packages.lhs.citations.pdf_highlight import compute_rects_bundle
from packages.lhs.sentinel.schema import SentinelExtraction


def needs_recompute(ext_path: Path, rects_path: Path, force: bool) -> bool:
    if force or not rects_path.exists():
        return True
    return rects_path.stat().st_mtime < ext_path.stat().st_mtime


def main() -> None:
    force = "--force" in sys.argv
    total = located_total = missed_total = 0

    for doc in DOCS:
        ext_path = extraction_path_for(doc)
        if not ext_path.exists():
            continue
        if doc.pdf_path is None or not doc.pdf_path.exists():
            print(f"[skip] {doc.slug}: no PDF (markdown-only)")
            continue

        rects_path = rects_path_for(doc)
        if not needs_recompute(ext_path, rects_path, force):
            print(f"[cached] {doc.slug}")
            continue

        if not doc.path.exists():
            print(f"[skip] {doc.slug}: source text missing")
            continue

        extraction = SentinelExtraction.model_validate(
            json.loads(ext_path.read_text(encoding="utf-8"))
        )
        source_text = doc.path.read_text(encoding="utf-8")
        started = time.time()
        bundle = compute_rects_bundle(
            doc.pdf_path,
            source_text,
            extraction,
            page_start=doc.pdf_start_page,
            page_end=doc.pdf_end_page,
        )
        elapsed = time.time() - started

        rects_path.write_text(
            json.dumps(bundle.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

        located = sum(1 for r in bundle.citation_rects if r)
        missed = len(bundle.citation_rects) - located
        total += len(bundle.citation_rects)
        located_total += located
        missed_total += missed
        print(
            f"[ok]  {doc.slug}: {located}/{len(bundle.citation_rects)} located "
            f"({missed} missed)  pages={doc.pdf_start_page}-{doc.pdf_end_page}  "
            f"{elapsed:.2f}s"
        )

    if total:
        pct = 100.0 * located_total / total
        print(f"\nTotal: {located_total}/{total} citations located ({pct:.1f}%) — {missed_total} missed")


if __name__ == "__main__":
    main()
