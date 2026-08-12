"""Propose the Guidewire Bronze → FHCF_EXPOSURE mapping through the agentic
schema mapper — Step 2 of the FL FHCF build.

The multi-table sibling of scripts/propose_mapping.py: instead of profiling a
single onboarded file, it runs the mapper's DB-side profiler
(packages.rhs.mapper.crawler.pull_to_profile) over the four Guidewire Bronze
source tables in the DuckDB warehouse

    GW_PC_POLICY (p) · GW_PC_HOPOLICYLINE (line) · GW_PC_HOCOVERAGE (cov) ·
    GW_PC_HODWELLING (dw)   [+ GW_PC_UWCOMPANY (uw) as carrier reference]

merges them into one alias-qualified SourceProfile, and asks the SchemaMapper
agent for a MappingSpec onto the registered FHCF_EXPOSURE target
(SILVER.FHCF_EXPOSURE_STAGING). The join relation is fixed by the pipeline and
passed as source context; the agent maps columns, it does not invent joins.

Raw proposal → materialized/mappings/guidewire_fl_fhcf.mapping.json
(a human review pass then produces guidewire_fl_fhcf.reviewed.json, and
scripts/compile_fhcf_mapping.py compiles that to the artifact run_fhcf loads).

Usage:
    REGULAI_DB=duckdb uv run python -m scripts.propose_fhcf_mapping
    REGULAI_DB=duckdb uv run python -m scripts.propose_fhcf_mapping --profile-only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from packages.rhs.mapper.crawler import pull_to_profile
from packages.rhs.mapper.schema import ColumnProfile, SourceProfile

LABEL = "guidewire_fl_fhcf"
TARGET_NAME = "FHCF_EXPOSURE"
OUT_DIR = Path("materialized/mappings")

# alias → Bronze table. The first four are the row-level join; uw is the
# single-row carrier reference used via a scalar subquery.
SOURCE_TABLES = [
    ("p", "GW_PC_POLICY"),
    ("line", "GW_PC_HOPOLICYLINE"),
    ("cov", "GW_PC_HOCOVERAGE"),
    ("dw", "GW_PC_HODWELLING"),
    ("uw", "GW_PC_UWCOMPANY"),
]

# The pipeline-fixed source relation (identical to the hand-written
# FHCF_SILVER_SQL's FROM/WHERE). Stored on the spec so the compiler can emit
# the full INSERT…SELECT without any file source.
SOURCE_RELATION = (
    "INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY p\n"
    "    JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_HOPOLICYLINE line ON line.policy_id = p.id\n"
    "    JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_HOCOVERAGE cov ON cov.policyline_id = line.id\n"
    "    JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_HODWELLING dw ON dw.policyline_id = line.id"
)
SOURCE_FILTER = "UPPER(TRIM(dw.state)) = 'FL'"

CONTEXT = f"""The source is a live Guidewire PolicyCenter Bronze layer (a relational
warehouse), not a single file. Every column in the profile is alias-qualified
(alias.column) with the table alias it carries in the join below — reference
columns exactly that way in transform_sql.

The row-level join relation is FIXED by the pipeline (do not change it):

FROM {SOURCE_RELATION}
WHERE {SOURCE_FILTER}

One output row per FL property policy. The uw.* columns come from
INSURANCE_REGULATORY.BRONZE.GW_PC_UWCOMPANY, the single-row reporting-carrier
reference table which is NOT part of the row-level join — to use it, emit a
scalar subquery, e.g.
(SELECT ... FROM INSURANCE_REGULATORY.BRONZE.GW_PC_UWCOMPANY uw).

Constant literals are allowed in transform_sql for per-data-call-cycle values
(e.g. the reporting year, the fixed extract file name)."""


def _duckdb_path() -> Path:
    from packages.rhs.duckdb_client import DB_PATH
    return DB_PATH


def build_profile() -> SourceProfile:
    """Stage 1 — run the mapper's DB profiler over each source table, then
    merge into one alias-qualified profile for the propose stage."""
    dsn = f"duckdb://{_duckdb_path().resolve().as_posix()}"
    merged: list[ColumnProfile] = []
    for alias, table in SOURCE_TABLES:
        prof = pull_to_profile(dsn, "BRONZE", table)
        print(f"  profiled BRONZE.{table:<20} ({alias}) · {prof.row_count} rows · "
              f"{len(prof.columns)} columns")
        for c in prof.columns:
            merged.append(c.model_copy(update={"name": f"{alias}.{c.name}"}))

    # Row count of the actual FL join — the shape the mapping produces.
    import duckdb
    con = duckdb.connect(str(_duckdb_path()), read_only=True)
    try:
        n = con.execute(
            f"SELECT COUNT(*) FROM {SOURCE_RELATION.replace('INSURANCE_REGULATORY.', '')} "
            f"WHERE {SOURCE_FILTER.replace('INSURANCE_REGULATORY.', '')}"
        ).fetchone()[0]
    finally:
        con.close()

    return SourceProfile(
        source_label=LABEL, row_count=n, sampled_rows=n, columns=merged,
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Propose the Guidewire→FHCF_EXPOSURE mapping spec.")
    ap.add_argument("--profile-only", action="store_true",
                    help="Profile the source tables and stop (no LLM).")
    ap.add_argument("--out", default=str(OUT_DIR),
                    help="Directory to write the raw spec JSON.")
    args = ap.parse_args()

    print(f"Profiling Guidewire Bronze sources for target {TARGET_NAME}\n")
    profile = build_profile()
    print(f"\n  merged profile: {len(profile.columns)} alias-qualified columns · "
          f"{profile.row_count} FL join rows")

    if args.profile_only:
        return 0

    # Lazy import so --profile-only needs no API key / SDK.
    from packages.adapters.shared.llm.openai_adapter import OpenAIAdapter
    from packages.rhs.mapper.agent import SchemaMapper

    print("\nInvoking SchemaMapper (Propose stage)…")
    llm = OpenAIAdapter()
    mapper = SchemaMapper(llm, target_table=TARGET_NAME)
    spec = mapper.map(profile, context=CONTEXT)

    review = sum(1 for m in spec.mappings if m.needs_review)
    print(f"  model {llm.model} · {len(spec.mappings)} mappings proposed · "
          f"{review} flagged needs_review · "
          f"{len(spec.unmapped_source_columns)} source columns unmapped")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = spec.model_dump()
    # Spec-level source + provenance the (single-file) MappingSpec model does
    # not carry: the fixed relation the compiler needs, and the target's
    # registry name for resolution by pipelines.
    payload["target"] = TARGET_NAME
    payload["source_relation"] = SOURCE_RELATION
    payload["source_filter"] = SOURCE_FILTER
    payload["provenance"] = {
        "stage": "proposed",
        "proposed_by": f"openai:{llm.model}",
        "tokens": llm.last_total_tokens,
    }
    out_path = out_dir / f"{LABEL}.mapping.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\n✓ Raw proposal written to {out_path}")
    print("  (Next: human review → <label>.reviewed.json → scripts.compile_fhcf_mapping.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
