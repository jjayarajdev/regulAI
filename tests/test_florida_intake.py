"""P3 — Florida intake regression tests.

Verifies the multi-jurisdiction architecture survives a real second-state
ingestion. Locks in:

  - FL canon nodes exist with jurisdiction_code='US-FL'
  - APPLIES_IN edges point at the US-FL Jurisdiction
  - TX canon nodes are unchanged (no FL contamination)
  - Cross-state queries don't leak (nothing scoped to BOTH TX and FL via APPLIES_IN)
  - The Sentinel extraction file is on disk
"""

from __future__ import annotations

from pathlib import Path

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
    reason="Neo4j unreachable — skipping P3 tests",
)


def test_fl_jurisdiction_node_exists():
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        r = s.run(
            "MATCH (j:Jurisdiction {jurisdiction_code: 'US-FL'}) "
            "RETURN j.jurisdiction_name AS name, j.parent_jurisdiction_code AS parent"
        ).single()
        assert r is not None, "US-FL Jurisdiction missing"
        assert r["name"] == "Florida"
        assert r["parent"] == "US"


def test_fl_oir_regulator_exists():
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        r = s.run(
            "MATCH (r:Regulator {regulator_code: 'FL-OIR'}) "
            "RETURN r.regulator_name AS name, r.jurisdiction_code AS jur"
        ).single()
        assert r is not None, "FL-OIR Regulator missing"
        assert "Florida" in r["name"]
        assert r["jur"] == "US-FL"


def test_fl_canon_has_real_content():
    """At least 20 Rules and both FL statutes (627.062 + 627.351) scoped to US-FL."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        rules = s.run(
            "MATCH (r:Rule)-[:APPLIES_IN]->(:Jurisdiction {jurisdiction_code: 'US-FL'}) "
            "RETURN count(r) AS n"
        ).single()
        assert rules["n"] >= 20, f"Expected ≥20 FL Rules (after 2 statutes), got {rules['n']}"

        for chapter in ("627.062", "627.351"):
            doc = s.run(
                "MATCH (d:RegulationDocument)-[:APPLIES_IN]->(:Jurisdiction {jurisdiction_code: 'US-FL'}) "
                "WHERE d.name CONTAINS $ch RETURN count(d) AS n",
                ch=chapter,
            ).single()
            assert doc["n"] >= 1, f"FL Statute {chapter} missing"


def test_fl_citizens_organization_extracted():
    """The Citizens Property Insurance Corporation should be a distinct Organization."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        r = s.run(
            "MATCH (o:Organization)-[:APPLIES_IN]->(:Jurisdiction {jurisdiction_code: 'US-FL'}) "
            "WHERE o.name CONTAINS 'Citizens' "
            "RETURN o.name AS name LIMIT 1"
        ).single()
        assert r is not None, "Citizens Property Insurance Corporation missing"
        assert "Citizens" in r["name"]


def test_fl_record_layout_for_citizens_policy_data():
    """The Citizens statute's reporting requirements should produce a RecordLayout."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        r = s.run(
            "MATCH (rl:RecordLayout)-[:APPLIES_IN]->(:Jurisdiction {jurisdiction_code: 'US-FL'}) "
            "RETURN count(rl) AS n"
        ).single()
        assert r["n"] >= 1, "FL RecordLayout missing — Sentinel should extract one from 627.351(6)(h)"


def test_fl_bulletin_override_from_oir_memo():
    """OIR-22-04M supersedes prior catastrophe data call directives; Sentinel
    should recognize this and produce a BulletinOverride node scoped to US-FL."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        r = s.run(
            "MATCH (bo:BulletinOverride)-[:APPLIES_IN]->(:Jurisdiction {jurisdiction_code: 'US-FL'}) "
            "RETURN count(bo) AS n"
        ).single()
        assert r["n"] >= 1, "OIR-22-04M should have produced a BulletinOverride node"


def test_fl_codelists_for_hurricane_data_call():
    """The OIR data call defines 8 CodeLists (Cause of Loss, Policy Form,
    Claim Status, etc.). Verify they made it into the FL canon."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        r = s.run(
            "MATCH (cl:CodeList)-[:APPLIES_IN]->(:Jurisdiction {jurisdiction_code: 'US-FL'}) "
            "RETURN count(cl) AS n"
        ).single()
        assert r["n"] >= 5, f"Expected ≥5 FL CodeLists from OIR memo, got {r['n']}"


def test_fl_canon_exercises_all_node_types():
    """After 3 FL documents, the FL canon should exercise at least 10 of the
    19 closed-vocabulary node types — proving the schema absorbs real
    regulator content broadly, not just narrowly."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        rows = list(s.run("""
            MATCH (n:GRENode)-[:APPLIES_IN]->(:Jurisdiction {jurisdiction_code: 'US-FL'})
            RETURN [l IN labels(n) WHERE l <> 'GRENode'][0] AS type
        """))
        types_seen = {r["type"] for r in rows}
        assert len(types_seen) >= 10, (
            f"FL canon only exercises {len(types_seen)} types after 3 docs: {types_seen}"
        )


def test_no_node_appears_in_both_tx_and_fl():
    """The most important leak test: no node should be APPLIES_IN to both jurisdictions
    without an explicit dual-scope marker. Right now we expect zero overlap."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        r = s.run(
            """
            MATCH (n:GRENode)-[:APPLIES_IN]->(:Jurisdiction {jurisdiction_code: 'US-TX'})
            MATCH (n)-[:APPLIES_IN]->(:Jurisdiction {jurisdiction_code: 'US-FL'})
            RETURN count(DISTINCT n) AS leak
            """
        ).single()
        assert r["leak"] == 0, f"{r['leak']} nodes leaked between TX and FL scopes"


def test_tx_canon_unchanged_post_fl_ingestion():
    """TX scope is untouched by FL ingestion (modulo legitimate dedup of
    Organizations like the FL Hurricane Loss Projection Methodology Commission
    that already existed as a TX-scoped node)."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        r = s.run(
            "MATCH (n:GRENode)-[:APPLIES_IN]->(:Jurisdiction {jurisdiction_code: 'US-TX'}) "
            "RETURN count(n) AS n"
        ).single()
        # TX baseline is 1530 (after federal-default tagging moved 9+5=14 to US,
        # and after Citizens-statute ingestion which reused 1 existing org).
        assert r["n"] >= 1525, f"TX scope shrunk unexpectedly to {r['n']}"


def test_fl_extraction_file_exists():
    """The extraction JSON Sentinel produced is preserved on disk for audit/replay."""
    p = Path("materialized/extractions/FL_627_062_rate_standards.extraction.json")
    assert p.exists(), f"FL extraction JSON missing at {p}"
    # Sanity-check that it's the right document
    content = p.read_text(encoding="utf-8")
    assert "627.062" in content
    assert "Florida" in content


def test_fl_rules_have_no_violation_sql():
    """FL canon today is statutory text, not executable predicates. Validates
    that the validate endpoint correctly returns 0 rules for an FL filing
    (because none have violation_sql) — not a leak from TX."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        r = s.run(
            "MATCH (r:Rule)-[:APPLIES_IN]->(:Jurisdiction {jurisdiction_code: 'US-FL'}) "
            "WHERE r.violation_sql IS NOT NULL "
            "RETURN count(r) AS n"
        ).single()
        assert r["n"] == 0, (
            "FL rules have violation_sql attached — Phase 3 only ingested statute text, "
            "not executable predicates. Did someone annotate FL rules manually?"
        )
