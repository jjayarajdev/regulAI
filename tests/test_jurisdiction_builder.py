"""P2.3 — jurisdiction-aware reference-SQL builder tests.

Confirms:
  - fetch_rules accepts a jurisdiction argument
  - federal-default rules appear under any jurisdiction
  - state-specific rules only appear under their own jurisdiction
  - the override-by-supersedes_federal_rule_id mechanism removes the federal
    default in the overriding state's scope

Note: the only KG rule with violation_sql today is A.34-valid-codes (US-TX),
not federal — so this test family creates a small synthetic federal-default
rule with violation_sql to exercise the union/override paths.
"""

from __future__ import annotations

import uuid as _uuid

import pytest


def _neo4j_available() -> bool:
    try:
        from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
        with Neo4jGREAdapter() as gre:
            gre.count_nodes()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _neo4j_available(),
    reason="Neo4j unreachable — skipping P2.3 tests",
)


def _make_federal_rule(s, rule_id: str, rule_number: int = 9999) -> None:
    """Create a synthetic federal-default rule with violation_sql + APPLIES_IN→US."""
    s.run("""
        MATCH (us:Jurisdiction {jurisdiction_code: 'US'})
        CREATE (r:GRENode:Rule {
            id: $id, type: 'Rule', name: 'pytest federal rule',
            rule_number: $num, section: 'A', title: 'pytest fed',
            target_table: 'BRONZE.GW_PC_JOB', target_id_expr: 'j.publicid',
            violation_sql: 'FALSE',
            violation_reason: 'pytest synthetic',
            severity: 'ERROR', citation: 'pytest',
            is_federal_default: true,
            version: 1, status: 'approved',
            jurisdiction_code: 'US',
            created_at: datetime(), created_by: 'pytest'
        })
        CREATE (r)-[:APPLIES_IN]->(us)
    """, id=rule_id, num=rule_number)


def _make_state_override(s, override_id: str, federal_id: str) -> None:
    """Create a US-TX rule that supersedes the federal default."""
    s.run("""
        MATCH (tx:Jurisdiction {jurisdiction_code: 'US-TX'})
        CREATE (r:GRENode:Rule {
            id: $id, type: 'Rule', name: 'pytest TX override',
            rule_number: 9999, section: 'A', title: 'pytest override',
            target_table: 'BRONZE.GW_PC_JOB', target_id_expr: 'j.publicid',
            violation_sql: 'FALSE',
            violation_reason: 'pytest TX-specific override',
            severity: 'ERROR', citation: 'TX statute',
            is_federal_default: false,
            supersedes_federal_rule_id: $fed_id,
            version: 1, status: 'approved',
            jurisdiction_code: 'US-TX',
            created_at: datetime(), created_by: 'pytest'
        })
        CREATE (r)-[:APPLIES_IN]->(tx)
    """, id=override_id, fed_id=federal_id)


def test_federal_default_appears_under_us_tx_scope():
    """A US-scoped federal rule appears when fetching for US-TX."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
    from scripts.build_validation_rules_reference import fetch_rules

    fed_id = f"pytest-fed-{_uuid.uuid4().hex[:8]}"
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        _make_federal_rule(s, fed_id)

    try:
        rows = fetch_rules(jurisdiction="US-TX")
        ids = {r["id"] for r in rows}
        assert fed_id in ids, "federal-default rule missing from US-TX scope"
        # And it carries the federal-default marker
        fed = next(r for r in rows if r["id"] == fed_id)
        assert fed["is_federal_default"] is True
        assert fed["jurisdiction_code"] == "US"
    finally:
        with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
            s.run("MATCH (r:Rule {id: $id}) DETACH DELETE r", id=fed_id)


def test_state_override_replaces_federal_in_its_scope():
    """When US-TX has a rule with supersedes_federal_rule_id, the federal one
    is excluded from the US-TX scope."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
    from scripts.build_validation_rules_reference import fetch_rules

    fed_id = f"pytest-fed-{_uuid.uuid4().hex[:8]}"
    ovr_id = f"pytest-ovr-{_uuid.uuid4().hex[:8]}"
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        _make_federal_rule(s, fed_id, rule_number=8888)
        _make_state_override(s, ovr_id, fed_id)

    try:
        rows = fetch_rules(jurisdiction="US-TX")
        ids = {r["id"] for r in rows}
        assert ovr_id in ids, "override rule missing"
        assert fed_id not in ids, "federal rule should be excluded when overridden"
    finally:
        with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
            s.run("MATCH (r:Rule) WHERE r.id IN [$o, $f] DETACH DELETE r", o=ovr_id, f=fed_id)


def test_state_specific_rule_invisible_in_other_jurisdiction():
    """A US-TX rule shouldn't appear when fetching for US-FL."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
    from scripts.build_validation_rules_reference import fetch_rules

    # Pre-condition: at least one US-TX rule with violation_sql exists
    rows_tx = fetch_rules(jurisdiction="US-TX")
    assert rows_tx, "expected at least one TX rule for the test to be meaningful"
    tx_only_ids = {r["id"] for r in rows_tx if not r["is_federal_default"]}

    # Fetch for FL — none of the TX-only rules should appear (FL canon is empty)
    rows_fl = fetch_rules(jurisdiction="US-FL")
    fl_ids = {r["id"] for r in rows_fl}
    leak = tx_only_ids & fl_ids
    assert not leak, f"TX-specific rules leaked into FL scope: {leak}"


def test_emitted_sql_carries_jurisdiction_column():
    """The generated SQL has the jurisdiction_code column + per-row value."""
    from scripts.build_validation_rules_reference import build_sql, fetch_rules

    rows = fetch_rules(jurisdiction="US-TX")
    sql = build_sql(rows, jurisdiction="US-TX")
    assert "jurisdiction_code" in sql.lower()
    assert "'US-TX'" in sql or "us-tx" in sql.lower()
    assert "is_federal_default" in sql.lower()
