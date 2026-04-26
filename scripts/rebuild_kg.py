"""End-to-end rebuild of the Neo4j KG from cached, on-disk artifacts.

DESTRUCTIVE: wipes the database, re-applies migrations, then replays:
  1. the hand-crafted regulatory canon (scripts.seed)
  2. every cached LLM extraction (materialized/extractions/<doc>.extraction.json)
     using the SAME materialize() path /api/regulations/{slug}/approve uses
  3. the deterministic wire-layout parser for the Homeowners record layout

No LLM calls — fully reproducible from disk. Use this whenever you want
to start from a known clean state without re-spending tokens.

Run: uv run python -m scripts.rebuild_kg
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from api.registry import DOCS, extraction_path_for, rects_path_for
from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
from packages.lhs.citations.pdf_highlight import CitationRectsBundle
from packages.lhs.materialization.materialize import materialize
from packages.lhs.sentinel.schema import SentinelExtraction


def _step(n: int, total: int, label: str) -> None:
    print(f"\n[{n}/{total}] {label}")
    print("-" * (8 + len(label)))


def main() -> None:
    total_steps = 6

    _step(1, total_steps, "Wipe + migrate")
    with Neo4jGREAdapter() as gre:
        gre.wipe_all()
    print("  Database wiped.")
    rc = subprocess.call([sys.executable, "-m", "scripts.migrate"])
    if rc != 0:
        print("  Migrate failed.")
        sys.exit(rc)

    _step(2, total_steps, "Seed hand-crafted regulatory canon")
    rc = subprocess.call([sys.executable, "-m", "scripts.seed"])
    if rc != 0:
        sys.exit(rc)

    # Slugs the deterministic parser owns — LLM extractions for these
    # are unreliable for tabular content, so we skip them here and let
    # parse_record_layout produce the canonical extraction in step 4.
    PARSER_OWNED = {
        "tico-record-layout-homeowners",
        "tico-section-c",
        "tico-section-d",
        "tico-section-e",
        "tico-section-g",
    }

    # Slugs that exist for the `make demo-new-bulletin` demo and are
    # deliberately NOT loaded by rebuild_kg, so the demo can ingest them
    # freshly against a clean baseline and show real ADD/MODIFY/SUPERSEDE
    # diffs. Loaded only on demand via demo_new_bulletin.py.
    DEMO_ONLY = {
        "bulletin-2027-q1-117",
    }

    _step(3, total_steps, "Replay cached LLM extractions")
    replayed = 0
    for doc in DOCS:
        ext_path = extraction_path_for(doc)
        if not ext_path.exists():
            continue
        if doc.slug in PARSER_OWNED:
            print(f"  [parser-owned] {doc.slug}  (skipping LLM extraction; parser will handle)")
            continue
        if doc.slug in DEMO_ONLY:
            print(f"  [demo-only]    {doc.slug}  (skipped — load via `make demo-new-bulletin`)")
            continue
        if not doc.path.exists():
            print(f"  [skip] {doc.slug}: source text missing")
            continue

        extraction = SentinelExtraction.model_validate(
            json.loads(ext_path.read_text(encoding="utf-8"))
        )
        rects_bundle: CitationRectsBundle | None = None
        rects_path = rects_path_for(doc)
        if rects_path.exists():
            rects_bundle = CitationRectsBundle.model_validate(
                json.loads(rects_path.read_text(encoding="utf-8"))
            )
        with Neo4jGREAdapter() as gre:
            result = materialize(
                extraction, gre, document_label=doc.slug, rects_bundle=rects_bundle
            )
        print(
            f"  [ok] {doc.slug:<35}  +{len(result.nodes_created)} nodes  "
            f"({len(result.nodes_reused)} reused, "
            f"{result.relationships_created} rels, {result.citations_created} cites)"
        )
        replayed += 1
    print(f"  Replayed {replayed} cached extractions.")

    _step(4, total_steps, "Run deterministic parser (HO PDF + Stat Plan C/D/E/G)")
    rc = subprocess.call([sys.executable, "-m", "scripts.parse_record_layout"])
    if rc != 0:
        sys.exit(rc)

    _step(5, total_steps, "Cleanup phantom layouts + orphan fields")
    rc = subprocess.call([sys.executable, "-m", "scripts.cleanup_kg"])
    if rc != 0:
        sys.exit(rc)

    _step(6, total_steps, "Apply BulletinOverrides (version-bump targets)")
    rc = subprocess.call([sys.executable, "-m", "scripts.apply_bulletin", "--all"])
    if rc != 0:
        sys.exit(rc)

    print("\n" + "=" * 60)
    with Neo4jGREAdapter() as gre:
        total = gre.count_nodes()
        rels = gre.count_relationships()
        by_type = gre.count_by_type()
    print(f"Final state: {total} nodes, {rels} relationships")
    for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {t:<25} {c:>4}")
    print("\nKG is in a clean, fully reproducible state.")


if __name__ == "__main__":
    main()
