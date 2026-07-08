"""Propose a source→canonical mapping for an arbitrary insurer dataset.

The RHS mirror of `scripts/extract.py`: instead of extracting a KG from a
regulation document, it profiles a data file and asks the agent to map it onto
SILVER.TSPR_PREMIUM_STAGING — the first slice of agentic ETL.

Usage:
    uv run python -m scripts.propose_mapping <file.csv|file.parquet>
    uv run python -m scripts.propose_mapping <file> --profile-only   # no API key needed
    uv run python -m scripts.propose_mapping <file> --out materialized/mappings

`--profile-only` runs the deterministic profiler and stops — useful to show the
input the agent reasons over without spending a token.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from packages.rhs.mapper.profiler import profile_file


def _print_profile(profile) -> None:
    print(f"\nSOURCE: {profile.source_label}  ·  {profile.row_count} rows "
          f"(profiled {profile.sampled_rows})  ·  {len(profile.columns)} columns\n")
    print(f"  {'column':<28} {'type':<14} {'null%':>6} {'distinct':>9}  samples")
    print("  " + "-" * 90)
    for c in profile.columns:
        samples = ", ".join(c.sample_values[:3])
        print(f"  {c.name:<28} {c.inferred_type:<14} {c.null_rate*100:>5.1f}% "
              f"{c.distinct_count:>9}  {samples[:40]}")


def _print_spec(spec) -> None:
    mapped = [m for m in spec.mappings if m.source_column]
    review = [m for m in spec.mappings if m.needs_review]
    print(f"\nMAPPING SPEC → {spec.target_table}")
    print(f"  {len(mapped)} mapped · {len(review)} need review · "
          f"{len(spec.unmapped_source_columns)} source columns unmapped\n")
    print(f"  {'target':<22} {'source':<24} {'conf':>4}  R  transform / rationale")
    print("  " + "-" * 96)
    for m in sorted(spec.mappings, key=lambda x: (not x.needs_review, -x.confidence)):
        flag = "!" if m.needs_review else " "
        src = m.source_column or "—"
        print(f"  {m.target_column:<22} {src:<24} {m.confidence:>4.2f}  {flag}  "
              f"{(m.transform_sql or '')[:34]}")
        print(f"  {'':<22} {'':<24} {'':>4}     └ {m.rationale[:70]}")
    if spec.unmapped_source_columns:
        print("\n  UNMAPPED SOURCE COLUMNS:")
        for u in spec.unmapped_source_columns:
            print(f"    · {u.name}: {u.reason}")
    if spec.notes:
        print(f"\n  NOTES: {spec.notes}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Propose a source→TSPR mapping spec.")
    ap.add_argument("path", help="Source .csv or .parquet file")
    ap.add_argument("--profile-only", action="store_true", help="Profile and stop (no LLM).")
    ap.add_argument("--out", default="materialized/mappings", help="Directory to write the spec JSON.")
    args = ap.parse_args()

    profile = profile_file(args.path)
    _print_profile(profile)

    if args.profile_only:
        return 0

    # Lazy import so --profile-only needs no API key / SDK.
    from packages.adapters.shared.llm.openai_adapter import OpenAIAdapter
    from packages.rhs.mapper.agent import SchemaMapper

    print("\nInvoking SchemaMapper…")
    mapper = SchemaMapper(OpenAIAdapter())
    spec = mapper.map(profile)
    _print_spec(spec)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{profile.source_label}.mapping.json"
    out_path.write_text(json.dumps(spec.model_dump(), indent=2), encoding="utf-8")
    print(f"\n✓ Spec written to {out_path}")
    print("  (Next stages: human review → compile to INSERT…SELECT → validate.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
