"""CrawlPlanner agent — the agent step of stage 0 (DB Crawler).

Where `SchemaMapper` maps *columns* of one known file onto the target, the
CrawlPlanner works one tier up: given a whole database's `CatalogProfile`, it
decides *which tables* are candidate sources for the canonical model, what role
each plays (policy / premium / location / …), and how they join — before any
regulated data is pulled. The SME confirms the plan; then the chosen tables go
through pull → profile → propose → review → compile → validate.

LLM-agnostic: depends only on the same `extract_structured` port as SchemaMapper.
"""

from __future__ import annotations

import json
from typing import Protocol, TypeVar

from pydantic import BaseModel

from packages.rhs.mapper.catalog import CatalogProfile, CrawlPlan

T = TypeVar("T", bound=BaseModel)


class LLMPort(Protocol):
    def extract_structured(self, system_prompt: str, user_content: str,
                           response_model: type[T]) -> T: ...


_SYSTEM_PROMPT = """You are a source-discovery agent for an insurance regulatory pipeline.

You are given a CATALOG of an arbitrary carrier's source database — its schemas,
tables, columns (with keys), and a few sample rows per table. Your job is to
decide which tables are candidate sources for the canonical target table
`{target_table}` (policy-level premium statistics for statutory reporting).

You author a *crawl plan* (config). You do not pull data — a human approves your
plan, then deterministic code samples only the approved tables.

=== WHAT THE TARGET NEEDS ===
Policy identity (policy number, carrier NAIC), effective/expiration dates, state
and ZIP, coverage limits and deductible, written premium, transaction type, and
risk attributes (protection class, construction, year built). These are usually
spread across a policy table, a premium/financial table, and a location table.

=== RULES ===
1. Score each table's `relevance` (0..1) toward the target and give it a `role`:
   policy | premium | location | claim | reference | junk.
2. Operational/system tables (logs, batch journals, audit) are `junk`,
   relevance near 0. Say so — don't silently drop them.
3. Identify `key_columns`: primary keys and the join keys that stitch the
   candidate tables together (e.g. the shared policy-number column).
4. Cryptic legacy names are expected. Infer role from column names, types, and
   sample values (e.g. POLMAST with POLNO/EFFDT is the policy master).
5. Set needs_review=true for any table whose role or join you are not confident
   about, and for any table that appears to carry PII or sensitive data.
6. In `suggested_join`, describe in plain language how the candidate tables join
   into one policy-level row. Use '' if a single table already suffices.
7. In `notes`, flag ambiguity, likely PII columns to mask before pull, and any
   coverage the catalog seems to be missing.

Return a CrawlPlan that conforms exactly to the provided schema."""


class CrawlPlanner:
    """Proposes a CrawlPlan from a database catalog toward a canonical target."""

    def __init__(self, llm: LLMPort, target_table: str = "SILVER.TSPR_PREMIUM_STAGING") -> None:
        self.llm = llm
        self.target_table = target_table
        self._system_prompt = _SYSTEM_PROMPT.format(target_table=target_table)

    def plan(self, catalog: CatalogProfile) -> CrawlPlan:
        user_content = (
            f"DATABASE: {catalog.database}  (engine: {catalog.engine})\n"
            f"TABLE COUNT: {catalog.table_count}\n\n"
            f"=== CATALOG (JSON) ===\n"
            f"{json.dumps([t.model_dump() for t in catalog.tables], indent=2, default=str)}\n"
            f"=== END CATALOG ===\n\n"
            f"Produce a CrawlPlan for target {self.target_table}: score and role every "
            f"table, identify join keys, and describe the join. Flag junk and PII."
        )
        plan = self.llm.extract_structured(
            system_prompt=self._system_prompt,
            user_content=user_content,
            response_model=CrawlPlan,
        )
        plan.database = catalog.database
        plan.target_table = self.target_table
        return plan
