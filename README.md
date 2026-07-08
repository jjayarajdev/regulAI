# RegulAI

Regulation → Knowledge Graph → executable filing schema **and** a live
validation/filing workstation, for US property/casualty statistical reporting
(Texas residential property → TICO, plus a Florida FHCF slice).

The system reads regulation PDFs (statutes, statistical plans, commissioner
bulletins), extracts a closed-vocabulary KG of every report, column, and legal
code value — with pixel-perfect citation provenance back to the source PDF —
and lets that KG drive both **submission generation** (LHS) and **carrier-data
validation, resolution, and sign-off** (RHS).

## The two halves

**LHS — regulation → KG.** Regulation PDFs → Sentinel LLM (prose) + deterministic
PyMuPDF parser (tabular wire layouts) → proposal JSON → idempotent `materialize()`
→ Neo4j KG with closed vocabulary, citation provenance, append-only versioning.

**RHS — carrier data → validated filing.** Source data (Guidewire CDC) → medallion
warehouse (Bronze/Silver/Gold) → rules-as-data validation engine (rules live in the
KG, executed against the warehouse) → a **workstation** where compliance officers
resolve violations, apply regulator bulletins, walk the sign-off chain, and submit —
with a full audit trail.

The KG is the contract between the two; hardcoded regulatory rules anywhere in the
pipeline are an antipattern.

## Pick your data engine — no code changes

The RHS warehouse is a **runtime switch** (`REGULAI_DB` in `.env`), so demos don't
depend on any one vendor's billing or connectivity. Same app, same SQL seam
(`packages/rhs/db.py`), three backends:

| `REGULAI_DB` | Engine | Use it for | Setup |
|---|---|---|---|
| `snowflake` (default) | Snowflake | production / original path | `SNOWFLAKE_*` in `.env` |
| `duckdb` | local DuckDB file | free, offline demos — can't fail | `uv run python -m scripts.seed_duckdb` |
| `databricks` | Databricks SQL warehouse | cloud demos | `uv sync --extra databricks` + `DATABRICKS_*` + `uv run python -m scripts.seed_databricks` |

Rollback to Snowflake is just `REGULAI_DB=snowflake` — the Snowflake driver and its
full KG/bulletin pipeline are untouched. See
[`docs/data-engine-architecture.md`](docs/data-engine-architecture.md).

## The two UIs

- **React workstation** (current) — `web/`, Vite + React + Tailwind. Overview,
  Filing workshop, Regulations + knowledge-graph view, Bulletins, Audit log.
  Runs against the live API **or** fully offline on realistic mock data
  (`VITE_API_MODE=mock`). See [`web/README.md`](web/README.md).
- **Single-file workstation** (legacy) — `ui/workstation.html`, served by the API
  at `make ui` → http://localhost:8765.

## Quickstart

### LHS — rebuild the KG and prove it round-trips
```bash
make install                # uv sync
cp .env.example .env        # add OPENAI_API_KEY; pick REGULAI_DB (default snowflake)
make up                     # Neo4j in Docker
make migrate
make rebuild-kg             # ~30s, reproducible from on-disk extractions; no LLM tokens
make e2e                    # round-trip regression
```

### RHS — run the workstation with no Snowflake (DuckDB)
```bash
uv run python -m scripts.seed_duckdb                 # build the local warehouse from Parquet
REGULAI_DB=duckdb uv run uvicorn api.main:app --port 8765
cd web && pnpm install && pnpm dev                   # http://localhost:5173
```

### RHS — demo on a live Databricks warehouse
```bash
make up && make seed                                  # Neo4j for the Regulations/KG screen
uv run python -m scripts.seed_databricks              # one-time, reads DATABRICKS_* from .env
REGULAI_DB=databricks uv run uvicorn api.main:app --port 8765
cd web && REGULAI_API_URL=http://localhost:8765 VITE_API_MODE=live pnpm dev
```

Fastest "just show the UI" path — no backend at all:
```bash
cd web && pnpm install && pnpm dev    # mock mode is the default
```

## Reading order

- [`docs/solution-architecture.md`](docs/solution-architecture.md) — what problem and why
- [`docs/how-it-works.md`](docs/how-it-works.md) — operational runbook
- [`docs/rhs-build-summary.md`](docs/rhs-build-summary.md) — the RHS pipeline + workstation
- [`docs/data-engine-architecture.md`](docs/data-engine-architecture.md) — the `REGULAI_DB` engine switch + rollback
- [`docs/technical-architecture.md`](docs/technical-architecture.md) — how it's built
- [`docs/kg-schema.md`](docs/kg-schema.md) — closed-vocabulary catalogue
- [`web/README.md`](web/README.md) — the React frontend

## Status

LHS and RHS are both operational. The RHS workstation runs end-to-end on
Snowflake, DuckDB, or Databricks via `REGULAI_DB`. Releases are tagged
`v1.0.0-snowflake` (pre-multi-engine baseline) and `v1.1.0-multi-engine`
(current). Open work and decisions: [`docs/poc-decisions.md`](docs/poc-decisions.md).
