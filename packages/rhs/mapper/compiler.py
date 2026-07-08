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
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

DEFAULT_TARGET = "SILVER.TSPR_PREMIUM_STAGING"


class CompiledMapping(BaseModel):
    target_table: str
    columns: list[str]
    select_sql: str
    insert_sql: str
    source_path: str
    excluded: list[dict]  # {target, reason} — rows deliberately not compiled


def _is_accepted(m: dict) -> bool:
    # Reviewed specs carry an explicit `accepted`; raw specs don't — fall back to
    # "accept the confident rows, hold anything flagged for review".
    if "accepted" in m:
        return bool(m["accepted"])
    return not m.get("needs_review", False)


def compile_spec(
    spec: dict,
    source_path: str | Path,
    target_table: str = DEFAULT_TARGET,
    dialect: str = "duckdb",
) -> CompiledMapping:
    source_path = Path(source_path)
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

    select_list = ",\n  ".join(f"{tx} AS {target}" for target, tx in included)
    if dialect == "duckdb":
        # DuckDB reads the source file directly — no landing table needed.
        source_ref = f"read_csv_auto('{source_path.as_posix()}')"
    else:
        source_ref = f"{source_path.stem.upper()}_STAGING /* land source as a table first */"

    select_sql = f"SELECT\n  {select_list}\nFROM {source_ref}"
    cols = [t for t, _ in included]
    insert_sql = f"INSERT INTO {target_table} (\n  {', '.join(cols)}\n)\n{select_sql}"

    return CompiledMapping(
        target_table=target_table,
        columns=cols,
        select_sql=select_sql,
        insert_sql=insert_sql,
        source_path=str(source_path),
        excluded=excluded,
    )
