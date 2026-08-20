"""OK executable rules — every violation_sql runs and catches exactly its
designated violator (mirrors test_fl_rules_execute, but self-contained: the
rules come from the jurisdiction's content file and the fixture rows from
the seed script, so no live Neo4j/warehouse is needed)."""

import json
from pathlib import Path

import duckdb
import pytest

from scripts.seed_ok_stat import OK_FIXTURES, _row_params

OK_VALIDATION_RULES = json.loads(
    Path("references/validation_rules/US-OK.json").read_text(encoding="utf-8"))

# policy → the single rule_number it is designed to violate (clean = none).
EXPECTED = {
    "POL-OK-0001": set(),
    "POL-OK-0002": set(),
    "POL-OK-0003": {"OK.1"},
    "POL-OK-0004": {"OK.2"},
    "POL-OK-0005": {"OK.3"},
    "POL-OK-0006": {"OK.4"},
    "POL-OK-0007": {"OK.5"},
    "POL-OK-0008": {"OK.6"},
    "POL-OK-0009": {"OK.7"},
    "POL-OK-0010": {"OK.8"},
    "POL-OK-0011": {"OK.9"},
    "POL-OK-0012": {"OK.10"},
}


@pytest.fixture(scope="module")
def conn():
    c = duckdb.connect(":memory:")
    # Same Snowflake-dialect shims the production DuckDB driver installs.
    c.execute("CREATE MACRO regexp_like(s, pat) AS regexp_matches(s, pat)")
    c.execute("CREATE SCHEMA gold")
    c.execute("""
        CREATE TABLE gold.ok_stat_records (
          policy_number VARCHAR, record_type VARCHAR, naic_code VARCHAR,
          county_fips VARCHAR, transaction_code VARCHAR, written_premium DOUBLE,
          aoi_thousands BIGINT, deductible_type VARCHAR, wind_deductible_pct DOUBLE,
          mitigation_credit DOUBLE, mitigation_code VARCHAR, cause_of_loss VARCHAR,
          accident_date DATE, paid_amount DOUBLE, disposition_code VARCHAR,
          cat_serial BIGINT, reported_lag_days BIGINT, effective_date DATE,
          filing_batch_id VARCHAR
        )
    """)
    for policy, (base, over) in OK_FIXTURES.items():
        c.execute(
            "INSERT INTO gold.ok_stat_records VALUES (" + ", ".join(["?"] * 19) + ")",
            list(_row_params(policy, base, over)),
        )
    return c


def _violators(conn, rule) -> set[str]:
    rows = conn.execute(
        f"SELECT j.policy_number FROM gold.ok_stat_records j WHERE {rule['violation_sql']}"
    ).fetchall()
    return {r[0] for r in rows}


def test_rule_execution_does_not_error(conn):
    for rule in OK_VALIDATION_RULES:
        _violators(conn, rule)  # raises on bad SQL / missing columns


def test_each_rule_catches_exactly_its_designated_violator(conn):
    for rule in OK_VALIDATION_RULES:
        got = _violators(conn, rule)
        expected = {p for p, rules in EXPECTED.items() if rule["rule_number"] in rules}
        assert got == expected, (
            f"{rule['rule_number']} caught {sorted(got)}, expected {sorted(expected)}"
        )


def test_clean_policies_pass_every_rule(conn):
    clean = {p for p, rules in EXPECTED.items() if not rules}
    for rule in OK_VALIDATION_RULES:
        hits = _violators(conn, rule) & clean
        assert not hits, f"{rule['rule_number']} false-positived on clean {sorted(hits)}"


def test_fixture_covers_every_rule():
    covered = set().union(*EXPECTED.values())
    assert covered == {r["rule_number"] for r in OK_VALIDATION_RULES}
