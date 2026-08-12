"""Compile the reviewed Guidewire→FHCF_EXPOSURE mapping spec to the runnable
artifact scripts/run_fhcf.py loads — stage 4 of the agentic-ETL pipeline for
the FHCF data call.

Deterministic: loads materialized/mappings/guidewire_fl_fhcf.reviewed.json
(resolved by target name FHCF_EXPOSURE), compiles it with the mapper's
compiler, dry-runs the projection on the DuckDB warehouse read-only, and
writes materialized/mappings/<label>.compiled.json. Re-running from the same
reviewed spec always writes the same SQL.

Run:  REGULAI_DB=duckdb uv run python -m scripts.compile_fhcf_mapping
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from packages.rhs.mapper.compiler import MAPPINGS_DIR, compile_spec, load_reviewed_spec

TARGET_NAME = "FHCF_EXPOSURE"


def _dry_run(select_sql: str) -> int:
    """Execute the compiled projection read-only on the DuckDB warehouse."""
    import duckdb

    from packages.rhs.duckdb_client import DB_PATH
    # Direct file connection: strip the attached-catalog prefix the pipeline
    # SQL carries (schemas resolve at the file's top level).
    sql = select_sql.replace("INSURANCE_REGULATORY.", "")
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        return len(con.execute(sql).fetchall())
    finally:
        con.close()


def main() -> int:
    spec = load_reviewed_spec(TARGET_NAME)
    if spec is None:
        print(f"No reviewed spec for target {TARGET_NAME} in {MAPPINGS_DIR}/", file=sys.stderr)
        return 1
    spec_path = spec.pop("_path")
    print(f"Compiling {spec_path} → target {TARGET_NAME}")

    cm = compile_spec(spec)
    if cm.excluded:
        print(f"  ⚠ {len(cm.excluded)} mappings excluded: {cm.excluded}", file=sys.stderr)
        return 1

    n = _dry_run(cm.select_sql)
    print(f"  dry-run on DuckDB (read-only): {n} rows · {len(cm.columns)} columns")

    artifact = {
        "target": TARGET_NAME,
        "target_table": cm.target_table,
        "columns": cm.columns,
        "insert_sql": cm.insert_sql,
        "select_sql": cm.select_sql,
        "source_relation": cm.source_relation,
        "compiled_from": spec_path,
        "compiled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "provenance": spec.get("provenance", {}),
    }
    out = Path(spec_path.replace(".reviewed.json", ".compiled.json"))
    out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(f"✓ Compiled artifact written to {out}")
    print("  scripts/run_fhcf.py resolves it by target name and swaps out FHCF_SILVER_SQL.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
