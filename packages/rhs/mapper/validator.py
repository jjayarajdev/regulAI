"""Stage 5: validate the compiled load — fail-closed.

Executes the compiled projection on an ephemeral in-memory DuckDB (reading the
source file directly, no persistent state) and checks the output against the
target contract:

  - row-count parity  — output rows == source rows (no silent drops/fan-out)
  - required coverage — every REQUIRED target is populated and non-null
  - numeric conformance — number-typed targets actually landed numeric

`ok` is True only if every check passes. A REQUIRED target that was excluded in
review (e.g. the TSPR-encoded dates awaiting SME curation) fails the gate by
design — a partially-mapped filing must not pass as complete.

The compiled transforms are Spark-flavored (the agent's dialect); a tiny shim
adapts the few that differ for the local DuckDB dry-run. Production runs the
portable insert_sql through the query() seam on the real engine.
"""

from __future__ import annotations

import re

import duckdb

from packages.rhs.mapper.compiler import CompiledMapping
from packages.rhs.mapper.target_schema import TSPR_PREMIUM_STAGING

_TARGET_BY_NAME = {c.name: c for c in TSPR_PREMIUM_STAGING}
_REQUIRED = [c for c in TSPR_PREMIUM_STAGING if c.required and not c.system_populated]


def _to_duckdb(sql: str) -> str:
    """Adapt the handful of Spark spellings the agent emits to DuckDB."""
    return re.sub(r"\bAS\s+STRING\b", "AS VARCHAR", sql, flags=re.IGNORECASE)


def validate_compiled(compiled: CompiledMapping) -> dict:
    con = duckdb.connect()  # in-memory; nothing persisted
    try:
        src = compiled.source_path
        src_count = con.execute(
            f"SELECT COUNT(*) FROM read_csv_auto('{src}')"
        ).fetchone()[0]

        con.execute(f"CREATE TABLE mapping_output AS {_to_duckdb(compiled.select_sql)}")
        out_count = con.execute("SELECT COUNT(*) FROM mapping_output").fetchone()[0]
        col_types = {r[0]: str(r[1]) for r in con.execute("DESCRIBE mapping_output").fetchall()}

        checks: list[dict] = []

        checks.append({
            "name": "row_count_parity",
            "ok": src_count == out_count,
            "detail": f"source={src_count} output={out_count}",
        })

        compiled_cols = set(compiled.columns)
        for c in _REQUIRED:
            if c.name not in compiled_cols:
                checks.append({
                    "name": f"required:{c.name}",
                    "ok": False,
                    "detail": "required target not populated — excluded in review, needs curation/SME sign-off",
                })
                continue
            nulls = con.execute(
                f"SELECT COUNT(*) FROM mapping_output WHERE {c.name} IS NULL"
            ).fetchone()[0]
            checks.append({
                "name": f"required:{c.name}",
                "ok": nulls == 0,
                "detail": "populated, no nulls" if nulls == 0 else f"{nulls} null(s)",
            })

        for name in compiled.columns:
            if _TARGET_BY_NAME.get(name) and _TARGET_BY_NAME[name].dtype == "number":
                t = col_types.get(name, "").upper()
                numeric = any(k in t for k in
                              ("INT", "DECIMAL", "DOUBLE", "FLOAT", "NUMERIC", "HUGEINT"))
                checks.append({
                    "name": f"numeric:{name}",
                    "ok": numeric,
                    "detail": f"type={col_types.get(name)}",
                })

        ok = all(ch["ok"] for ch in checks)
        return {
            "ok": ok,
            "row_count_source": src_count,
            "row_count_output": out_count,
            "compiled_columns": compiled.columns,
            "excluded": compiled.excluded,
            "checks": checks,
        }
    finally:
        con.close()
