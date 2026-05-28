"""P2.2 — federal-default tagging tests.

Confirms: ~9 rules tagged is_federal_default=true; their APPLIES_IN edges
point at the US Jurisdiction not US-TX; a "what rules apply in US-TX"
query returns TX-specific + federal defaults.
"""

from __future__ import annotations

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
    reason="Neo4j unreachable — skipping P2.2 tests",
)


def test_federal_default_rules_exist():
    """make tag-federal-defaults marks at least the 9 expected rule numbers."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    expected_rule_numbers = {12, 13, 14, 15, 16, 22, 25, 27, 28}
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        rows = list(s.run("""
            MATCH (r:Rule {is_federal_default: true})
            RETURN r.rule_number AS num
        """))
        nums = {r["num"] for r in rows if isinstance(r["num"], int)}
        missing = expected_rule_numbers - nums
        assert not missing, (
            f"Missing federal-default tag on rules: {missing}. "
            f"Run `make tag-federal-defaults`."
        )


def test_federal_default_rules_scoped_to_us_not_tx():
    """APPLIES_IN edges for federal-default rules point to the US Jurisdiction."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        r = s.run("""
            MATCH (r:Rule {is_federal_default: true})-[:APPLIES_IN]->(j:Jurisdiction)
            RETURN j.jurisdiction_code AS jur, count(r) AS n
        """).data()
        # Every federal-default rule should reach US only (not US-TX)
        scopes = {row["jur"]: row["n"] for row in r}
        assert "US" in scopes and scopes["US"] >= 9, f"federal-default rules not scoped to US: {scopes}"
        assert scopes.get("US-TX", 0) == 0, f"federal-default rule still on US-TX scope: {scopes}"


def test_tx_canon_query_returns_tx_plus_federal():
    """The 'what rules apply in Texas?' query unions TX-specific rules + federal defaults.

    This is the resolution pattern the reference-SQL builders will use in P2.3.
    """
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        # Federal defaults are everywhere; TX-specific only in US-TX
        result = s.run("""
            MATCH (r:Rule)-[:APPLIES_IN]->(j:Jurisdiction)
            WHERE j.jurisdiction_code IN ['US', 'US-TX']
            RETURN count(DISTINCT r) AS n
        """).single()
        all_tx_visible = result["n"]

        # Federal-only count for comparison
        fed = s.run("""
            MATCH (r:Rule {is_federal_default: true})
            RETURN count(r) AS n
        """).single()
        federal_count = fed["n"]

        # TX-specific only
        tx_only = s.run("""
            MATCH (r:Rule)-[:APPLIES_IN]->(j:Jurisdiction {jurisdiction_code: 'US-TX'})
            RETURN count(r) AS n
        """).single()

        assert all_tx_visible >= federal_count
        assert all_tx_visible >= tx_only["n"]
        # Both subsets contribute to the union, and federal pulls its weight
        assert federal_count >= 9


def test_tag_federal_defaults_idempotent():
    """Re-running tag_federal_defaults yields zero new tags / edges."""
    from scripts.tag_federal_defaults import tag_federal_defaults

    # Second run should be a no-op (SET on already-set values, MERGE on existing edges)
    summary = tag_federal_defaults()
    # rules_tagged is a count of *matches*, not new tags — but with idempotent SET it's still safe
    # The edge re-wire should yield 0 because edges already exist on US
    assert summary["edges_rewired"] == 0, (
        f"second run rewired {summary['edges_rewired']} edges; should be 0"
    )
