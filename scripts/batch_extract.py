"""Batch-run Sentinel extraction on every document in the registry.

Idempotent: skips documents whose extraction JSON already exists in
materialized/extractions/. Use `make batch-extract-force` to re-run all.

Run via: uv run python -m scripts.batch_extract
"""

import json
import sys
import time
from pathlib import Path

from api.registry import DOCS, WIRE_LAYOUTS_FOR_SLUG
from packages.adapters.shared.llm.openai_adapter import OpenAIAdapter
from packages.lhs.sentinel.agent import Sentinel
from packages.lhs.sentinel.filter import strip_parser_owned

# All documents we want extracted, in priority order. Order matters for the
# demo dropdown — first listed is the headline document.
DOCUMENTS: list[Path] = [
    Path("synthetic_regulations/real/sections/section_A_general.md"),
    Path("synthetic_regulations/real/sections/section_B_coding.md"),
    Path("synthetic_regulations/real/sections/section_C_record.md"),
    Path("synthetic_regulations/real/sections/section_D_record.md"),
    Path("synthetic_regulations/real/sections/section_E_record.md"),
    Path("synthetic_regulations/real/sections/section_F_additional.md"),
    Path("synthetic_regulations/real/sections/section_G_record.md"),
    Path("synthetic_regulations/real/HB02067I.txt"),
    Path("synthetic_regulations/synthetic/bulletins/B-2026-Q3-104.md"),
]

OUT_DIR = Path("materialized/extractions")


def extract_one(sentinel: Sentinel, doc_path: Path, force: bool = False) -> dict:
    out_path = OUT_DIR / f"{doc_path.stem}.extraction.json"
    if out_path.exists() and not force:
        return {"path": doc_path, "status": "cached", "out": out_path}

    text = doc_path.read_text(encoding="utf-8")
    started = time.time()
    extraction = sentinel.extract(text, document_label=doc_path.name)
    elapsed = time.time() - started

    # Defense: drop parser-owned types if this path is a parser-owned slug.
    slug = next((d.slug for d in DOCS if d.path == doc_path), None)
    if slug and slug in WIRE_LAYOUTS_FOR_SLUG:
        extraction, _ = strip_parser_owned(extraction)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(extraction.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    return {
        "path": doc_path,
        "status": "extracted",
        "out": out_path,
        "elapsed_sec": elapsed,
        "n_nodes": len(extraction.proposed_nodes),
        "n_rels": len(extraction.proposed_relationships),
        "n_cites": len(extraction.citations),
    }


def main() -> None:
    force = "--force" in sys.argv
    llm = OpenAIAdapter()
    sentinel = Sentinel(llm)
    print(f"Batch extraction with model={llm.model}, force={force}\n")

    results = []
    for i, doc in enumerate(DOCUMENTS, start=1):
        if not doc.exists():
            print(f"[{i}/{len(DOCUMENTS)}] {doc}  ✗ MISSING — skipping")
            continue
        print(f"[{i}/{len(DOCUMENTS)}] {doc}  ({doc.stat().st_size:,} bytes)")
        try:
            r = extract_one(sentinel, doc, force=force)
            if r["status"] == "cached":
                print(f"    ✓ cached at {r['out']}")
            else:
                print(
                    f"    ✓ extracted in {r['elapsed_sec']:.1f}s — "
                    f"{r['n_nodes']} nodes, {r['n_rels']} rels, {r['n_cites']} citations"
                )
            results.append(r)
        except Exception as e:  # noqa: BLE001 — log and continue
            print(f"    ✗ FAILED: {e}")
            results.append({"path": doc, "status": "failed", "error": str(e)})

    extracted = [r for r in results if r.get("status") == "extracted"]
    cached = [r for r in results if r.get("status") == "cached"]
    failed = [r for r in results if r.get("status") == "failed"]
    print(f"\nDone. {len(extracted)} fresh, {len(cached)} cached, {len(failed)} failed.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
