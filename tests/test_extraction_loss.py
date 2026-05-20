"""CI gate on Sentinel → materialize content loss.

Every cached extraction is replayed through materialize() during
`make rebuild-kg` and writes a snapshot to materialized/approved/. This
test reads those snapshots and asserts each one's skip rate is under
threshold. If Sentinel starts dropping more content (or someone tightens a
schema in a way that rejects existing extractions), CI fails loud here
instead of letting the loss go silent.

Threshold rationale:
  As of the FL ingestion (P3.6), the OIR memo drops ~20% of its
  proposals because Rule schema requires section + rule_number (statute-
  shaped) while memo provisions aren't section-numbered. We're temporarily
  past the ideal 10% target. Threshold is set to 30% so the test passes
  now but will catch regressions; tighten to 10% once Cluster B (Rule
  polymorphism) lands and recovers the dropped memo provisions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.config.settings import settings

# Tighten this once Cluster B (Rule polymorphism) is shipped.
SKIP_THRESHOLD_PCT = 30.0


def _snapshot_paths() -> list[Path]:
    approved = settings.materialized_dir / "approved"
    return sorted(approved.glob("*.materialized.json"))


@pytest.mark.parametrize("snapshot_path", _snapshot_paths(), ids=lambda p: p.stem)
def test_extraction_skip_rate_under_threshold(snapshot_path: Path):
    """Each cached extraction's materialize() drops < threshold% of proposals."""
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


