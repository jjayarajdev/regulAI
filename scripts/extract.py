"""Run Sentinel extraction on a regulation document.

Usage:
    uv run python -m scripts.extract <doc-path>

Examples:
    make extract DOC=synthetic_regulations/synthetic/bulletins/B-2026-Q3-104.md
    uv run python -m scripts.extract synthetic_regulations/real/HB02067I.txt
"""

import json
import sys
from pathlib import Path

from api.registry import DOCS, WIRE_LAYOUTS_FOR_SLUG
from packages.adapters.shared.llm.openai_adapter import OpenAIAdapter
from packages.lhs.sentinel.agent import Sentinel
from packages.lhs.sentinel.filter import strip_parser_owned


def main(doc_path_str: str) -> None:
    doc_path = Path(doc_path_str)
    if not doc_path.exists():
        print(f"✗ Document not found: {doc_path}")
        sys.exit(1)

    text = doc_path.read_text(encoding="utf-8")
    print(f"Document: {doc_path}")
    print(f"  Size: {len(text):,} chars")

    print("\nInvoking Sentinel...")
    llm = OpenAIAdapter()
    print(f"  Model: {llm.model}")

    sentinel = Sentinel(llm)
    extraction = sentinel.extract(text, document_label=doc_path.name)

    # Defense: drop parser-owned types if this path corresponds to a registry
    # slug the deterministic parser owns.
    slug = next((d.slug for d in DOCS if d.path == doc_path), None)
    if slug and slug in WIRE_LAYOUTS_FOR_SLUG:
        extraction, fs = strip_parser_owned(extraction)
        if fs["dropped_nodes"]:
            print(f"  (filtered out {fs['dropped_nodes']} parser-owned nodes — slug {slug!r} is parser-owned)")

    # Stats — coverage uses UNION of intervals, not sum (avoids double-counting overlaps)
    n_nodes = len(extraction.proposed_nodes)
    n_rels = len(extraction.proposed_relationships)
    n_cites = len(extraction.citations)
    n_uncited = len(extraction.uncited_spans)

    intervals = sorted((c.char_start, c.char_end) for c in extraction.citations)
    merged: list[tuple[int, int]] = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    cited_chars = sum(e - s for s, e in merged)
    coverage = cited_chars / extraction.document_total_chars if extraction.document_total_chars else 0.0

    print(f"\nExtraction summary:")
    print(f"  Nodes proposed: {n_nodes}")
    print(f"  Relationships:  {n_rels}")
    print(f"  Citations:      {n_cites} ({len(merged)} after merging overlaps)")
    print(f"  Uncited spans:  {n_uncited}")
    print(f"  Coverage:       {coverage:.1%}")

    print(f"\nNode types proposed:")
    by_type: dict[str, int] = {}
    for n in extraction.proposed_nodes:
        key = n.type.value if hasattr(n.type, "value") else str(n.type)
        by_type[key] = by_type.get(key, 0) + 1
    for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {t:25s} {c:3d}")

    # Persist
    out_dir = Path("materialized/extractions")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{doc_path.stem}.extraction.json"
    out_path.write_text(
        json.dumps(extraction.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    print(f"\n✓ Wrote {out_path}")
    print(f"\nSummary (from agent):")
    print(f"  {extraction.summary}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python -m scripts.extract <doc-path>")
        sys.exit(1)
    main(sys.argv[1])
