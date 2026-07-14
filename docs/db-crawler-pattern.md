# DB Crawler — design brief

A reusable pattern for **pointing an LLM at an unknown database and having it
decide what's worth using** — without ever letting the model touch or mutate the
data. Built for RegulAI, but the core is domain-agnostic and portable.

## The idea

Two stages, each with a deterministic bookend and an agent in the middle:

```
introspect (deterministic) → plan (agent) → pull (human-approved) → hand off
   catalog, no LLM            score tables    read-only sample       to your pipeline
```

- **Introspect** reads the database catalog (schemas → tables → columns, PK/FK,
  a few sample rows) — cheap, deterministic, no LLM.
- **Plan** hands that *catalog* (never the raw data) to an agent that scores each
  table's relevance to your target, assigns a role, and finds the join.
- **Pull** is the only step that moves real data, and it's human-gated and
  read-only.

## Three principles that make it safe

1. **The LLM authors config, not data.** The agent reasons over the *schema*, not
   rows. This bounds token cost and keeps the data plane deterministic and
   auditable.
2. **Read-only, always.** Every connector opens in read-only mode
   (`duckdb read_only=True`, SQLite `mode=ro`, Postgres
   `default_transaction_read_only`). The crawler physically cannot write to a
   source.
3. **Fail-closed + human-gated.** Introspection sees schema only; moving real data
   is a separate, explicit, approved action. High-confidence *table* matches can
   auto-stage, but the pull itself is never auto-approved.

## The reusable heart: one connector interface, N engines

The whole thing hangs off a small `Connector` abstraction — add an engine by
writing one subclass, nothing else:

```python
class Connector:
    def tables(self) -> list[tuple[str, str]]: ...              # (schema, table)
    def columns(self, schema, table) -> list[ColumnNode]: ...   # name, dtype, nullable, pk, fk
    def row_count(self, schema, table) -> int: ...
    def sample(self, schema, table, limit) -> (names, rows): ...
```

We implemented it three ways:

- **DuckDB** & **Postgres** → `information_schema` + native constraint tables.
- **SQLite** → `sqlite_master` + `PRAGMA table_info` / `PRAGMA foreign_key_list`.

A `connect(dsn)` factory dispatches on URL scheme (`duckdb://`, `sqlite://`,
`postgresql://`) or a bare file path.

## Components

| File | Role |
|---|---|
| `crawler.py` | The connectors + `introspect(dsn)` → `CatalogProfile`, `pull_to_profile()` → a profile your pipeline consumes |
| `catalog.py` | Pydantic contracts: `CatalogProfile`, `TableNode`, `ColumnNode`, `CrawlPlan` |
| `crawler_agent.py` | `CrawlPlanner` — feeds the catalog + your target contract to the LLM, returns a scored, role-tagged plan with a join path |
| `seed_source_dbs.py` | Builds heterogeneous demo DBs (clean, cryptic-legacy, multi-schema) so the agent has something real to reason over |
| API `/api/crawler/*` | `sources`, `catalog` (deterministic), `plan` (agent), `transform` (agent), `apply` |
| `crawler.html` | Guided demo UI: introspect → plan → pull → review |

## What the agent actually produces

Given a catalog + "what my target model needs," it returns a **CrawlPlan**:

- per-table relevance score (0–1),
- a role (`policy` / `premium` / `location` / `junk` / …),
- the join keys,
- a plain-language join path,
- PII / uncertainty flags for human review.

In practice it correctly picked the `policy` / `premium` tables out of cryptic
mainframe names (`POLMAST`, `PREMDTL`) and rejected an operational log table
(`SYSLOG`) as junk at relevance 0.01.

## To seed a new project from this

1. Keep `crawler.py` + `catalog.py` nearly verbatim — that's the domain-agnostic
   engine.
2. Replace the **target contract** (what the agent maps *toward*) and the
   **planner prompt** in `crawler_agent.py` with your domain's schema + roles.
3. Point `pull_to_profile()` at whatever your downstream expects (we emit a
   column-profile; you might emit rows, a DataFrame, a staging insert).
4. Reuse the read-only + fail-closed discipline as-is — it's the part that makes
   it trustworthy.

**Dependencies:** `duckdb` (core), `sqlite3` (stdlib), `psycopg` (optional, for
Postgres). Any LLM behind a one-method
`extract_structured(system_prompt, user_content, response_model)` port — swap
OpenAI / Anthropic freely.

## Related

- The transform half of the pipeline (rule registry + resolver) is documented in
  [`agentic-etl.md`](agentic-etl.md).
- The crawler is stage 0 of that agentic-ETL flow:
  crawl → profile → propose → review → compile → validate.
