"""FL FHCF medallion transform, end-to-end on the DuckDB backend.

tests/test_fl_rules_execute.py proves the 10 rules' SQL semantics against
hand-built fixtures. This file proves the TRANSFORM: seed the 15 FL
Guidewire Bronze policies (scripts.seed_fl_fhcf) → run the Bronze→Silver→
Gold FHCF transforms (scripts.run_fhcf) → assert the Gold table has the
right rows, the filing_batch_id stamp, and that the 5 dirty policies each
trigger exactly their intended rule when the REFERENCE-table rule SQL is
executed against GOLD.FHCF_EXPOSURE_RECORDS the same way /validate does.

Run:  REGULAI_DB=duckdb uv run pytest tests/test_fhcf_pipeline.py -q
"""

from __future__ import annotations

import os

os.environ.setdefault("REGULAI_DB", "duckdb")

import pytest

FILING = "FHCF-A-2026"

# Ground truth from scripts/seed_fl_fhcf.py's data design:
# policy_number → the single rule_number it must trigger (dirty rows),
# or None (clean rows).
CLEAN_POLICIES = {f"POL-FL-{i:04d}" for i in range(1001, 1011)}
DIRTY_EXPECTATIONS = {
    "POL-FL-1011": "2",   # TX zip prefix          → ZIP_TX_PREFIX_INVALID
    "POL-FL-1012": "3",   # county FIPS 99          → COUNTY_FIPS_VALID
    "POL-FL-1013": "5",   # deductible 1500         → HURRICANE_DEDUCTIBLE_RANGE
    "POL-FL-1014": "6",   # coverage_a $12M         → COVERAGE_A_PLAUSIBLE
    "POL-FL-1015": "8",   # effective > expiry      → DATE_ORDER
}
ALL_POLICIES = CLEAN_POLICIES | set(DIRTY_EXPECTATIONS)


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
def fhcf_gold():
    """Seed FL Bronze + run the FHCF Silver/Gold transforms once."""
    from scripts.run_fhcf import gold_fhcf, silver_fhcf
    from scripts.seed_fl_fhcf import _load_fl_rules, _seed_bronze

    n_bronze = _seed_bronze()
    _load_fl_rules()
    n_silver = silver_fhcf()
    n_gold = gold_fhcf()
    return {"bronze": n_bronze, "silver": n_silver, "gold": n_gold}


def test_transform_row_counts(fhcf_gold):
    """15 FL Bronze policies → 15 Silver rows → 15 Gold rows."""
    assert fhcf_gold == {"bronze": 15, "silver": 15, "gold": 15}


def test_gold_rows_and_filing_stamp(fhcf_gold):
    from packages.rhs.db import query

    rows = query(
        "SELECT policy_number, filing_batch_id, insurer_naic, state_code, "
        "       reporting_year "
        "FROM INSURANCE_REGULATORY.GOLD.FHCF_EXPOSURE_RECORDS "
        "ORDER BY policy_number"
    )
    assert {r["policy_number"] for r in rows} == ALL_POLICIES
    # Jurisdiction-scoped stamping: every FL row belongs to the FHCF filing.
    assert all(r["filing_batch_id"] == FILING for r in rows)
    # Silver normalizations: 10-digit NAIC, FL state, data-call year.
    assert all(r["insurer_naic"] == "0000012345" for r in rows)
    assert all(r["reporting_year"] == 2025 for r in rows)


def test_transform_is_idempotent(fhcf_gold):
    """Re-running the transforms must not duplicate rows."""
    from packages.rhs.db import query
    from scripts.run_fhcf import gold_fhcf, silver_fhcf

    assert silver_fhcf() == 15
    assert gold_fhcf() == 15
    r = query("SELECT COUNT(*) AS n FROM INSURANCE_REGULATORY.GOLD.FHCF_EXPOSURE_RECORDS")
    assert r[0]["n"] == 15


def _violations_by_policy() -> dict[str, set[str]]:
    """Execute every US-FL reference rule exactly the way /validate does
    (FROM INSURANCE_REGULATORY.{target_table} j WHERE ({violation_sql}))."""
    from packages.rhs.db import query

    rules = query(
        "SELECT rule_number, target_table, target_id_expr, violation_sql "
        "FROM INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES "
        "WHERE jurisdiction_code = 'US-FL' ORDER BY rule_number"
    )
    assert len(rules) == 10, f"expected 10 US-FL reference rules, got {len(rules)}"
    assert all(r["target_table"] == "GOLD.FHCF_EXPOSURE_RECORDS" for r in rules), (
        "US-FL rules must target GOLD.FHCF_EXPOSURE_RECORDS — regenerate "
        "materialized/reference/tspr_validation_rules_us_fl.sql"
    )

    by_policy: dict[str, set[str]] = {p: set() for p in ALL_POLICIES}
    for r in rules:
        hits = query(
            f"SELECT {r['target_id_expr']} AS record_id "
            f"FROM INSURANCE_REGULATORY.{r['target_table']} j "
            f"WHERE ({r['violation_sql']})"
        )
        for h in hits:
            by_policy.setdefault(h["record_id"], set()).add(str(r["rule_number"]))
    return by_policy


def test_dirty_policies_trigger_exactly_their_rule(fhcf_gold):
    by_policy = _violations_by_policy()
    for policy, rule_num in DIRTY_EXPECTATIONS.items():
        assert by_policy.get(policy) == {rule_num}, (
            f"{policy} expected to violate exactly rule {rule_num}, "
            f"got {sorted(by_policy.get(policy, set()))}"
        )


def test_clean_policies_trigger_no_rules(fhcf_gold):
    by_policy = _violations_by_policy()
    dirty = {p: v for p, v in by_policy.items() if p in CLEAN_POLICIES and v}
    assert not dirty, f"clean policies flagged: {dirty}"
