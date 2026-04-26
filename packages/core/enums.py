"""Closed-vocabulary enums for the GRE.

These enums are part of the contract — adding/removing values is a schema change
that requires deliberate review. Agent extractions must conform to these.
"""

from enum import Enum


class NodeStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class DocumentKind(str, Enum):
    """Kind of regulation document."""

    STAT_PLAN = "StatPlan"
    STATUTE = "Statute"
    BULLETIN = "Bulletin"
    RULE_ADOPTION = "RuleAdoption"


class ReportCadence(str, Enum):
    MONTHLY = "Monthly"
    QUARTERLY = "Quarterly"
    ANNUAL = "Annual"


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
    """The 14 closed-vocabulary node types. See docs/kg-schema.md."""

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


class RelationshipType(str, Enum):
    """The 12 closed-vocabulary relationship types. See docs/kg-schema.md."""

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
