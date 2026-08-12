"""The agent-compiled FHCF mapping is provably equivalent to the hand-written
transform it replaced.

Loads the reviewed Guidewire→FHCF_EXPOSURE spec (materialized/mappings/,
resolved by target name), recompiles it with the mapper's compiler, dry-runs
it on the DuckDB warehouse, and proves the compiled INSERT produces EXACTLY
the same SILVER.FHCF_EXPOSURE_STAGING contents as scripts/run_fhcf.py's
hand-written FHCF_SILVER_SQL reference — same 15 rows, same values, via an
EXCEPT check in both directions.

Run:  REGULAI_DB=duckdb uv run pytest tests/test_fhcf_mapping_compile.py -q
"""

from __future__ import annotations

import os

os.environ.setdefault("REGULAI_DB", "duckdb")

import pytest

TARGET_NAME = "FHCF_EXPOSURE"
STAGING = "INSURANCE_REGULATORY.SILVER.FHCF_EXPOSURE_STAGING"
REF_SNAPSHOT = "INSURANCE_REGULATORY.SILVER.FHCF_STAGING_HANDWRITTEN_REF"


def _duckdb_ready() -> bool:
    try:
        from packages.rhs.db import backend_name, query
        if backend_name() != "duckdb":
            return False
        query("SELECT 1 AS one")
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _duckdb_ready(),
    reason="DuckDB backend unavailable (set REGULAI_DB=duckdb and run scripts.seed_duckdb)",
)


@pytest.fixture(scope="module")
def fl_bronze():
    """Seed the 15 FL Guidewire Bronze policies once for this module."""
    from scripts.run_fhcf import ensure_tables
    from scripts.seed_fl_fhcf import _seed_bronze

    n = _seed_bronze()
    ensure_tables()
    return n


@pytest.fixture(scope="module")
def reviewed_spec():
    from packages.rhs.mapper.compiler import load_reviewed_spec

    spec = load_reviewed_spec(TARGET_NAME)
    assert spec is not None, "no reviewed spec for target FHCF_EXPOSURE in materialized/mappings/"
    return spec


@pytest.fixture(scope="module")
def artifact():
    from packages.rhs.mapper.compiler import load_compiled_artifact

    art = load_compiled_artifact(TARGET_NAME)
    assert art is not None, "no compiled artifact for target FHCF_EXPOSURE in materialized/mappings/"
    return art


def test_spec_loads_and_covers_every_column(reviewed_spec):
    """Every FHCF business column is mapped and accepted; none left to chance."""
    from scripts.run_fhcf import FHCF_COLUMNS

    mapped = [m["target_column"] for m in reviewed_spec["mappings"]]
    assert mapped == FHCF_COLUMNS
    assert all(m.get("accepted") for m in reviewed_spec["mappings"])
    # The relation-shaped source is present — the compiler needs no file.
    assert reviewed_spec.get("source_relation")
    assert reviewed_spec.get("source_filter")


def test_spec_compiles_and_matches_stored_artifact(reviewed_spec, artifact):
    """The compiler is deterministic: recompiling the reviewed spec reproduces
    the stored artifact's SQL (no drift between spec and artifact)."""
    from packages.rhs.mapper.compiler import compile_spec

    cm = compile_spec(reviewed_spec)
    assert cm.excluded == []
    assert cm.target_table == artifact["target_table"]
    assert cm.columns == artifact["columns"]
    assert cm.insert_sql == artifact["insert_sql"]


def test_compiled_select_dry_runs_on_duckdb(fl_bronze, artifact):
    """The compiled projection executes on the warehouse: one row per FL policy."""
    from packages.rhs.db import query

    rows = query(artifact["select_sql"])
    assert len(rows) == 15
    assert {r["policy_number"] for r in rows} == {f"POL-FL-{i:04d}" for i in range(1001, 1016)}


def test_compiled_equals_handwritten_exactly(fl_bronze, artifact):
    """EXCEPT in both directions: compiled INSERT and hand-written
    FHCF_SILVER_SQL load byte-identical business rows into Silver."""
    from packages.rhs.db import query
    from scripts.run_fhcf import FHCF_COLUMNS, FHCF_SILVER_SQL, silver_fhcf

    cols = ", ".join(FHCF_COLUMNS)
    try:
        # Hand-written reference load → snapshot the business columns.
        query(f"TRUNCATE TABLE {STAGING}")
        query(FHCF_SILVER_SQL)
        query(f"CREATE OR REPLACE TABLE {REF_SNAPSHOT} AS SELECT {cols} FROM {STAGING}")

        # Compiled load into the same (truncated) staging table.
        query(f"TRUNCATE TABLE {STAGING}")
        query(artifact["insert_sql"])

        n_ref = query(f"SELECT COUNT(*) AS n FROM {REF_SNAPSHOT}")[0]["n"]
        n_cmp = query(f"SELECT COUNT(*) AS n FROM {STAGING}")[0]["n"]
        assert n_ref == n_cmp == 15

        only_in_compiled = query(
            f"SELECT COUNT(*) AS n FROM "
            f"(SELECT {cols} FROM {STAGING} EXCEPT SELECT {cols} FROM {REF_SNAPSHOT})"
        )[0]["n"]
        only_in_handwritten = query(
            f"SELECT COUNT(*) AS n FROM "
            f"(SELECT {cols} FROM {REF_SNAPSHOT} EXCEPT SELECT {cols} FROM {STAGING})"
        )[0]["n"]
        assert only_in_compiled == 0, f"{only_in_compiled} compiled rows differ from hand-written"
        assert only_in_handwritten == 0, f"{only_in_handwritten} hand-written rows differ from compiled"
    finally:
        query(f"DROP TABLE IF EXISTS {REF_SNAPSHOT}")
        # Leave Silver in its normal pipeline state (audit columns stamped).
        silver_fhcf()


def test_pipeline_uses_compiled_artifact(fl_bronze):
    """silver_fhcf() resolves and executes the compiled artifact, not the fallback."""
    import scripts.run_fhcf as run_fhcf

    assert run_fhcf.silver_fhcf() == 15
    assert run_fhcf.LAST_SILVER_MAPPING is not None
    assert run_fhcf.LAST_SILVER_MAPPING.startswith("compiled:"), (
        f"expected compiled mapping path, got {run_fhcf.LAST_SILVER_MAPPING}"
    )
