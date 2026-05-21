"""Execute every FL violation_sql against synthetic data in DuckDB.

Tests in test_fl_rhs_pipeline.py verify the SQL *artifact* is well-formed.
This file verifies the SQL *actually catches violators*. Together they
close the loop: KG → artifact → execution against in-process data.

The fixture data lives in tests/_fl_duckdb_harness.py — kept in sync with
the Snowflake DDL fixture in references/files -Snowflake/03_bronze_fl_fhcf.sql.

Per-rule expected outcomes (from the fixture; rule_number is the integer
value Sentinel pulled from the FHCF markdown's "Validation Rules" section):
  POL-FL-0001 (clean Miami-Dade)              — violates: none
  POL-FL-0002 (clean Tallahassee)             — violates: none
  POL-FL-0003 (risk_zip='77002' — TX)         — violates: 2 only
  POL-FL-0004 (county_fips='99')              — violates: 3 only
  POL-FL-0005 (state_code='TX')               — violates: 4 only
  POL-FL-0006 (insurer_naic='123')            — violates: 1 only
  POL-FL-0007 (hurricane_deductible=1500)     — violates: 5 only
  POL-FL-0008 (coverage_a=10000000)           — violates: 6 only
  POL-FL-0009 (effective_date > expiry_date)  — violates: 8 only
  POL-FL-0010 (year_built=1850)               — violates: 9 only
  POL-FL-0011 (wind_mit='Y', companions null) — violates: 7 only
  POL-FL-0012 (lat set, lng null)             — violates: 10 only
"""

from __future__ import annotations

import pytest

from tests._fl_duckdb_harness import (
    execute_rule,
    fetch_fl_rules_from_kg,
    load_fl_bronze,
)


def _neo4j_available() -> bool:
    try:
        from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
        with Neo4jGREAdapter() as gre:
            gre.count_nodes()
        return True
    except Exception:
        return False


# Ground-truth expectations: for each policy, the set of rule_numbers it
# should violate. Anything outside this map indicates either a rule
# regression or a fixture-data drift.
EXPECTED_VIOLATIONS_BY_POLICY: dict[str, set[str]] = {
    "POL-FL-0001": set(),
    "POL-FL-0002": set(),
    "POL-FL-0003": {"2"},   # ZIP_TX_PREFIX_INVALID
    "POL-FL-0004": {"3"},   # COUNTY_FIPS_VALID
    "POL-FL-0005": {"4"},   # STATE_CODE_FIXED
    "POL-FL-0006": {"1"},   # NAIC_NUMERIC
    "POL-FL-0007": {"5"},   # HURRICANE_DEDUCTIBLE_RANGE
    "POL-FL-0008": {"6"},   # COVERAGE_A_PLAUSIBLE
    "POL-FL-0009": {"8"},   # DATE_ORDER
    "POL-FL-0010": {"9"},   # YEAR_BUILT_RANGE
    "POL-FL-0011": {"7"},   # WIND_MITIGATION_FBC_REQUIRED
    "POL-FL-0012": {"10"},  # GEOCODE_PRESENT_OR_NULL
}


@pytest.fixture(scope="module")
def fl_rules():
    if not _neo4j_available():
        pytest.skip("Neo4j unavailable")
    rules = fetch_fl_rules_from_kg()
    if not rules:
        pytest.skip("No FL rules with violation_sql; run `make migrate-fl-validation-rules`")
    return rules


@pytest.fixture(scope="module")
def db():
    return load_fl_bronze()


def test_each_rule_returns_only_its_designated_violator(fl_rules, db):
    """The dirty fixtures were designed so each triggers exactly one
    rule. This catches both false positives (a clean row falsely flagged)
    and overreach (one dirty row tripping multiple rules)."""
    actual_by_rule: dict[str, set[str]] = {}
    for rule in fl_rules:
        violators = set(execute_rule(db, rule))
        actual_by_rule[rule.rule_number] = violators

    # Per policy, compute the set of rules that flagged it
    actual_by_policy: dict[str, set[str]] = {
        p: set() for p in EXPECTED_VIOLATIONS_BY_POLICY
    }
    for rule_num, violators in actual_by_rule.items():
        for policy in violators:
            actual_by_policy.setdefault(policy, set()).add(rule_num)

    errors: list[str] = []
    for policy, expected_rules in EXPECTED_VIOLATIONS_BY_POLICY.items():
        actual_rules = actual_by_policy.get(policy, set())
        if actual_rules != expected_rules:
            missing = expected_rules - actual_rules
            extra = actual_rules - expected_rules
            parts = []
            if missing:
                parts.append(f"expected to be flagged by {missing} but wasn't")
            if extra:
                parts.append(f"unexpectedly flagged by {extra}")
            errors.append(f"  {policy}: {' AND '.join(parts)}")

    assert not errors, "Per-policy violation set mismatches:\n" + "\n".join(errors)


def test_clean_policies_pass_every_rule(fl_rules, db):
    """The clean fixtures (POL-FL-0001, POL-FL-0002) must not violate any
    wired rule. A single false positive breaks the demo (and customer
    trust in the validation engine)."""
    for rule in fl_rules:
        violators = set(execute_rule(db, rule))
        clean_policies = {
            p for p, rules in EXPECTED_VIOLATIONS_BY_POLICY.items() if not rules
        }
        false_positives = violators & clean_policies
        assert not false_positives, (
            f"Rule {rule.rule_number} ({rule.rule_name}) falsely flagged clean "
            f"policies: {sorted(false_positives)}"
        )


def test_dirty_policies_are_caught(fl_rules, db):
    """Each dirty fixture must be caught by *at least* the rule it was
    designed for. Counterpart to test_clean_policies_pass — protects
    against false negatives (a rule's SQL silently no-ops)."""
    rule_by_num = {r.rule_number: r for r in fl_rules}
    for policy, expected_rule_nums in EXPECTED_VIOLATIONS_BY_POLICY.items():
        for rule_num in expected_rule_nums:
            rule = rule_by_num.get(rule_num)
            if rule is None:
                pytest.fail(f"{policy} expects rule {rule_num} but it's not in KG")
            violators = set(execute_rule(db, rule))
            assert policy in violators, (
                f"Rule {rule_num} ({rule.rule_name}) failed to catch its "
                f"designated dirty fixture {policy}. violation_sql may be wrong."
            )


def test_rule_execution_does_not_error(fl_rules, db):
    """Catches the alias-mismatch class of bug (e.g. violation_sql uses
    `p.col` but production aliases the table as `j`). If any rule errors,
    /validate would error too — production-correctness in CI."""
    errors: list[str] = []
    for rule in fl_rules:
        try:
            execute_rule(db, rule)
        except Exception as e:
            errors.append(f"  {rule.rule_number} ({rule.rule_name}): {type(e).__name__}: {e}")
    assert not errors, "Rules that errored when executed:\n" + "\n".join(errors)
