# Dagster Orchestration

This document covers the Dagster integration for the RegulAI data pipeline — how it's wired, how to run it locally, and how the admin schedule UI is the only thing carriers actually see.

## Why Dagster

Production data pipelines need more than `cron` gives you: dependency management between pipeline steps, visible run history, retries on failure, alerting hooks, and a UI to debug individual steps. Dagster is the orchestrator we picked because:

- It's Python-native (no DSL learning curve for the existing pipeline code)
- Asset-based modeling will give us KG-table-level lineage later
- The web UI on `:3000` lets the data team debug individual op failures
- The compliance-officer UI at `/admin/schedule` keeps Dagster invisible to non-technical users

The choice over Airflow / Prefect: Dagster has the most natural fit for systems where the canonical artifacts (KG nodes, Snowflake tables) are the unit of value, not just the pipeline runs.

## Architecture at a glance

```
                ┌─────────────────────────────────────────┐
   browser ───► │  FastAPI on :8765                       │
                │  GET  /admin/schedule  (page)           │
                │  GET  /api/admin/schedule (config+runs) │
                │  PUT  /api/admin/schedule (save config) │
                │  POST /api/admin/schedule/run-now       │
                └────────────────────┬────────────────────┘
                                     │ writes JSON   │ GraphQL (httpx)
                                     ▼               ▼
              ┌────────────────────────────┐   ┌───────────────────────────┐
              │ dagster_project/           │   │ Dagster webserver on :3000│
              │   runtime_config.json      │◄──┤  dagster dev              │
              │ (schedule cron + enabled)  │   │  (loads dagster_project/) │
              └────────────────────────────┘   └────────────┬──────────────┘
                                                            │ launches
                                                            ▼
                                          ┌─────────────────────────────────┐
                                          │ full_pipeline_job:              │
                                          │  load_bronze → run_silver       │
                                          │   → run_gold → validate +       │
                                          │      detect_anomalies           │
                                          │  (each op shells to scripts/X)  │
                                          └─────────────────────────────────┘
```

## File layout

```
dagster_project/
├── __init__.py              # re-exports `defs`
├── definitions.py           # entry point: Definitions(jobs, schedules)
├── runtime_config.json      # editable: cron + enabled
├── ops/
│   ├── __init__.py
│   └── pipeline_ops.py      # @op wrappers around scripts/*.py
├── jobs/
│   ├── __init__.py
│   └── pipeline_jobs.py     # full_pipeline_job
└── schedules.py             # editable schedule reading runtime_config.json

packages/scheduling/
├── __init__.py              # ScheduleConfig + load/save (shared by API & Dagster)
└── dagster_client.py        # thin GraphQL client (list runs, launch run, health)

api/main.py                  # /admin/schedule routes + page
ui/admin-schedule.html       # the admin UI page
```

## Run it locally

You need two terminals.

**Terminal 1 — FastAPI (the admin UI lives here):**
```bash
make ui
```

**Terminal 2 — Dagster (the orchestrator):**
```bash
make dagster
```

Then:
- Admin UI: <http://localhost:8765/admin/schedule>
- Dagster web UI (for the data team): <http://localhost:3000>

To run the pipeline once without the webserver (CI smoke / debugging):
```bash
make dagster-run-once
```

## How the editable schedule works

The neat trick: Dagster's standard `@schedule(cron_schedule="0 2 * * *")` decorator bakes the cron in at definition time. To make the cron editable from the UI without restarting Dagster, the schedule is registered with `cron_schedule="* * * * *"` (every minute) and its `should_execute` body reads the *user-configured* cron from `runtime_config.json` and gates the fire itself.

Sequence when an admin edits the schedule:
1. Admin saves new config via `PUT /api/admin/schedule`
2. FastAPI calls `packages.scheduling.save()` → atomically writes `runtime_config.json`
3. Dagster's daemon ticks the schedule (next minute boundary)
4. `should_execute` re-reads the config, sees the new cron, decides whether this minute matches
5. If yes, returns `RunRequest`; if no, returns `SkipReason`

**No Dagster restart needed.** Schedule changes take effect on the next minute boundary (≤60s).

## Demo flow

In a customer demo, the line to use:

> *"This is Dagster under the hood — same orchestrator Stripe and Toast use for their data platforms. Your compliance officers see this clean form; the underlying pipeline DAG is in Dagster's UI on port 3000 if your data team wants to dig in. One screen for the user, one orchestrator for production."*

That answers "what's your production orchestration?" without forcing you to navigate Dagster's UI live.

## Production deployment (later)

Today: `dagster dev` runs the webserver + daemon in one process. For production, split them:

- `dagster-webserver --workspace-file workspace.yaml --port 3000`
- `dagster-daemon run`
- Persistent storage: configure `DAGSTER_HOME` with a `dagster.yaml` pointing at a PostgreSQL backend for run/event storage
- Run launcher: K8s `K8sRunLauncher` so each pipeline run lands in its own pod

This is documented but not yet wired — out of scope for Phase 1.

## Phase 2A: Excel upload → Bronze → medallion

The end goal (per user direction): a compliance officer uploads an Excel file via the admin UI, the file lands in Snowflake's BRONZE layer, and the medallion pipeline runs end-to-end. Phase 2A delivers that for **one Bronze table** (`gw_pc_policy`) so the pattern is proven; adding more tables is mechanical (append a `TemplateSpec` to `packages/uploads/schemas.py`).

### Flow

```
1. User opens /admin/upload
2. Downloads pc_policy_template.xlsx (generated on-the-fly from schemas.py)
3. Fills it in. Row 1 = column headers, rows 2-3 are hints/examples (auto-skipped)
4. POST /api/admin/uploads (multipart) → server:
     a. Saves Excel to materialized/uploads/<upload_id>/original/
     b. Validates column headers match template
     c. Coerces cells to typed values per ColumnSpec
     d. Writes Parquet to materialized/uploads/<upload_id>/parquet/
     e. Registers in materialized/uploads/_registry.json with status='converted'
5. UI history table shows upload with "Process" button
6. User clicks Process → POST /api/admin/uploads/<id>/process →
     launchRun mutation against Dagster's upload_to_gold_job
     with run_config = {ops: {op_load_bronze_from_upload: {config: {
       upload_id, bronze_table
     }}}}
7. Dagster runs: op_load_bronze_from_upload → silver → gold → validate +
   detect_anomalies → op_mark_upload_done
8. Final op flips registry status to 'done'
```

### Key files (Phase 2A)

| File | Role |
|---|---|
| `packages/uploads/schemas.py` | `TEMPLATES` registry. Add a `TemplateSpec` here to enable a new table. |
| `packages/uploads/templates.py` | Generates the downloadable `.xlsx` from a `TemplateSpec`. Hint row + example row + `_README` sheet. |
| `packages/uploads/xlsx_to_parquet.py` | Validates headers, coerces cells, writes typed Parquet. Raises `ConversionError` with row-level details. |
| `packages/uploads/storage.py` | `_registry.json` IO, `upl_*` ID format, per-upload sidecar `meta.json` for defense in depth. |
| `dagster_project/ops/upload_ops.py` | `op_load_bronze_from_upload` (typed Config: upload_id + bronze_table) + `op_mark_upload_done`. |
| `dagster_project/jobs/pipeline_jobs.py` | `upload_to_gold_job` chains upload-bronze → silver → gold → validate + anomalies. |
| `scripts/load_bronze_from_upload.py` | The subprocess the op invokes. Reads env vars, PUTs+COPY INTOs scoped to the upload. |
| `ui/admin-upload.html` | Three-step UI: download template / upload+validate / process. History table with auto-refresh. |

### Demo line for Phase 2A

> *"Customer compliance team uploads their policy file. We validate the schema before saving anything. They click Process — Dagster loads it into Bronze, runs Silver and Gold transformations, validates against the rules in our Knowledge Graph, and flags any violations. From Excel to a TICO-ready filing in under a minute, with full audit trail."*

### What's NOT in Phase 2A (Phase 2B)

- **Multi-table uploads** — today: one .xlsx per table. Tomorrow: one .xlsx with N sheets.
- **Direct-to-Snowflake-stage** — skip the local Parquet hop, PUT straight into Snowflake from the API.
- **Carrier-specific column mapping** — today: assume template-exact. Tomorrow: store mapping in REFERENCE and apply at conversion.
- **Sensor-triggered processing** — today: admin clicks Process. Tomorrow: a Dagster sensor detects new uploads and auto-launches.
- **SFTP / S3 watch** — for carriers who already ship from a data warehouse.

## What Phase 2 (broader) brings

When the demo needs to grow up further:

- **Native ops** — replace subprocess wrappers with direct imports of `scripts.X.main()` for richer logs and faster startup
- **Assets, not just ops** — model each Snowflake table as a Dagster asset so lineage shows on the Dagster UI's asset graph
- **Resources** — Snowflake + Neo4j as Dagster resources (cleaner connection management, configurable per environment)
- **Sensors** — "new cached extraction lands → re-run materialize"; "regulator portal posts new bulletin → trigger ingest"
- **Per-jurisdiction jobs** — `full_pipeline_job_tx` vs `full_pipeline_job_fl` so they can be scheduled independently
