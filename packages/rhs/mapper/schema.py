"""Pydantic contracts for agentic source-mapping.

`SourceProfile` is produced deterministically by the profiler.
`MappingSpec` is the agent's structured output — the mirror of Sentinel's
`SentinelExtraction`. Kept flat and default-free so it round-trips cleanly
through OpenAI/Anthropic structured-output (strict-schema) parsing.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Deterministic profiler output ────────────────────────────────────────
class ColumnProfile(BaseModel):
    name: str
    inferred_type: str = Field(description="Physical type as read (e.g. int64, string, double, timestamp).")
    null_rate: float = Field(description="Fraction of null/empty values in the profiled sample, 0..1.")
    distinct_count: int = Field(description="Distinct values in the profiled sample.")
    sample_values: list[str] = Field(description="A few example non-null values, stringified.")


class SourceProfile(BaseModel):
    source_label: str
    row_count: int = Field(description="Total rows in the source file.")
    sampled_rows: int = Field(description="Rows actually inspected for the per-column stats.")
    columns: list[ColumnProfile]


# ── Agent output: the mapping spec ───────────────────────────────────────
class ProposedMapping(BaseModel):
    target_column: str = Field(description="Canonical target column this mapping populates.")
    source_column: str | None = Field(
        description="Best-matching source column, or null if the target has no source and must be derived/curated."
    )
    transform_sql: str = Field(
        description="A Spark/Databricks SQL expression that produces the target value, "
        "referencing source column name(s). Use the bare source column when it maps 1:1. "
        "Use NULL when it cannot be produced from the source."
    )
    confidence: float = Field(description="0..1 confidence in this mapping.")
    rationale: str = Field(description="One line: why this source column / expression.")
    needs_review: bool = Field(
        description="True when a human must confirm — low confidence, a domain encoding "
        "(e.g. TSPR MMDDY), unit ambiguity, or a required target with no clear source."
    )


class UnmappedSourceColumn(BaseModel):
    name: str
    reason: str = Field(description="Why it wasn't mapped (no target, free-text, duplicate, provenance-only, etc.).")


class MappingSpec(BaseModel):
    source_label: str
    target_table: str
    mappings: list[ProposedMapping]
    unmapped_source_columns: list[UnmappedSourceColumn]
    notes: str = Field(description="Overall caveats: coverage, risky assumptions, columns needing SME input.")
