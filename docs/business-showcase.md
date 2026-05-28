# RegulAI — Business Showcase

**Last updated**: 2026-05-18
**For**: insurance executives, compliance officers, prospective customers

---

## In one sentence

**RegulAI is the regulatory canon engine that turns published insurance regulations into the reference data your warehouse and pipelines use to file with the regulator — automatically, with citations, every time.**

---

## The problem

Statistical reporting in insurance is one of the few places where compliance is still a spreadsheet, an aging specialist, and a 45-day deadline.

Every Texas residential property carrier files three streams of data with the Texas Department of Insurance every month and every year:

- **TSPR** monthly statistical filings to TICO (premium + loss + cancellation records)
- **B-0019** annual market conditions data call
- **HB 2067** quarterly cancellation/nonrenewal/declination notices (new for 2026)

Each filing is a 200-column fixed-width ASCII file with hundreds of validation rules — symbol-encoded negative numbers, single-character year codes, deductible code 7 only valid in territories 8-10, credit-score reasons that can't stand alone, market withdrawals that must stand alone, and on, and on.

Today, this work is:

- **Manual** — extracted to spreadsheets, transformed by hand, submitted via ShareFile after a person eyeballs the file
- **Tribal** — the rules live in the heads of three or four senior specialists who've been doing it for fifteen years
- **Fragile** — when the Commissioner publishes a bulletin (HB 2067 added Section E reporting overnight, effective Jan 1 2026), the affected coding logic gets re-written by an analyst, re-tested manually, and re-deployed
- **Risky** — filing errors invite market conduct examination scrutiny; state insurance departments collect over $190M annually in penalties, much of it driven by filing accuracy issues

The combined market that has this problem: roughly **6,400 to 6,800 NAIC-reporting filers** in the US, across $1.06T of P&C direct written premium and $970B of Life and A&H premium.

The workforce demographics make it worse. The U.S. Bureau of Labor Statistics projects 400,000 insurance professionals will leave the industry by end of 2026. About half of the remaining workforce will retire within a decade. Statistical reporting is concentrated in the most senior tier of that population.

---

## What RegulAI does

It treats the regulation itself as the source of truth — and turns it into the data your filing pipeline runs on.

When TDI publishes the Texas Statistical Plan, RegulAI reads the PDF and extracts every rule, every code, every field requirement into a knowledge graph with full provenance back to the source document. When the Commissioner publishes a bulletin that amends a rule, RegulAI extracts the change and propagates it. The graph is the canonical record of what the regulation currently requires.

Downstream, your data warehouse holds reference tables that mirror the canon — code lists, validation rules, crosswalks. Your statistical reporting pipeline reads those reference tables at runtime to validate every record before submission. **The pipeline doesn't have rules baked into code; it reads them from data sourced from the regulation.**

When a bulletin lands:

1. RegulAI extracts the change
2. Knowledge graph version-bumps the affected rule
3. Reference tables regenerate
4. Next pipeline run sees the new rule
5. Filings produced for that period reflect the change automatically

No engineer reads the bulletin. No spreadsheet is edited. No deployment is required. The audit trail is complete: every filing record can be traced to the rule that validated it, and every rule to the regulation that defined it.

---

## What you actually see

The proof of concept is now a single integrated workstation at `/workstation` covering the Texas Statistical Plan filing end-to-end, with three live filings (TPA-Q4-2025, RES-M03-2026, CL-Q4-2025) running in parallel against a synthetic Guidewire feed of ~371 policies and ~154 claims. Five screens — a compliance analyst's actual day.

### Screen 1 — Dashboard

Land on the Dashboard. See pass-rate KPIs across all three filings, an estimate of fines avoided (driven by violations caught before submission), and an Active filings list. Each row shows the filing's current stage in the sign-off chain (`Resolving blockers` / `Awaiting approval` / `Submitted`), live blocker count, and days until the regulator deadline. Click any filing to open it.

### Screen 2 — Filing Workshop

The compliance analyst's workhorse screen. Top of the screen: a state-driven **sign-off rail** that walks the filing through `validated → analyst signed → actuary approved → officer approved → submitted → TICO ACKed`. Each step has a real button for the role that owns it — clicking "Approve as actuary →" writes a `USER_ACTION` row, advances the state, and locks subsequent steps until the next role acts.

Below the rail, seven **section badges** (A–G) mirroring the TSPR record layout. Each badge shows pass/fail counts for that section's rules; click a badge to filter the kanban to that section only.

The kanban groups every open blocker into three columns by severity. Each ticket carries the policy or claim id, the rule it violates, the regulatory citation, the suggested fix, and the assignee (analyst / actuary / officer / unassigned). A reason-code violator gets a one-click "Apply bulletin →" button when the pending bulletin would clear it; everything else gets a "Fix manually →" editor that mutates the underlying Bronze row.

Side popouts for the records that matter: **All records** (every policy in the filing), **Claims** (with reporting-lag and CAT-period flags), **Anomalies** (premium spikes, hail clusters, freeze-in-summer claims), **Compare filings** (three-column snapshot of TPA vs RES vs CL with best-value highlighting per metric), and **Wire preview** (the actual fixed-width 200-column ASCII bytes that go to TICO, with the SHA-256 seal).

### Screen 3 — Watch a bulletin propagate

A synthetic bulletin (B-2026-Q4-118) modifies one rule: it permits credit-score-only declinations during state-declared catastrophe periods.

Click **Apply bulletin**. RegulAI materializes the change in the knowledge graph, version-bumps the affected `CodeValue`, regenerates the reference table from the new graph, and re-runs validation across every filing. A toast appears naming the policies that just flipped INVALID → VALID; their tickets in the kanban briefly flash green and disappear from the failure list. Behind the scenes, every closed exception is tagged `resolution_action='bulletin'` so the audit log records that the bulletin (not a human fix) resolved it.

A filing that was rejected thirty seconds ago is now ready for sign-off. Nothing in the application code changed. Nothing was deployed.

### Screen 4 — Regulation Explorer

A three-pane view. Left: the full TSPR rule tree, color-coded by section. Center: when you click a rule, its plain-language explanation, its citation, the executable SQL that runs against your warehouse, and a **live KG neighborhood graph** rendered via vis-network showing how the rule connects to its citations, parent section, and companion rules in Neo4j. Right: the actual records on the current filing that violate (or pass) this rule, with one-click drill-through to the policy / claim detail.

A "View regulator text →" button on every citation fetches the matching section text directly from the loaded regulation document (TX stat plan, HB 2067, or any TDI bulletin) and shows it inline. The regulator text lives in `BRONZE_REGDOCS.RAW_REG_SECTION` — 426 sections indexed by citation pattern — so a compliance officer can trace any flagged record all the way back to the prose in the published plan.

### Screen 5 — Audit log

Every action against the filing in reverse-chronological order: validation runs, manual fixes, bulletin applies, role-by-role sign-offs, the seal event with the SHA-256 of the actual ASCII bytes that left the building, and the TICO ACK receipt. This is the chain of custody you hand a regulator who asks "why was this record reported this way?"

---

## What this changes operationally

The transformation is from spreadsheet-driven to canon-driven. Concretely:

| Today | With RegulAI |
|---|---|
| Plan rule changes require analyst interpretation, manual recoding, weeks of testing | Plan rule changes are PDF ingestion + automatic propagation |
| Filing logic lives in spreadsheets and tribal knowledge | Filing logic lives in versioned reference tables sourced from regulation |
| "What rejected this filing?" requires a senior specialist | "What rejected this filing?" returns a SQL verdict with regulatory citation |
| Audit trail: spreadsheet history + email chains | Audit trail: SHA-256 hashed submission, regulation → KG → reference → record lineage |
| Coverage of plan rules: human-curated subset | Coverage of plan rules: every published rule, queryable, executable |
| Two-year retention managed in shared drives | Two-year retention as a computed `retention_expiry_date` column |
| Mid-year retirement = filing risk | Mid-year retirement = no impact (knowledge is in the system) |

For a mid-size P&C carrier filing TSPR plus three to four other statistical plans, the labor savings alone — five to ten actuarial and compliance FTE hours per cycle freed up at $120K-$160K fully-loaded cost — would be **$600K-$1.2M per year**. The bigger benefit is the elimination of key-person dependency at the moment your specialist workforce is retiring.

---

## Why now

Three forces converging:

**Regulatory complexity is accelerating.** HB 2067 added Section E reporting in a single filing cycle. NAIC's 2025 priorities include reviewing all data collection systems. New SSAP revisions every year. The platform that encodes rules as data — where a rule change is a data update, not a code release — is the only architecture that scales with that change rate.

**The workforce is exiting.** 400,000 professionals leaving by end of 2026; statistical reporting expertise concentrated in the most senior tier. RegulAI is a knowledge codification mechanism: every rule the system has extracted survives any retirement.

**The data infrastructure is ready.** Snowflake and Databricks both support the medallion architecture out of the box. Guidewire's Data Platform exports CDC events directly to S3. The integration friction of five years ago is gone — what's missing is the governance layer that connects the regulation to the data plane. That's RegulAI.

---

## How it integrates

RegulAI is **not** a replacement for your data warehouse, your policy administration system, or your billing system. It sits beside them.

```
       Regulator                  Carrier
          │                          │
   ┌──────┴──────┐         ┌─────────┴─────────┐
   │ TSPR plan   │         │ PolicyCenter      │
   │ Bulletins   │         │ ClaimCenter       │
   │ Statutes    │         │ BillingCenter     │
   └──────┬──────┘         └─────────┬─────────┘
          │                          │
          ▼                          ▼
    ┌──────────┐              ┌────────────┐
    │ RegulAI  │              │ Snowflake  │
    │ KG canon │              │ or         │
    │          │  generates   │ Databricks │
    │          ├─reference───►│ medallion  │
    │          │  tables      │            │
    └──────────┘              └─────┬──────┘
                                    │
                                    ▼
                              TICO submission
                              (TDI / regulator)
```

For a customer engagement:

- Carrier already has Guidewire and Snowflake (or Databricks) → standard
- Carrier has 30 days of read-only access to give RegulAI the reference plan PDFs
- RegulAI populates the knowledge graph from those PDFs
- One-time integration: replace the carrier's manually-maintained reference seed data with KG-generated reference tables
- Pipeline starts running against KG-driven reference; the manual reference becomes the fallback during transition
- Bulletin flow goes live: any new bulletin published by TDI is extracted by RegulAI within 24 hours and propagated to the warehouse on the next regeneration cycle

---

## Beyond TSPR

The same architecture extends to every NAIC statistical plan and every regulator-facing data call. Each new reporting obligation needs its own KG vocabulary and reference schema, but the pattern — extract the regulation, generate the reference, drive the pipeline — is identical:

- **NCCI WCSP** — workers compensation statistical plan
- **ISO commercial lines** data calls (CGL, CAB, CMP)
- **AAIS** rural and farm market filings
- **ACLI / SOA** life and annuity experience studies
- **State-specific market conduct** filings (MCAS in 38 states)
- **Schedule F** (P&C reinsurance year-end)
- **L&A assumed reinsurance** settlement reconciliation under SSAP 61R

A carrier doing all of those today maintains a separate spreadsheet, a separate analyst, and a separate filing cycle for each. RegulAI consolidates the reference layer across all of them.

---

## What's compelling beyond efficiency

Three things matter more than the FTE numbers.

**Audit defensibility.** Every submitted record traces back through the medallion pipeline to the rule that validated it, to the reference row that defined it, to the KG node that holds it, to the page in the regulation it came from. If TDI questions a number two years from now, the answer takes minutes to assemble — and it's been provable since the day the filing went out.

**Regulatory change as a data update.** When the Commissioner publishes a bulletin in October, you don't have to schedule a development sprint to re-implement the filing logic for the next month's submission. You add the bulletin PDF to RegulAI's intake. The system handles it.

**Knowledge codification as a moat.** Every edge case that gets resolved — every "freeze plus burst pipe maps to code 71 not 61" — is encoded once as a graph node and reused forever. The platform's reference layer is the institutional knowledge of your statistical reporting team, made durable. It survives reorganizations, retirements, and acquisitions.

---

## Today's status

The proof of concept covers Texas Statistical Plan filings end-to-end across **three live filings** (TPA-Q4-2025, RES-M03-2026, CL-Q4-2025) running against synthetic Guidewire data:

- **Knowledge graph in production** (Neo4j) with the full TSPR plan, HB 2067, and three synthetic TDI bulletins extracted, plus 6 source documents + 426 indexed citation sections in `BRONZE_REGDOCS` for click-through-to-prose drill-down.
- **Reference schema** generated from the KG and deployed to Snowflake (6 tables, 110 rows, every row carries provenance to its source).
- **14 executable validation rules** spanning TSPR Sections A, B, D, and F. Each is one INSERT row away from the KG, runs as live SQL against Bronze, and cites the controlling statute.
- **15 Bronze tables** populated with ~371 synthetic policies and ~154 claims, mixing a curated demo set (21 policies designed to exercise every rule) with bulk-synth statistical mass for anomaly detection.
- **Silver and Gold layers** running on demand against the Bronze data, producing TSPR-coded staging records and submission-ready record tables stamped with `filing_batch_id` per row.
- **Sign-off workflow** with strict state machine: `validated → analyst_signed → actuary_approved → officer_approved → submitted → acked`. Each transition writes a `USER_ACTION` row. Sealing is hard-gated on officer approval + zero ERROR blockers.
- **ASCII renderer** producing the actual 200-column fixed-width TSPR file with SHA-256 seal, persisted to `FILING_SUBMISSION`, with a synthesized TICO ACK callback closing the chain.
- **Anomaly detector** populating `TSPR_ANOMALY_FLAGS` with premium spikes (>3σ), hail clusters (>3 claims / same ZIP / 1 week), and freeze-in-summer claims — surfaced as a popout on the Filing screen.
- **Bulletin flow** wired into the Filing screen — applying a bulletin re-validates every filing inline, tags every newly-closed exception with `resolution_action='bulletin'`, and shows a toast naming the policies that flipped INVALID → VALID.
- **Three-pane Regulation Explorer** with rule tree, plain-language + SQL + live KG neighborhood graph (rendered via vis-network from the Neo4j 1-hop slice), and per-rule violators on the active filing.
- **Critical-path test suite** covering audit reconciliation, bulletin attribution, sign-off rejection, and bronze-fix mutation. Runs under `make test`.
- **Idempotent migrations** in `materialized/migrations/` — six numbered SQL files replayable via `make migrate-snowflake`.

The architectural thesis — **the regulation drives the data plane, the workflow, and the file on the wire** — is provable today, end to end, with every step visible in the application and every artifact persisted with provenance.

---

## What's next for a real customer

The major remaining work for a production engagement:

1. **Customer-specific Guidewire integration.** Replace the synthetic Parquet generator with a Snowpipe pointed at the carrier's GDP S3 bucket. The Bronze schemas are already byte-identical to GDP exports; this is a configuration change, not a code change.
2. **More executable rules.** TSPR's canon has 84 descriptive rules; 14 are now executable. Each new rule = one row in a numbered migration + one small UI fix-spec entry. Mechanical, low-risk.
3. **Real TICO ACK webhook.** Current implementation synthesizes the receipt on a button-click for demo purposes; production would expose an inbound endpoint that TICO ShareFile calls when it processes the submission.
4. **Bulletin auto-ingestion.** Bulletins are dropped into the synthetic folder manually today. Production would poll the TDI Commissioner's Bulletin feed and run Sentinel extraction automatically.
5. **Databricks parity.** The Snowflake reference DDLs and procedures have Databricks equivalents in the reference architecture doc; not loaded today.
6. **Additional plans.** NCCI WCSP, ISO commercial lines, AAIS farm/rural — each is a new KG vocabulary + reference schema; the architecture is the same.

Beyond TSPR, the platform extends one regulation at a time. Each new vertical reuses the same KG → reference → pipeline → ASCII → audit pattern.

---

## The pitch in one slide

> Statistical reporting is fragile because the rules live in spreadsheets and people. RegulAI moves them into a knowledge graph sourced from the regulation itself, generates the reference tables your warehouse needs, and gives your medallion pipeline a canon to validate against. When the regulator publishes a change, the change propagates automatically. When an auditor asks why a record was filed a certain way, the answer is one query — and it cites the statute.

Open `/demo` in the proof of concept to watch this in 30 seconds.
