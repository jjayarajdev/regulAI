"""Sentinel agent + schema tests with a mocked LLM port.

These tests do NOT call OpenAI. Hermetic, fast, free.
"""

from typing import TypeVar

import pytest
from pydantic import BaseModel

from packages.core.enums import CitationKind, NodeType, RelationshipType
from packages.lhs.sentinel.agent import Sentinel
from packages.lhs.sentinel.prompts import build_system_prompt
from packages.lhs.sentinel.schema import (
    CitationProposal,
    ProposedNode,
    ProposedRelationship,
    SentinelExtraction,
    UncitedSpan,
)

T = TypeVar("T", bound=BaseModel)


class FakeLLM:
    """Stub LLMPort that returns a pre-canned SentinelExtraction."""

    def __init__(self, canned: SentinelExtraction) -> None:
        self.canned = canned
        self.calls: list[tuple[str, str, type]] = []

    def extract_structured(
        self,
        system_prompt: str,
        user_content: str,
        response_model: type[T],
    ) -> T:
        self.calls.append((system_prompt, user_content, response_model))
        return self.canned  # type: ignore[return-value]


def _sample_extraction() -> SentinelExtraction:
    """A small but realistic SentinelExtraction for tests."""
    return SentinelExtraction(
        summary="Test bulletin adds COL 26 (Named Storm Wind).",
        document_total_chars=1000,
        proposed_nodes=[
            ProposedNode(
                temp_id="doc-1",
                type=NodeType.REGULATION_DOCUMENT,
                name="Bulletin B-X",
                confidence=0.95,
                title="Test Bulletin",
            ),
            ProposedNode(
                temp_id="cv-26",
                type=NodeType.CODE_VALUE,
                name="COL 26 — Named Storm Wind",
                confidence=0.92,
                code="26",
                description="Named Storm Wind",
                code_list_temp_id="cl-col",
            ),
        ],
        proposed_relationships=[
            ProposedRelationship(
                type=RelationshipType.CITES,
                src_temp_id="cv-26",
                dst_temp_id="doc-1",
                char_start=100,
                char_end=300,
                citation_kind=CitationKind.DEFINES,
            ),
        ],
        citations=[
            CitationProposal(
                node_temp_id="cv-26",
                char_start=100,
                char_end=300,
                kind=CitationKind.DEFINES,
            ),
        ],
        uncited_spans=[
            UncitedSpan(char_start=900, char_end=1000, note="signature"),
        ],
    )


def test_extraction_schema_roundtrip() -> None:
    e = _sample_extraction()
    data = e.model_dump(mode="json")
    restored = SentinelExtraction.model_validate(data)
    assert restored.summary == e.summary
    assert len(restored.proposed_nodes) == 2
    assert restored.proposed_nodes[1].code == "26"
    assert restored.citations[0].kind == CitationKind.DEFINES


def test_sentinel_invokes_llm_with_schema() -> None:
    canned = _sample_extraction()
    fake = FakeLLM(canned)
    sentinel = Sentinel(fake)  # type: ignore[arg-type]

    result = sentinel.extract(
        document_text="some regulation text",
        document_label="test.md",
    )

    # Returned the canned response
    assert result is canned

    # Was called exactly once with the system prompt and the document content
    assert len(fake.calls) == 1
    sys_prompt, user_content, response_model = fake.calls[0]
    assert "RegulAI Sentinel" in sys_prompt
    assert "closed vocabulary" in sys_prompt.lower()
    assert "test.md" in user_content
    assert "some regulation text" in user_content
    assert response_model is SentinelExtraction


def test_system_prompt_lists_all_node_types() -> None:
    """Every closed-vocabulary type must appear in the system prompt."""
    prompt = build_system_prompt()
    for nt in NodeType:
        # Names appear without quotes; the wrapped name (e.g., RegulationDocument) should be present
        assert nt.value in prompt, f"{nt.value} missing from system prompt"


def test_system_prompt_lists_all_relationship_types() -> None:
    prompt = build_system_prompt()
    for rt in RelationshipType:
        assert rt.value in prompt, f"{rt.value} missing from system prompt"


def test_proposed_node_confidence_validation() -> None:
    """Confidence must be in [0, 1]."""
    with pytest.raises(ValueError):
        ProposedNode(
            temp_id="x",
            type=NodeType.RULE,
            name="bad",
            confidence=1.5,
        )
    with pytest.raises(ValueError):
        ProposedNode(
            temp_id="x",
            type=NodeType.RULE,
            name="bad",
            confidence=-0.1,
        )


def test_extraction_with_empty_lists_is_valid() -> None:
    """Edge case: agent returns no proposals (empty document)."""
    e = SentinelExtraction(
        summary="Empty document.",
        document_total_chars=0,
        proposed_nodes=[],
        proposed_relationships=[],
        citations=[],
        uncited_spans=[],
    )
    assert e.summary == "Empty document."


def test_uncited_span_requires_note() -> None:
    """Coverage discipline: every uncited span must explain itself."""
    span = UncitedSpan(char_start=0, char_end=50, note="header")
    assert span.note == "header"
