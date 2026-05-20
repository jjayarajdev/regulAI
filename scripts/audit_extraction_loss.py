"""Audit extraction → materialization content loss.

Scans every `materialized/approved/*.materialized.json` snapshot and reports:

  - How many proposals each extraction made
  - How many became KG nodes (created + reused)
  - How many were dropped by schema validation (skipped_proposals)
  - The skip rate per extraction

Exits non-zero if any extraction's skip rate exceeds --threshold (default 25%).

Why this exists:
  Before this script, content loss was silent. When Sentinel proposed a
  Rule without `rule_number` (e.g., from a regulator memo whose provisions
  aren't section-numbered like statutes), proposed_to_typed_node() raised
  ValueError, materialize() caught it and appended to skipped_proposals,
  and nothing surfaced unless you read the snapshot JSON by hand.

  This audit makes that loss loud — both for humans (`make
  audit-extraction-loss`) and for CI (tests/test_extraction_loss.py).

Run: uv run python -m scripts.audit_extraction_loss [--threshold 25.0] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from packages.config.settings import settings


def _load_snapshots(approved_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(approved_dir.glob("*.materialized.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [warn] {path.name}: failed to parse ({e})", file=sys.stderr)
            continue
        rows.append({"path": path, "data": data})
    return rows


def _totals(snapshot: dict) -> dict:
    """Backfill totals on older snapshots (pre-audit feature) by counting
    list lengths. Newer snapshots already carry a `totals` block."""
    if "totals" in snapshot:
        return snapshot["totals"]
    created = len(snapshot.get("nodes_created") or [])
    reused = len(snapshot.get("nodes_reused") or [])
    skipped = len(snapshot.get("skipped_proposals") or [])
    proposed = created + reused + skipped
    return {
        "proposed": proposed,
        "created": created,
        "reused": reused,
        "skipped": skipped,
        "skip_pct": (skipped / proposed * 100.0) if proposed else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--threshold",
        type=float,
        default=25.0,
        help="Fail if any extraction's skip_pct exceeds this (default 25.0)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print every skipped proposal, not just the offending ones",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=settings.materialized_dir / "approved",
        help="Directory of *.materialized.json snapshots",
    )
    args = parser.parse_args()

    rows = _load_snapshots(args.dir)
    if not rows:
        print(f"No snapshots found in {args.dir}")
        return 0

    print(f"Extraction loss audit — {len(rows)} snapshots in {args.dir}")
    print(f"Threshold: skip_pct must be < {args.threshold:.1f}%\n")
    print(f"  {'doc':<45}  {'prop':>5} {'kept':>5} {'drop':>5}  {'pct':>6}")
    print(f"  {'-'*45}  {'-'*5} {'-'*5} {'-'*5}  {'-'*6}")

    offenders: list[tuple[str, dict]] = []
    total_proposed = total_kept = total_skipped = 0

    for row in rows:
        snap = row["data"]
        doc = snap.get("document_label", row["path"].stem)
        t = _totals(snap)
        kept = t.get("created", 0) + t.get("reused", 0)
        pct = t.get("skip_pct", 0.0)
        total_proposed += t.get("proposed", 0)
        total_kept += kept
        total_skipped += t.get("skipped", 0)
        flag = " ✗" if pct >= args.threshold else ""
        print(f"  {doc[:45]:<45}  {t.get('proposed',0):>5} {kept:>5} {t.get('skipped',0):>5}  {pct:>5.1f}%{flag}")
        if pct >= args.threshold:
            offenders.append((doc, snap))

    grand_pct = (total_skipped / total_proposed * 100.0) if total_proposed else 0.0
    print(f"  {'-'*45}  {'-'*5} {'-'*5} {'-'*5}  {'-'*6}")
    print(f"  {'TOTAL':<45}  {total_proposed:>5} {total_kept:>5} {total_skipped:>5}  {grand_pct:>5.1f}%")

    # Detail per offender
    if offenders:
        print(f"\n{'='*72}")
        print(f"{len(offenders)} extraction(s) over {args.threshold:.1f}% threshold:")
        for doc, snap in offenders:
            print(f"\n  {doc}")
            for sp in snap.get("skipped_proposals", []):
                print(f"    ✗ {sp.get('type','?')}: {sp.get('name','')[:70]}")
                print(f"      reason: {sp.get('reason','')[:100]}")
                if sp.get("char_start") is not None:
                    print(f"      source span: [{sp['char_start']}..{sp['char_end']}]")
        return 1

    # Verbose: show all skips even when under threshold
    if args.verbose:
        print(f"\n{'='*72}")
        print("All skipped proposals (under threshold, informational):")
        for row in rows:
            snap = row["data"]
            skipped = snap.get("skipped_proposals") or []
            if not skipped:
                continue
            doc = snap.get("document_label", row["path"].stem)
            print(f"\n  {doc}")
            for sp in skipped:
                print(f"    ✗ {sp.get('type','?')}: {sp.get('name','')[:70]}")
                print(f"      reason: {sp.get('reason','')[:100]}")

    print("\nOK — all extractions under threshold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
