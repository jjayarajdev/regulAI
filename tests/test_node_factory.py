"""node_factory leniency — agent proposals that carry more than the schema
wants should be normalized, not skipped (skips silently lose canon)."""

from uuid import uuid4

from packages.core.enums import NodeType, RuleKind
from packages.lhs.materialization.node_factory import proposed_to_typed_node
from packages.lhs.sentinel.schema import ProposedNode


def test_statute_rule_with_redundant_heading_materializes():
    """Sentinel filled section + rule_number AND a descriptive heading (the
    OK intake shape). Statutes are cited by §section.number — the heading is
    dropped, and the rule must materialize instead of skipping."""
    doc_uuid, rule_uuid = uuid4(), uuid4()
    p = ProposedNode(
        temp_id="r1", type=NodeType.RULE, name="Rule 1 — Quarterly Reporting",
        confidence=0.95, section="1", rule_number=1,
        heading="Quarterly Reporting Obligation", document_temp_id="doc1",
    )
    rule = proposed_to_typed_node(p, rule_uuid, {"doc1": doc_uuid, "r1": rule_uuid})
    assert rule.rule_kind == RuleKind.STATUTE
    assert rule.heading is None
    assert rule.section == "1"
    assert rule.rule_number == 1


def test_memo_rule_still_lifts_heading_from_section():
    """The existing memo leniency is unchanged: no rule_number → memo kind,
    heading lifted off section when Sentinel parked it there."""
    doc_uuid, rule_uuid = uuid4(), uuid4()
    p = ProposedNode(
        temp_id="r2", type=NodeType.RULE, name="Weekly claims data call",
        confidence=0.9, section="Special Provisions", document_temp_id="doc1",
    )
    rule = proposed_to_typed_node(p, rule_uuid, {"doc1": doc_uuid, "r2": rule_uuid})
    assert rule.rule_kind == RuleKind.MEMO_DIRECTIVE
    assert rule.heading == "Special Provisions"
    assert rule.section is None
