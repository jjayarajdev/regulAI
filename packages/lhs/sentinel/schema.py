"""SentinelExtraction — the structured output schema the agent fills.

The agent extracts to a "proposal" form: nodes/relationships have temp_ids
that are local to one extraction. After human approval, the GRE adapter
materializes proposals into real KG nodes/relationships with stable UUIDs
and SUPERSEDES chains where applicable.

Design constraint: must be compatible with OpenAI Structured Outputs (strict
JSON Schema). Properties are flat (not type-discriminated unions) — the agent
fills the type-specific fields and leaves the rest null.
"""

from pydantic import BaseModel, ConfigDict, Field

from packages.core.enums import (
    CitationKind,
    DocumentKind,
    HITLSeverity,
    NodeType,
    OrgKind,
    RelationshipType,
    ReportCadence,
)


class ProposedNode(BaseModel):
    """A node the agent proposes adding to the KG.

    The `type` field discriminates which subset of properties is meaningful.
    All properties are optional; the agent fills only those relevant to the type.
    """

    model_config = ConfigDict(extra="forbid")

    temp_id: str = Field(description="Local id used for cross-references within this extraction (e.g., 'doc1', 'rule_a28').")
    type: NodeType
    name: str = Field(description="Human-readable name/label for this node.")
    confidence: float = Field(ge=0.0, le=1.0)

    # Common-ish properties
    description: str | None = None
    title: str | None = None
    effective_date: str | None = Field(default=None, description="ISO date YYYY-MM-DD if applicable.")

    # RegulationDocument
    kind: DocumentKind | None = None
    hash: str | None = None
    source_url: str | None = None

    # StatPlanEdition
    edition_name: str | None = None
    supersedes_edition: str | None = None

    # Rule
    section: str | None = None
    rule_number: int | None = None

    # ReportTemplate
    report_name: str | None = None
    cadence: ReportCadence | None = None
    deadline_days_after_close: int | None = None

    # RecordLayout
    layout_name: str | None = None
    record_format: str | None = None

    # FieldRequirement
    field_name: str | None = None
    position_start: int | None = None
    position_length: int | None = None
    format: str | None = None
    is_required: bool | None = None

    # CodeList / CodeValue
    code_list_name: str | None = None
    code: str | None = None
    notes: str | None = None

    # CoverageType
    coverage_name: str | None = None
    applies_to_forms: list[str] | None = None

    # EndorsementRule
    form_code: str | None = None
    form_name: str | None = None
    coverage_effect: str | None = None

    # ReconciliationRule
    against_target: str | None = None
    tolerance: str | None = None

    # Organization
    org_name: str | None = None
    org_kind: OrgKind | None = None

    # HITLTriggerRule
    trigger_name: str | None = None
    condition_summary: str | None = None
    severity: HITLSeverity | None = None

    # Cross-references to other ProposedNodes by temp_id
    document_temp_id: str | None = Field(
        default=None,
        description="For Rule: temp_id of the RegulationDocument it belongs to.",
    )
    bulletin_temp_id: str | None = Field(
        default=None,
        description="For BulletinOverride: temp_id of the Bulletin RegulationDocument.",
    )
    from_report_temp_id: str | None = Field(
        default=None,
        description="For ReconciliationRule: temp_id of the source ReportTemplate.",
    )
    code_list_temp_id: str | None = Field(
        default=None,
        description="For CodeValue: temp_id of its parent CodeList.",
    )


class ProposedRelationship(BaseModel):
    """A relationship between two ProposedNodes (referenced by temp_id)."""

    model_config = ConfigDict(extra="forbid")

    type: RelationshipType
    src_temp_id: str
    dst_temp_id: str
    char_start: int | None = Field(
        default=None,
        description="For CITES: char offset where the citation begins in the source document.",
    )
    char_end: int | None = Field(
        default=None,
        description="For CITES: char offset where the citation ends.",
    )
    citation_kind: CitationKind | None = None


class CitationProposal(BaseModel):
    """A span in the source document that supports a proposed node.

    char offsets refer to the input text the agent was given. Multiple citations
    may exist per node (a node may be supported by multiple spans).
    """

    model_config = ConfigDict(extra="forbid")

    node_temp_id: str
    char_start: int
    char_end: int
    kind: CitationKind


class UncitedSpan(BaseModel):
    """A span the agent did NOT extract from. Coverage gap if substantive."""

    model_config = ConfigDict(extra="forbid")

    char_start: int
    char_end: int
    note: str = Field(description="Why this span was not extracted (e.g., 'preamble', 'signature block', 'cross-reference only').")


class SentinelExtraction(BaseModel):
    """Top-level Sentinel agent output.

    All char offsets reference the input document text the agent was given.
    """

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(description="2-3 sentence overall summary of what the document does.")
    proposed_nodes: list[ProposedNode]
    proposed_relationships: list[ProposedRelationship]
    citations: list[CitationProposal]
    uncited_spans: list[UncitedSpan]
    document_total_chars: int = Field(description="Total character count of the input document — used to compute coverage percentage.")
