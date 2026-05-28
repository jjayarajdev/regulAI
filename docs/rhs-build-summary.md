# RegulAI — RHS Build Summary

**Last updated**: 2026-05-18
**Branch**: `feature/ui-designs` (also fast-forwarded to `dev` and `release`)
**Companion docs**: [solution-architecture.md](solution-architecture.md), [how-it-works.md](how-it-works.md)

---

## What this document covers

The engineering record of the right-hand side (RHS) — the Snowflake medallion pipeline that consumes Guidewire data, validates against the regulatory canon, produces the actual TSPR ASCII filing, and tracks the compliance workflow end-to-end. It complements the LHS docs already in this folder.

If you're new to the project, read [solution-architecture.md](solution-architecture.md) first; it explains the LHS / RHS division. This doc picks up from "the canon is in Neo4j, what's the data plane and the application?"

---

## The architecture in one diagram

```
┌──────────────────────────┐         ┌──────────────────────────┐
│   TSPR plan PDF          │         │  Guidewire (synthetic)   │
│   HB 2067 statute        │         │   PolicyCenter           │
│   TDI bulletins          │         │   ClaimCenter            │
└─────────────┬────────────┘         │   BillingCenter          │
              │                      └─────────────┬────────────┘
              │ Sentinel + Parser                  │ generate_bronze_data.py
              ▼                                    ▼
   ┌──────────────────────┐               ┌────────────────────┐
   │  Neo4j (Docker, KG)  │               │  Parquet stage     │
   │  RegulationDocument  │               │  policycenter/     │
   │  Rule, CodeList,     │               │  claimcenter/      │
   │  CodeValue,          │               │  billingcenter/    │
   │  RecordLayout,       │               └─────────┬──────────┘
   │  BulletinOverride    │                         │ PUT + COPY INTO
   └──────────┬───────────┘                         ▼
              │ build_reference_*.py      ┌────────────────────┐
              │ + build_validation_*.py   │  Snowflake BRONZE  │
              │ + load_bronze_regdocs.py  │  15 tables · 525 r │
              ▼                           └─────────┬──────────┘
   ┌──────────────────────┐                         │ run_silver.py
   │  Snowflake REFERENCE │                         ▼
   │  6 tables · 110 rows │               ┌────────────────────┐
   │  ── codes (LOB,      │ ◄─── reads ───│  Snowflake SILVER  │
   │     form, reason,    │     at runtime│  4 tables · 759 r  │
   │     cause-of-loss,   │               └─────────┬──────────┘
   │     roof type)       │                         │ run_gold.py
   │  ── validation rules │                         ▼
   │     (14 executable)  │               ┌────────────────────┐
   │  BRONZE_REGDOCS      │               │  Snowflake GOLD    │
   │  3 tables · 432 r    │               │  4 record tables + │
   │  (rule citations →   │               │  4 workflow tables │
   │  regulator text)     │               │  759 records       │
   └──────────────────────┘               │  + transmittal     │
                                          └────────────────────┘
                                                    │
                                                    ▼
                                          ┌────────────────────┐
                                          │  ASCII renderer    │
                                          │  fixed-width TSPR  │
                                          │  + SHA-256 seal    │
                                          └─────────┬──────────┘
                                                    ▼
                                          TICO ShareFile + ACK
```

**Two upstream sources, one warehouse, one source of regulatory truth, one filing on the wire.**
Bronze comes from Guidewire. Reference comes from RegulAI's KG. Silver/Gold join them. The ASCII renderer ships the actual bytes to TICO and persists the SHA-256 hash + ACK receipt to an immutable audit trail.

---

## What's deployed in Snowflake

Account: `GJMJTZB-MZ61598` · Database: `INSURANCE_REGULATORY` · Region: AWS ap-south-1.

| Schema | Tables | Rows | Purpose | Source |
|---|---|---|---|---|
| `BRONZE` | 15 | 525 | Raw Guidewire CDC events, append-only | Synthetic Parquet (mimics GDP) |
| `BRONZE_REGDOCS` | 3 | 432 | Regulator-source documents + per-section text | `load_bronze_regdocs.py` |
| `REFERENCE` | 6 | 110 | TSPR plan rules as data | RegulAI KG (Neo4j) |
| `SILVER` | 4 | 759 | TSPR field-mapped staging | `run_silver.py` |
| `GOLD` | 4 record tables + 4 audit/workflow | 759 + audit | Submission-ready SDF records + sign-off chain | `run_gold.py` + API |
| `GOLD_AUDIT` | 2 | live | Validation match results + user actions | API write-path |
| `STAGING` | 1 stage | — | Snowpipe target | — |

### REFERENCE (the canon bridge)

| Table | Rows | TICO Section | Source CodeList in KG |
|---|---|---|---|
| `TSPR_REASON_CODE_MAP` | 21 | E (notices) | Reason Code List |
| `TSPR_LOB_CODES` | 17 | B.4 | Line of Business |
| `TSPR_FORM_CODES` | 17 | B.5 | Form (Policy) |
| `TSPR_CAUSE_OF_LOSS_CODES` | 6 | B.12 | Cause of Loss |
| `TSPR_ROOF_COVERAGE_TYPE_CODES` | 35 | B.8A | Roof Coverage Type |
| `TSPR_VALIDATION_RULES` | **14** | A, B, D, F | Mix of KG-derived (A.34) + hand-curated migrations |

Every row carries provenance columns (`kg_code_value_id`, `kg_canon_version`, `kg_source_document_id`). Full lineage back to the regulation.

### The 14 executable validation rules

| Rule | Section | Target | What it catches |
|---|---|---|---|
| A.22 | A | `GW_PC_POLICYPERIOD` | NAIC must be 5 numeric digits |
| A.30 | A | `GW_PC_POLICYPERIOD` | Written premium plausibility range |
| A.34 (L-companion) | A | `GW_PC_JOB` | Code L (credit) requires companion |
| A.34 (J-alone) | A | `GW_PC_JOB` | Code J must appear alone |
| A.34-valid-codes | A | `GW_PC_JOB` | Reason codes must be in the plan |
| A.40 | A | `GW_PC_POLICYPERIOD` | Term type must be standard |
| A.42 | A | `GW_PC_JOB` | Notice date required |
| B.6 | B | `GW_PC_HODWELLING` | HO forms = 1-4 families |
| B.11 | B | `GW_CC_CLAIM` | Loss cause in TSPR codeset |
| B.14 | B | `GW_CC_CLAIM` | Loss reported >90 days (WARN) |
| B.18 | B | `GW_PC_HODWELLING` | TX ZIPs begin with 7 |
| D.12 | D | `GW_CC_CLAIM` | CAT-attributable loss reporting |
| D.13 | D | `GW_CC_CLAIM` | Wind/Hail attribution required |
| F.0 | F | `GW_PC_JOB` | Notice source = Insurer or Insured |

### BRONZE_REGDOCS (citation → regulator text)

| Table | Rows | Purpose |
|---|---|---|
| `RAW_REG_DOCUMENT` | 6 | One row per source document (stat plan, statute, record layout, 3 bulletins) |
| `RAW_REG_SECTION` | 426 | Per-section slices, keyed by document + citation pattern |
| `RAW_REG_CHANGE_LOG` | 0 | Edition diffs (placeholder — bulletin-driven) |

Powers the **"View regulator text →"** button on every rule citation in the UI.

### GOLD records + workflow tables

```
GOLD record tables (after run_gold.py):
  TSPR_PREMIUM_RECORDS         371   Section C
  TSPR_LOSS_RECORDS            153   Section D
  TSPR_CANCELLATION_RECORDS    235   Section E + G (Rule 34 aggregated)
  TSPR_MONTHLY_AGGREGATES        1   Section 29 transmittal

GOLD workflow / audit tables (live):
  FILING_BATCH                   3   one row per filing (status, sign-off state)
  FILING_SUBMISSION            n/a   sealed ASCII bytes, SHA-256, ACK receipt
  FILING_EXCEPTION             live  one row per open/closed violation
  TSPR_ANOMALY_FLAGS             8   premium spikes / hail clusters / freeze-in-summer

GOLD_AUDIT (live):
  RULE_MATCH_RESULT             live  every rule × record match, with run_id
  USER_ACTION                   live  every analyst/actuary/officer/system action
```

Every GOLD record table now carries `FILING_BATCH_ID` (added in migration 005) — replaces the previous ZIP-overlap heuristic for cancellation scoping.

### BRONZE — synthetic Guidewire feed (scaled)

```
PolicyCenter (8 tables, ~371 policies)     ClaimCenter (6 tables, ~154 claims)
  GW_PC_UWCOMPANY            1               GW_CC_CLAIM                 154
  GW_PC_POLICY             371               GW_CC_EXPOSURE              154
  GW_PC_POLICYPERIOD       371               GW_CC_TRANSACTION           ~
  GW_PC_JOB                ~                 GW_CC_RESERVELINE           154
  GW_PC_HOPOLICYLINE       371               GW_CC_ADDRESS               154
  GW_PC_HOCOVERAGE         371               GW_CC_CLAIM_STATUS_HISTORY  ~
  GW_PC_HODWELLING         371             BillingCenter (1 table)
  GW_PC_ADDRESS            371               GW_BC_POLICYPERIODPREMIUM   ~
```

**Three filings, layered datasets:**

| Filing | Plan | Curated demo IDs | Bulk synth IDs | Cadence |
|---|---|---|---|---|
| `TPA-Q4-2025` | Texas Private Passenger Auto / Homeowners | POL-0001..0019 | POL-2100..2299 | Quarterly |
| `RES-M03-2026` | Residential Property — March 2026 | POL-0030..0034 | POL-2300..2399 | Monthly |
| `CL-Q4-2025` | Commercial Lines | POL-0050..0053 | POL-2400..2449 | Quarterly |

The curated set carries deliberate violations across A/B/D/F sections so every rule has something to fire on. The bulk synth set provides statistical mass for anomaly detection.

---

## Application surface

### Modern workstation (`/workstation`)

The primary UI. Cool-slate palette (Stripe/Vercel style). Five screens accessed via the left rail:

| Screen | What it shows |
|---|---|
| **Dashboard** | Pass-rate KPIs, fines-avoided estimate, Active filings list (all 3), recent activity, wire preview |
| **Filing** | Sign-off chain rail (`validated → analyst_signed → actuary_approved → officer_approved → submitted → acked`), A–G section badges (click to filter), three-column kanban (high/med/low blocker severity), per-rule fix editor, all-records / claims / anomalies / compare popouts |
| **Regulations** | **Three-pane explorer**: rule tree (left) · plain-language + citation + executable SQL + KG neighborhood graph rendered via vis-network (center) · per-rule violators + bronze sample (right) |
| **Bulletins** | Bulletin inbox with apply / reset · impact panel showing before/after deltas · re-evaluation flow that re-validates each filing and tags closed exceptions with `resolution_action='bulletin'` |
| **Audit** | Per-filing chain of custody — every USER_ACTION row in reverse-chronological order, plus the FILING_SUBMISSION with SHA-256 and TICO ACK receipt |

### API endpoints (`/api/rhs/*`)

```
# State / catalog
GET  /state                          bulletin applied?
GET  /catalog                        every schema, table, row count
GET  /pipeline/state                 per-layer counts

# Reference + KG
GET  /reference/table/{name}         generic reference-table viewer
GET  /reference/reason-codes         reason codes with provenance
GET  /kg/reason-code/{code}          KG-side view of a code
GET  /kg/rules                       every Rule node + executable flag
GET  /kg/neighborhood/{rule_id}      1-hop graph slice for vis-network

# Regulator documents (BRONZE_REGDOCS)
GET  /reg/documents                  every loaded document
GET  /reg/citation?q=...             fuzzy-match a citation → regulator text

# Filings
GET  /filings                        list all registered filings
GET  /validate                       run every rule (legacy alias: /validate/cancellations)
GET  /bronze/cancellations           bronze cancellation jobs
GET  /bronze/claims                  bronze claims with rule overlay
GET  /validation                     BRONZE ⋈ REFERENCE join verdict
GET  /audit/{filing_id}              chain of custody for one filing
POST /bronze/fix                     manual fix → mutate bronze row

# Approval workflow
GET  /filing/{id}/approval-state     status, open_blockers, next_role, can_seal
POST /filing/{id}/approve            body {role: analyst|actuary|officer}
GET  /filing/{id}/file               render fixed-width ASCII
GET  /filing/{id}/file?persist=true  seal + SHA-256 + FILING_SUBMISSION row
POST /filing/{id}/ack                synthesize TICO ACK callback

# Anomaly detection
GET  /anomalies?filing=...           list anomalies (optionally scoped)
POST /anomalies/detect               re-run the 3 detectors

# Bulletin flow
GET  /bulletin                       bulletin markdown
POST /bulletin/apply                 materialize → re-validate per filing → return deltas
POST /bulletin/reset                 roll back the bulletin

# Pipeline orchestration
POST /pipeline/silver                Bronze → Silver
POST /pipeline/gold                  Silver → Gold
```

---

## How the pieces fit

### LHS → REFERENCE bridge (the architectural thesis)

The single most important piece. Plan rules live as data in Snowflake; the rows are generated from the KG, not hand-seeded.

```
1. Sentinel extracts a regulation PDF → KG nodes (Rule, CodeList, CodeValue)
2. scripts/build_*_reference_*.py reads those nodes via Cypher
3. Emits a SQL file with DDL + INSERTs in materialized/migrations/*.sql
4. snow CLI runs the SQL — Snowflake reference table is updated
5. Silver / Gold pipelines + validate endpoint read from REFERENCE at runtime
```

The **bulletin flow** (LHS bulletin re-evaluation, now wired into the workstation) plugs in cleanly:

1. `apply_credit_score_bulletin.py` materializes the bulletin into the KG
2. `apply_bulletin.py` version-bumps and supersedes the old CodeValue
3. `build_reference_reason_codes.py` regenerates the SQL from the new KG state
4. The API's `/bulletin/apply` endpoint runs all three, then **re-validates every filing inline** and tags every newly-closed `FILING_EXCEPTION` row with `resolution_action='bulletin'`
5. The UI shows a 6-second toast naming the policies that flipped INVALID → VALID, with a green flash on the affected kanban tickets

### Approval workflow (the chain-of-custody story)

`FILING_BATCH.status` is a strict state machine:

```
draft  →  resolving  ←──┐
             │          │   (validation re-runs while ERROR blockers remain)
             ▼          │
         validated  ────┘
             │
         (analyst clicks "Approve as analyst →")
             ▼
       analyst_signed
             │
         (actuary clicks "Approve as actuary →")
             ▼
       actuary_approved
             │
         (officer clicks "Approve as officer →")
             ▼
       officer_approved
             │
         (officer clicks "Seal & submit →")
             ▼
         submitted   (FILING_SUBMISSION row written with file_sha256)
             │
         (TICO callback — POST /filing/{id}/ack synthesizes for demo)
             ▼
            acked
```

Each transition writes a `USER_ACTION` row tagged with the actor. Sealing is hard-gated on `status='officer_approved' AND open_blockers=0` — a 409 is returned otherwise.

### The ASCII renderer

`GET /api/rhs/filing/{id}/file` produces the actual fixed-width 200-column ASCII TSPR file:

1. Reads `GOLD.TSPR_PREMIUM_RECORDS`, `TSPR_LOSS_RECORDS`, `TSPR_CANCELLATION_RECORDS` scoped by `filing_batch_id`
2. Renders one line per record: header, P-records (Section C), L-records (Section D), C-records (Section E+G), footer
3. Computes SHA-256 of the byte stream
4. With `?persist=true`, inserts a `FILING_SUBMISSION` row and advances `FILING_BATCH.status → submitted`

Per-filing byte counts (current state):
- TPA-Q4-2025: 443 records · ~89 KB
- RES-M03-2026: 209 records · ~42 KB
- CL-Q4-2025: 107 records · ~21 KB

### Anomaly detector

`scripts/detect_anomalies.py` runs three deterministic detectors against Bronze/Gold and writes to `GOLD.TSPR_ANOMALY_FLAGS`:

| Detector | Predicate | Severity |
|---|---|---|
| `premium_spike` | ZIP total premium > 3σ from corpus mean | WARN |
| `hail_cluster` | >3 Hail claims in same ZIP within 7-day window | INFO |
| `freeze_in_summer` | `losscause='Freeze' AND MONTH(lossdate) BETWEEN 6 AND 9` | WARN |

Current state: 8 anomalies (2 premium spikes, 6 freeze-in-summer). Surfaced as a popout on the Filing screen with re-run button.

### Validation engine

`REFERENCE.TSPR_VALIDATION_RULES` holds 14 executable rules (was 4 at the start of the build). Each row is `(rule_id, rule_number, target_table, target_id_expr, violation_sql, severity, citation, …)`. The `/validate` endpoint reads them, runs each `violation_sql` against the named target table, scopes by `filing_batch_id` policy ranges, persists a `RULE_MATCH_RESULT` row per match + reconciles `FILING_EXCEPTION` (closes any that no longer fire).

Adding a rule = INSERT one row in a numbered migration file.
Updating a rule = bulletin flow.
Asking "what rejected this filing?" = JOIN against `RULE_MATCH_RESULT`.

---

## Make targets

```
# RHS — once-off setup
snowflake-test            connection check
snowflake-setup           create database + schemas
bronze-ddl                load IBM Bronze DDLs
migrate-snowflake         run every numbered migration in materialized/migrations/

# Reference (KG → Snowflake)
build-reference           build reason-code SQL
load-reference            build + load reason-code SQL
build-reference-all       build all 5 codelist tables
load-reference-all        load all 5 codelist tables
migrate-validation-rules  attach validation_sql to KG Rule nodes
build-validation-rules    KG → tspr_validation_rules.sql
load-validation-rules     push to Snowflake
load-custom-validation-rules
                          re-apply migrations 002 + 003 (the hand-curated
                          rules that don't survive the auto-gen overwrite)

# Bronze (synthetic Guidewire)
build-bronze              generate Parquet
load-bronze               PUT + COPY INTO

# Regulator documents
(scripts/load_bronze_regdocs.py — no make target yet; run via `uv run python -m scripts.load_bronze_regdocs`)

# Pipeline
run-silver                Bronze → Silver
run-gold                  Silver → Gold
detect-anomalies          populate GOLD.TSPR_ANOMALY_FLAGS
run-pipeline              full chain (bronze → reference → custom rules →
                          silver → gold → anomaly detection)

# Bulletin demo
demo-bulletin-baseline    show baseline (no bulletin)
demo-bulletin-apply       apply bulletin, show flip
demo-bulletin-reset       roll back to baseline

# UI
ui                        uvicorn :8765 with --reload
test                      pytest tests/ -v
```

---

## Migrations

`materialized/migrations/` holds numbered, idempotent SQL files. `make migrate-snowflake` runs them in order.

| # | File | Purpose |
|---|---|---|
| 001 | `audit_tables.sql` | `FILING_BATCH`, `FILING_SUBMISSION`, `FILING_EXCEPTION`, `RULE_MATCH_RESULT`, `USER_ACTION` |
| 002 | `extra_validation_rules.sql` | Hand-curated rules: A.22, A.30, A.34 variants, A.40, A.42, B.6, B.18, D.13, F.0 |
| 003 | `claim_validation_rules.sql` | Claim-side rules: B.11, B.14, D.12 |
| 004 | `bronze_regdocs.sql` | `BRONZE_REGDOCS` schema + 3 tables |
| 005 | `gold_filing_batch_id.sql` | Adds `FILING_BATCH_ID` to the 3 Gold record tables |
| 006 | `anomaly_flags_extensions.sql` | Adds `FILING_BATCH_ID`, `SOURCE_RECORDS`, `SEVERITY` to `TSPR_ANOMALY_FLAGS` |

All migrations use `CREATE TABLE IF NOT EXISTS` / `ALTER ADD COLUMN IF NOT EXISTS` / `INSERT … WHERE NOT EXISTS` — safe to replay.

---

## Tests

```bash
make test    # → pytest tests/ -v
```

`tests/test_critical_paths.py` covers the three RHS workflows most likely to silently break:

1. `test_record_validation_run_is_idempotent` — empty validation run doesn't churn exceptions
2. `test_exception_close_carries_resolution_action` — closed exceptions get tagged with the action
3. `test_approval_chain_rejects_premature_signoff` — officer-first rejected with 409
4. `test_approval_chain_rejects_invalid_role` — unknown role rejected with 400
5. `test_bronze_fix_mutates_underlying_row` — `/bronze/fix` actually updates the row

Auto-skipped if Snowflake unreachable.

---

## Stack

| Layer | Tech |
|---|---|
| Regulatory canon | Neo4j (local Docker, `bolt://localhost:7687`) |
| Extraction | OpenAI GPT-5.5 + Sentinel agent |
| Data warehouse | Snowflake Enterprise (ap-south-1, GJMJTZB-MZ61598) |
| Ingest | PUT to internal stage + COPY INTO with MATCH_BY_COLUMN_NAME |
| Web app | FastAPI + uvicorn (port 8765) |
| Frontend | Vanilla HTML + JS (no framework) · vis-network from CDN for KG graph |
| Synthetic data | pyarrow Parquet generator (~371 policies, 154 claims) |
| Build orchestration | Make + uv |
| Tests | pytest with FastAPI TestClient |

---

## What's not built (yet)

Major items that remain real work for a production engagement:

1. **Real Guidewire ingestion** — production would replace `generate_bronze_data.py` with Snowpipe pointed at a customer's GDP S3 bucket. Schema is already byte-identical.
2. **More executable rules** — TSPR has 84 descriptive rules in the canon; 14 are now executable. The pattern extends mechanically — each new rule = one row in a migration + one `FIX_SPEC` entry.
3. **Databricks parity** — Snowflake reference DDLs and procedures have Databricks equivalents in the architecture doc; not loaded here.
4. **Genuine TICO ACK webhook** — current implementation synthesizes the receipt. Production would expose an inbound endpoint TICO ShareFile calls.
5. **Bulletin auto-ingestion from TDI feed** — bulletins are currently dropped into `synthetic_regulations/synthetic/bulletins/` manually. Production would poll the TDI Commissioner's Bulletin RSS or scrape page.
6. **NCCI / ISO / AAIS plan support** — same architecture applies, but each requires its own KG vocabulary + reference schema.

The vertical slice is intentional. The thesis (regulation → KG → reference → pipeline → ASCII filing → audit → ACK, all with citation lineage) is provable end-to-end with what's built today.

---

## Repo navigation

```
api/
  main.py                            FastAPI app, route definitions
  rhs_demo.py                        /api/rhs/* endpoints (28 routes)
  registry.py                        document slug → file path mapping

packages/
  rhs/
    snowflake_client.py              thin connector using ~/.snowflake/config.toml
    codelist_generator.py            generic CodeList → reference SQL
    filings.py                       canonical filing registry (shared by API + run_gold)
  lhs/
    sentinel/                        bulletin/regulation extraction (LHS)
    materialization/                 KG write-path
    citations/                       PDF rect-based provenance
  adapters/lhs/gre/
    neo4j_adapter.py                 KG read/write

scripts/
  build_reference_reason_codes.py    KG → reason-code SQL
  build_all_reference_tables.py      KG → 4 more reference tables
  build_validation_rules_reference.py KG → executable rules SQL
  migrate_kg_validation_rules.py     attach validation_sql to KG Rule nodes
  apply_credit_score_bulletin.py     bulletin materialization (LHS)
  reset_credit_score_bulletin.py     bulletin rollback (LHS)
  generate_bronze_data.py            synthetic Guidewire Parquet (curated + bulk)
  load_bronze_to_snowflake.py        PUT + COPY INTO
  load_bronze_regdocs.py             regulation PDFs → BRONZE_REGDOCS
  run_silver.py                      Bronze → Silver
  run_gold.py                        Silver → Gold (with filing_batch_id stamping)
  detect_anomalies.py                Bronze/Gold → TSPR_ANOMALY_FLAGS

ui/
  workstation.html                   PRIMARY UI — 5-screen workstation
  index.html                         landing page (legacy)
  regulations.html                   /explore (legacy regulation browser)
  demo.html                          /demo (legacy bulletin flow)
  validate.html                      /validate (legacy rule engine)
  pipeline.html                      /pipeline (legacy Bronze→Silver→Gold runner)
  mockups/regulai-vision.html        standalone vision mockup (5 screens)

materialized/
  migrations/                        numbered, idempotent SQL files (001-006)
  reference/                         auto-generated reference SQL (one per codelist)
  bronze_parquet/                    generated Parquet (one folder per source table)
  extractions/                       cached Sentinel outputs (LHS)

tests/
  test_critical_paths.py             RHS regression tests (5 cases)
  test_materialization.py            LHS write-path
  test_neo4j_adapter.py              LHS Neo4j adapter
  test_sentinel.py                   LHS extraction
  test_models.py                     LHS pydantic models

references/
  files-Snowflake/                   target architecture DDLs (the IBM-authored reference)
  regulations/                       source plan PDFs
  TSPR Platform Architecture.pdf     the reference architecture document
```

---

## Operational notes

**Snowflake connection** — uses Programmatic Access Token (PAT) auth with a network policy locked to a single IP. To switch IP: `ALTER NETWORK POLICY regulai_policy SET ALLOWED_IP_LIST = ('<new ip>');`. Token lives in `~/.snowflake/config.toml` (gitignored).

**Neo4j connection** — local Docker instance (`bolt://localhost:7687`). Started with `make up`. Connection string in `.env` (gitignored).

**Restarting the API** — `uvicorn` runs with `--reload` so Python code changes pick up automatically. HTML/JS changes require a browser hard-reload (Cmd-Shift-R). New endpoint added? Restart the API (Ctrl-C and re-run) — `--reload` watches files, not route registrations.

**Misleading "Snowflake unreachable" banner** — actually triggers whenever `/api/rhs/state` fails. Most common cause is the running uvicorn predating recent code changes and 404-ing on a new endpoint; restart fixes it.

**Time taken** — `feature/rhs-snowflake` branched 2026-04-27. End-to-end pipeline operational 2026-05-06. `feature/ui-designs` (this work) merged into dev+release 2026-05-18, adding: ASCII renderer, approval workflow + ACK, anomaly detector, three-pane Regulation Explorer, BRONZE_REGDOCS, 10 more executable rules, neovis.js graph, migration tracking, critical-path tests.
