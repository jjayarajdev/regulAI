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

## What Phase 2 brings

When the demo needs to grow up:

- **Native ops** — replace subprocess wrappers with direct imports of `scripts.X.main()` for richer logs and faster startup
- **Assets, not just ops** — model each Snowflake table as a Dagster asset so lineage shows on the Dagster UI's asset graph
- **Resources** — Snowflake + Neo4j as Dagster resources (cleaner connection management, configurable per environment)
- **Sensors** — "new cached extraction lands → re-run materialize"; "regulator portal posts new bulletin → trigger ingest"
- **Per-jurisdiction jobs** — `full_pipeline_job_tx` vs `full_pipeline_job_fl` so they can be scheduled independently
