"""Agentic source-mapping (RHS) — the data-plane mirror of the LHS Sentinel.

Sentinel (packages/lhs/sentinel) turns a messy *regulation document* into a
structured, cited extraction. This package turns a messy *source dataset* into
a structured mapping onto the canonical TSPR staging model.

Same philosophy as rules-as-data: the LLM authors a **mapping spec** (config),
a human approves it, and deterministic code compiles + runs it through the
`query()` seam. The model never touches data rows at pipeline time.

Pipeline: profile (deterministic) → propose (agent) → review (human) →
compile (spec → INSERT…SELECT) → validate (fail-closed). This slice implements
profile + propose.
"""

from packages.rhs.mapper.agent import SchemaMapper
from packages.rhs.mapper.catalog import CatalogProfile, CrawlPlan
from packages.rhs.mapper.crawler import introspect, pull_to_profile
from packages.rhs.mapper.profiler import profile_file
from packages.rhs.mapper.schema import MappingSpec, SourceProfile

__all__ = [
    "SchemaMapper",
    "profile_file",
    "MappingSpec",
    "SourceProfile",
    "CatalogProfile",
    "CrawlPlan",
    "introspect",
    "pull_to_profile",
]
