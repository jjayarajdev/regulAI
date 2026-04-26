"""End-to-end regression test for the LHS slice.

Three checks, all must pass:

  1. `rebuild_kg`            — full reproducible rebuild from disk artifacts
  2. `validate_kg_coverage`  — every populated wire-format layout at 200/200
  3. round-trip               — for each wire-format layout, generate N sample
                                records and validate each one. All must PASS.

Exits 0 on success, 1 on any failure. Wire into CI to catch regressions when
the parser, materialize(), generator, or validator change.

Run:  uv run python -m scripts.regression_test
"""

from __future__ import annotations

import random
import subprocess
import sys

from scripts.generate_sample_submission import fetch_layout, fill_record
from scripts.validate_submission import validate_record

SAMPLES_PER_LAYOUT = 5
LAYOUTS_TO_CHECK = [
    "Premium Record Layout",
    "Loss Record Layout",
    "Notice Record Layout",
    "Notice Count Record Layout",
    "Homeowners Premium Record Layout",
    "Homeowners Loss Record Layout",
]


def _run_step(label: str, argv: list[str]) -> bool:
    print(f"\n━━ {label} ━━")
    rc = subprocess.call([sys.executable, "-m", *argv])
    if rc != 0:
        print(f"  FAIL: {label} exited with {rc}")
        return False
    return True


def _run_round_trip() -> bool:
    print("\n━━ round-trip per layout ━━")
    rng = random.Random(1)
    all_ok = True
    for layout_name in LAYOUTS_TO_CHECK:
        try:
            name, fields = fetch_layout(layout_name)
        except SystemExit:
            print(f"  ✗ {layout_name}: layout missing or empty in KG")
            all_ok = False
            continue
        if not fields:
            print(f"  ✗ {layout_name}: 0 fields connected")
            all_ok = False
            continue

        layout_ok = True
        for i in range(SAMPLES_PER_LAYOUT):
            record, _fills = fill_record(fields, "new-policy", rng)
            res = validate_record(record, fields, record_index=i)
            if not res.ok:
                layout_ok = False
                print(
                    f"  ✗ {layout_name}: record {i + 1} has {len(res.errors)} error(s):"
                )
                for e in res.errors[:3]:
                    print(
                        f"      cols {e.column_start}-{e.column_end} "
                        f"({e.short_code}) [{e.kind}] {e.detail}"
                    )
        if layout_ok:
            print(f"  ✓ {layout_name}: {SAMPLES_PER_LAYOUT}/{SAMPLES_PER_LAYOUT} PASS")
        else:
            all_ok = False
    return all_ok


def main() -> None:
    ok = True
    ok &= _run_step("rebuild_kg", ["scripts.rebuild_kg"])
    if not ok:
        sys.exit(1)
    ok &= _run_step("validate_kg_coverage", ["scripts.validate_kg_coverage"])
    if not ok:
        sys.exit(1)
    ok &= _run_round_trip()

    print("\n" + "=" * 60)
    if ok:
        print("REGRESSION TEST: PASS")
        sys.exit(0)
    else:
        print("REGRESSION TEST: FAIL — see above")
        sys.exit(1)


if __name__ == "__main__":
    main()
