"""Cluster D — FL through the RHS validation pipeline.

Asserts the LHS → REFERENCE chain works multi-state. We don't actually
execute against Snowflake in CI (the demo flow does that), but we verify:

  1. The 3 FHCF validation rules carry executable violation_sql in the KG
  2. `build_validation_rules_reference --jur US-FL` produces a valid SQL
     artifact tagged with the correct jurisdiction
  3. The FL rules target the FL Bronze table (no accidental TX target)
  4. The FL SQL artifact doesn't accidentally include TX-only rules
  5. The FL Bronze DDL exists and matches what the rules reference
  6. The synthetic FL data covers both clean and dirty cases for each rule

This is the LHS-side proof that the pipeline is multi-state. Actually
firing the SQL against Snowflake is a manual demo step (and out of scope
for CI which has no Snowflake creds).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
FL_REFERENCE_SQL = REPO_ROOT / "materialized" / "reference" / "tspr_validation_rules_us_fl.sql"
FL_BRONZE_DDL = REPO_ROOT / "references" / "files -Snowflake" / "03_bronze_fl_fhcf.sql"


def _neo4j_available() -> bool:
    try:
        from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
        with Neo4jGREAdapter() as gre:
            gre.count_nodes()
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def fl_reference_sql() -> str:
    """Build (or read) the FL-scoped REFERENCE.TSPR_VALIDATION_RULES SQL.

    Regenerates on every test run so changes to the KG or build script
    are caught immediately."""
    if not _neo4j_available():
        pytest.skip("Neo4j unavailable")
    rc = subprocess.call(
        [sys.executable, "-m", "scripts.build_validation_rules_reference", "-j", "US-FL"],
        cwd=REPO_ROOT,
    )
    assert rc == 0, "build_validation_rules_reference -j US-FL failed"
    assert FL_REFERENCE_SQL.exists(), f"FL reference SQL not written to {FL_REFERENCE_SQL}"
    return FL_REFERENCE_SQL.read_text(encoding="utf-8")


def test_fl_bronze_ddl_file_exists():
    """The FHCF Bronze table DDL must exist on disk — the validation rules
    reference it by name (BRONZE.FL_FHCF_POLICY). If someone deletes the
    DDL, the rules become unrunnable."""
    assert FL_BRONZE_DDL.exists(), f"FL Bronze DDL missing at {FL_BRONZE_DDL}"
    content = FL_BRONZE_DDL.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS fl_fhcf_policy" in content
    # Every column the validation rules reference must exist
    for col in ("risk_zip", "county_fips", "state_code", "policy_number"):
        assert col in content, f"FL Bronze DDL missing column referenced by rules: {col}"


def test_fl_bronze_ddl_includes_test_fixtures():
    """The DDL ships with synthetic rows that exercise each wired rule.
    Tests + demos depend on these specific policy_numbers."""
    content = FL_BRONZE_DDL.read_text(encoding="utf-8")
    # Clean rows
    assert "POL-FL-0001" in content, "Clean row POL-FL-0001 missing"
    assert "POL-FL-0002" in content, "Clean row POL-FL-0002 missing"
    # Dirty rows — one per rule (10 total)
    expected_dirty = [
        ("POL-FL-0003", "'77002'",  "Validation.2"),
        ("POL-FL-0004", "'99'",     "Validation.3"),
        ("POL-FL-0005", "'TX'",     "Validation.4"),
        ("POL-FL-0006", "'123'",    "Validation.1"),
        ("POL-FL-0007", "1500",     "Validation.5"),
        ("POL-FL-0008", "10000000", "Validation.6"),
        ("POL-FL-0009", None,       "Validation.8"),    # date inversion — no single literal
        ("POL-FL-0010", "1850",     "Validation.9"),
        ("POL-FL-0011", None,       "Validation.7"),    # wind_mit=Y + null companions
        ("POL-FL-0012", "30670000", "Validation.10"),
    ]
    for policy, marker, rule in expected_dirty:
        assert policy in content, f"Dirty row {policy} missing — {rule} has no fixture"
        if marker:
            assert marker in content, (
                f"Dirty row {policy} ({rule}) missing its diagnostic literal {marker!r}"
            )


def test_fl_reference_sql_contains_all_ten_validation_rules(fl_reference_sql):
    """All 10 wired FHCF validation rules appear in the FL-scoped SQL."""
    expected_rule_names = [
        "Rule Validation.1 — NAIC_NUMERIC",
        "Rule Validation.2 — ZIP_TX_PREFIX_INVALID",
        "Rule Validation.3 — COUNTY_FIPS_VALID",
        "Rule Validation.4 — STATE_CODE_FIXED",
        "Rule Validation.5 — HURRICANE_DEDUCTIBLE_RANGE",
        "Rule Validation.6 — COVERAGE_A_PLAUSIBLE",
        "Rule Validation.7 — WIND_MITIGATION_FBC_REQUIRED",
        "Rule Validation.8 — DATE_ORDER",
        "Rule Validation.9 — YEAR_BUILT_RANGE",
        "Rule Validation.10 — GEOCODE_PRESENT_OR_NULL",
    ]
    missing = [n for n in expected_rule_names if n not in fl_reference_sql]
    assert not missing, f"FL reference SQL missing rules: {missing}"


def test_fl_reference_sql_targets_fl_gold(fl_reference_sql):
    """Every wired FL rule targets GOLD.FHCF_EXPOSURE_RECORDS (the
    filing-ready table built by scripts/run_fhcf.py) — no rule
    accidentally points at a TX table (which would silently no-op or
    return TX violations under an FL filing)."""
    # All 10 FHCF validation rules wired.
    inserts = re.findall(r"INSERT INTO TSPR_VALIDATION_RULES", fl_reference_sql)
    assert len(inserts) == 10, f"Expected 10 INSERTs, got {len(inserts)}"
    # All target the FL Gold exposure table
    fl_target_count = fl_reference_sql.count("'GOLD.FHCF_EXPOSURE_RECORDS'")
    assert fl_target_count == 10, (
        f"Only {fl_target_count}/10 FL rules target GOLD.FHCF_EXPOSURE_RECORDS — "
        f"the others may be pointing at a TX table (or the retired "
        f"BRONZE.FL_FHCF_POLICY shortcut) by mistake"
    )
    # Negative: no FL rule should target a TX table
    assert "BRONZE.GW_PC_JOB" not in fl_reference_sql, (
        "FL reference SQL includes a TX target (BRONZE.GW_PC_JOB) — "
        "jurisdiction filter regressed"
    )


def test_fl_reference_sql_jurisdiction_isolation(fl_reference_sql):
    """Every INSERT in the FL artifact tags jurisdiction_code='US-FL'.
    No TX rule leaks into the row data. The one allowed 'US-TX' literal
    is the column DEFAULT in the CREATE TABLE clause (legacy back-compat
    for hand-curated migrations) — that's DDL, not data."""
    # Strip lines that are clearly DDL (column definitions) before checking
    data_lines = [
        line for line in fl_reference_sql.splitlines()
        if "DEFAULT 'US-TX'" not in line
    ]
    data_sql = "\n".join(data_lines)

    fl_count = data_sql.count("'US-FL'")
    tx_count = data_sql.count("'US-TX'")
    # 'US-FL' should appear at least once per FL rule (10 rules) plus the
    # DELETE clause that scopes by jurisdiction.
    assert fl_count >= 11, f"Expected ≥11 'US-FL' literals in data, got {fl_count}"
    assert tx_count == 0, (
        f"FL reference SQL leaks {tx_count} 'US-TX' reference(s) in row data — "
        f"jurisdiction isolation broken at the build_validation_rules_reference layer"
    )


def test_fl_reference_sql_replaces_fl_safely(fl_reference_sql):
    """The artifact must DELETE existing FL rows before inserting, so
    re-runs are idempotent. Must NOT delete TX rows (that would break
    multi-state coexistence in REFERENCE)."""
    assert "DELETE FROM TSPR_VALIDATION_RULES WHERE jurisdiction_code = 'US-FL'" in fl_reference_sql
    # No DELETE of TX rows
    assert "WHERE jurisdiction_code = 'US-TX'" not in fl_reference_sql, (
        "FL load would delete TX rules — multi-state coexistence broken"
    )


def test_fl_violation_sql_is_well_formed(fl_reference_sql):
    """Sanity-check the SQL bodies for the patterns that make each rule
    actually detect its target violation. If Sentinel ever re-runs and
    overwrites the rule properties, these patterns must still be there."""
    # ZIP_TX_PREFIX_INVALID — must check first char of risk_zip.
    # Alias `j` is the production convention (api/rhs_demo.py validate loop
    # aliases the target_table as `j`); rules must reference `j.col` to run.
    assert "LEFT(TRIM(j.risk_zip), 1) <> ''3''" in fl_reference_sql or \
           "LEFT(TRIM(j.risk_zip), 1) <> '3'" in fl_reference_sql, \
           "Validation.2 SQL missing first-digit ZIP check (or wrong alias)"
    # COUNTY_FIPS_VALID — must range-check 1..67
    assert "BETWEEN 1 AND 67" in fl_reference_sql, \
           "Validation.3 SQL missing FL county FIPS range"
    # STATE_CODE_FIXED — must enforce state_code = 'FL'
    assert "j.state_code IS NULL" in fl_reference_sql, \
           "Validation.4 SQL missing state_code presence check (or wrong alias)"


def test_kg_fl_rules_have_complete_validation_props():
    """Lock in the schema for FL rules: every wired rule has all 5
    properties the validator depends on (target_table, target_id_expr,
    violation_sql, violation_reason, severity)."""
    if not _neo4j_available():
        pytest.skip("Neo4j unavailable")
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        r = s.run(
            """
            MATCH (r:Rule)-[:APPLIES_IN]->(:Jurisdiction {jurisdiction_code: 'US-FL'})
            WHERE r.violation_sql IS NOT NULL
            RETURN r.rule_number AS rule_number,
                   r.target_table AS target_table,
                   r.target_id_expr AS target_id_expr,
                   r.violation_reason AS violation_reason,
                   r.severity AS severity,
                   r.citation AS citation
            ORDER BY r.rule_number
            """
        ).data()
        assert len(r) >= 10, f"Expected ≥10 wired FL rules, found {len(r)}"
        for row in r:
            assert row["target_table"], f"Rule {row['rule_number']} missing target_table"
            assert row["target_id_expr"], f"Rule {row['rule_number']} missing target_id_expr"
            assert row["violation_reason"], f"Rule {row['rule_number']} missing violation_reason"
            assert row["severity"] in {"ERROR", "WARNING"}, f"Rule {row['rule_number']} bad severity: {row['severity']!r}"
            assert row["citation"], f"Rule {row['rule_number']} missing citation"
