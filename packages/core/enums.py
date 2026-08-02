"""Closed-vocabulary enums for the GRE.

These enums are part of the contract — adding/removing values is a schema change
that requires deliberate review. Agent extractions must conform to these.
"""

from enum import Enum


class NodeStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"  # sent back by a human reviewer — never activates
    SUPERSEDED = "superseded"


class DocumentKind(str, Enum):
    """Kind of regulation document."""

    STAT_PLAN = "StatPlan"
    STATUTE = "Statute"
    BULLETIN = "Bulletin"
    RULE_ADOPTION = "RuleAdoption"


class ReportCadence(str, Enum):
    WEEKLY = "Weekly"
    MONTHLY = "Monthly"
    QUARTERLY = "Quarterly"
    ANNUAL = "Annual"
    # Real-world catastrophe data calls and on-event reports (FL OIR-22-04M,
    # TX HB 2067 declination notices) don't fit a fixed cadence — they fire
    # when an event happens. Distinguished from "irregular" so the UI can
    # render an explanation instead of an empty field.
    ON_EVENT = "OnEvent"
    AS_NEEDED = "AsNeeded"


class RuleKind(str, Enum):
    """Distinguishes statute-shaped rules (numbered §sections) from
    bulletin/memo provisions (heading-shaped, no §number).

    Statutes cite as "§627.062(2)(a)"; bulletin provisions cite as
    "OIR-22-04M / Reporting Requirements / Cadence". Both are Rules in
    the KG, but only statutes carry section + rule_number.
    """
    STATUTE = "Statute"
    BULLETIN_PROVISION = "BulletinProvision"
    MEMO_DIRECTIVE = "MemoDirective"


class OrgKind(str, Enum):
    STATISTICAL_AGENT = "StatisticalAgent"
    REGULATOR = "Regulator"
    INSURER = "Insurer"
    RATING_BUREAU = "RatingBureau"


class CitationKind(str, Enum):
    """Why a node cites a particular regulation rule/span."""

    DEFINES = "defines"
    MODIFIES = "modifies"
    REFERENCES = "references"


class HITLSeverity(str, Enum):
    AUTO_HANDLE = "auto-handle"
    TIER1 = "Tier1"
    TIER2 = "Tier2"
    TIER3 = "Tier3"


class NodeType(str, Enum):
    """The 19 closed-vocabulary node types. See docs/kg-schema.md."""

    REGULATION_DOCUMENT = "RegulationDocument"
    STAT_PLAN_EDITION = "StatPlanEdition"
    RULE = "Rule"
    REPORT_TEMPLATE = "ReportTemplate"
    RECORD_LAYOUT = "RecordLayout"
    FIELD_REQUIREMENT = "FieldRequirement"
    CODE_LIST = "CodeList"
    CODE_VALUE = "CodeValue"
    COVERAGE_TYPE = "CoverageType"
    ENDORSEMENT_RULE = "EndorsementRule"
    BULLETIN_OVERRIDE = "BulletinOverride"
    RECONCILIATION_RULE = "ReconciliationRule"
    ORGANIZATION = "Organization"
    HITL_TRIGGER_RULE = "HITLTriggerRule"
    KG_AUDIT_ENTRY = "KGAuditEntry"
    # ── Phase 2: multi-jurisdiction ──
    JURISDICTION = "Jurisdiction"
    REGULATOR = "Regulator"
    STATISTICAL_AGENT = "StatisticalAgent"
    FILING_OBLIGATION = "FilingObligation"


class JurisdictionType(str, Enum):
    """Whether a Jurisdiction is a state, federal, or supranational scope."""

    FEDERAL  = "federal"   # US-wide, NAIC defaults, federal statutes
    STATE    = "state"     # US-TX, US-FL, US-CA, ...
    REGIONAL = "regional"  # multi-state compacts (e.g., GoM coastal)


class KGAuditAction(str, Enum):
    """The kinds of logical operations that mutate the KG canon.

    One audit entry per logical operation — a 'bulletin_apply' produces
    multiple node/edge writes but a single audit row referencing all of them
    via MUTATED_BY edges.
    """

    NODE_CREATE     = "node_create"
    NODE_SUPERSEDE  = "node_supersede"
    NODE_DELETE     = "node_delete"
    BULLETIN_APPLY  = "bulletin_apply"
    BULLETIN_RESET  = "bulletin_reset"
    EXTRACTION      = "extraction"
    BACKFILL        = "backfill"
    REBUILD         = "rebuild"
    MANUAL_EDIT     = "manual_edit"


class RelationshipType(str, Enum):
    """The 17 closed-vocabulary relationship types. See docs/kg-schema.md."""

    SUPERSEDES = "SUPERSEDES"
    EFFECTIVE_FROM = "EFFECTIVE_FROM"
    CITES = "CITES"
    CONTAINED_IN = "CONTAINED_IN"
    CONTAINS_LAYOUT = "CONTAINS_LAYOUT"
    REQUIRES = "REQUIRES"
    HAS_VALUE = "HAS_VALUE"
    CODED_BY = "CODED_BY"
    OVERRIDES = "OVERRIDES"
    DESIGNATED_BY = "DESIGNATED_BY"
    RECONCILES_WITH = "RECONCILES_WITH"
    APPLIES_TO = "APPLIES_TO"
    MUTATED_BY = "MUTATED_BY"
    # ── Phase 2: multi-jurisdiction ──
    APPLIES_IN = "APPLIES_IN"             # Rule | CodeList | … → Jurisdiction
    ISSUED_BY = "ISSUED_BY"               # RegulationDocument | BulletinOverride → Regulator
    OBLIGATES = "OBLIGATES"               # FilingObligation → Organization (the carrier)
    RECEIVES_SUBMISSION = "RECEIVES_SUBMISSION"  # FilingObligation → StatisticalAgent
