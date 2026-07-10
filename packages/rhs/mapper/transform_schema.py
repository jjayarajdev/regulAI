"""Contracts for the TransformResolver agent (stage-4 transform selection).

Where `MappingSpec` free-writes a `transform_sql` string, a `TransformPlan`
constrains the agent to the registry: each step names a `rule_id` that must
exist in transforms.REGISTRY plus its parameters. Deterministic code compiles
the step to SQL — the model never emits raw SQL. Flat + default-free for
strict structured-output parsing.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ParamKV(BaseModel):
    name: str
    value: str


class RuleCall(BaseModel):
    rule_id: str = Field(
        description="A transform rule id from the provided REGISTRY vocabulary. Never invent one."
    )
    params: list[ParamKV] = Field(description="Parameters this rule requires, as name/value pairs.")


class ResolvedTransform(BaseModel):
    target_column: str = Field(description="Canonical target column this step populates.")
    source_column: str | None = Field(
        description="Source column the chain reads, or null for a 'null' rule (required target, no source)."
    )
    rules: list[RuleCall] = Field(
        description="Rules applied left-to-right to the source column. One rule for a simple "
        "conversion; a chain when the source needs normalizing before an encoding "
        "(e.g. mmddyyyy_to_date THEN date_to_mmddy for a legacy text date)."
    )
    confidence: float = Field(description="0..1 confidence in this chain + params choice.")
    needs_review: bool = Field(
        description="True for regulatory/domain encodings (date_to_mmddy, overpunch_decode, "
        "iso_month_char), low confidence, or a required target with no source."
    )
    rationale: str = Field(description="One line: why this chain and these params.")


class TransformPlan(BaseModel):
    source_label: str
    target_table: str
    transforms: list[ResolvedTransform]
    unresolved_targets: list[str] = Field(
        description="Required target columns no registry rule could satisfy from this source."
    )
    notes: str = Field(description="Overall caveats: assumptions, columns needing SME curation.")
