"""Demo: a new bulletin arrives → Sentinel + RAG → human review → KG update.

The end-to-end rules-level loop, narrated for a stakeholder audience.
Walks through six visible steps with the same care a compliance officer
would take when a real bulletin lands in their inbox.

  1. New document arrives.
  2. KG context retrieved (RAG augmentation).
  3. Sentinel extracts proposed changes against that context.
  4. Diff displayed: ADD / MODIFY / SUPERSEDE per node.
  5. Human approves.
  6. Materialize → apply_bulletin → before/after impact shown.

Run:
  make demo-new-bulletin                        # interactive
  make demo-new-bulletin AUTO=1                 # no prompts (skip approval)
  uv run python -m scripts.demo_new_bulletin --slug bulletin-2027-q1-117
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from api.registry import extraction_path_for, get_doc, rects_path_for
from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
from packages.adapters.shared.llm.openai_adapter import OpenAIAdapter
from packages.lhs.materialization.materialize import materialize
from packages.lhs.sentinel.agent import Sentinel
from packages.lhs.sentinel.kg_context import render_kg_context
from packages.lhs.sentinel.schema import SentinelExtraction


# -- visual helpers -----------------------------------------------------------


def _color(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


B  = lambda s: _color(s, "1")     # noqa: E731 bold
G  = lambda s: _color(s, "32")    # noqa: E731 green
R  = lambda s: _color(s, "31")    # noqa: E731 red
Y  = lambda s: _color(s, "33")    # noqa: E731 yellow
C  = lambda s: _color(s, "36")    # noqa: E731 cyan
DIM = lambda s: _color(s, "2")    # noqa: E731


def _step(n: int, total: int, icon: str, title: str) -> None:
    print()
    print(B(f"{icon}  STEP {n}/{total} — {title}"))
    print(DIM("─" * 76))


def _pause(seconds: float = 0.6) -> None:
    if sys.stdout.isatty():
        time.sleep(seconds)


# -- KG diff: which proposed nodes are NEW vs reuse existing ------------------


def _classify_proposals(extraction: SentinelExtraction) -> dict:
    """Bucket proposed_nodes against existing KG: addition / modification / supersession."""
    added: list[tuple[str, str]] = []
    modified: list[tuple[str, str]] = []        # exists in KG by name → reused
    superseded: list[tuple[str, str]] = []      # explicitly OVERRIDES targets

    # Collect OVERRIDES target names for marking
    override_targets: set[str] = set()
    for r in extraction.proposed_relationships:
        if r.type.value == "OVERRIDES":
            for n in extraction.proposed_nodes:
                if n.temp_id == r.dst_temp_id:
                    override_targets.add(n.name)

    with Neo4jGREAdapter() as gre, gre.driver.session() as s:
        existing = s.run(
            "MATCH (n:GRENode) RETURN n.name AS name, labels(n)[1] AS type"
        ).data()
    existing_names = {(e["type"], e["name"]) for e in existing}

    for n in extraction.proposed_nodes:
        type_label = n.type.value if hasattr(n.type, "value") else str(n.type)
        key = (type_label, n.name)
        if n.name in override_targets:
            superseded.append((type_label, n.name))
        elif key in existing_names:
            modified.append((type_label, n.name))
        else:
            added.append((type_label, n.name))

    return {
        "added": added,
        "modified": modified,
        "superseded": superseded,
    }


def _print_diff(extraction: SentinelExtraction, classification: dict) -> None:
    a, m, su = classification["added"], classification["modified"], classification["superseded"]

    print()
    print(B(f"   {len(a):>3} ADDITIONS   ")
          + B(f"{len(m):>3} REUSES (existing in KG)   ")
          + B(f"{len(su):>3} SUPERSESSIONS"))
    print()
    if a:
        print(G("   ➕ ADDITIONS — new nodes the KG will gain:"))
        for type_label, name in a[:15]:
            print(f"      ({type_label:<18}) {name}")
        if len(a) > 15:
            print(DIM(f"      … and {len(a) - 15} more"))
        print()
    if m:
        print(C("   ◯  REUSES — Sentinel referenced existing KG nodes by exact name:"))
        for type_label, name in m[:8]:
            print(f"      ({type_label:<18}) {name}")
        if len(m) > 8:
            print(DIM(f"      … and {len(m) - 8} more"))
        print()
    if su:
        print(Y("   ⚠  SUPERSESSIONS — these existing rules will be marked superseded:"))
        for type_label, name in su:
            print(f"      ({type_label:<18}) {name}")
        print()
    n_rels = len(extraction.proposed_relationships)
    n_cites = len(extraction.citations)
    print(DIM(f"   Plus {n_rels} relationships and {n_cites} citation spans."))


# -- the demo flow ------------------------------------------------------------


def demo(slug: str, auto: bool, fast: bool) -> None:
    doc = get_doc(slug)
    if doc is None:
        print(R(f"Unknown slug: {slug!r}. Add it to api/registry.py first."))
        sys.exit(1)
    if not doc.path.exists():
        print(R(f"Source file missing: {doc.path}"))
        sys.exit(1)

    pause = 0.0 if fast else 0.6

    # ── STEP 1 ──
    _step(1, 6, "📥", "New document arriving in the system")
    print(f"   File:    {C(str(doc.path))}")
    print(f"   Slug:    {doc.slug}")
    print(f"   Label:   {doc.label}")
    body = doc.path.read_text(encoding="utf-8")
    print(f"   Size:    {len(body):,} chars")
    print(f"   Preview: {DIM(body.strip().splitlines()[0][:75])}…")
    _pause(pause)

    # ── STEP 2 ──
    _step(2, 6, "🔍", "Retrieving KG context (RAG augmentation)")
    print(DIM("   Pulling existing entities so Sentinel can reference them by exact name"))
    print(DIM("   instead of inventing parallel variants."))
    _pause(pause)
    kg_context = render_kg_context(max_per_type=20)
    n_lines = len(kg_context.splitlines())
    print(f"   {G('✓')} {n_lines} lines of KG context built")
    print(DIM(f"     ({kg_context.splitlines()[0]})"))
    _pause(pause)

    # ── STEP 3 ──
    _step(3, 6, "🤖", "Sentinel extracting (with KG context as RAG)")
    cached_path = extraction_path_for(doc)
    if cached_path.exists() and os.environ.get("FORCE") != "1":
        print(DIM(f"   Cached extraction found: {cached_path}"))
        print(DIM("   Using it (no LLM tokens). Set FORCE=1 to re-extract."))
        _pause(pause)
        from packages.lhs.sentinel.schema import SentinelExtraction as _SE
        extraction = _SE.model_validate(json.loads(cached_path.read_text()))
        elapsed = 0.0
    else:
        print(DIM("   Running Sentinel against the bulletin text."))
        print(DIM("   Sentinel sees the bulletin AND the existing KG digest at once."))
        _pause(pause)
        started = time.time()
        llm = OpenAIAdapter()
        sentinel = Sentinel(llm)
        extraction = sentinel.extract(body, document_label=doc.path.name, kg_context=kg_context)
        elapsed = time.time() - started

    # Compute coverage same way scripts/extract.py does
    intervals = sorted((c.char_start, c.char_end) for c in extraction.citations)
    merged: list[tuple[int, int]] = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    cited_chars = sum(e - s for s, e in merged)
    coverage = cited_chars / extraction.document_total_chars if extraction.document_total_chars else 0.0

    if elapsed > 0:
        print(f"   {G('✓')} Sentinel returned in {elapsed:.1f}s")
    else:
        print(f"   {G('✓')} Loaded from cache (would have called Sentinel otherwise)")
    print(f"     Nodes proposed:   {len(extraction.proposed_nodes)}")
    print(f"     Relationships:    {len(extraction.proposed_relationships)}")
    print(f"     Citations:        {len(extraction.citations)} (coverage: {coverage:.1%})")
    print(f"     Uncited spans:    {len(extraction.uncited_spans)}")
    print()
    print(f"   {DIM('Sentinel summary:')}")
    print(f"     {extraction.summary}")
    _pause(pause)

    # ── STEP 4 ──
    _step(4, 6, "📋", "Reviewing the diff against existing KG")
    classification = _classify_proposals(extraction)
    _print_diff(extraction, classification)
    _pause(pause)

    # Persist extraction so re-runs / UI can see it
    ext_path = extraction_path_for(doc)
    ext_path.parent.mkdir(parents=True, exist_ok=True)
    ext_path.write_text(
        json.dumps(extraction.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    print(f"   {G('✓')} Cached extraction → {DIM(str(ext_path))}")
    _pause(pause)

    # ── STEP 5 ──
    _step(5, 6, "⚖️ ", "Human approval")
    if auto:
        print(f"   {Y('AUTO=1 — skipping interactive prompt, approving automatically')}")
    else:
        try:
            ans = input(f"   Approve and materialize into the KG? [{G('Y')}/n]: ").strip().lower()
        except EOFError:
            ans = "y"
        if ans == "n":
            print(R("   Aborted by user. Extraction remains on disk; no KG changes."))
            return
    _pause(pause)

    # ── STEP 6 ──
    _step(6, 6, "✅", "Materializing diff + applying bulletin")
    with Neo4jGREAdapter() as gre:
        result = materialize(extraction, gre, document_label=slug)
    print(f"   {G('✓')} {len(result.nodes_created)} nodes created, "
          f"{len(result.nodes_reused)} reused, "
          f"{result.relationships_created} relationships, "
          f"{result.citations_created} citations.")
    if result.skipped_proposals:
        print(Y(f"   ⚠ skipped {len(result.skipped_proposals)} proposals:"))
        for s in result.skipped_proposals[:5]:
            print(f"     - {s.type} '{s.name}': {s.reason}")

    # If the extraction included a BulletinOverride, apply it now to bump
    # versions on its OVERRIDES targets.
    has_bulletin_override = any(
        (n.type.value if hasattr(n.type, "value") else str(n.type)) == "BulletinOverride"
        for n in extraction.proposed_nodes
    )
    if has_bulletin_override:
        print()
        print(DIM("   Bulletin contains a BulletinOverride — applying version-bump..."))
        rc = subprocess.call([sys.executable, "-m", "scripts.apply_bulletin", "--all"])
        if rc != 0:
            print(R(f"   apply_bulletin exited {rc}"))

    # ── Wrap-up summary ──
    print()
    print(B("=" * 76))
    print(B(" Done. The KG has been updated."))
    print(B("=" * 76))
    print()
    print(f"   Bulletin:      {C(doc.label)}")
    print(f"   What changed:  {len(classification['added'])} new nodes, "
          f"{len(classification['superseded'])} supersessions")
    print()
    print(DIM("   To see the impact:"))
    print(f"     {C('make e2e')}                  — verify all layouts still pass")
    print(f"     {C('make demo-bulletin')}        — temporal pinning before/after")
    print(f"     {C('make ui')} then open the doc — review in the side-by-side UI")
    print()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default="bulletin-2027-q1-117",
                    help="Registry slug of the bulletin to ingest.")
    ap.add_argument("--auto", action="store_true",
                    help="Skip interactive approval prompt.")
    ap.add_argument("--fast", action="store_true",
                    help="Skip narration pauses.")
    args = ap.parse_args()
    if not args.auto and os.environ.get("AUTO") == "1":
        args.auto = True
    demo(args.slug, auto=args.auto, fast=args.fast)


if __name__ == "__main__":
    main()
