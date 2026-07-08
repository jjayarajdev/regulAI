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

T = TypeVar("T", bound=BaseModel)


class LLMPort(Protocol):
    """The one method the mapper needs — satisfied by OpenAIAdapter today."""

    def extract_structured(self, system_prompt: str, user_content: str,
                           response_model: type[T]) -> T: ...


class SchemaMapper:
    """Proposes a MappingSpec from a source profile onto a canonical table."""

    def __init__(self, llm: LLMPort, target_table: str = "SILVER.TSPR_PREMIUM_STAGING") -> None:
        self.llm = llm
        self.target_table = target_table
        self._system_prompt = build_system_prompt(target_table)

    def map(self, profile: SourceProfile) -> MappingSpec:
        user_content = (
            f"SOURCE LABEL: {profile.source_label}\n"
            f"ROW COUNT: {profile.row_count} (profiled {profile.sampled_rows} rows)\n\n"
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
