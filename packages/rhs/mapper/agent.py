"""SchemaMapper agent — the RHS mirror of lhs/sentinel/agent.py:Sentinel.

Reads a deterministic SourceProfile, returns a structured MappingSpec onto the
canonical target. LLM-agnostic: it depends only on the `extract_structured`
port that OpenAIAdapter (and a future AnthropicAdapter) implement.
"""

from __future__ import annotations

import json
from typing import Protocol, TypeVar

from pydantic import BaseModel

from packages.rhs.mapper.prompts import build_system_prompt
from packages.rhs.mapper.schema import MappingSpec, SourceProfile
from packages.rhs.mapper.target_schema import TargetSchema, get_target

T = TypeVar("T", bound=BaseModel)


class LLMPort(Protocol):
    """The one method the mapper needs — satisfied by OpenAIAdapter today."""

    def extract_structured(self, system_prompt: str, user_content: str,
                           response_model: type[T]) -> T: ...


class SchemaMapper:
    """Proposes a MappingSpec from a source profile onto a canonical table."""

    def __init__(
        self,
        llm: LLMPort,
        target_table: str = "SILVER.TSPR_PREMIUM_STAGING",
        target: TargetSchema | None = None,
    ) -> None:
        self.llm = llm
        # `target_table` may be a registry name (e.g. "FHCF_EXPOSURE") or a
        # table name — both resolve through the target registry; the historical
        # default keeps pointing at the CIOM contract.
        self.target = target or get_target(target_table)
        self.target_table = self.target.table
        self._system_prompt = build_system_prompt(target=self.target)

    def map(self, profile: SourceProfile, context: str = "") -> MappingSpec:
        """Propose a spec. `context` is optional extra source context (e.g. the
        fixed join relation and column-alias convention for a multi-table
        warehouse source) appended verbatim to the user message."""
        context_block = f"=== SOURCE CONTEXT ===\n{context.strip()}\n=== END CONTEXT ===\n\n" if context.strip() else ""
        user_content = (
            f"SOURCE LABEL: {profile.source_label}\n"
            f"ROW COUNT: {profile.row_count} (profiled {profile.sampled_rows} rows)\n\n"
            f"{context_block}"
            f"=== SOURCE PROFILE (JSON) ===\n"
            f"{json.dumps([c.model_dump() for c in profile.columns], indent=2)}\n"
            f"=== END PROFILE ===\n\n"
            f"Propose a MappingSpec onto {self.target_table} following your system "
            f"prompt. Be precise; flag domain-encoded and low-confidence targets for review."
        )
        spec = self.llm.extract_structured(
            system_prompt=self._system_prompt,
            user_content=user_content,
            response_model=MappingSpec,
        )
        # The model fills source_label/target_table from context; pin them to the
        # ground truth so the persisted spec is never mislabeled.
        spec.source_label = profile.source_label
        spec.target_table = self.target_table
        return spec
