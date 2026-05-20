"""Convert flat ProposedNode → typed GRENode subclass.

The Sentinel agent emits a flat ProposedNode with all type-specific fields
optional. The materialization step picks the right typed Pydantic class
based on `type` and pulls the relevant fields.
"""

from datetime import date, datetime
from uuid import UUID

from packages.core.enums import NodeType, RuleKind
from packages.core.nodes import (
    BulletinOverride,
    CodeList,
    CodeValue,
    CoverageType,
    EndorsementRule,
    FieldRequirement,
    GRENode,
    HITLTriggerRule,
    Organization,
    ReconciliationRule,
    RecordLayout,
    RegulationDocument,
    ReportTemplate,
    Rule,
    StatPlanEdition,
)
from packages.lhs.sentinel.schema import ProposedNode


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def proposed_to_typed_node(
    p: ProposedNode,
    node_id: UUID,
    temp_id_to_uuid: dict[str, UUID],
) -> GRENode:
    """Map a flat ProposedNode to its typed Pydantic class.

    `temp_id_to_uuid` resolves cross-references (e.g., a Rule's document_temp_id
    points at a ProposedNode for the RegulationDocument; we look up the UUID
    that was assigned to that temp_id).
    """
    common_kwargs = {
        "id": node_id,
        "name": p.name,
        "created_at": datetime.now(),
        "created_by": "sentinel",
        "effective_from": _parse_date(p.effective_date),
    }

    t = p.type

    if t == NodeType.REGULATION_DOCUMENT:
        return RegulationDocument(
            **common_kwargs,
            kind=p.kind,
            title=p.title or p.name,
            hash=p.hash or f"sentinel-{p.temp_id}",
            source_url=p.source_url,
        )

    if t == NodeType.STAT_PLAN_EDITION:
        if not p.edition_name:
            raise ValueError(f"StatPlanEdition '{p.name}' missing edition_name")
        if not p.effective_date:
            raise ValueError(f"StatPlanEdition '{p.name}' missing effective_date")
        return StatPlanEdition(
            **common_kwargs,
            edition_name=p.edition_name,
            effective_date=_parse_date(p.effective_date) or date.today(),
            supersedes_edition=p.supersedes_edition,
        )

    if t == NodeType.RULE:
        document_id = temp_id_to_uuid.get(p.document_temp_id) if p.document_temp_id else None
        if not document_id:
            raise ValueError(f"Rule '{p.name}' has unresolvable document_temp_id={p.document_temp_id!r}")

        # Infer rule_kind from the proposal shape:
        #   - integer rule_number + section → STATUTE
        #   - section set (as a heading) but no rule_number → MEMO_DIRECTIVE
        #   - neither → MEMO_DIRECTIVE with no anchor (rare; still allowed)
        # The OIR-22-04M memo provisions land as MEMO_DIRECTIVE.
        if p.rule_kind:
            rule_kind = p.rule_kind
        elif p.section is not None and p.rule_number is not None:
            rule_kind = RuleKind.STATUTE
        else:
            rule_kind = RuleKind.MEMO_DIRECTIVE

        # Statute-kind rules must cite §section.number for traceability.
        # Bulletin/memo provisions cite by document + heading instead, so
        # we don't require section/rule_number for those.
        if rule_kind == RuleKind.STATUTE and (p.section is None or p.rule_number is None):
            raise ValueError(
                f"Statute-kind Rule '{p.name}' missing section/rule_number "
                f"(rule_kind={rule_kind.value!r}, section={p.section!r}, rule_number={p.rule_number!r})"
            )

        # For memo/bulletin provisions, lift the heading off the `section`
        # field if Sentinel parked it there (which it does today — see
        # OIR-22-04M extraction). Future Sentinel runs can fill `heading`
        # directly; we accept both.
        heading = p.heading
        if rule_kind != RuleKind.STATUTE and heading is None and p.section is not None:
            heading = p.section

        return Rule(
            **common_kwargs,
            rule_kind=rule_kind,
            section=p.section if rule_kind == RuleKind.STATUTE else None,
            rule_number=p.rule_number if rule_kind == RuleKind.STATUTE else None,
            heading=heading,
            title=p.title or p.name,
            document_id=document_id,
        )

    if t == NodeType.REPORT_TEMPLATE:
        return ReportTemplate(
            **common_kwargs,
            report_name=p.report_name or p.name,
            cadence=p.cadence,
            deadline_days_after_close=p.deadline_days_after_close or 45,
        )

    if t == NodeType.RECORD_LAYOUT:
        return RecordLayout(
            **common_kwargs,
            layout_name=p.layout_name or p.name,
            record_format=p.record_format or "Fixed-ASCII-SDF",
        )

    if t == NodeType.FIELD_REQUIREMENT:
        return FieldRequirement(
            **common_kwargs,
            field_name=p.field_name or p.name,
            position_start=p.position_start,
            position_length=p.position_length,
            format=p.format,
            is_required=p.is_required if p.is_required is not None else True,
        )

    if t == NodeType.CODE_LIST:
        return CodeList(
            **common_kwargs,
            code_list_name=p.code_list_name or p.name,
            description=p.description,
        )

    if t == NodeType.CODE_VALUE:
        if p.code is None:
            raise ValueError(f"CodeValue '{p.name}' missing code")
        code_list_id = temp_id_to_uuid.get(p.code_list_temp_id) if p.code_list_temp_id else None
        if not code_list_id:
            raise ValueError(f"CodeValue '{p.name}' has unresolvable code_list_temp_id")
        return CodeValue(
            **common_kwargs,
            code=p.code,
            description=p.description or p.name,
            notes=p.notes,
            code_list_id=code_list_id,
        )

    if t == NodeType.COVERAGE_TYPE:
        return CoverageType(
            **common_kwargs,
            coverage_name=p.coverage_name or p.name,
            applies_to_forms=p.applies_to_forms or [],
        )

    if t == NodeType.ENDORSEMENT_RULE:
        return EndorsementRule(
            **common_kwargs,
            form_code=p.form_code or p.name,
            form_name=p.form_name or p.name,
            coverage_effect=p.coverage_effect,
        )

    if t == NodeType.BULLETIN_OVERRIDE:
        bulletin_id = temp_id_to_uuid.get(p.bulletin_temp_id) if p.bulletin_temp_id else None
        if not bulletin_id:
            raise ValueError(f"BulletinOverride '{p.name}' has unresolvable bulletin_temp_id")
        return BulletinOverride(
            **common_kwargs,
            bulletin_ref=bulletin_id,
            effective_date=_parse_date(p.effective_date) or date.today(),
        )

    if t == NodeType.RECONCILIATION_RULE:
        from_report_id = temp_id_to_uuid.get(p.from_report_temp_id) if p.from_report_temp_id else None
        if not from_report_id:
            raise ValueError(f"ReconciliationRule '{p.name}' has unresolvable from_report_temp_id")
        return ReconciliationRule(
            **common_kwargs,
            from_report_id=from_report_id,
            against_target=p.against_target or "unspecified",
            tolerance=p.tolerance,
        )

    if t == NodeType.ORGANIZATION:
        if p.org_kind is None:
            raise ValueError(f"Organization '{p.name}' missing org_kind")
        return Organization(
            **common_kwargs,
            org_name=p.org_name or p.name,
            org_kind=p.org_kind,
            description=p.description,
        )

    if t == NodeType.HITL_TRIGGER_RULE:
        if p.severity is None:
            raise ValueError(f"HITLTriggerRule '{p.name}' missing severity")
        return HITLTriggerRule(
            **common_kwargs,
            trigger_name=p.trigger_name or p.name,
            condition_summary=p.condition_summary or p.description or "",
            severity=p.severity,
        )

    raise ValueError(f"Unknown node type: {t!r}")
