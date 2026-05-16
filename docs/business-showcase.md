# RegulAI — Business Showcase

**Last updated**: 2026-05-06
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

The proof of concept demonstrates this end-to-end with the Texas Statistical Plan and a synthetic Guidewire data feed. There are four screens.

### Screen 1 — Browse the regulation

Pick any section of the TSPR plan. See what RegulAI has extracted from it: rules, code lists, field requirements, with citations back to the page in the source PDF. Switch to the **Deployed in Snowflake** tab and see the reference tables those extractions produced — the regulation, now living as queryable rows in your warehouse.

### Screen 2 — Watch a bulletin propagate

A synthetic bulletin (B-2026-Q4-118) modifies one rule: it permits credit-score-only declinations during state-declared catastrophe periods. Today, this would mean an analyst reading the bulletin and editing a coding spreadsheet.

In RegulAI, you click **Process this bulletin**. The screen shows two cards side by side — RegulAI's knowledge graph on one side, your Snowflake reference table on the other. They start in sync. After processing:

- The KG updates: Code L now version 2, with companion-required = false
- The Snowflake reference row regenerates from the KG
- Both panels show the change with a green highlight

A filing that was previously rejected (POL-0011 declined for credit alone) is now accepted. Nothing else changed. Nothing else needed to.

### Screen 3 — See validation in action

Every TSPR Section A plan rule lives as a row of executable SQL in `REFERENCE.TSPR_VALIDATION_RULES`. Click **Run validation**. The system executes every rule against the current Bronze data and shows a verdict with the regulatory citation:

> POL-0011 — Rejected
> Reason Code L (credit/insurance score) requires at least one companion reason code
> Source: Tex. Ins. Code §559.052(a)(2); TICO Stat Plan Rule A.34

Click **Show executable SQL** on any rule and you see the actual SQL that ran, sourced from the reference table, sourced from the regulation. Adding a new rule means inserting a row. Updating a rule means the bulletin flow you just watched.

### Screen 4 — The medallion pipeline

Three stage cards: Bronze (raw Guidewire), Silver (TSPR-coded staging), Gold (submission-ready records). Click **Run Silver**, watch four staging tables populate. Click **Run Gold**, watch four record tables populate plus a Section 29 transmittal totals panel showing premium totals, loss totals, cancellation counts — exactly the control numbers TICO expects on the cover sheet.

The pipeline runs against your Snowflake account. Every transformation reads from the reference tables that came from the knowledge graph that came from the regulation.

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

The proof of concept covers Texas Statistical Plan filings end-to-end:

- Knowledge graph in production (Neo4j Aura) with the full TSPR plan, HB 2067, and synthetic bulletins extracted
- Reference schema generated from the KG and deployed to Snowflake (6 tables, 100 rows, every row carries provenance to its source)
- 15 Bronze tables populated with synthetic Guidewire CDC data covering 6 policies and 4 claims with deliberately chosen TSPR rule scenarios
- Silver and Gold layers running on demand against the Bronze data, producing TSPR-coded staging records and submission-ready record tables with Section 29 transmittal totals
- Validation engine executing every rule from the reference table with regulatory citations on every violation
- Bulletin flow demonstrated: synthetic Commissioner's Bulletin propagating through the entire stack, flipping a previously-rejected filing to accepted, with full audit trail

The architectural thesis — **the regulation drives the data plane, not the other way around** — is provable today, end to end, in roughly thirty seconds of clicking through four screens.

---

## What's next for a real customer

Three things would round this out for a production engagement:

1. **SDF renderer + submission audit.** Take Gold records, render the actual 200-column fixed-width ASCII files with Rule 12 negative-number encoding, hash with SHA-256, log to an immutable submission table with 25-month retention. About a week of focused work.
2. **Customer-specific Guidewire integration.** Replace the synthetic Parquet generator with a Snowpipe pointed at the carrier's GDP S3 bucket. The Bronze schemas are already byte-identical to GDP exports; this is a configuration change, not a code change.
3. **Anomaly detection.** Phase 2c of Gold assembly — flag premium spikes >2.5σ, hail clusters >3.0σ, freeze losses in summer months. Surface for actuary review before SDF rendering.

Beyond TSPR, the platform extends one regulation at a time. Each new vertical reuses the same KG → reference → pipeline pattern.

---

## The pitch in one slide

> Statistical reporting is fragile because the rules live in spreadsheets and people. RegulAI moves them into a knowledge graph sourced from the regulation itself, generates the reference tables your warehouse needs, and gives your medallion pipeline a canon to validate against. When the regulator publishes a change, the change propagates automatically. When an auditor asks why a record was filed a certain way, the answer is one query — and it cites the statute.

Open `/demo` in the proof of concept to watch this in 30 seconds.
