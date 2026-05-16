"""Generate every Snowflake reference table from the KG.

Walks a curated list of TICO CodeLists in our KG and emits one SQL file
per target reference table. The reason-code map keeps its own dedicated
generator (it has the constraint flags pulled inline as a separate
column set); everything else flows through the generic codelist
generator.

Run: `make build-reference-all`
"""

from __future__ import annotations

from pathlib import Path

from packages.rhs.codelist_generator import ReferenceSpec, materialize

OUT_DIR = Path("materialized/reference")

SPECS = [
    ReferenceSpec(
        section="B.4",
        description="Line of Business codes (LOB) — TSPR field col 41",
        codelist_name="Line of Business (LOB) — Loss Record Layout col41",
        target_table="TSPR_LOB_CODES",
    ),
    ReferenceSpec(
        section="B.5",
        description="Form (Policy) codes — TSPR field col 50",
        codelist_name="Form (Policy) (FM) — Premium Record Layout col50",
        target_table="TSPR_FORM_CODES",
    ),
    ReferenceSpec(
        section="B.12",
        description="Cause of Loss codes — TSPR field cols 90-91",
        codelist_name="Cause of Loss Code List",
        target_table="TSPR_CAUSE_OF_LOSS_CODES",
    ),
    ReferenceSpec(
        section="B.8A",
        description="Roof Coverage Type codes — TSPR field col 153",
        codelist_name="Roof Coverage Type (RCT) — Loss Record Layout col153",
        target_table="TSPR_ROOF_COVERAGE_TYPE_CODES",
    ),
]


def main() -> int:
    print("Building reference tables from KG…")
    print()
    total_rows = 0
    paths: list[tuple[ReferenceSpec, Path, int]] = []
    for spec in SPECS:
        try:
            path, count = materialize(spec, OUT_DIR)
            paths.append((spec, path, count))
            total_rows += count
            print(f"  ✓ {spec.section:<6} {spec.target_table:<32} {count:>4} rows  → {path}")
        except Exception as e:
            print(f"  ✗ {spec.section:<6} {spec.target_table:<32} FAILED: {e}")
    print()
    print(f"Total: {len(paths)} files, {total_rows} rows")
    print()
    print("Next: make load-reference-all")
    return 0 if paths else 1


if __name__ == "__main__":
    raise SystemExit(main())
