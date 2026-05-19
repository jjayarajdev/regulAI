"""Pydantic models for the 14 closed-vocabulary KG node types.

Every node carries common base fields (id, type, name, version, status,
effective_from/to, created_at, created_by) plus type-specific properties.

In Neo4j these map to nodes labeled `:GRENode:<TypeName>`.

Citations to regulation source spans are modeled as a CITES relationship
with char_start/char_end properties, NOT as fields on these models.
See packages/core/relationships.py.
"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    DocumentKind,
    HITLSeverity,
    KGAuditAction,
    NodeStatus,
    OrgKind,
    ReportCadence,
)


class GRENodeBase(BaseModel):
    """Common properties shared by every KG node."""

    model_config = ConfigDict(use_enum_values=False)

    id: UUID = Field(default_factory=uuid4)
    type: str  # set by each subclass via Literal default
    name: str
    version: int = 1
    status: NodeStatus = NodeStatus.DRAFT
    effective_from: date | None = None
    effective_to: date | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    created_by: str | None = None


class RegulationDocument(GRENodeBase):
    """Source regulation document — stat plan, statute, bulletin, rule adoption.

    Schema justification: Rules 1, 21, 28, 29 of TICO Stat Plan reference
    TDI-issued instructions; Bulletin B-0008-25 is itself a regulation document.
    """

    type: Literal["RegulationDocument"] = "RegulationDocument"
    kind: DocumentKind
    title: str
    hash: str
    source_url: str | None = None
    published_date: date | None = None


class StatPlanEdition(GRENodeBase):
    """A specific version of a stat plan with effective date.

    Schema justification: Rule 1 (Scope) — "reporting periods on or after
    January 1, 2026" supersedes "July 1, 2022."
    """

    type: Literal["StatPlanEdition"] = "StatPlanEdition"
    edition_name: str  # e.g., "THSP_2026"
    effective_date: date
    supersedes_edition: str | None = None


class Rule(GRENodeBase):
    """A numbered rule within a regulation document. Citation anchor.

    Schema justification: Section A has 35 numbered rules; Section B has 20+;
    every other node naturally cites a specific rule.
    """

    type: Literal["Rule"] = "Rule"
    section: str  # "A", "B", "C", ...
    rule_number: int
    title: str
    document_id: UUID  # back-reference to the RegulationDocument


class ReportTemplate(GRENodeBase):
    """A required report (Premium / Loss / Notice / Notice Count / Transmittal).

    Schema justification: Rule 28 lists the four data reports;
    Rule 29 defines the transmittal as its own report.
    """

    type: Literal["ReportTemplate"] = "ReportTemplate"
    report_name: str
    cadence: ReportCadence
    deadline_days_after_close: int


class RecordLayout(GRENodeBase):
    """The layout of records within a report (Sections C/D/E/G of the plan).

    Schema justification: Sections C, D, E, G are each titled "Record Layout for X."
    """

    type: Literal["RecordLayout"] = "RecordLayout"
    layout_name: str
    record_format: str = "Fixed-ASCII-SDF"


class FieldRequirement(GRENodeBase):
    """A specific required field on a record layout.

    Schema justification: Sections C–G enumerate fields with positions and formats.
    """

    type: Literal["FieldRequirement"] = "FieldRequirement"
    field_name: str
    position_start: int | None = None
    position_length: int | None = None
    format: str | None = None
    is_required: bool = True
    code_list_ref: UUID | None = None  # if value comes from a code list


class CodeList(GRENodeBase):
    """A named enumeration of allowed values.

    Schema justification: Section B is structured as ~20 named code lists;
    the dominant pattern in the regulation. Primary type.
    """

    type: Literal["CodeList"] = "CodeList"
    code_list_name: str  # e.g., "Cause of Loss", "Line of Business"
    description: str | None = None


class CodeValue(GRENodeBase):
    """A single value within a CodeList. Primary type.

    Schema justification: Every code table in Section B; Rule 30 Tenure;
    Rule 31 TWIA; Section F HB 2067 reasons.
    """

    type: Literal["CodeValue"] = "CodeValue"
    code: str  # e.g., "25", "WH", "02"
    description: str
    notes: str | None = None
    code_list_id: UUID


class CoverageType(GRENodeBase):
    """A coverage part: Dwelling, Personal Property, Loss of Use, etc.

    Schema justification: Rule 6 — "for HO and dwelling forms: Dwelling,
    Personal Property, Loss of Use."
    """

    type: Literal["CoverageType"] = "CoverageType"
    coverage_name: str
    applies_to_forms: list[str] = Field(default_factory=list)


class EndorsementRule(GRENodeBase):
    """An endorsement form classification rule.

    Schema justification: Rule 18 endorsement codes; Rule 33 Replacement Cost endorsements.
    """

    type: Literal["EndorsementRule"] = "EndorsementRule"
    form_code: str
    form_name: str
    coverage_effect: str | None = None


class BulletinOverride(GRENodeBase):
    """Mid-edition modification to a base rule, originating from a TDI bulletin.

    Schema justification: Bulletin B-0008-25 modifies Stat Plan implementation timing;
    similar bulletins are typical.
    """

    type: Literal["BulletinOverride"] = "BulletinOverride"
    bulletin_ref: UUID  # RegulationDocument.id of kind=Bulletin
    effective_date: date


class ReconciliationRule(GRENodeBase):
    """A rule requiring one report to reconcile against another data source.

    Schema justification: Rule 35 — "counts should reconcile with those provided
    to the NAIC for the Market Conduct Annual Statement (MCAS)."
    """

    type: Literal["ReconciliationRule"] = "ReconciliationRule"
    from_report_id: UUID
    against_target: str  # e.g., "NAIC MCAS Cancellations"
    tolerance: str | None = None


class Organization(GRENodeBase):
    """A regulatory or industry organization referenced by the regs.

    Schema justification: Rule 28 (TICO); plan published by TDI; NAIC in Rule 35;
    ISO/AAIS in B§5; TWIA in Rule 31.
    """

    type: Literal["Organization"] = "Organization"
    org_name: str
    org_kind: OrgKind
    description: str | None = None


class HITLTriggerRule(GRENodeBase):
    """Application-internal rule for routing records to RHS HITL.

    Lives in the KG (versioned, citable) but cited from internal SOPs,
    not regulations directly. Application-derived, not regulation-derived.
    """

    type: Literal["HITLTriggerRule"] = "HITLTriggerRule"
    trigger_name: str
    condition_summary: str
    severity: HITLSeverity


class KGAuditEntry(GRENodeBase):
    """Audit-trail entry for every logical mutation to the KG canon.

    One row per logical operation (a 'bulletin_apply' produces multiple node
    writes but a single audit entry, with MUTATED_BY edges pointing back from
    every affected node). Mirrors GOLD_AUDIT.USER_ACTION on the RHS side.

    For CLI scripts actor='system' is acceptable. For workstation-triggered
    flows the caller passes the authenticated user.
    """

    type: Literal["KGAuditEntry"] = "KGAuditEntry"
    action: KGAuditAction
    actor: str = "system"
    summary: str
    details_json: str | None = None  # JSON blob with operation-specific context
    occurred_at: datetime = Field(default_factory=datetime.now)
    affected_count: int = 0  # number of MUTATED_BY edges this entry will receive


# Discriminated union covering every node type — useful for parsing extractions
# and for typed iteration over heterogeneous node lists.
GRENode = (
    RegulationDocument
    | StatPlanEdition
    | Rule
    | ReportTemplate
    | RecordLayout
    | FieldRequirement
    | CodeList
    | CodeValue
    | CoverageType
    | EndorsementRule
    | BulletinOverride
    | ReconciliationRule
    | Organization
    | HITLTriggerRule
    | KGAuditEntry
)
