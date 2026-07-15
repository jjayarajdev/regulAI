# RegulAI — environment setup & run (one-file guide)

Everything needed to get RegulAI running from a clean checkout. **RegulAI always
runs on Databricks** (`REGULAI_DB=databricks`) — do not use the DuckDB path.

---

## 0 · Prerequisites

- **Python ≥ 3.11** and **[uv](https://docs.astral.sh/uv/)** (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **git**
- A **Databricks SQL warehouse** (host, HTTP path, token) — the data engine
- An **OpenAI API key** *with quota* — only for LLM features (regulation extract,
  crawler/transform propose). The dashboard, records, validation, and submission
  views work without it.
- *(optional)* **Neo4j** (Aura or local) for the Knowledge Graph views; **Dagster**
  for orchestration. Neither is needed for the core experience/records/validation flow.

---

## 1 · Install dependencies

```bash
git clone <repo> && cd regulAI
uv sync --extra databricks          # core + Databricks SQL connector
# optional extras:
#   uv sync --extra databricks --extra crawler   # + Postgres source crawling (psycopg)
#   uv sync --extra databricks --extra dev        # + pytest/ruff
```

---

## 2 · Configure `.env`

```bash
cp .env.example .env
```

Then fill in these (leave the rest at defaults). **Never commit `.env`.**

| Key | Value | For |
|---|---|---|
| `REGULAI_DB` | `databricks` | **engine — must be databricks** |
| `DATABRICKS_SERVER_HOSTNAME` | `adb-xxxx.azuredatabricks.net` | warehouse host |
| `DATABRICKS_HTTP_PATH` | `/sql/1.0/warehouses/xxxx` | warehouse SQL path |
| `DATABRICKS_TOKEN` | `dapi…` | warehouse PAT |
| `DATABRICKS_CATALOG` | `INSURANCE_REGULATORY` | Unity catalog |
| `OPENAI_API_KEY` | `sk-…` | LLM features |
| `OPENAI_MODEL` | e.g. `gpt-5` | LLM model |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | *(optional)* | Knowledge-Graph views |

> Snowflake keys in `.env.example` are legacy — leave blank when on Databricks.

---

## 3 · Build the Databricks warehouse (all three medallion layers)

Run once (idempotent). This creates + populates **Bronze → Silver → Gold** so the
records, validation, and final-submission views have data.

```bash
# 3a. Bronze + Reference + operational Gold tables (from Parquet fixtures)
uv run python -m scripts.seed_databricks

# 3b. Create the SILVER + statistical-GOLD tables (ports the Snowflake DDL to Delta)
uv run python -m scripts.seed_databricks_medallion

# 3c. Run the transforms — Bronze → Silver → Gold
uv run python -m scripts.run_silver
uv run python -m scripts.run_gold
```

Verify (should show non-zero rows in all three):

```bash
uv run python -c "
from packages.rhs.db import query
for t in ['BRONZE.GW_PC_POLICYPERIOD','SILVER.TSPR_PREMIUM_STAGING','GOLD.TSPR_PREMIUM_RECORDS']:
    print(t, query(f'SELECT count(*) n FROM INSURANCE_REGULATORY.{t}')[0]['n'])
"
```

*(Knowledge Graph, optional):* if using Neo4j, seed it with
`make rebuild-kg migrate-validation-rules seed-jurisdictions seed-filing-obligations`.

---

## 4 · Run the app

```bash
make ui           # → uvicorn api.main:app --reload --port 8765  (Databricks from .env)
```

Open:

| URL | Page |
|---|---|
| http://localhost:8765/experience | **new CBRE workstation** — dashboard · records · record detail (edit + final submission record) |
| http://localhost:8765/app/ | React workstation *(run `cd web && pnpm build` once to populate `web/dist`)* |
| http://localhost:8765/admin/regulations | upload a bulletin/regulation PDF → Sentinel (LLM) → Knowledge Graph |
| http://localhost:8765/admin/crawler | DB crawler + transform (agentic ETL) |
| http://localhost:8765/admin/mapping | file onboarding (profile → map → validate) |

*(optional)* orchestration UI: `make dagster` → http://localhost:3000 (admin page at `/admin/schedule`).

---

## 5 · Troubleshooting

- **Wrong / stale numbers on a page** → you're on a DuckDB instance. Use Databricks
  only: never start with `REGULAI_DB=duckdb`. `make ui` uses `.env` (databricks).
- **`insufficient_quota` / 429** on extract or crawler-propose → the OpenAI key is
  out of quota (billing). Non-LLM views still work.
- **First query is slow** → the serverless Databricks warehouse is cold-starting;
  the connector wakes it and retries automatically.
- **Silver/Gold empty** → run step 3 (`seed_databricks_medallion` then
  `run_silver`/`run_gold`); `run_silver` defaults `ACCOUNTING_MONTH=2026-03`.

---

## TL;DR

```bash
uv sync --extra databricks
cp .env.example .env        # fill DATABRICKS_* + OPENAI_API_KEY, keep REGULAI_DB=databricks
uv run python -m scripts.seed_databricks
uv run python -m scripts.seed_databricks_medallion
uv run python -m scripts.run_silver && uv run python -m scripts.run_gold
make ui                     # → http://localhost:8765/experience
```
