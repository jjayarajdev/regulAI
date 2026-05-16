# RegulAI — RHS Build Summary

**Last updated**: 2026-05-06
**Branch**: `feature/rhs-snowflake`
**Companion docs**: [solution-architecture.md](solution-architecture.md), [how-it-works.md](how-it-works.md)

---

## What this document covers

This is the engineering record of the right-hand side (RHS) build — the Snowflake medallion pipeline that consumes Guidewire data and produces submission-ready records, with the regulatory canon driving the reference schema. It complements the LHS docs already in this folder.

If you're new to the project, read [solution-architecture.md](solution-architecture.md) first; it explains the LHS / RHS division. This doc picks up from "the canon is in Aura, what's the data plane?"

---

## The architecture in one diagram

```
┌──────────────────────────┐         ┌──────────────────────────┐
│   TSPR plan PDF          │         │  Guidewire (synthetic)   │
│   HB 2067 statute        │         │   PolicyCenter           │
│   Synthetic bulletins    │         │   ClaimCenter            │
└─────────────┬────────────┘         │   BillingCenter          │
              │                      └─────────────┬────────────┘
              │ Sentinel + Parser                  │ generate_bronze_data.py
              ▼                                    ▼
   ┌──────────────────────┐               ┌────────────────────┐
   │  Neo4j Aura (KG)     │               │  Parquet stage     │
   │  RegulationDocument  │               │  policycenter/     │
   │  Rule, CodeList,     │               │  claimcenter/      │
   │  CodeValue,          │               │  billingcenter/    │
   │  RecordLayout,       │               └─────────┬──────────┘
   │  BulletinOverride    │                         │ PUT + COPY INTO
   └──────────┬───────────┘                         ▼
              │ build_reference_*.py      ┌────────────────────┐
              │ + build_validation_*.py   │  Snowflake BRONZE  │
              ▼                           │  15 tables · 78 r  │
   ┌──────────────────────┐               └─────────┬──────────┘
   │  Snowflake REFERENCE │                         │ run_silver.py
   │  6 tables · 100 rows │                         ▼
   │  ── codes (LOB,      │               ┌────────────────────┐
   │     form, reason,    │ ◄─── reads ───│  Snowflake SILVER  │
   │     cause-of-loss,   │     at runtime│  4 tables · 19 r   │
   │     roof type)       │               └─────────┬──────────┘
   │  ── validation rules │                         │ run_gold.py
   │     (executable SQL) │                         ▼
   └──────────────────────┘               ┌────────────────────┐
                                          │  Snowflake GOLD    │
                                          │  4 tables · 16 r   │
                                          │  + transmittal     │
                                          └────────────────────┘
```

**Two upstream sources, one warehouse, one source of regulatory truth.** Bronze comes from Guidewire. Reference comes from RegulAI's KG. Silver/Gold join them.

---

## What's deployed in Snowflake

Account: `GJMJTZB-MZ61598` · Database: `INSURANCE_REGULATORY` · Region: AWS ap-south-1.

| Schema | Tables | Rows | Purpose | Source |
|---|---|---|---|---|
| `BRONZE` | 15 | 78 | Raw Guidewire CDC events, append-only | Synthetic Parquet (mimics GDP) |
| `REFERENCE` | 6 | 100 | TSPR plan rules as data | RegulAI KG (Aura) |
| `SILVER` | 4 | 19 | TSPR field-mapped staging | run_silver.py |
| `GOLD` | 4 | 16 | Submission-ready SDF records | run_gold.py |
| `STAGING` | 1 stage | — | Snowpipe target | — |

### REFERENCE (the bridge)

| Table | Rows | TICO Section | Source CodeList in KG |
|---|---|---|---|
| `TSPR_REASON_CODE_MAP` | 21 | E (notices) | Reason Code List |
| `TSPR_LOB_CODES` | 17 | B.4 | Line of Business |
| `TSPR_FORM_CODES` | 17 | B.5 | Form (Policy) |
| `TSPR_CAUSE_OF_LOSS_CODES` | 6 | B.12 | Cause of Loss |
| `TSPR_ROOF_COVERAGE_TYPE_CODES` | 35 | B.8A | Roof Coverage Type |
| `TSPR_VALIDATION_RULES` | 4 | A | Section A executable rules |

Every row carries provenance columns: `kg_code_value_id`, `kg_canon_version`, `kg_source_document_id`. Full lineage back to the regulation.

### BRONZE (what Guidewire would send)

```
PolicyCenter (8 tables, 38 rows)         ClaimCenter (6 tables, 30 rows)
  GW_PC_UWCOMPANY            1 row         GW_CC_CLAIM                 4
  GW_PC_POLICY               6 rows        GW_CC_EXPOSURE              4
  GW_PC_POLICYPERIOD         6 rows        GW_CC_TRANSACTION           8
  GW_PC_JOB                  5 rows        GW_CC_RESERVELINE           4
  GW_PC_HOPOLICYLINE         6 rows        GW_CC_ADDRESS               4
  GW_PC_HOCOVERAGE           6 rows        GW_CC_CLAIM_STATUS_HISTORY  6
  GW_PC_HODWELLING           6 rows
  GW_PC_ADDRESS              6 rows      BillingCenter (1 table, 6 rows)
                                           GW_BC_POLICYPERIODPREMIUM   6
```

Six policies and four claims chosen to exercise distinct TSPR rules:

**Policies — Section E scenarios**
| Policy | Action | Reason | Why it's there |
|---|---|---|---|
| POL-0001 | Renewal | — | baseline / claim parent |
| POL-0007 | Cancellation | A | failure to pay (valid single) |
| POL-0010 | Nonrenewal | LD | credit + claims (valid combo) |
| POL-0011 | Declination | L | INVALID — L alone (§559.052) |
| POL-0012 | Declination | JD | INVALID — J must be alone |
| POL-0013 | Cancellation | J | valid (J alone is fine) |

**Claims — Section D scenarios**
| Claim | Cause | Demonstrates |
|---|---|---|
| CLM-001 | Wind | KIND=7 (reserve only, no payment) |
| CLM-002 | Hail roof | KIND=6 + DEPREC (RC vs ACV) |
| CLM-005 | Fire | LAE excluded per Rule 11 |
| CLM-009 | Wind reopened | RCC=1 (Rule 15 state machine) |

---

## How the pieces fit

### LHS → REFERENCE bridge (the architectural thesis)

The single most important piece of the build. Plan rules live as data in Snowflake; the rows are generated from the KG, not hand-seeded.

```
1. Sentinel extracts a regulation PDF → KG nodes (Rule, CodeList, CodeValue)
2. scripts/build_*_reference_*.py reads those nodes via Cypher
3. Emits a SQL file with DDL + INSERTs in materialized/reference/*.sql
4. snow CLI runs the SQL — Snowflake reference table is updated
5. Silver / Gold pipelines read from REFERENCE at every transformation
```

The **bulletin flow** (LHS bulletin re-evaluation, already built) plugs in cleanly:

- `apply_credit_score_bulletin.py` materializes a bulletin's effects into KG (new CodeValue version, BulletinOverride node, OVERRIDES edge)
- `apply_bulletin.py` marks the old version superseded
- Re-running `build-reference-all` regenerates the SQL — superseded versions are filtered out, new ones come through
- Next Silver/Gold run sees the new reference flags automatically

The /demo page demonstrates this end-to-end with a row that flips from INVALID to VALID.

### BRONZE — synthetic Guidewire feed

`scripts/generate_bronze_data.py` produces 15 Parquet files in three GDP-shaped directories. `scripts/load_bronze_to_snowflake.py` PUTs them to the `STAGING.BRONZE_INGEST` stage and `COPY INTO`s with `MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE` — same path real Snowpipe ingestion uses.

Subtle gotcha worth remembering: PyArrow defaults to nanosecond timestamps which Snowflake's `COPY INTO` interprets as something else. We write Parquet with `use_deprecated_int96_timestamps=True` for Julian-day + nanosecond layout that Snowflake parses correctly.

### SILVER and GOLD

Both are Python orchestrators (`scripts/run_silver.py`, `scripts/run_gold.py`) that issue `INSERT ... SELECT` statements. The reference Snowflake stored procedures from the architecture doc (1186 + 766 lines) stay in `references/files-Snowflake/` as a target implementation; for the demo dataset, focused Python is faster to iterate.

Silver's most interesting transform is `TSPR_CLAIM_STATE` — the Rules 13-16 SCD-2 state machine. NCC=1 only in the month a claim is first reported; PCC=1 only on first payment; RCC=1 only on the first record of a previously-closed claim's reopen. The CLM-009 close+reopen scenario in BRONZE is what exercises this path.

Gold's most interesting transform is `TSPR_CANCELLATION_RECORDS` — Rule 34 unique-combination-key aggregation. Multiple Section E notices with identical (notification_date, action_type, type_of_policy, RSI, 60D, ZIP, effective_date, reason_code_list) collapse to a single row with summed `recipient_count`.

### Validation engine

`REFERENCE.TSPR_VALIDATION_RULES` holds 4 executable rules from TICO Section A. Each row is `(rule_id, rule_number, target_table, target_id_expr, violation_sql, severity, citation, …)`. The validator endpoint reads them, runs each `violation_sql` against the named target table, and returns per-row violations with citations.

Adding a rule = INSERT one row.
Updating a rule = bulletin flow already in place.
Asking "what rejected this filing?" = a JOIN against this table.

---

## Application surface (where to look)

| URL | Purpose |
|---|---|
| `/` | Stakeholder landing page |
| `/explore` | Browse regulations — KG side, with **Deployed in Snowflake** tab showing the live catalog and any reference table's rows |
| `/demo` | Bulletin propagation demo — KG and Snowflake cards side-by-side with **Process this bulletin** trigger |
| `/validate` | Live validation engine — runs every rule from REFERENCE, shows violations with citations and the executable SQL |
| `/pipeline` | Bronze → Silver → Gold runner with stage cards and Section 29 transmittal totals |

API endpoints under `/api/rhs/`:

```
GET  /api/rhs/state                      bulletin applied?
GET  /api/rhs/catalog                    every schema, table, row count
GET  /api/rhs/reference/reason-codes     code-by-code with provenance
GET  /api/rhs/reference/table/{name}     generic table viewer
GET  /api/rhs/kg/reason-code/{code}      KG-side view of a code
GET  /api/rhs/bronze/cancellations       Bronze cancellation jobs
GET  /api/rhs/validation                 BRONZE ⋈ REFERENCE join verdict
GET  /api/rhs/validate/cancellations     full rule engine pass
GET  /api/rhs/bulletin                   bulletin markdown
POST /api/rhs/bulletin/apply             materialize bulletin → KG → SF
POST /api/rhs/bulletin/reset             roll back the bulletin
GET  /api/rhs/pipeline/state             per-layer counts
POST /api/rhs/pipeline/silver            run Bronze → Silver
POST /api/rhs/pipeline/gold              run Silver → Gold
```

---

## Make targets

```
# RHS — once-off setup (per Snowflake account)
snowflake-test           connection check
snowflake-setup          create database + schemas
bronze-ddl               load IBM Bronze DDLs

# Reference (KG → Snowflake)
build-reference          build reason-code SQL
load-reference           build + load reason-code SQL
build-reference-all      build all 5 codelist tables
load-reference-all       load all 5 codelist tables
migrate-validation-rules attach validation_sql to KG Rule nodes
build-validation-rules   KG → tspr_validation_rules.sql
load-validation-rules    push to Snowflake

# Bronze (synthetic Guidewire)
build-bronze             generate Parquet
load-bronze              PUT + COPY INTO

# Pipeline (Bronze → Silver → Gold)
run-silver               Bronze → Silver
run-gold                 Silver → Gold
run-pipeline             full chain (bronze + reference + silver + gold)

# Bulletin demo
demo-bulletin-baseline   show baseline (no bulletin)
demo-bulletin-apply      apply bulletin, show flip
demo-bulletin-reset      roll back to baseline

# Other
demo-join                BRONZE ⋈ REFERENCE join (text output)
```

---

## Stack

| Layer | Tech |
|---|---|
| Regulatory canon | Neo4j Aura (Free tier, ap-south-1) |
| Extraction | OpenAI GPT-5.5 + Sentinel agent |
| Data warehouse | Snowflake Enterprise (ap-south-1, GJMJTZB-MZ61598) |
| Ingest | PUT to internal stage + COPY INTO with MATCH_BY_COLUMN_NAME |
| Web app | FastAPI + uvicorn (port 8765) |
| Frontend | Vanilla HTML + JS (no framework) |
| Synthetic data | pyarrow Parquet generator |
| Build orchestration | Make + uv |

---

## What's not built (yet)

These are real gaps if we wanted to take this to a customer instance:

1. **SDF renderer** — Phase 3 of Gold assembly. Take Gold records and write the actual fixed-width 200-column ASCII files with Rule 12 negative encoding (`}`/`J`/`K`/…/`R`).
2. **Approval workflow + audit log** — `actuary_approved_by`, `compliance_approved_by`, SHA-256 file hash, immutable submission log with 25-month retention column.
3. **Anomaly detector** — Phase 2c of Gold: 12-month rolling z-score for premium spikes, hail spikes >3σ, freeze losses in summer months.
4. **Real Guidewire ingestion** — production would replace `generate_bronze_data.py` with Snowpipe pointed at a customer's GDP S3 bucket. Schema is already byte-identical.
5. **More Silver coverage** — TSPR Section A has 35 rules; we have validation_sql wired for 4. The pattern extends mechanically.
6. **Databricks parity** — Snowflake reference DDLs and procedures have Databricks equivalents in the architecture doc; not loaded here.

The vertical slice is intentional. The thesis (KG drives reference, bulletin flow propagates, medallion runs, validation cites) is provable with what's built today.

---

## Repo navigation

```
api/
  main.py                    FastAPI app, route definitions
  rhs_demo.py                /api/rhs/* endpoints
  registry.py                document slug → file path mapping

packages/
  rhs/
    snowflake_client.py      thin connector wrapper using ~/.snowflake/config.toml
    codelist_generator.py    generic CodeList → reference SQL
  lhs/
    sentinel/                bulletin/regulation extraction (LHS)
    materialization/         KG write-path
    citations/               PDF rect-based provenance
  adapters/lhs/gre/
    neo4j_adapter.py         KG read/write

scripts/
  build_reference_reason_codes.py        KG → reason-code SQL
  build_all_reference_tables.py          KG → 4 more reference tables
  build_validation_rules_reference.py    KG → executable rules SQL
  migrate_kg_validation_rules.py         attach validation_sql to KG Rule nodes
  apply_credit_score_bulletin.py         demo bulletin materialization
  reset_credit_score_bulletin.py         demo bulletin rollback
  generate_bronze_data.py                synthetic Guidewire Parquet
  load_bronze_to_snowflake.py            PUT + COPY INTO
  run_silver.py                          Bronze → Silver
  run_gold.py                            Silver → Gold

ui/
  index.html                 landing page
  regulations.html           /explore (regulation browser + Snowflake catalog tab)
  demo.html                  /demo (bulletin flow)
  validate.html              /validate (rule engine)
  pipeline.html              /pipeline (Bronze→Silver→Gold runner)

materialized/
  reference/                 generated SQL files (one per reference table)
  bronze_parquet/            generated Parquet (one folder per source table)
  extractions/               cached Sentinel outputs (LHS)

references/
  files-Snowflake/           target architecture DDLs (the IBM-authored reference)
  regulations/               source plan PDFs
  TSPR Platform Architecture.pdf  the reference architecture document
```

---

## Operational notes

**Snowflake connection** — uses Programmatic Access Token (PAT) auth with a network policy locked to a single IP. To switch IP: `ALTER NETWORK POLICY regulai_policy SET ALLOWED_IP_LIST = ('<new ip>');`. Token lives in `~/.snowflake/config.toml` (gitignored).

**Neo4j connection** — Aura free instance `eaa350ec`. Database name == account locator (Aura quirk). Connection string in `.env` (gitignored).

**Time taken** — feature/rhs-snowflake branched from dev on 2026-04-27. End-to-end pipeline operational on 2026-05-06. Most of the time was spent on Snowflake column-width and reserved-keyword constraints, not on architecture.
