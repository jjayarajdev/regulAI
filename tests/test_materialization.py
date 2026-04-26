"""Materialization tests — full integration with Neo4j.

Requires Neo4j running. The fixture wipes the DB before each test.
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from neo4j.exceptions import ServiceUnavailable

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
from packages.core.enums import (
    CitationKind,
    DocumentKind,
    NodeStatus,
    NodeType,
    OrgKind,
    RelationshipType,
)
from packages.core.nodes import Organization, RegulationDocument
from packages.lhs.materialization.materialize import materialize
from packages.lhs.sentinel.schema import (
    CitationProposal,
    ProposedNode,
    ProposedRelationship,
    SentinelExtraction,
    UncitedSpan,
)


@pytest.fixture
def gre():
    try:
        with Neo4jGREAdapter() as adapter:
            adapter.wipe_all()
            yield adapter
    except ServiceUnavailable:
        pytest.skip("Neo4j not running")


def _basic_extraction() -> SentinelExtraction:
    return SentinelExtraction(
        summary="Test extraction with a doc, an org, and a rule.",
        document_total_chars=500,
        proposed_nodes=[
            ProposedNode(
                temp_id="doc-1",
                type=NodeType.REGULATION_DOCUMENT,
                name="Test Bulletin Alpha",
                confidence=0.95,
                kind=DocumentKind.BULLETIN,
                title="Test Bulletin Alpha",
                hash="hash-alpha",
            ),
            ProposedNode(
                temp_id="org-tdi",
                type=NodeType.ORGANIZATION,
                name="TDI",
                confidence=0.99,
                org_name="Texas Department of Insurance",
                org_kind=OrgKind.REGULATOR,
            ),
            ProposedNode(
                temp_id="rule-1",
                type=NodeType.RULE,
                name="Rule §1 — Authority",
                confidence=0.95,
                section="§1",
                rule_number=1,
                title="Authority",
                document_temp_id="doc-1",
            ),
        ],
        proposed_relationships=[
            ProposedRelationship(
                type=RelationshipType.CONTAINED_IN,
                src_temp_id="rule-1",
                dst_temp_id="doc-1",
            ),
        ],
        citations=[
            CitationProposal(
                node_temp_id="rule-1",
                char_start=10,
                char_end=80,
                kind=CitationKind.DEFINES,
            ),
        ],
        uncited_spans=[],
    )


def test_materialize_creates_nodes_and_relationships(gre: Neo4jGREAdapter) -> None:
    with TemporaryDirectory() as tmp:
        result = materialize(
            _basic_extraction(),
            gre,
            document_label="test-bulletin-alpha",
            snapshot_dir=Path(tmp),
        )

        assert len(result.nodes_created) == 3
        assert result.relationships_created == 1  # CONTAINED_IN
        assert result.citations_created == 1
        assert gre.count_nodes() == 3
        # 1 explicit relationship + 1 citation = 2 total relationships
        assert gre.count_relationships() == 2

        assert result.materialized_path is not None
        assert result.materialized_path.exists()
        snapshot = json.loads(result.materialized_path.read_text())
        assert snapshot["document_label"] == "test-bulletin-alpha"
        assert len(snapshot["nodes_created"]) == 3


def test_materialize_dedupes_against_existing_nodes(gre: Neo4jGREAdapter) -> None:
    """Pre-existing TDI Organization should be reused, not duplicated."""
    pre_existing = Organization(
        name="TDI",
        org_name="Texas Department of Insurance",
        org_kind=OrgKind.REGULATOR,
        status=NodeStatus.APPROVED,
    )
    gre.create_node(pre_existing)

    with TemporaryDirectory() as tmp:
        result = materialize(
            _basic_extraction(),
            gre,
            document_label="test-dedup",
            snapshot_dir=Path(tmp),
        )

    # 3 proposals: doc + org + rule. Org should match existing → reused.
    assert len(result.nodes_reused) == 1
    assert result.nodes_reused[0] == ("Organization", "TDI")
    assert len(result.nodes_created) == 2  # doc + rule

    # KG should have: pre-existing TDI + new doc + new rule = 3 nodes total
    assert gre.count_nodes() == 3


def test_materialize_dedupes_documents_by_hash(gre: Neo4jGREAdapter) -> None:
    """A RegulationDocument with a matching hash should be reused even if names differ."""
    pre_existing = RegulationDocument(
        name="Test Bulletin Alpha (existing)",
        kind=DocumentKind.BULLETIN,
        title="Test Bulletin Alpha",
        hash="hash-alpha",  # same as proposed
        status=NodeStatus.APPROVED,
    )
    gre.create_node(pre_existing)

    with TemporaryDirectory() as tmp:
        result = materialize(
            _basic_extraction(),
            gre,
            document_label="test-doc-hash-dedup",
            snapshot_dir=Path(tmp),
        )

    # The doc should be reused via hash match
    assert ("RegulationDocument", "Test Bulletin Alpha") in result.nodes_reused
    # Only org + rule are created
    assert len(result.nodes_created) == 2


def test_materialize_resolves_cross_references(gre: Neo4jGREAdapter) -> None:
    """Rule's document_temp_id must resolve to the doc's UUID."""
    with TemporaryDirectory() as tmp:
        materialize(
            _basic_extraction(),
            gre,
            document_label="test-xref",
            snapshot_dir=Path(tmp),
        )

    # Verify the Rule has document_id pointing at the doc
    from packages.core.nodes import Rule
    with gre.driver.session(database=gre.database) as session:
        rec = session.run(
            "MATCH (r:Rule {name: 'Rule §1 — Authority'}) RETURN r"
        ).single()
        assert rec is not None
        rule_data = dict(rec["r"].items())

    rule = Rule.model_validate(rule_data)
    doc_match = session = gre.driver.session(database=gre.database)
    with gre.driver.session(database=gre.database) as session:
        rec = session.run(
            "MATCH (d:RegulationDocument {name: 'Test Bulletin Alpha'}) RETURN d.id AS id"
        ).single()
        assert rec is not None
        from uuid import UUID
        assert rule.document_id == UUID(rec["id"])
