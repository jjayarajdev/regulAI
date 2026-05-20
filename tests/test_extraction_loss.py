"""CI gate on Sentinel → materialize content loss.

Every cached extraction is replayed through materialize() during
`make rebuild-kg` and writes a snapshot to materialized/approved/. This
test reads those snapshots and asserts each one's skip rate is under
threshold. If Sentinel starts dropping more content (or someone tightens a
schema in a way that rejects existing extractions), CI fails loud here
instead of letting the loss go silent.

Threshold rationale:
  After Cluster B (Rule polymorphism + cadence broadening), all live
  rebuild-kg snapshots drop 0% of their proposals. Older one-shot
  snapshots (extraction-stem-named) and demo-only bulletins retain
  small drops because they weren't refreshed; threshold of 10% catches
  any future regression on live extractions while tolerating the
  legacy 2–8% noise.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.config.settings import settings

SKIP_THRESHOLD_PCT = 10.0


def _live_snapshot_paths() -> list[Path]:
    """Only the snapshots regenerated on each `make rebuild-kg` — i.e. those
    whose document_label is a registry slug. One-shot extraction-stem-named
    snapshots from `make materialize-fl` aren't refreshed automatically and
    can lag behind the schema; we don't gate on them."""
    from api.registry import DOCS

    slugs = {d.slug for d in DOCS}
    approved = settings.materialized_dir / "approved"
    return [
        p for p in sorted(approved.glob("*.materialized.json"))
        if p.stem.replace(".materialized", "") in slugs
    ]


@pytest.mark.parametrize("snapshot_path", _live_snapshot_paths(), ids=lambda p: p.stem)
def test_extraction_skip_rate_under_threshold(snapshot_path: Path):
    """Each live (registry-slug-named) extraction's materialize() drops
    < threshold% of proposals. Stale one-shot snapshots aren't gated."""
    snap = json.loads(snapshot_path.read_text(encoding="utf-8"))
    totals = snap.get("totals")
    if totals is None:
        # Older snapshot, no totals block — derive
        created = len(snap.get("nodes_created") or [])
        reused = len(snap.get("nodes_reused") or [])
        skipped = len(snap.get("skipped_proposals") or [])
        proposed = created + reused + skipped
        skip_pct = (skipped / proposed * 100.0) if proposed else 0.0
    else:
        skip_pct = totals["skip_pct"]
        skipped = totals["skipped"]

    if skip_pct >= SKIP_THRESHOLD_PCT:
        # Build a helpful failure message: show the first few dropped items
        # so the failing test points the developer straight at the problem.
        drops = snap.get("skipped_proposals") or []
        lines = [
            f"{snapshot_path.stem}: dropped {skipped} of {totals['proposed'] if totals else '?'} "
            f"proposals ({skip_pct:.1f}% ≥ {SKIP_THRESHOLD_PCT:.1f}% threshold)",
        ]
        for d in drops[:5]:
            lines.append(f"  ✗ {d.get('type','?')} '{d.get('name','')[:60]}': {d.get('reason','')[:120]}")
        if len(drops) > 5:
            lines.append(f"  … and {len(drops) - 5} more")
        pytest.fail("\n".join(lines))


