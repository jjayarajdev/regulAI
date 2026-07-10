"""Resolve transforms for a source table and show them running.

Stage 4 (transform) driven by the registry + agent, demonstrated end to end:
    1. pull    — crawl a bounded sample of the table (extract)
    2. resolve — agent picks a registry rule + params per target column
    3. compile — deterministic code turns each choice into tested DuckDB SQL
    4. run     — apply the SQL to the real sample and print before → after

Usage:
    uv run python -m scripts.resolve_transforms data/source_dbs/legacy_admin.sqlite main.PREMDTL
    uv run python -m scripts.resolve_transforms data/source_dbs/pas_export.duckdb pas.policy --profile-only

`--profile-only` stops after the pull (no LLM / API key) so you can see the input
the agent reasons over. Any duckdb://, sqlite://, postgresql:// DSN or bare file
path the crawler accepts works here.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb

from packages.rhs.mapper.crawler import connect, pull_to_profile


def _load_sample(dsn: str, schema: str, table: str, limit: int):
    """Fetch the sample rows into an in-memory DuckDB `src` table (all VARCHAR —
    legacy sources arrive as text anyway) so transforms can run live over them."""
    con = connect(dsn)
    try:
        names, rows = con.sample(schema, table, limit)
    finally:
        con.close()
    mem = duckdb.connect(":memory:")
    cols_ddl = ", ".join(f'"{n}" VARCHAR' for n in names)
    mem.execute(f"CREATE TABLE src ({cols_ddl})")
    if rows:
        placeholders = ",".join("?" * len(names))
        mem.executemany(
            f"INSERT INTO src VALUES ({placeholders})",
            [[None if v is None else str(v) for v in r] for r in rows],
        )
    return mem, names


def _print_profile(profile) -> None:
    print(f"\nPULLED: {profile.source_label}  ·  {profile.row_count} rows "
          f"(sampled {profile.sampled_rows})  ·  {len(profile.columns)} columns\n")
    for c in profile.columns:
        samples = ", ".join(c.sample_values[:3])
        print(f"  {c.name:<22} {c.inferred_type:<10}  {samples[:44]}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Resolve + run registry transforms for a source table.")
    ap.add_argument("dsn", help="duckdb://, sqlite://, postgresql:// DSN or a *.duckdb/*.sqlite path")
    ap.add_argument("table", help="SCHEMA.TABLE to transform (e.g. main.PREMDTL, pas.policy)")
    ap.add_argument("--profile-only", action="store_true", help="Pull + profile, no LLM.")
    ap.add_argument("--limit", type=int, default=5000, help="Row cap for the pull (default 5000).")
    ap.add_argument("--show", type=int, default=4, help="Rows to show in before→after (default 4).")
    ap.add_argument("--out", default="materialized/transforms", help="Directory to write the plan JSON.")
    args = ap.parse_args()

    if "." not in args.table:
        print("table must be SCHEMA.TABLE (e.g. main.PREMDTL, pas.policy)", file=sys.stderr)
        return 2
    schema, table = args.table.split(".", 1)

    profile = pull_to_profile(args.dsn, schema, table, limit=args.limit)
    _print_profile(profile)
    if args.profile_only:
        return 0

    # Lazy import so --profile-only needs no API key / SDK.
    from packages.adapters.shared.llm.openai_adapter import OpenAIAdapter
    from packages.rhs.mapper.transform_agent import TransformResolver, compiled_sql

    print("\nInvoking TransformResolver…")
    plan = TransformResolver(OpenAIAdapter()).resolve(profile)

    # ── the plan ─────────────────────────────────────────────────────────────
    print(f"\nTRANSFORM PLAN → {plan.target_table}")
    print(f"  {'target':<20} {'source':<16} {'rule chain':<30} {'conf':>4}  R")
    print("  " + "-" * 92)
    mem, _ = _load_sample(args.dsn, schema, table, args.show)
    live: list[tuple] = []
    for s in sorted(plan.transforms, key=lambda x: (not x.needs_review, -x.confidence)):
        flag = "!" if s.needs_review else " "
        chain = " │ ".join(c.rule_id for c in s.rules) or "—"
        is_null = all(c.rule_id == "null" for c in s.rules) if s.rules else True
        sql, err = compiled_sql(s)
        print(f"  {s.target_column:<20} {(s.source_column or '—'):<16} {chain:<30} "
              f"{s.confidence:>4.2f}  {flag}")
        if err:
            print(f"  {'':<20} {'':<16} ⚠ {err[:64]}")
        elif s.source_column and not is_null:
            live.append((s, sql))

    # ── run a few live before → after ────────────────────────────────────────
    if live:
        print(f"\nLIVE (first {args.show} rows, source → transformed):")
        for s, sql in live:
            chain = " │ ".join(c.rule_id for c in s.rules)
            try:
                rows = mem.execute(
                    f'SELECT "{s.source_column}" AS before, {sql} AS after FROM src LIMIT {args.show}'
                ).fetchall()
            except Exception as e:
                print(f"\n  {s.target_column}  [{chain}]  ⚠ {type(e).__name__}: {str(e)[:60]}")
                continue
            print(f"\n  {s.target_column}  ←  {s.source_column}  [{chain}]")
            for before, after in rows:
                print(f"      {str(before)[:28]:<30} →  {after}")

    if plan.unresolved_targets:
        print(f"\n  UNRESOLVED (fail-closed): {', '.join(plan.unresolved_targets)}")
    if plan.notes:
        print(f"\n  NOTES: {plan.notes}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{profile.source_label}.transform.json"
    out_path.write_text(json.dumps(plan.model_dump(), indent=2), encoding="utf-8")
    print(f"\n✓ Transform plan written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
