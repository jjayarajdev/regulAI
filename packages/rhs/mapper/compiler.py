"""Stage 4: compile a reviewed MappingSpec into runnable SQL.

The agent proposed a spec; a human reviewed/accepted rows; this turns the
approved rows into an `INSERT INTO <target> (...) SELECT <transforms> FROM
<source>`. Only *accepted*, non-NULL mappings are compiled — a target left
unaccepted (e.g. the TSPR-encoded dates awaiting SME curation) is excluded and
reported, never silently defaulted.

Two SQL forms are produced:
  - insert_sql  — portable INSERT for the real pipeline (runs through query()).
  - select_sql  — a self-contained projection over the source file that the
                  validator executes on an ephemeral DuckDB for a local dry-run.

Sources come in two shapes:
  - a single file (CSV/Parquet) — the original onboarding path; pass
    `source_path` and the projection reads it via read_csv_auto.
  - a warehouse *relation* — the spec carries `source_relation` (a FROM-clause
    body, joins included, with table aliases) and optionally `source_filter`
    (a WHERE predicate). Transforms reference alias-qualified columns. This is
    how the FHCF Guidewire Bronze→Silver mapping compiles.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

DEFAULT_TARGET = "SILVER.TSPR_PREMIUM_STAGING"
MAPPINGS_DIR = Path("materialized/mappings")


class CompiledMapping(BaseModel):
    target_table: str
    columns: list[str]
    select_sql: str
    insert_sql: str
    source_path: str = ""       # file-shaped sources
    source_relation: str = ""   # relation-shaped sources (FROM-clause body)
    excluded: list[dict]  # {target, reason} — rows deliberately not compiled


def _is_accepted(m: dict) -> bool:
    # Reviewed specs carry an explicit `accepted`; raw specs don't — fall back to
    # "accept the confident rows, hold anything flagged for review".
    if "accepted" in m:
        return bool(m["accepted"])
    return not m.get("needs_review", False)


def compile_spec(
    spec: dict,
    source_path: str | Path | None = None,
    target_table: str | None = None,
    dialect: str = "duckdb",
) -> CompiledMapping:
    # The reviewed spec knows its own target table; an explicit argument (or
    # the historical CIOM default when neither is present) still wins.
    target_table = target_table or spec.get("target_table") or DEFAULT_TARGET
    source_relation = (spec.get("source_relation") or "").strip()
    source_filter = (spec.get("source_filter") or "").strip()

    included: list[tuple[str, str]] = []
    excluded: list[dict] = []

    for m in spec.get("mappings", []):
        target = m["target_column"]
        tx = (m.get("transform_sql") or "").strip()
        if not _is_accepted(m):
            excluded.append({"target": target, "reason": "not accepted in review"})
            continue
        if tx == "" or tx.upper() == "NULL":
            excluded.append({"target": target, "reason": "no source column / NULL transform"})
            continue
        included.append((target, tx))

    if not included:
        raise ValueError("no accepted, non-NULL mappings to compile")

    if source_relation:
        # Warehouse relation source: the spec fixes the join; nothing file-based.
        source_ref = source_relation
    elif source_path is not None:
        source_path = Path(source_path)
        if dialect == "duckdb":
            # DuckDB reads the source file directly — no landing table needed.
            source_ref = f"read_csv_auto('{source_path.as_posix()}')"
        else:
            source_ref = f"{source_path.stem.upper()}_STAGING /* land source as a table first */"
    else:
        raise ValueError("spec has no source_relation and no source_path was given")

    select_list = ",\n  ".join(f"{tx} AS {target}" for target, tx in included)
    select_sql = f"SELECT\n  {select_list}\nFROM {source_ref}"
    if source_filter:
        select_sql += f"\nWHERE {source_filter}"
    cols = [t for t, _ in included]
    insert_sql = f"INSERT INTO {target_table} (\n  {', '.join(cols)}\n)\n{select_sql}"

    return CompiledMapping(
        target_table=target_table,
        columns=cols,
        select_sql=select_sql,
        insert_sql=insert_sql,
        source_path="" if source_path is None else str(source_path),
        source_relation=source_relation,
        excluded=excluded,
    )


# ── Compiled-artifact store ───────────────────────────────────────────────
# A reviewed spec compiles to a versioned artifact JSON next to the specs
# (materialized/mappings/<label>.compiled.json) carrying the target registry
# name. Pipelines resolve the artifact by target name — scripts/run_fhcf.py
# swaps its hand-written FHCF_SILVER_SQL for the artifact this way.

def load_compiled_artifact(
    target_name: str, mappings_dir: Path = MAPPINGS_DIR
) -> dict | None:
    """Return the compiled mapping artifact for a registered target name, or
    None when no artifact exists. The artifact dict gains an `_path` key."""
    if not mappings_dir.exists():
        return None
    for p in sorted(mappings_dir.glob("*.compiled.json")):
        try:
            artifact = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if artifact.get("target") == target_name:
            artifact["_path"] = str(p)
            return artifact
    return None


def load_reviewed_spec(
    target_name: str, mappings_dir: Path = MAPPINGS_DIR
) -> dict | None:
    """Return the human-reviewed spec for a registered target name, or None."""
    if not mappings_dir.exists():
        return None
    for p in sorted(mappings_dir.glob("*.reviewed.json")):
        try:
            spec = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if spec.get("target") == target_name:
            spec["_path"] = str(p)
            return spec
    return None
