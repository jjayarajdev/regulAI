"""Integration tests for Neo4jGREAdapter.

Requires Neo4j running (`make up && make migrate`). These tests wipe the
database before each test, so don't run against a database with real data.
"""

from datetime import date
from uuid import uuid4

import pytest
from neo4j.exceptions import ServiceUnavailable

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
from packages.core.enums import (
    CitationKind,
    DocumentKind,
    NodeStatus,
    OrgKind,
    RelationshipType,
)
from packages.core.nodes import (
    CodeList,
    CodeValue,
    Organization,
    RegulationDocument,
)
from packages.core.relationships import CitesRelationship, GRERelationship


@pytest.fixture
def gre():
    """Adapter fixture that wipes the DB before each test."""
    try:
        with Neo4jGREAdapter() as adapter:
            adapter.wipe_all()
            yield adapter
    except ServiceUnavailable:
        pytest.skip("Neo4j not running (run `make up && make migrate` first)")


def test_create_and_get_node(gre: Neo4jGREAdapter) -> None:
    doc = RegulationDocument(
        name="TICO TX Stat Plan (test)",
        kind=DocumentKind.STAT_PLAN,
        title="TX Stat Plan",
        hash="test-hash-001",
        status=NodeStatus.APPROVED,
    )
    gre.create_node(doc)

    fetched = gre.get_node(doc.id)
    assert fetched is not None
    assert isinstance(fetched, RegulationDocument)
    assert fetched.id == doc.id
    assert fetched.title == doc.title
    assert fetched.kind == DocumentKind.STAT_PLAN


def test_get_missing_node_returns_none(gre: Neo4jGREAdapter) -> None:
    assert gre.get_node(uuid4()) is None


def test_count_nodes(gre: Neo4jGREAdapter) -> None:
    assert gre.count_nodes() == 0

    for i in range(3):
        gre.create_node(
            Organization(
                name=f"Org {i}",
                org_name=f"Test Org {i}",
                org_kind=OrgKind.REGULATOR,
            )
        )
    assert gre.count_nodes() == 3


def test_count_by_type(gre: Neo4jGREAdapter) -> None:
    gre.create_node(
        Organization(name="TICO", org_name="TICO", org_kind=OrgKind.STATISTICAL_AGENT)
    )
    gre.create_node(
        Organization(name="TDI", org_name="TDI", org_kind=OrgKind.REGULATOR)
    )
    gre.create_node(
        RegulationDocument(
            name="Plan",
            kind=DocumentKind.STAT_PLAN,
            title="Plan",
            hash="h",
        )
    )
    by_type = gre.count_by_type()
    assert by_type["Organization"] == 2
    assert by_type["RegulationDocument"] == 1


def test_create_relationship(gre: Neo4jGREAdapter) -> None:
    cl = CodeList(name="Cause of Loss", code_list_name="Cause of Loss")
    cv = CodeValue(
        name="25 — Windstorm",
        code="25",
        description="Windstorm",
        code_list_id=cl.id,
    )
    gre.create_node(cl)
    gre.create_node(cv)

    rel = GRERelationship(
        type=RelationshipType.HAS_VALUE,
        src_node_id=cl.id,
        dst_node_id=cv.id,
    )
    gre.create_relationship(rel)
    assert gre.count_relationships() == 1


def test_cites_relationship_carries_span(gre: Neo4jGREAdapter) -> None:
    src_id = uuid4()
    dst_id = uuid4()
    # Create stub nodes so the MATCH succeeds
    gre.create_node(
        Organization(
            name="src",
            org_name="src",
            org_kind=OrgKind.REGULATOR,
            id=src_id,
        )
    )
    gre.create_node(
        Organization(
            name="dst",
            org_name="dst",
            org_kind=OrgKind.REGULATOR,
            id=dst_id,
        )
    )

    cite = CitesRelationship(
        src_node_id=src_id,
        dst_node_id=dst_id,
        char_start=140,
        char_end=210,
        kind=CitationKind.DEFINES,
    )
    gre.create_relationship(cite)
    assert gre.count_relationships() == 1


def test_query_active_as_of(gre: Neo4jGREAdapter) -> None:
    doc = RegulationDocument(
        name="TICO TX Stat Plan",
        kind=DocumentKind.STAT_PLAN,
        title="TX Stat Plan",
        hash="active-test",
        status=NodeStatus.APPROVED,
        effective_from=date(2026, 1, 1),
    )
    gre.create_node(doc)

    # Query as of after effective date — should find it
    result = gre.query_active_as_of(
        node_type="RegulationDocument",
        name=doc.name,
        as_of=date(2026, 6, 1),
    )
    assert result is not None
    assert result.id == doc.id

    # Query as of before effective date — should not find it
    result_before = gre.query_active_as_of(
        node_type="RegulationDocument",
        name=doc.name,
        as_of=date(2025, 1, 1),
    )
    assert result_before is None


def test_wipe_all(gre: Neo4jGREAdapter) -> None:
    gre.create_node(
        Organization(name="X", org_name="X", org_kind=OrgKind.REGULATOR)
    )
    assert gre.count_nodes() == 1
    gre.wipe_all()
    assert gre.count_nodes() == 0


def test_node_roundtrip_preserves_all_fields(gre: Neo4jGREAdapter) -> None:
    """Critical: every Pydantic field must round-trip through Neo4j."""
    cl = CodeList(
        name="Cause of Loss",
        code_list_name="Cause of Loss",
        description="Loss-cause codes per Rule B§12",
        status=NodeStatus.APPROVED,
        effective_from=date(2026, 1, 1),
        created_by="seed-script",
    )
    gre.create_node(cl)
    fetched = gre.get_node(cl.id)
    assert fetched is not None
    assert isinstance(fetched, CodeList)
    assert fetched.code_list_name == cl.code_list_name
    assert fetched.description == cl.description
    assert fetched.status == NodeStatus.APPROVED
    assert fetched.effective_from == date(2026, 1, 1)
    assert fetched.created_by == "seed-script"
