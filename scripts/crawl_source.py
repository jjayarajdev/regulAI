"""Crawl a source database to determine which tables feed the canonical model.

Stage 0 of agentic ETL, end to end from the command line:
    1. introspect  — read the DB catalog (schemas/tables/columns/keys) generically
    2. plan        — agent scores each table's relevance + role, finds the joins
    3. (hand off)  — pull an approved table → SourceProfile → propose_mapping

Usage:
    # deterministic catalog only — no API key needed
    uv run python -m scripts.crawl_source data/source_dbs/pas_export.duckdb --profile-only

    # full: catalog + agent crawl plan
    uv run python -m scripts.crawl_source data/source_dbs/legacy_admin.sqlite

    # postgres (needs `uv sync --extra crawler`)
    uv run python -m scripts.crawl_source postgresql://localhost/regulai_src

    # after planning, pull one table into a source profile for the mapper
    uv run python -m scripts.crawl_source <dsn> --pull pas.policy

Accepts a duckdb://, sqlite://, or postgresql:// DSN, or a bare *.duckdb / *.sqlite path.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from packages.rhs.mapper.crawler import introspect, pull_to_profile


def _print_catalog(cat) -> None:
    print(f"\nCATALOG: {cat.database}  ·  engine {cat.engine}  ·  {cat.table_count} tables\n")
    for t in cat.tables:
        pk = ",".join(c.name for c in t.columns if c.primary_key) or "—"
        print(f"  ▸ {t.qualified:<28} {t.row_count:>6} rows   pk: {pk}")
        for c in t.columns:
            flags = []
            if c.primary_key:
                flags.append("pk")
            if c.references:
                flags.append(f"→{c.references}")
            if not c.nullable:
                flags.append("not-null")
            tag = f"  [{', '.join(flags)}]" if flags else ""
            print(f"      {c.name:<22} {c.dtype:<16}{tag}")


def _print_plan(plan) -> None:
    print(f"\nCRAWL PLAN → {plan.target_table}")
    ordered = sorted(plan.candidates, key=lambda c: -c.relevance)
    print(f"  {'table':<26} {'role':<10} {'rel':>4}  R  keys / rationale")
    print("  " + "-" * 92)
    for c in ordered:
        flag = "!" if c.needs_review else " "
        keys = ",".join(c.key_columns) or "—"
        print(f"  {f'{c.schema_name}.{c.table}':<26} {c.role:<10} {c.relevance:>4.2f}  {flag}  {keys}")
        print(f"  {'':<26} {'':<10} {'':>4}     └ {c.rationale[:70]}")
    if plan.suggested_join:
        print(f"\n  JOIN: {plan.suggested_join}")
    if plan.notes:
        print(f"\n  NOTES: {plan.notes}")


def _print_profile(profile) -> None:
    print(f"\nPULLED PROFILE: {profile.source_label}  ·  {profile.row_count} rows "
          f"(sampled {profile.sampled_rows})  ·  {len(profile.columns)} columns\n")
    print(f"  {'column':<24} {'type':<12} {'null%':>6} {'distinct':>9}  samples")
    print("  " + "-" * 86)
    for c in profile.columns:
        samples = ", ".join(c.sample_values[:3])
        print(f"  {c.name:<24} {c.inferred_type:<12} {c.null_rate*100:>5.1f}% "
              f"{c.distinct_count:>9}  {samples[:36]}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Crawl a source DB for canonical-mapping candidates.")
    ap.add_argument("dsn", help="duckdb://, sqlite://, postgresql:// DSN, or a *.duckdb/*.sqlite path")
    ap.add_argument("--profile-only", action="store_true", help="Catalog only — no LLM, no API key.")
    ap.add_argument("--pull", metavar="SCHEMA.TABLE", help="Pull one table into a SourceProfile and stop.")
    ap.add_argument("--limit", type=int, default=5000, help="Row cap for --pull (default 5000).")
    ap.add_argument("--out", default="materialized/crawls", help="Directory to write the crawl plan JSON.")
    args = ap.parse_args()

    # --pull: the human-gated extract that hands off to propose_mapping.
    if args.pull:
        if "." not in args.pull:
            print("--pull needs SCHEMA.TABLE (e.g. pas.policy, main.POLMAST)", file=sys.stderr)
            return 2
        schema, table = args.pull.split(".", 1)
        profile = pull_to_profile(args.dsn, schema, table, limit=args.limit)
        _print_profile(profile)
        print("\n  Next: feed this table to the mapper — "
              "propose → review → compile → validate.")
        return 0

    catalog = introspect(args.dsn)
    _print_catalog(catalog)

    if args.profile_only:
        return 0

    # Lazy import so --profile-only needs no API key / SDK.
    from packages.adapters.shared.llm.openai_adapter import OpenAIAdapter
    from packages.rhs.mapper.crawler_agent import CrawlPlanner

    print("\nInvoking CrawlPlanner…")
    plan = CrawlPlanner(OpenAIAdapter()).plan(catalog)
    _print_plan(plan)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    label = catalog.database.replace("/", "_")
    out_path = out_dir / f"{label}.crawl.json"
    out_path.write_text(json.dumps(plan.model_dump(), indent=2), encoding="utf-8")
    print(f"\n✓ Crawl plan written to {out_path}")
    print("  Approve a table, then: "
          f"uv run python -m scripts.crawl_source {args.dsn} --pull <schema.table>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
