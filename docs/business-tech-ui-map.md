# RegulAI — Business ↔ Technology ↔ UI Map

**Last updated**: 2026-05-18
**Purpose**: a single doc that ties every compliance problem we set out to solve to the technical artifact we built for it and the place in the application where it surfaces. Useful for executives walking through the demo, engineers onboarding, and auditors tracing what the platform actually does.

**Companion docs**: [`business-showcase.md`](business-showcase.md) (executive framing), [`rhs-build-summary.md`](rhs-build-summary.md) (RHS engineering record), [`solution-architecture.md`](solution-architecture.md), [`technical-architecture.md`](technical-architecture.md), [`poc-decisions.md`](poc-decisions.md).

---

## At a glance

| Compliance Problem | Technical Solution | Where You See It in the UI |
|---|---|---|
| Plan rules live in spreadsheets and tribal knowledge | Knowledge graph (Neo4j) is the canon · `REFERENCE.TSPR_VALIDATION_RULES` is its Snowflake projection · 14 executable rules with citations | Regulations screen (3-pane) · KG neighborhood graph · "Run rule" button next to SQL predicate |
| "Why was this filing rejected?" needs a senior specialist | `/api/rhs/validate` runs every rule, returns violations with citation + record id | Filing kanban tickets, each pill carrying rule number + reason code · per-rule fix editor |
| Bulletin published → analyst rewrites coding logic for weeks | LHS bulletin flow: materialize → version-bump KG → regenerate reference → re-validate per filing · closed exceptions tagged `resolution_action='bulletin'` | Bulletins screen · "Apply bulletin" on Filing screen · toast naming flipped policies + green flash on kanban tickets |
| Key-person risk: knowledge retires with senior staff | Every rule's SQL, every CodeValue, every citation lives as data with provenance. Workstation makes the knowledge browsable | Regulation Explorer · Audit log · KG graph |
| "Did we file on time?" / "Who signed off?" answered by an email chain | Strict state machine: `draft → resolving → validated → analyst_signed → actuary_approved → officer_approved → submitted → acked` · every transition writes a `USER_ACTION` | Sign-off rail above the kanban with per-role buttons · Audit log screen |
| Filing errors invite regulator examinations and fines | 14 executable rules covering Sections A/B/D/F · 8 anomaly flags · sealing gated on `officer_approved AND open_blockers=0` | A–G section badges showing pass/fail by TSPR record type · Anomalies popout · Seal & submit returns 409 if blockers remain |
| "Prove this record was filed under the correct rule" | `FILING_SUBMISSION` SHA-256 of byte stream + `RULE_MATCH_RESULT` row per (rule × record × run) + `FILING_EXCEPTION` reconciliation history | Audit log screen · Wire preview popout (real ASCII bytes + SHA hash) |
| "Show me the regulator paragraph that says this" | `BRONZE_REGDOCS` schema with 426 indexed citation sections from the TX stat plan, HB 2067, and 3 TDI bulletins | "View regulator text →" button on every citation in the Regulation Explorer |
| Pipeline correctness will collapse at carrier scale | `filing_batch_id` stamped on every Gold record (replacing ZIP heuristic) · cartesian explosion fixed in Silver (5,310 → 235 rows) · 5 regression tests covering audit reconciliation + bulletin flow + manual fix · 6 idempotent numbered migrations | Invisible — but the per-filing record counts are now correct (TPA 443 / RES 209 / CL 107 vs. the prior cross-filing-leaked 529/388/304) |
| Three filings, one team, one console | Shared `FILINGS` registry + three-way "Compare filings" snapshot popout · per-filing scope on every endpoint and every Gold row | Dashboard Active filings list (3 rows) · Filing rail with switch-on-click · Compare filings popout |
| Anomalies caught after submission = penalty | Detector populates `GOLD.TSPR_ANOMALY_FLAGS` with 3 algorithms (premium spike, hail cluster, freeze-in-summer) before the filing is sealed | Anomalies popout on Filing screen with severity pills + re-run button |
| TICO ack lives in a separate inbox / receipt PDF | `POST /filing/{id}/ack` synthesizes a `TICO-ACK-XXXXXXXX` receipt id, advances state to `acked`, writes `acked_at` to `FILING_SUBMISSION` + `FILING_BATCH` + `USER_ACTION` | "Simulate TICO ACK →" button on the sign-off rail's `submitted` step · receipt id in audit log |

---

## 1 — The regulation as queryable data

### Business value
Statistical plans, statutes, and bulletins are PDFs. Today, compliance teams hand-translate them into spreadsheets, ETL code, and reference tables. RegulAI's premise: **the regulation is the executable artifact**, the rest of the pipeline reads from it.

### Technical components
- **Sentinel** (LHS) — LLM-backed extraction agent that reads PDFs and emits typed nodes
- **Parser** (LHS) — deterministic extractor for tabular wire-format PDFs (record layouts)
- **Neo4j KG** — `Rule`, `CodeList`, `CodeValue`, `Citation`, `RegulationDocument`, `RecordLayout`, `FieldRequirement`, `BulletinOverride` nodes; ~1,500 nodes, ~1,900 relationships
- **`scripts/build_*_reference_*.py`** — Cypher queries that materialize KG slices as Snowflake DDL + INSERTs
- **`REFERENCE` schema** — 6 tables, 110 rows, every row carries `kg_code_value_id`, `kg_canon_version`, `kg_source_document_id` for provenance
- **`BRONZE_REGDOCS`** — 6 source documents + 426 indexed citation sections backing the "view regulator text" drill-down

### Where it shows up in the UI
| Screen | Element |
|---|---|
| **Regulations** | Left pane — rule tree color-coded by TSPR section |
| **Regulations** | Center pane — plain-language explanation, citation badge, severity, target table |
| **Regulations** | Center pane — **KG neighborhood graph** rendered via vis-network from `/api/rhs/kg/neighborhood/{rule_id}` |
| **Regulations** | Center pane — **"View regulator text →"** button fetches matching section from `BRONZE_REGDOCS.RAW_REG_SECTION` and shows it inline |
| **Bulletins** | Inbox listing TDI bulletins extracted by Sentinel |

### Code anchors
- `packages/lhs/sentinel/` — extraction
- `packages/adapters/lhs/gre/neo4j_adapter.py` — KG read/write
- `scripts/build_reference_reason_codes.py`, `scripts/build_validation_rules_reference.py` — KG → reference SQL
- `scripts/load_bronze_regdocs.py` — PDF text → `BRONZE_REGDOCS`
- `api/rhs_demo.py::kg_neighborhood` — Cypher 1-hop slice for vis-network
- `api/rhs_demo.py::reg_citation` — fuzzy citation match

---

## 2 — Live validation with regulatory citations

### Business value
The compliance officer needs to answer "what blocks this filing?" in seconds, with a defensible audit trail back to the statute. Today the answer requires senior specialists. With RegulAI, it's a SQL query against a reference table sourced from the regulation.

### Technical components
- **`REFERENCE.TSPR_VALIDATION_RULES`** — 14 rules, each row: `(rule_id, rule_number, target_table, target_id_expr, violation_sql, severity, citation, …)`
- **`GET /api/rhs/validate`** — reads every rule, executes its `violation_sql` against the target table, scopes by `filing_batch_id` policy ranges, returns rule_results + violations with citation
- **`GOLD_AUDIT.RULE_MATCH_RESULT`** — one row per (rule × record × run); `pass` rows summarized by absence
- **`GOLD.FILING_EXCEPTION`** — open/closed exception tracking with MERGE-based reconciliation

### Rules covered

| Rule | Section | What it catches |
|---|---|---|
| A.22 | A | NAIC company number must be 5 digits |
| A.30 | A | Written premium plausibility |
| A.34 (3 variants) | A | Reason-code rules (valid codes, L-companion, J-alone) |
| A.40 | A | Term type standardization |
| A.42 | A | Notice date required |
| B.6 | B | HO policies = 1-4 families |
| B.11 | B | Loss cause in TSPR codeset |
| B.14 | B | Loss reporting lag >90 days |
| B.18 | B | Texas ZIP first-digit-7 |
| D.12 | D | CAT-attributable loss reporting |
| D.13 | D | Wind/Hail attribution required |
| F.0 | F | Notice source = Insurer or Insured |

### Where it shows up in the UI
| Screen | Element |
|---|---|
| **Filing** | **Section A–G badges** above the kanban — each shows N rules passing or X fails; click to filter |
| **Filing** | **Three-column kanban** by severity (high/med/low) — one ticket per open violation |
| **Filing** | Each ticket shows policy id, rule number, citation, severity pill, assigned role |
| **Filing** | Claim-side rules (B.11/B.14/D.12/D.13) render with sky-blue **`claim`** pill + claim id |
| **Regulations** | "Run" button on the SQL predicate — executes the rule live and shows row count |
| **Regulations** | Right pane lists every record on the active filing that violates the selected rule |

### Code anchors
- `api/rhs_demo.py::validate_cancellations` — the rule engine
- `materialized/migrations/002_extra_validation_rules.sql` — hand-curated rules
- `materialized/migrations/003_claim_validation_rules.sql` — claim-side rules
- `ui/workstation.html::renderFilingKanban`, `renderFilingSectionBadges`

---

## 3 — Bulletin propagation as a data update

### Business value
When TDI issues a Commissioner's bulletin amending a rule, the cost of compliance today is weeks of analyst time. RegulAI's premise: **the bulletin is data, the propagation is automatic, the audit trail is complete**.

### Technical components
- **`apply_credit_score_bulletin.py`** — materializes the bulletin into the KG (new `CodeValue` version, `BulletinOverride` node, `OVERRIDES` edge)
- **`apply_bulletin.py`** — version-bumps and supersedes the old `CodeValue`
- **`build_reference_reason_codes.py`** — regenerates the reference SQL from the new KG state
- **`POST /api/rhs/bulletin/apply`** — runs all three above, then **re-runs validation for every filing inline** and tags every newly-closed `FILING_EXCEPTION` with `resolution_action='bulletin'`. Returns per-filing deltas.
- **`_record_validation_run(filing_id, …, resolution_action='bulletin')`** — passes the attribution down to the exception close

### Where it shows up in the UI
| Screen | Element |
|---|---|
| **Bulletins** | Inbox of TDI bulletins, current one selectable |
| **Bulletins** | **Apply bulletin** button + impact panel showing before/after deltas |
| **Filing** | **Apply bulletin** button on each L-companion ticket (one-click bulletin application from the offending record) |
| **Filing** | After applying: **6-second toast** naming the policies that flipped INVALID → VALID |
| **Filing** | After applying: brief **green flash** on the affected kanban tickets as they disappear from the failure list |
| **Audit** | `USER_ACTION` row with `action_type='bulletin_apply'` · per-filing exception rows show `resolution_action='bulletin'` |

### Code anchors
- `api/rhs_demo.py::bulletin_apply` — orchestrates LHS flow + per-filing re-validation
- `api/rhs_demo.py::_record_validation_run(resolution_action=…)`
- `ui/workstation.html::showBulletinFlipToast`

---

## 4 — Workflow with chain of custody

### Business value
"Who signed off?" "When?" "Were there open blockers when this was submitted?" Today these answers live in email and Jira. RegulAI makes them a state machine + audit log.

### Technical components
- **`GOLD.FILING_BATCH.status`** — enum: `draft → resolving → validated → analyst_signed → actuary_approved → officer_approved → submitted → acked`
- **`POST /api/rhs/filing/{id}/approve`** — body `{role: analyst|actuary|officer}`. Enforces required prior state + zero ERROR blockers. Writes `USER_ACTION` with actor label.
- **`GET /api/rhs/filing/{id}/approval-state`** — compact state useful for rendering the rail
- **`POST /api/rhs/filing/{id}/ack`** — synthesizes TICO ACK receipt, advances to `acked`
- **Seal gating** — `GET /api/rhs/filing/{id}/file?persist=true` returns **409** unless `status='officer_approved' AND open_blockers=0`
- **`USER_ACTION`** — every transition + every manual fix + every bulletin apply + every validation run gets a row

### State machine

```
draft ──► resolving ◄──┐   (validation re-runs while ERROR blockers remain)
            │          │
            ▼          │
        validated ─────┘
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
        submitted   (FILING_SUBMISSION written with file_sha256)
            │
   (TICO ACK — POST /filing/{id}/ack)
            ▼
          acked
```

### Where it shows up in the UI
| Screen | Element |
|---|---|
| **Filing** | **Sign-off rail** above the kanban — 7 stages, current one bordered, prior ones checkmarked |
| **Filing** | Inline **role-button** at the current stage: "Approve as analyst →" / "Approve as actuary →" / "Approve as officer →" |
| **Filing** | **Seal & submit →** button enabled only at `officer_approved` |
| **Filing** | **Simulate TICO ACK →** button on the `submitted` step |
| **Audit** | Reverse-chronological list of every `USER_ACTION` with actor, timestamp, summary, and details JSON |

### Code anchors
- `api/rhs_demo.py::APPROVAL_CHAIN` — role → (required_state, next_state, actor_label) mapping
- `api/rhs_demo.py::filing_approve`, `filing_ack`, `filing_approval_state`
- `api/rhs_demo.py::filing_file` — seal gating logic
- `ui/workstation.html::STAGES` — UI rendering of the state machine

---

## 5 — The actual file on the wire

### Business value
The filing **is** the 200-column fixed-width ASCII file. Everything else is plumbing. The compliance officer needs to see, hash, and audit the exact bytes that go to TICO ShareFile.

### Technical components
- **`GET /api/rhs/filing/{id}/file`** — produces the byte stream:
  - Header line
  - One P-record per `GOLD.TSPR_PREMIUM_RECORDS` row (Section C)
  - One L-record per `GOLD.TSPR_LOSS_RECORDS` row (Section D)
  - One C-record per `GOLD.TSPR_CANCELLATION_RECORDS` row (Section E + G)
  - Footer with Section 29 transmittal totals
- **`?persist=true`** — inserts `FILING_SUBMISSION` row with `file_sha256`, `file_size_bytes`, `record_count`; advances state to `submitted`
- **Scope by `filing_batch_id`** — every Gold record carries this column (migration 005), so the renderer pulls exactly the rows belonging to the active filing
- **`_render_*` helpers** — `_pad_alpha`, `_pad_num`, `_pad_date` enforce the column widths required by TSPR

### Per-filing byte totals (current state)
| Filing | P recs | L recs | C recs | Total records | ASCII size |
|---|---|---|---|---|---|
| TPA-Q4-2025 | 212 | 83 | 148 | 443 | ~89 KB |
| RES-M03-2026 | 105 | 50 | 54 | 209 | ~42 KB |
| CL-Q4-2025 | 54 | 20 | 33 | 107 | ~21 KB |

### Where it shows up in the UI
| Screen | Element |
|---|---|
| **Filing** | **Wire preview** popout shows the actual rendered ASCII (first ~12 lines + scrollable) + SHA-256 + total bytes |
| **Filing** | **ShareFile modal** — `Seal & submit →` button generates the file with `?persist=true`, displays the resulting `submission_id` |
| **Audit** | `FILING_SUBMISSION` row visible with sha, byte count, channel, submitted_by, submitted_at |

### Code anchors
- `api/rhs_demo.py::filing_file` — renderer
- `api/rhs_demo.py::_render_header`, `_render_premium_record`, `_render_loss_record`, `_render_cancellation_record`, `_render_footer`
- `ui/workstation.html` — `data-action="seal-and-submit"` handler

---

## 6 — Anomaly detection before submission

### Business value
Some filing errors are not rule violations — they're statistical outliers a human would catch. RegulAI runs three deterministic detectors before sealing so anomalies surface for review, not after the regulator escalates.

### Technical components
- **`scripts/detect_anomalies.py`** — three detectors, idempotent (TRUNCATEs table at start)
- **`GOLD.TSPR_ANOMALY_FLAGS`** — extended with `filing_batch_id`, `source_records VARIANT`, `severity` (migration 006)
- **`GET /api/rhs/anomalies?filing=...`** — list per filing
- **`POST /api/rhs/anomalies/detect`** — re-run from UI

### Detectors

| Type | Predicate | Severity | Currently flagged |
|---|---|---|---|
| `premium_spike` | ZIP total premium > 3σ above corpus mean | WARN | 2 (ZIP 77002 at 4.2σ, ZIP 78701 at 3.0σ) |
| `hail_cluster` | >3 Hail claims · same ZIP · 7-day window | INFO | 0 |
| `freeze_in_summer` | `losscause='Freeze' AND MONTH(lossdate) BETWEEN 6 AND 9` | WARN | 6 |

### Where it shows up in the UI
| Screen | Element |
|---|---|
| **Filing** | **Anomalies** button on the meta-line, count badge |
| **Filing** | **Anomalies popout** — per-anomaly card with type icon (⤴ spike, ⊕ cluster, ❄ freeze), severity pill, ZIP, plain-language description, contributing record IDs, σ score |
| **Filing** | **Re-run detection** button inside the popout |

### Code anchors
- `scripts/detect_anomalies.py::detect_premium_spike`, `detect_hail_cluster`, `detect_freeze_in_summer`
- `api/rhs_demo.py::anomalies_list`, `anomalies_detect`
- `ui/workstation.html::openDetail_filing('anomalies')`

---

## 7 — Multi-filing orchestration

### Business value
A mid-size carrier files multiple statistical plans every cycle. One operator should manage all of them from one console without context-switching, and should be able to compare them.

### Technical components
- **`packages/rhs/filings.py`** — canonical `FILINGS` registry (3 entries), shared by `api/rhs_demo.py` and `scripts/run_gold.py`
- **`policy_id_ranges: list[tuple[int,int]]`** — non-contiguous ranges so curated demo cases + bulk synth both scope to the same filing
- **`filing_batch_id` stamped on Gold** — added by migration 005, populated via `policy_id_to_filing_case()` CASE expression
- **`policy_number_to_filing_case(column)`** — helper that builds the equivalent CASE for the Silver→Gold step
- **`GET /api/rhs/filings`** — lists every registered filing
- **`/validate`, `/audit`, `/bronze/*`, `/filing/*/file`, `/anomalies`** — all accept `?filing=...` and scope accordingly

### Three filings currently registered

| Filing | Plan | Curated demo IDs | Bulk synth IDs | Cadence | Due |
|---|---|---|---|---|---|
| `TPA-Q4-2025` | Texas Private Passenger Auto / Homeowners | POL-0001..0019 | POL-2100..2299 | Quarterly | 2026-03-31 |
| `RES-M03-2026` | Residential Property — March 2026 | POL-0030..0034 | POL-2300..2399 | Monthly | 2026-04-15 |
| `CL-Q4-2025` | Commercial Lines | POL-0050..0053 | POL-2400..2449 | Quarterly | 2026-05-15 |

### Where it shows up in the UI
| Screen | Element |
|---|---|
| **Dashboard** | **Active filings list** — one row per filing with stage label, progress bar, blocker count, days-until-due. Click to switch context |
| **(left rail)** | **My filings** group — switch-on-click with live blocker count badge per filing |
| **Filing** | **Compare filings** popout — three-column snapshot with pass-rate cards + 6-row metric table (records, ASCII bytes, rules run, fails, violations, anomalies) with best-per-row highlighting |
| **Filing** | Top-bar "filing-id" label always shows the active filing's plan code + period |

### Code anchors
- `packages/rhs/filings.py` — `FILINGS`, `filing_ranges`, `policy_id_to_filing_case`, `policy_number_to_filing_case`
- `api/rhs_demo.py::_filing_ranges`, `_filing_policy_numbers`, `_scope_clause`
- `scripts/run_gold.py::FILING_CASE_BY_POLICY_NUMBER`, `FILING_CASE_BY_BRONZE_ID`
- `ui/workstation.html::renderRail`, the `switch-filing` action handler, `openDetail_filing('compare')`

---

## 8 — Audit defensibility

### Business value
If TDI asks "why was this record reported this way?" two years from now, the answer takes minutes to assemble and is provable since the day the filing went out.

### Technical components
- **`GOLD_AUDIT.RULE_MATCH_RESULT`** — every (rule × record × run): status (pass/fail/error), violation_reason, severity, citation, evidence
- **`GOLD_AUDIT.USER_ACTION`** — every transition, manual fix, bulletin apply, validation run, regulator ACK
- **`GOLD.FILING_EXCEPTION`** — open/closed history with `resolution_action` attribution (`fix` / `bulletin` / `manual`)
- **`GOLD.FILING_SUBMISSION`** — SHA-256 of the byte stream + ACK receipt + file_size_bytes + record_count
- **MERGE-based reconciliation** — `_record_validation_run` opens new exceptions and closes any no-longer-firing ones in a single pass, idempotent under re-runs
- **`GET /api/rhs/audit/{filing_id}`** — chain-of-custody endpoint

### Where it shows up in the UI
| Screen | Element |
|---|---|
| **Audit** | Per-filing screen with batch metadata header (status, last_validated_at, open_blockers, generated_at, submitted_at, acked_at) |
| **Audit** | Reverse-chronological **user-action feed** — actor, action_type, target, summary, timestamp |
| **Audit** | **Exceptions table** — every open/fixed exception with rule_number, policy_number, opened_at, resolved_at, resolution_action |
| **Audit** | **Submission record** — file_name, sha256, byte_count, channel, submitted_at, acknowledgment receipt |

### Code anchors
- `api/rhs_demo.py::audit_history`
- `api/rhs_demo.py::_record_action`, `_record_validation_run`, `_audit_safe`
- `ui/workstation.html::renderAudit`

---

## 9 — Engineering correctness (the invisible foundation)

### Business value
"It works at demo scale" is not enough. The platform has to be correct at carrier scale, replayable on demand, and have regression tests.

### Technical components
- **Cancellation cartesian fix** (`scripts/run_silver.py`) — dropped the non-unique `GW_PC_ADDRESS.postalcode` JOIN; cancellation staging went from 5,310 rows to 235 (~1:1 with source jobs)
- **`filing_batch_id` FK** (migration 005) — replaces the ZIP-overlap heuristic for cancellation scoping; per-filing record counts dropped from inflated 529/388/304 to correct 443/209/107
- **Idempotent migrations** (`materialized/migrations/001..006`) — replayable via `make migrate-snowflake`; all use `IF NOT EXISTS` and `WHERE NOT EXISTS`
- **Critical-path tests** (`tests/test_critical_paths.py`) — 5 cases covering audit reconciliation, bulletin attribution, approval-state rejection (×2), bronze-fix mutation
- **`--reload` uvicorn** + clean module imports — API picks up code changes automatically; `import api.rhs_demo` is the smoke test for syntax validity
- **`packages/rhs/filings.py`** — canonical registry shared by API + run_gold (was duplicated, drift-prone)

### Where it shows up in the UI
Invisible — but the **numbers are correct**. Compare-filings popout shows 443/209/107 records. ASCII rendering completes deterministically. The same code path handles the curated 21 policies and the bulk 350+ policies without special-casing.

### Code anchors
- `scripts/run_silver.py::silver_cancellation` — cartesian fix
- `scripts/run_gold.py` — filing_batch_id stamping
- `materialized/migrations/` — six numbered files
- `tests/test_critical_paths.py` — 5 regression tests
- `Makefile::migrate-snowflake`, `run-pipeline`

---

## 10 — The user surface

### `/workstation` — the integrated workstation

| Screen | Elements | Backing endpoint(s) |
|---|---|---|
| **Dashboard** | KPI tiles (pass-rate, fines avoided, regulator readiness) · Active filings list (3 rows) · Recent activity · Wire preview | `/state`, `/filings`, `/validate?filing=*` (one per filing) |
| **Filing** | Sign-off rail · A–G section badges · 3-column severity kanban · meta-line popout buttons (All records / Claims / Rules / Anomalies / Compare / Wire preview) · per-rule fix editor | `/validate`, `/anomalies`, `/filing/{id}/approval-state`, `/bronze/*`, `/audit/{id}`, `/filing/{id}/file` |
| **Regulations** | Rule tree (left) · plain-language + citation + executable SQL + KG neighborhood graph (center) · per-rule violators + bronze sample (right) | `/kg/rules`, `/kg/neighborhood/{id}`, `/reg/citation`, `/validate` |
| **Bulletins** | Bulletin inbox · selected bulletin text · before/after impact panel | `/bulletin`, `/bulletin/apply`, `/bulletin/reset` |
| **Audit** | Batch header · USER_ACTION feed · FILING_EXCEPTION table · FILING_SUBMISSION row | `/audit/{filing_id}` |

### Cross-cutting UI components
- **Left rail** — screen nav + "My filings" group with live blocker badges
- **Top bar** — active filing label + bulletin status indicator + KG/Snowflake/ShareFile health pills
- **Help overlay** — context-aware "What am I looking at?" with per-screen prose explaining the page
- **Toasts** — bulletin-flip celebrations, error notifications
- **Detail popouts** — slide-in panels driven by `openDetail_filing(section)` for popout-style drill-ins without losing the main view

---

## Where to go next

| Need | Open |
|---|---|
| Executive 30-second pitch | [`business-showcase.md`](business-showcase.md) |
| Architectural deep dive (LHS + RHS) | [`solution-architecture.md`](solution-architecture.md) |
| RHS engineering record + API reference | [`rhs-build-summary.md`](rhs-build-summary.md) |
| LHS extraction + KG schema | [`technical-architecture.md`](technical-architecture.md) + [`kg-schema.md`](kg-schema.md) |
| Operational runbook | [`how-it-works.md`](how-it-works.md) |
| Decision history | [`poc-decisions.md`](poc-decisions.md) |
| Try the demo | `make up && make ui` then open `http://localhost:8765/workstation` |
