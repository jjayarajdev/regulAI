"""Pydantic model validation tests — no external dependencies (no Neo4j needed)."""

from datetime import date
from uuid import uuid4

import pytest

from packages.core.enums import (
    CitationKind,
    DocumentKind,
    HITLSeverity,
    NodeStatus,
    OrgKind,
    RelationshipType,
    ReportCadence,
)
from packages.core.nodes import (
    BulletinOverride,
    CodeList,
    CodeValue,
    CoverageType,
    EndorsementRule,
    FieldRequirement,
    HITLTriggerRule,
    Organization,
    ReconciliationRule,
    RecordLayout,
    RegulationDocument,
    ReportTemplate,
    Rule,
    StatPlanEdition,
)
from packages.core.relationships import CitesRelationship, GRERelationship


def test_regulation_document_construction() -> None:
    doc = RegulationDocument(
        name="TICO TX Stat Plan",
        kind=DocumentKind.STAT_PLAN,
        title="Texas Statistical Plan for Residential Risks",
        hash="abc123",
    )
    assert doc.type == "RegulationDocument"
    assert doc.kind == DocumentKind.STAT_PLAN
    assert doc.version == 1
    assert doc.status == NodeStatus.DRAFT


def test_stat_plan_edition_construction() -> None:
    edition = StatPlanEdition(
        name="THSP_2026",
        edition_name="THSP_2026",
        effective_date=date(2026, 1, 1),
        supersedes_edition="THSP_2022",
    )
    assert edition.effective_date == date(2026, 1, 1)
    assert edition.type == "StatPlanEdition"


def test_rule_construction() -> None:
    doc_id = uuid4()
    rule = Rule(
        name="A.28 Designated Statistical Agent",
        section="A",
        rule_number=28,
        title="Designated Statistical Agent",
        document_id=doc_id,
    )
    assert rule.section == "A"
    assert rule.rule_number == 28
    assert rule.document_id == doc_id


def test_report_template_construction() -> None:
    template = ReportTemplate(
        name="HO Premiums",
        report_name="Dwelling, HO Premiums",
        cadence=ReportCadence.MONTHLY,
        deadline_days_after_close=45,
    )
    assert template.cadence == ReportCadence.MONTHLY
    assert template.deadline_days_after_close == 45


def test_record_layout_construction() -> None:
    layout = RecordLayout(
        name="Section C — Premiums",
        layout_name="Premiums Record Layout",
    )
    assert layout.record_format == "Fixed-ASCII-SDF"


def test_field_requirement_construction() -> None:
    field = FieldRequirement(
        name="ZIP Code",
        field_name="ZIP_CODE",
        position_start=131,
        position_length=5,
        format="numeric",
    )
    assert field.is_required is True
    assert field.position_start == 131


def test_code_list_and_value() -> None:
    cl = CodeList(
        name="Cause of Loss",
        code_list_name="Cause of Loss",
        description="Loss cause classification per Rule B§12",
    )
    cv = CodeValue(
        name="25 — Windstorm",
        code="25",
        description="Windstorm",
        code_list_id=cl.id,
    )
    assert cv.code == "25"
    assert cv.code_list_id == cl.id


def test_coverage_type_construction() -> None:
    cov = CoverageType(
        name="Dwelling",
        coverage_name="Dwelling",
        applies_to_forms=["HO-3", "HO-5", "DP-3"],
    )
    assert "HO-3" in cov.applies_to_forms


def test_endorsement_rule_construction() -> None:
    er = EndorsementRule(
        name="HO-15",
        form_code="HO-15",
        form_name="Special Personal Property Coverage",
    )
    assert er.form_code == "HO-15"


def test_bulletin_override_construction() -> None:
    bid = uuid4()
    bo = BulletinOverride(
        name="B-0008-25 override",
        bulletin_ref=bid,
        effective_date=date(2026, 4, 1),
    )
    assert bo.bulletin_ref == bid


def test_reconciliation_rule_construction() -> None:
    report_id = uuid4()
    rr = ReconciliationRule(
        name="Notice Count vs MCAS",
        from_report_id=report_id,
        against_target="NAIC MCAS Cancellations",
    )
    assert rr.against_target == "NAIC MCAS Cancellations"


def test_organization_construction() -> None:
    org = Organization(
        name="TICO",
        org_name="Texas Insurance Checking Office",
        org_kind=OrgKind.STATISTICAL_AGENT,
    )
    assert org.org_kind == OrgKind.STATISTICAL_AGENT


def test_hitl_trigger_rule_construction() -> None:
    htr = HITLTriggerRule(
        name="WH/WN Ambiguity",
        trigger_name="WH-vs-WN classification ambiguity",
        condition_summary="Wind/hail claim during named storm requires manual review",
        severity=HITLSeverity.TIER2,
    )
    assert htr.severity == HITLSeverity.TIER2


def test_cites_relationship_construction() -> None:
    src, dst = uuid4(), uuid4()
    cr = CitesRelationship(
        src_node_id=src,
        dst_node_id=dst,
        char_start=140,
        char_end=210,
        kind=CitationKind.DEFINES,
    )
    assert cr.type == RelationshipType.CITES
    assert cr.char_end == 210


def test_generic_relationship_construction() -> None:
    src, dst = uuid4(), uuid4()
    rel = GRERelationship(
        type=RelationshipType.HAS_VALUE,
        src_node_id=src,
        dst_node_id=dst,
    )
    assert rel.type == RelationshipType.HAS_VALUE


def test_node_serialization_roundtrip() -> None:
    """JSON serialization should preserve all critical fields."""
    cl = CodeList(
        name="Cause of Loss",
        code_list_name="Cause of Loss",
        status=NodeStatus.APPROVED,
    )
    data = cl.model_dump(mode="json")
    assert data["type"] == "CodeList"
    assert data["status"] == "approved"
    assert data["code_list_name"] == "Cause of Loss"

    # Round-trip through JSON
    restored = CodeList.model_validate(data)
    assert restored.id == cl.id
    assert restored.code_list_name == cl.code_list_name


def test_invalid_enum_value_rejected() -> None:
    """Closed-vocabulary discipline: invalid enum values must be rejected."""
    with pytest.raises(ValueError):
        Organization(
            name="Bogus",
            org_name="Bogus Org",
            org_kind="NotARealKind",  # type: ignore[arg-type]
        )
