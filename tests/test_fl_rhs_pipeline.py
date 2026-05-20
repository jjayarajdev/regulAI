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
    # Dirty rows — one per rule
    assert "POL-FL-0003" in content and "'77002'" in content, (
        "Dirty row POL-FL-0003 (TX ZIP) missing — Validation.2 has no fixture"
    )
    assert "POL-FL-0004" in content and "'99'" in content, (
        "Dirty row POL-FL-0004 (invalid county FIPS) missing — Validation.3 has no fixture"
    )
    assert "POL-FL-0005" in content and "'TX'" in content, (
        "Dirty row POL-FL-0005 (TX state code) missing — Validation.4 has no fixture"
    )


def test_fl_reference_sql_contains_three_validation_rules(fl_reference_sql):
    """All 3 wired FHCF validation rules appear in the FL-scoped SQL."""
    # The actual rule_number values that fall out of Sentinel's extraction
    # are integer "2", "3", "4" with section "Validation Rules" — preserve
    # that as the source-of-truth label.
    assert "Rule Validation.2 — ZIP_TX_PREFIX_INVALID" in fl_reference_sql
    assert "Rule Validation.3 — COUNTY_FIPS_VALID" in fl_reference_sql
    assert "Rule Validation.4 — STATE_CODE_FIXED" in fl_reference_sql


def test_fl_reference_sql_targets_fl_bronze(fl_reference_sql):
    """Every wired FL rule targets BRONZE.FL_FHCF_POLICY — no rule
    accidentally points at a TX table (which would silently no-op or
    return TX violations under an FL filing)."""
    # Count rule INSERT blocks
    inserts = re.findall(r"INSERT INTO TSPR_VALIDATION_RULES", fl_reference_sql)
    assert len(inserts) == 3, f"Expected 3 INSERTs, got {len(inserts)}"
    # All target FL Bronze
    fl_target_count = fl_reference_sql.count("'BRONZE.FL_FHCF_POLICY'")
    assert fl_target_count == 3, (
        f"Only {fl_target_count}/3 FL rules target BRONZE.FL_FHCF_POLICY — "
        f"the others may be pointing at a TX table by mistake"
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
    # 'US-FL' should appear at least once per FL rule (3 rules) plus the
    # DELETE clause that scopes by jurisdiction.
    assert fl_count >= 4, f"Expected ≥4 'US-FL' literals in data, got {fl_count}"
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
    # ZIP_TX_PREFIX_INVALID — must check first char of risk_zip
    assert "LEFT(TRIM(p.risk_zip), 1) <> ''3''" in fl_reference_sql or \
           "LEFT(TRIM(p.risk_zip), 1) <> '3'" in fl_reference_sql, \
           "Validation.2 SQL missing first-digit ZIP check"
    # COUNTY_FIPS_VALID — must range-check 1..67
    assert "BETWEEN 1 AND 67" in fl_reference_sql, \
           "Validation.3 SQL missing FL county FIPS range"
    # STATE_CODE_FIXED — must enforce state_code = 'FL'
    assert "p.state_code IS NULL" in fl_reference_sql, \
           "Validation.4 SQL missing state_code presence check"


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
        assert len(r) >= 3, f"Expected ≥3 wired FL rules, found {len(r)}"
        for row in r:
            assert row["target_table"], f"Rule {row['rule_number']} missing target_table"
            assert row["target_id_expr"], f"Rule {row['rule_number']} missing target_id_expr"
            assert row["violation_reason"], f"Rule {row['rule_number']} missing violation_reason"
            assert row["severity"] in {"ERROR", "WARNING"}, f"Rule {row['rule_number']} bad severity: {row['severity']!r}"
            assert row["citation"], f"Rule {row['rule_number']} missing citation"
