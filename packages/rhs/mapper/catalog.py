"""Contracts for the DB Crawler — stage 0 of agentic ETL.

The crawler introspects a live source database (its schemas, tables, columns)
and produces a `CatalogProfile`: the data-plane equivalent of listing the files
in `data/samples/`, but for a database the agent has never seen. This is what a
*relevance* agent reasons over to decide which tables are candidate sources for
the canonical model — before any regulated data is pulled.

Kept flat and default-lean so the profile round-trips cleanly through
structured-output parsing, exactly like `SourceProfile`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ColumnNode(BaseModel):
    name: str
    dtype: str = Field(description="Declared column type, as reported by the engine's catalog.")
    nullable: bool = True
    primary_key: bool = False
    references: str | None = Field(
        default=None,
        description="Foreign-key target as 'schema.table.column', or null if not a FK.",
    )


class TableNode(BaseModel):
    schema_name: str = Field(description="Owning schema (e.g. 'main', 'underwriting').")
    name: str
    row_count: int = Field(description="Total rows (COUNT(*) at crawl time).")
    columns: list[ColumnNode]
    sample_rows: list[dict] = Field(
        default_factory=list,
        description="A few stringified example rows — a schema-level peek, not a data pull.",
    )

    @property
    def qualified(self) -> str:
        return f"{self.schema_name}.{self.name}"


class CatalogProfile(BaseModel):
    engine: str = Field(description="Source engine: duckdb | sqlite | postgres.")
    database: str = Field(description="Database label / file name the crawler connected to.")
    tables: list[TableNode]

    @property
    def table_count(self) -> int:
        return len(self.tables)


# ── Relevance agent output (stage 0's agent step) ────────────────────────────
class CandidateTable(BaseModel):
    schema_name: str
    table: str
    relevance: float = Field(description="0..1 — how likely this table feeds the canonical target.")
    role: str = Field(description="Inferred role: policy | premium | location | claim | reference | junk.")
    key_columns: list[str] = Field(description="Columns that look like join keys or canonical identifiers.")
    rationale: str = Field(description="One line: why this table (or why it's noise).")
    needs_review: bool = Field(description="True when the SME must confirm before this table is pulled.")


class CrawlPlan(BaseModel):
    database: str
    target_table: str
    candidates: list[CandidateTable]
    suggested_join: str = Field(description="Plain-language join path across the candidate tables, or '' if none.")
    notes: str = Field(description="Coverage caveats, ambiguous tables, PII to flag before pull.")
