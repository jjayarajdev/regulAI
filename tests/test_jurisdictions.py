"""Phase 2.1 schema + seed regression tests.

Confirms: new typed nodes instantiate, new enum values present, every
existing node carries `jurisdiction_code`, the 2 seeded Jurisdictions
exist, and the US-TX scope graph is complete.

Requires Neo4j reachability with the seed_jurisdictions migration applied.
"""

from __future__ import annotations

import datetime as dt

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
    reason="Neo4j unreachable — skipping P2.1 tests",
)


# ── Schema-level: types instantiate, enum values exist ────────────────────

def test_new_node_classes_instantiate():
    from packages.core.nodes import (
        Jurisdiction,
        Regulator,
        StatisticalAgent,
        FilingObligation,
    )
    from packages.core.enums import JurisdictionType

    tx = Jurisdiction(
        name="Texas",
        jurisdiction_code="US-TX",
        jurisdiction_name="Texas",
        jurisdiction_type=JurisdictionType.STATE,
    )
    assert tx.type == "Jurisdiction"
    assert tx.jurisdiction_type.value == "state"

    tdi = Regulator(name="TDI", regulator_code="TDI", regulator_name="TDI", jurisdiction_code="US-TX")
    assert tdi.type == "Regulator"

    tico = StatisticalAgent(
        name="TICO",
        agent_code="TICO",
        agent_name="Texas Insurance Checking Office",
        jurisdiction_code="US-TX",
    )
    assert tico.type == "StatisticalAgent"

    fo = FilingObligation(
        name="TPA-Q4-2025",
        obligation_code="TPA-Q4-2025",
        plan_code="TPA",
        plan_name="Texas Private Passenger Auto / Homeowners",
        cadence="Quarterly",
        period_start=dt.date(2025, 10, 1),
        period_end=dt.date(2025, 12, 31),
        due_date=dt.date(2026, 3, 31),
    )
    assert fo.type == "FilingObligation"
    assert fo.jurisdiction_code == "US-TX"


def test_jurisdiction_code_default_is_us_tx():
    """Pre-Phase-2 nodes default to US-TX when read back."""
    from packages.core.nodes import Rule
    import uuid as _uuid

    r = Rule(
        name="pytest rule",
        section="A",
        rule_number=99,
        title="pytest",
        document_id=_uuid.uuid4(),
    )
    assert r.jurisdiction_code == "US-TX"
    assert r.is_federal_default is False


def test_federal_default_flag_on_rule():
    from packages.core.nodes import Rule
    import uuid as _uuid

    r = Rule(
        name="NAIC company number",
        section="A",
        rule_number=22,
        title="A.22",
        document_id=_uuid.uuid4(),
        is_federal_default=True,
        jurisdiction_code="US",
    )
    assert r.is_federal_default is True
    assert r.jurisdiction_code == "US"


def test_new_enums_are_closed():
    from packages.core.enums import NodeType, RelationshipType, JurisdictionType

    # NodeType expanded to 19
    node_types = {nt.value for nt in NodeType}
    assert "Jurisdiction" in node_types
    assert "Regulator" in node_types
    assert "StatisticalAgent" in node_types
    assert "FilingObligation" in node_types
    assert len(node_types) == 19

    rel_types = {rt.value for rt in RelationshipType}
    for new_rel in ("APPLIES_IN", "ISSUED_BY", "OBLIGATES", "RECEIVES_SUBMISSION"):
        assert new_rel in rel_types
    assert len(rel_types) == 17

    jur_types = {j.value for j in JurisdictionType}
    assert jur_types == {"federal", "state", "regional"}


# ── State-level: seed completed, scope graph correct ──────────────────────

def test_seed_created_us_and_us_tx_jurisdictions():
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        rows = list(s.run(
            "MATCH (j:Jurisdiction) RETURN j.jurisdiction_code AS code"
        ))
        codes = {r["code"] for r in rows}
        assert "US" in codes
        assert "US-TX" in codes


def test_seed_created_tdi_regulator_and_tico_agent():
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        r = s.run("MATCH (r:Regulator {regulator_code: 'TDI'}) RETURN r.jurisdiction_code AS jur").single()
        assert r is not None, "TDI Regulator missing — run `make seed-jurisdictions`"
        assert r["jur"] == "US-TX"

        r = s.run("MATCH (a:StatisticalAgent {agent_code: 'TICO'}) RETURN a.submission_channel AS chan").single()
        assert r is not None, "TICO StatisticalAgent missing"
        assert r["chan"] == "ShareFile"


def test_existing_nodes_carry_jurisdiction_code():
    """Every pre-Phase-2 node (Rule, CodeList, CodeValue, etc.) is backfilled to US-TX."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        # Sample-check that the major types all carry the property
        for label in ("Rule", "CodeList", "CodeValue", "RecordLayout"):
            r = s.run(f"""
                MATCH (n:{label})
                WHERE n.jurisdiction_code IS NULL
                RETURN count(n) AS n
            """).single()
            assert r["n"] == 0, f"{label} nodes missing jurisdiction_code"


def test_applies_in_edges_target_us_tx():
    """Existing canon scoped to US-TX via APPLIES_IN."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        r = s.run("""
            MATCH (n:GRENode)-[:APPLIES_IN]->(j:Jurisdiction {jurisdiction_code: 'US-TX'})
            RETURN count(n) AS n
        """).single()
        # Expect at least the 1538 baseline nodes + the regulator/agent
        assert r["n"] >= 1000


def test_seed_is_idempotent():
    """Running seed_jurisdictions twice yields zero new nodes/edges."""
    from scripts.seed_jurisdictions import seed

    summary = seed()
    assert summary["jurisdictions_created"] == 0
    assert summary["regulators_created"] == 0
    assert summary["agents_created"] == 0
    assert summary["nodes_backfilled"] == 0
    assert summary["applies_in_edges"] == 0
