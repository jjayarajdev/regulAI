"""Cluster C — parser/LLM boundary hard gate tests.

The check is pure: takes a SentinelExtraction + document_label, raises
ParserBoundaryViolation if the doc is parser-owned and the extraction
proposes parser-owned-type nodes. No DB required for these tests.
"""

from __future__ import annotations

import pytest

from packages.core.enums import NodeType
from packages.lhs.materialization.parser_boundary import (
    PARSER_OWNED_SLUGS,
    PARSER_OWNED_TYPES,
    ParserBoundaryViolation,
    check_parser_boundary,
)
from packages.lhs.sentinel.schema import ProposedNode, SentinelExtraction


def _extraction_with(*nodes: ProposedNode) -> SentinelExtraction:
    return SentinelExtraction(
        summary="test extraction",
        proposed_nodes=list(nodes),
        proposed_relationships=[],
        citations=[],
        uncited_spans=[],
        document_total_chars=0,
    )


def test_check_passes_when_doc_is_not_parser_owned():
    """Non-parser-owned docs may propose any node type, including
    RecordLayout / FieldRequirement — Citizens, FHCF, future state docs
    all rely on this."""
    extraction = _extraction_with(
        ProposedNode(
            temp_id="t1",
            type=NodeType.RECORD_LAYOUT,
            name="Citizens Office-Prescribed Policy Data Format",
            confidence=0.9,
        ),
        ProposedNode(
            temp_id="t2",
            type=NodeType.FIELD_REQUIREMENT,
            name="RISK_ZIP",
            confidence=0.9,
        ),
    )
    # Doesn't raise — this is the FL Citizens case
    check_parser_boundary(extraction, document_label="fl-627-351")


def test_check_passes_on_parser_owned_doc_with_only_allowed_types():
    """Parser-owned docs may still carry Rules, Documents, etc. from
    Sentinel — only RecordLayout / FieldRequirement are forbidden."""
    extraction = _extraction_with(
        ProposedNode(
            temp_id="t1",
            type=NodeType.RULE,
            name="Rule C.1 — Layout overview",
            confidence=0.9,
            section="C",
            rule_number=1,
        ),
    )
    # Doesn't raise — Rules on a parser-owned doc are fine
    check_parser_boundary(extraction, document_label="tico-section-c")


def test_check_raises_on_parser_owned_doc_with_recordlayout():
    """The exact regression Cluster C prevents: a Sentinel extraction of
    a parser-owned doc proposes a hallucinated RecordLayout."""
    extraction = _extraction_with(
        ProposedNode(
            temp_id="t1",
            type=NodeType.RECORD_LAYOUT,
            name="Residential Property Fixed ASCII Standard Data Format Layout",
            confidence=0.7,
        ),
    )
    with pytest.raises(ParserBoundaryViolation) as exc:
        check_parser_boundary(extraction, document_label="tico-section-c")
    assert "tico-section-c" in str(exc.value)
    assert "RecordLayout" in str(exc.value)
    assert "Residential Property" in str(exc.value)


def test_check_raises_on_parser_owned_doc_with_fieldrequirement():
    """The 138-orphan-fields class of bug — Sentinel proposes wire-format
    fields that the parser already owns."""
    extraction = _extraction_with(
        ProposedNode(
            temp_id="t1",
            type=NodeType.FIELD_REQUIREMENT,
            name="Policy Number — col 1",
            confidence=0.7,
            field_name="Policy Number",
        ),
        ProposedNode(
            temp_id="t2",
            type=NodeType.FIELD_REQUIREMENT,
            name="ZIP — col 50",
            confidence=0.7,
            field_name="ZIP",
        ),
    )
    with pytest.raises(ParserBoundaryViolation) as exc:
        check_parser_boundary(extraction, document_label="tico-record-layout-homeowners")
    # Both offenders surface in the error message
    assert "FieldRequirement" in str(exc.value)
    assert exc.value.document_label == "tico-record-layout-homeowners"
    assert len(exc.value.offenders) == 2


def test_materialize_invokes_the_gate(tmp_path, monkeypatch):
    """The gate must run inside materialize() itself — any direct caller
    bypassing batch_extract's filter is still protected."""
    # We don't need a working Neo4j here; the gate runs before any DB
    # access. Pass a sentinel object that would fail loudly if used.
    from packages.lhs.materialization.materialize import materialize

    extraction = _extraction_with(
        ProposedNode(
            temp_id="t1",
            type=NodeType.RECORD_LAYOUT,
            name="Phantom Layout",
            confidence=0.7,
        ),
    )

    class _ShouldNotBeUsed:
        def __getattr__(self, item):  # pragma: no cover - failure mode
            raise AssertionError(
                f"materialize() reached into gre.{item} despite a parser-"
                f"boundary violation — the Phase 0 gate didn't fire."
            )

    with pytest.raises(ParserBoundaryViolation):
        materialize(
            extraction,
            _ShouldNotBeUsed(),
            document_label="tico-section-c",
            snapshot_dir=tmp_path,
        )


def test_materialize_source_parser_bypasses_gate(tmp_path):
    """The parser itself produces RecordLayout / FieldRequirement on
    parser-owned slugs — that's the point. materialize(source='parser')
    must bypass the gate so parse_record_layout.py can do its job."""
    from packages.lhs.materialization.materialize import materialize

    extraction = _extraction_with(
        ProposedNode(
            temp_id="t1",
            type=NodeType.RECORD_LAYOUT,
            name="Premium Record Layout",
            confidence=1.0,
        ),
    )

    # Track whether the gate ran by inspecting the gre fallthrough — but
    # since we don't want to spin up Neo4j here, simply assert the gate
    # raised on source='sentinel' and didn't on source='parser'.
    with pytest.raises(ParserBoundaryViolation):
        materialize(
            extraction, gre=object(), document_label="tico-section-c",
            snapshot_dir=tmp_path, source="sentinel",
        )

    # With source='parser', the gate is bypassed and execution proceeds
    # into materialize phases. We'll fail later at the first gre.* call,
    # but a non-ParserBoundaryViolation exception confirms the gate
    # didn't intercept.
    with pytest.raises(Exception) as exc:
        materialize(
            extraction, gre=object(), document_label="tico-section-c",
            snapshot_dir=tmp_path, source="parser",
        )
    assert not isinstance(exc.value, ParserBoundaryViolation), (
        "Gate fired on source='parser' — the parser must be allowed to "
        "produce RecordLayout / FieldRequirement on parser-owned docs."
    )


def test_parser_owned_slugs_match_wire_layouts_registry():
    """Drift guard: PARSER_OWNED_SLUGS and the registry's
    WIRE_LAYOUTS_FOR_SLUG keys should agree — they're two views of the
    same fact ("this doc is parser-owned"). If they diverge, one of them
    is wrong."""
    from api.registry import WIRE_LAYOUTS_FOR_SLUG

    assert set(WIRE_LAYOUTS_FOR_SLUG.keys()) == set(PARSER_OWNED_SLUGS), (
        "PARSER_OWNED_SLUGS and WIRE_LAYOUTS_FOR_SLUG.keys() disagree. "
        f"In SLUGS not LAYOUTS: {set(PARSER_OWNED_SLUGS) - set(WIRE_LAYOUTS_FOR_SLUG)}. "
        f"In LAYOUTS not SLUGS: {set(WIRE_LAYOUTS_FOR_SLUG) - set(PARSER_OWNED_SLUGS)}."
    )


def test_parser_owned_types_includes_layout_and_field():
    """If someone adds a third type the parser owns (e.g. ColumnSpan),
    they should add it to PARSER_OWNED_TYPES too. This test locks in
    the current scope so we notice if the set is silently widened."""
    assert NodeType.RECORD_LAYOUT in PARSER_OWNED_TYPES
    assert NodeType.FIELD_REQUIREMENT in PARSER_OWNED_TYPES
    assert NodeType.RULE not in PARSER_OWNED_TYPES  # Sentinel may extract Rules
    assert NodeType.CODE_LIST not in PARSER_OWNED_TYPES  # both sources legitimate
