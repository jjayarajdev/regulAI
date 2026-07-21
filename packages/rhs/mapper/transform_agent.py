"""TransformResolver agent — selects transform rules from the registry.

The mapper decides *which* source column feeds a target; this agent decides
*how* to convert it, choosing a named rule from transforms.REGISTRY and its
parameters. Constraining the model to a closed, golden-tested vocabulary is what
makes the transform layer auditable: the agent can only pick rules that exist
and are proven, and deterministic code (`compiled_sql`) turns the selection into
SQL — the model never writes raw SQL.

LLM-agnostic: same `extract_structured` port as SchemaMapper / CrawlPlanner.
"""

from __future__ import annotations

import json
from typing import Protocol, TypeVar

from pydantic import BaseModel

from packages.rhs.mapper.schema import SourceProfile
from packages.rhs.mapper.target_schema import TSPR_PREMIUM_STAGING, render_target_contract
from packages.rhs.mapper.transform_schema import ResolvedTransform, TransformPlan
from packages.rhs.mapper.transforms import (
    REGISTRY,
    UnknownTransformError,
    compile_step,
    render_catalog,
)

T = TypeVar("T", bound=BaseModel)


class LLMPort(Protocol):
    def extract_structured(self, system_prompt: str, user_content: str,
                           response_model: type[T]) -> T: ...


def _build_system_prompt(target_table: str) -> str:
    contract = render_target_contract(TSPR_PREMIUM_STAGING)
    catalog = render_catalog()
    return f"""You are a data-transformation agent for an insurance regulatory pipeline.

Given a PROFILE of a source table and the canonical target `{target_table}`,
choose, for each target column you can populate, a CHAIN of transform rules from
the registry below (applied left-to-right) and their parameters. You author
config — you NEVER write SQL. Deterministic code compiles your rule chain into
tested SQL.

=== TARGET CONTRACT ({target_table}) ===
{contract}

=== TRANSFORM REGISTRY (choose rule_id from here — never invent one) ===
{catalog}

=== RULES ===
1. Prefer the SIMPLEST chain that is correct. A single `identity` for a clean 1:1
   map; a longer chain only when the data demands it.
2. Match rules to the OBSERVED data, not just the name:
   - money/limit strings like "$1,842.00" or "325,000"  → [money_to_decimal]
   - MMDDYYYY text dates like "01152025"                 → [mmddyyyy_to_date]
   - a ZIP that lost its leading zero                    → [zero_pad] (width from ZIP9)
   - coded status/occupancy values                       → [code_map] (give the mapping)
3. CHAIN when a source must be normalized before an encoding. Each rule's input
   is the previous rule's output. The rule types must line up: date_to_mmddy /
   iso_month_char take a DATE, so a legacy TEXT date must be parsed FIRST.
   - EFFECTIVE_DATE/EXPIRY_DATE from a real DATE source  → [date_to_mmddy]
   - EFFECTIVE_DATE/EXPIRY_DATE from MMDDYYYY text       → [mmddyyyy_to_date, date_to_mmddy]
4. DOMAIN-ENCODED / regulatory rules (date_to_mmddy, overpunch_decode,
   iso_month_char) MUST set needs_review=true — a human confirms the encoding.
5. Provide every parameter each rule in the chain requires. Omit params for rules
   that take none.
6. A REQUIRED target with no usable source → a single {{rule_id:"null"}} chain,
   source_column=null, needs_review=true. List it in unresolved_targets too.
7. Do not populate system-populated targets (they are excluded above).

Return a TransformPlan conforming exactly to the provided schema."""


class TransformResolver:
    """Resolves source columns to registry transforms toward a canonical target."""

    def __init__(self, llm: LLMPort, target_table: str = "SILVER.TSPR_PREMIUM_STAGING") -> None:
        self.llm = llm
        self.target_table = target_table
        self._system_prompt = _build_system_prompt(target_table)

    def resolve(self, profile: SourceProfile) -> TransformPlan:
        user_content = (
            f"SOURCE LABEL: {profile.source_label}\n"
            f"ROW COUNT: {profile.row_count} (profiled {profile.sampled_rows})\n\n"
            f"=== SOURCE PROFILE (JSON) ===\n"
            f"{json.dumps([c.model_dump() for c in profile.columns], indent=2)}\n"
            f"=== END PROFILE ===\n\n"
            f"Produce a TransformPlan onto {self.target_table}. Choose a registry rule "
            f"per populatable target; flag domain-encoded and low-confidence choices."
        )
        plan = self.llm.extract_structured(
            system_prompt=self._system_prompt,
            user_content=user_content,
            response_model=TransformPlan,
        )
        plan.source_label = profile.source_label
        plan.target_table = self.target_table
        return plan


def compiled_sql(step: ResolvedTransform) -> tuple[str | None, str | None]:
    """Fold a resolved rule chain into one DuckDB SQL expression (fail-closed).

    Each rule's output feeds the next. Returns (sql, error). A rule the agent
    hallucinated — one not in the registry — comes back as (None, message) so
    review surfaces it rather than the pipeline running invented SQL.
    """
    expr = step.source_column if step.source_column else "NULL"
    if not step.rules:
        return expr, None  # no-op chain = identity on the source
    try:
        for call in step.rules:
            params = {p.name: p.value for p in call.params}
            expr = compile_step(call.rule_id, expr, params)
        return expr, None
    except UnknownTransformError as e:
        return None, f"unknown transform: {e}"
    except ValueError as e:
        return None, str(e)


def is_known_rule(rule_id: str) -> bool:
    return rule_id in REGISTRY
