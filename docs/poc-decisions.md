# RegulAI Coded POC — Decisions & Open Questions

**Status**: brainstorming. This document is the running record of decisions made and questions still open for the **coded** POC (distinct from the existing `mock-ui-v2/` design artifact).

**Started**: 2026-04-25
**Source-of-truth scope doc**: `references/End to End Simple Use case.docx`

---

## North Star

A coded, runnable POC that takes synthetic source-system data (Guidewire as primary example) through a Snowflake medallion pipeline and produces a real TICO transmittal that satisfies what the Texas regulations demand — while showcasing **three differentiators** that together form RegulAI's commercial pitch:

1. **Record-level agentic+HITL loop** — agent classifies/normalizes each record; ambiguous cases route to HITL.
2. **Rules-level agentic+HITL loop** — agent ingests regulatory bulletins, proposes rule changes, human approves, in-flight records are re-evaluated under new rules with provenance.
3. **Knowledge Graph as regulatory canon** — the KG is the authoritative, versioned representation of what the regulations require. Every classification, edit check, Gold aggregation, and transmittal field cites a KG node. Tracing any output back to its regulatory source is a graph walk away. **"We are good at the source of reporting requirement as per regulation."**

Audience for the demo: insurance compliance professionals. Credibility is the primary bar.

---

## Architecture: LHS = RHS

The system is two halves meeting at a contract:

```
       LHS                                          RHS
  ┌─────────────────────┐                ┌─────────────────────┐
  │ Regulation docs     │                │ Source systems      │
  │ (TICO stat plan,    │                │ (Guidewire PC + CC, │
  │  HB 2067, bulletins)│                │  notice/UW feed,    │
  │       ↓             │                │  + future systems)  │
  │   LLM extraction    │                │       ↓             │
  │       ↓             │                │   Bronze (raw)      │
  │     KG (Neo4j)      │ ←── contract ─→│       ↓             │
  │       ↓             │                │   Silver (canonical │
  │  side-by-side       │                │   TX overlay)       │
  │  admin reviews      │                │       ↓             │
  │  + approves         │                │   Gold (templates   │
  │                     │                │   from KG → report) │
  └─────────────────────┘                └─────────────────────┘
   "what the regulation                    "what the system
    requires"                                produces"
```

### LHS — the regulatory demand side
- **Sources**: regulation documents (TICO stat plan, HB 2067, bulletins, future amendments).
- **Process**: Sentinel LLM extracts structured KG nodes/edges with citations to source spans.
- **State**: KG (Neo4j) is the system of record for "what the regulation requires."
- **UI**: side-by-side regulation ↔ KG with extraction highlighting and uncited-span coverage gaps.
- **HITL**: compliance/admin reviews extractions, edits, approves. Triggered by:
  - New document ingestion (new bulletin, new stat plan edition)
  - Admin manual edit (correction, addition)
  - Both flow through the same review/approval surface.

### RHS — the source-system supply side
- **Sources**: any source system that contributes records subject to LHS rules. POC: synthetic Guidewire (PolicyCenter + ClaimCenter) + synthetic notice/underwriting feed. Future: Workday GL, additional carriers, additional LOBs.
- **Process**: Bronze (raw landing) → Silver (canonical + TX classification overlay) → Gold (filing-ready marts).
- **State**: Snowflake medallion + MR_QUEUE + HITL_AUDIT_LOG + transmittal output.
- **HITL**: claim-data analyst / reviewer approves ambiguous record classifications. Different humans, different surface from LHS HITL.
- **The Bridge agent lives on RHS** but consults the LHS KG when classifying ambiguous records.

### The contract
The KG defines the contract: required reports, required fields per report, valid classifications, valid event types, edit-check rules, HITL trigger rules, edition pinning. RHS produces records that satisfy the contract; mismatches fail to MR_QUEUE.

Two HITL surfaces because they're two different human roles:

| | LHS HITL | RHS HITL |
|---|---|---|
| Who | Compliance officer / regulatory analyst | Claim-data analyst / reviewer |
| What they approve | Rule extractions, rule changes, schema | Record classifications, edge cases |
| Cadence | Per regulation event (rare, high-stakes) | Per ambiguous record (frequent, lower stakes) |
| UI surface | Side-by-side `mock-ui-v2/ontology.html` extension | `mock-ui-v2/review.html` extension |

Every future decision in this doc has an obvious place to live: LHS-side, RHS-side, or about the contract.

---

## Decisions made

### Scope & jurisdiction
- ✅ **Jurisdiction**: Texas
- ✅ **Line of business**: Homeowners (HO-3 sample form), residential property
- ✅ **Statistical agent**: TICO (TDI's designated agent)
- ✅ **Filing cadence**: **monthly** (per TICO Texas Residential Plan). Synthetic data should span at least one full filing month so the demo run produces a credible monthly transmittal.
- ✅ **Compliance hooks**: Texas Residential Stat Plan + HB 2067 notice reporting (cancellation, nonrenewal, **and declination** — all three event types)

### Differentiators (all three load-bearing — none is optional)
- ✅ **Record-level agentic+HITL loop (RHS)** — Bridge agent (Claude API) classifies records, ambiguous ones route to RHS HITL queue with the agent's draft pre-populated. Headline scenario: WH vs WN on Hurricane-Beryl-style claim. Every classification cites the KG node version it used.
- ✅ **Rules-level agentic+HITL loop (LHS)** — Sentinel agent reads synthetic TDI documents (stat plan, bulletins) or admin manual edits, proposes rule diffs as **KG node + edge changes**, compliance officer approves in side-by-side UI, edition-pinned RHS records re-evaluate.
- ✅ **Knowledge Graph as regulatory canon (the contract)** — native KG in **Neo4j**. Seeded in Phase 1 from synthetic-but-realistic TICO Texas Residential Plan + HB 2067 documents. Every RHS component (dbt edit checks, Bridge agent prompts, Gold aggregations, transmittal templates) reads from the KG. Every node carries citations to LHS source-document spans. Side-by-side UI shows regulation text ↔ extracted nodes with coverage gap indicators.

### Data
- ✅ **RHS sources** (POC): synthetic, **shaped exactly like Guidewire CDA** for Policy + Claim (right tables, keys, cardinality, field names) + a synthetic notice/underwriting feed for HB 2067 events. No real Guidewire access — treated as a feature, not a blocker. Guidewire is the *primary example* of an RHS source, not the only one — the architecture accommodates multiple source systems on RHS.
- ✅ **LHS sources** (POC): synthetic-but-realistic markdown of the TICO Texas Residential Stat Plan + HB 2067 statute + a couple of synthetic bulletins. Each treated as a `RegulationDocument` with sectioned text suitable for citation anchors.
- ✅ **Volume**: small portfolio, ~8–10 deliberate records covering edge cases (see scenario list below).
- ✅ **Mix**: deliberate good/bad records so edit checks fire and HITL routes happen.

### Fidelity
- ✅ **High-fidelity-where-it-matters** (not all-fidelity-everywhere):
  - TICO transmittal output: **true high fidelity**, would pass actual TICO validation
  - Business-logic fields: **true high fidelity** with real reference values. Specifically:
    - COL codes (WH, WN, HA, WD2/3/4, FR, FI, TH, VMM, OT)
    - Territory codes (TX 11–15 coastal, 21+ inland) **plus county/place** — ZIP→County→Territory is a chain that drives classification
    - Perils (peril codes normalized in Silver)
    - HB 2067 reason codes (all three event types: cancellation, nonrenewal, declination)
    - Stat plan edition (THSP_2019 / THSP_2024 / THSP_2026)
    - Catastrophe code (cat tagging from ClaimCenter)
    - Form code (HO-3, HO-5, DP-3, plus endorsements like HO-15)
  - PC must-flow-through fields: HO policy, coverage, premium, **address, deductible, term**
  - CC must-flow-through fields: loss date, peril, claim status, paid/incurred, **catastrophe tagging**
  - Notice must-flow-through fields: event type, effective date, sent date, reason text
  - Guidewire CDA input shape: **structurally accurate**, populate only fields that flow downstream
  - Demographic/cosmetic fields: realistic-looking placeholders

### Platform
- ✅ **Two-database split, one for each side**:
  - **LHS: Neo4j** (native KG) — system of record for regulations, rules, templates, triggers, citations, versions. Native Cypher for graph operations. Hosting choice deferred (AuraDB Free vs Docker Community) — both work; pick when scaffolding.
  - **RHS: Snowflake** — system of record for records, transmittals, MR_QUEUE, HITL_AUDIT_LOG. Free trial: $400 credit, 30 days; POC burn ~$5–10. Mitigation for trial expiry: all DDL/dbt models in git for fast rebuild.
- ✅ **The contract path (RHS reads LHS at runtime)** — KG slice materialized from Neo4j into a small Snowflake table (`gre_materialized_rules`) on every KG approval, so dbt and edit checks read clean SQL. Neo4j stays source of truth; materialization is cache. Materialization runs in seconds.
- ❌ **Snowflake Cortex LLM functions** rejected — locks to Snowflake-hosted models, region-limited Claude, no prompt caching/tool use.
- ✅ **Claude API direct from Python** for both Bridge (RHS) and Sentinel (LHS) agents.

### Output
- ✅ **JSON on disk + visual UI surface** — actual TICO transmittal file plus screen(s) demonstrating the agentic+HITL flow.

### Architecture pattern
- ✅ **Modular monolith with ports & adapters** (hexagonal). NOT microservices for POC — they add operational tax with no real benefit at single-developer scale. Module boundaries are drawn cleanly so future extraction to services is mechanical.
- ✅ **Single Python repo, single deployable** for the POC, organized as LHS modules + RHS modules + shared kernel.
- ✅ **KG is the contract**: LHS produces it; RHS reads from it (via the materialization path). Hardcoded regulatory rules anywhere on RHS are an antipattern.
- ✅ **Nine replaceable seams** defined as `Protocol` interfaces, organized by side.

### Tech stack
- ✅ **Language**: Python 3.11+ everywhere except SQL
- ✅ **Package mgmt**: `uv` (or Poetry as fallback)
- ✅ **Data warehouse**: Snowflake
- ✅ **Transformations**: **dbt-core** (free, SQL+Jinja, Snowflake adapter mature, compliance teams already speak it)
- ✅ **Orchestration**: `Makefile` + Python entry scripts. Defer Prefect/Airflow.
- ✅ **Agent runtime**: Anthropic SDK direct, behind `LLMPort`. Sonnet 4.6 for Bridge, Opus 4.7 candidate for Sentinel (rules reasoning is harder). Use prompt caching on SOP/reference content.
- ✅ **API**: **FastAPI** (async, Pydantic-native, free OpenAPI)
- ✅ **UI**: **Extend `mock-ui-v2/`** with FastAPI endpoints — keeps the design language. Skip Streamlit.
- ✅ **HITL state / GRE**: Snowflake tables (append-only versioned rules table). Defer Neo4j.
- ✅ **Synthetic data**: Python + Faker + hand-crafted scenario templates. Commit sample outputs to git for repeatability.
- ✅ **Reference data**: dbt seeds (CSVs in `seeds/`)
- ✅ **Config**: Pydantic settings + `.env`
- ✅ **Tests**: pytest. Pure transforms + agent IO contracts (mocked LLM).

---

## Scenario portfolio (the synthetic records)

### The anchor record (the single best demo thread)

Per the source-of-truth scope doc: **one HO-3 policy carrying both a wind/hail claim and an HB 2067 nonrenewal notice** is the sharpest single demo. That one record alone touches all four TICO reports (Premium, Loss, Notice, Notice Count) plus filing-agent submission, and carries the WH-vs-WN agentic classification — fewest moving parts, maximum coverage.

This is the **Phase 2 headliner**. The other 8 scenarios layer edge cases on top.

### The full portfolio

| # | Scenario | Why it's in the demo |
|---|---|---|
| 1 | Clean baseline HO-3, no claims, no notices | Boring control case; pipeline succeeds with no HITL. Contributes to Premium only. |
| 2 | **Anchor record** — coastal HO-3 + WH/WN wind/hail claim + HB 2067 nonrenewal at term end, same policy | **The single best demo thread.** Touches all four reports + agentic+HITL on the WH/WN call. Optional narrative tension: was nonrenewal driven by the claim? |
| 3 | Mid-term cancellation (insured-requested) | Cancellation count vs notice reporting; non-nonrenewal flavor |
| 4 | Edition-boundary policy (effective spans stat plan edition change) | Edition pinning demonstration |
| 5 | Ensuing loss (wind → water, multi-peril) | Multi-peril coding edge case |
| 6 | Reopened claim with supplemental payment | Transaction history matters |
| 7 | Endorsement-driven coverage shift (HO-15 added mid-term) | Coverage form classification |
| 8 | Novel form → HITL + GRE learning loop | "System has never seen this" path |
| 9 | Declination notice (application denied) | Third HB 2067 event type beyond cancellation/nonrenewal |
| 10 | (Stretch) Bulletin-affected re-evaluation | **Ties record-level and rules-level loops together — the killer moment** |

---

## Architecture

### Data flow

```
Synthetic Guidewire CDA + Notice extracts (JSON files / Snowflake stage)
        │
        ▼
   Bronze (raw landing, lineage cols)
        │   GW_POLICY_B, GW_CLAIM_B, GW_CLAIM_TXN_B, GW_NOTICE_B,
        │   TX_REF_CLASS_CODES_B   ← TX classification reference data raw
        ▼
   Silver (canonical TX entities + classifications + Bridge agent)
        │   POLICY_S, PROPERTY_S, CLAIM_S, CLAIM_FINANCIAL_S, NOTICE_S,
        │   TX_CLASSIFICATION_S    ← attaches county/place/territory/class overlay
        │                            (ZIP → County → Territory → Classification)
        │   + Bridge agent (Claude API): WH/WN, novel form, HB 2067 reason
        │   + edit checks → MR_QUEUE for HITL
        │   + reconciliation checks (notices sent vs actions taken)
        ▼
   HITL (UI: human reviews MR_QUEUE rows; decisions → HITL_AUDIT_LOG)
        │
        ▼
   Gold (filing marts, edition-pinned, monthly cadence)
        │   TX_HO_PREMIUM_STAT_G   — Dwelling/HO Premiums
        │   TX_HO_LOSS_STAT_G      — Dwelling/HO Losses
        │   TX_HO_NOTICE_STAT_G    — Cancellation/Nonrenewal/Declination Notices
        │   TX_HO_NOTICE_COUNT_G   — Counts AND reconciliation vs Notice report
        │   TX_TICO_TRANSMITTAL_G  — assembled transmittal
        ▼
   TICO transmittal file on disk

Sidecar: Sentinel agent reads synthetic bulletins → proposes RegChange
         → human approves in UI → new StatPlanEdition / COLCodeRule
         versions → in-flight records re-evaluated.
```

**`TX_CLASSIFICATION_S` is where the Texas-specific overlay lives** — county/place attributes attached from address, territory derived from county, classification attributes required by the Residential Plan. This table is what makes the Silver layer "Texas canonical" instead of generic homeowners canonical.

**Notice Count is reconciliation, not just counting** — every record in `TX_HO_NOTICE_STAT_G` (a notice sent) should reconcile against `TX_HO_NOTICE_COUNT_G` (an action taken). Mismatches (notice sent but no cancellation recorded; cancellation recorded with no notice) fail to `MR_QUEUE` for HITL review. This is a real edit check, not just an aggregate.

### Knowledge Graph (LHS) — the regulatory canon, in Neo4j

The KG is a **closed-vocabulary, citation-grounded, versioned** native graph in **Neo4j**. Every node carries provenance back to a regulation document span. Every RHS component reads from the KG (via the materialization path); nothing about regulation is hardcoded on RHS.

#### Storage shape (Neo4j; behind `GREStore` port)

Neo4j stores nodes and relationships natively — no schema tables to define for the graph itself. We use **labels** for node types and **relationship types** for edges. Plus a small set of constraints/indexes:

```cypher
// Constraints (uniqueness)
CREATE CONSTRAINT node_id_unique IF NOT EXISTS
  FOR (n:GRENode) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT document_hash_unique IF NOT EXISTS
  FOR (d:RegulationDocument) REQUIRE d.hash IS UNIQUE;

// Indexes for lookup
CREATE INDEX node_type_version IF NOT EXISTS
  FOR (n:GRENode) ON (n.type, n.version);

CREATE INDEX effective_date IF NOT EXISTS
  FOR (n:GRENode) ON (n.effective_from);
```

Common node properties: `id`, `type`, `name`, `version`, `status` (draft/approved/superseded), `effective_from`, `effective_to`, `created_at`, `created_by`. Citations are stored as relationships to `RegulationDocument` nodes carrying `char_start`/`char_end`/`kind` properties.

Versions are append-only. A "rule change" creates a new node version + a `SUPERSEDES` relationship from new→old. Edition pinning is a temporal Cypher query: `MATCH (n:GRENode {type: $t, name: $name}) WHERE n.effective_from <= $date AND (n.effective_to IS NULL OR n.effective_to > $date) RETURN n`.

#### The materialization path (RHS reads LHS)

dbt and edit checks run against Snowflake. The KG lives in Neo4j. We bridge with a small Python job:

```
Approval committed in side-by-side UI
  → Cypher write: new node version + SUPERSEDES edge in Neo4j
  → MaterializationJob runs (~seconds):
      Cypher: walk active rules at effective date
      → flatten to rows
      → write to Snowflake gre_materialized_rules,
                          gre_materialized_templates,
                          gre_materialized_triggers
  → next dbt run picks up new rules
```

Neo4j is **source of truth**. Snowflake materialized tables are **cache** — regenerable from Neo4j at any time. dbt models read only the materialized tables; they never reach into Neo4j directly. This keeps the dbt mental model simple and gives compliance-data engineers a flat audit artifact ("here are exactly the rules in effect after this approval").

#### Starter node types (closed vocabulary, ~12 types for POC)

| Node type | Purpose |
|---|---|
| `RegulationDocument` | The source PDF/text — stat plans, bulletins, statutes |
| `StatPlanEdition` | A specific edition of a stat plan (e.g., THSP_2024) |
| `ReportTemplate` | Defines structure of a Gold report (Premium / Loss / Notice / Notice Count) |
| `FieldRequirement` | A specific required field on a report (e.g., `NAMED_STORM_NWS_ID required when COL=WH`) |
| `COLCodeRule` | Cause-of-loss code definition + when it applies (WH, WN, HA, etc.) |
| `TerritoryRule` | TX territory definitions + ZIP/County→Territory mapping |
| `EndorsementRule` | Endorsement form classification rules (HO-15, HO-61, etc.) |
| `NoticeReasonCode` | HB 2067 reason codes (cancellation/nonrenewal/declination reasons) |
| `EditionEffectiveDate` | When a rule version takes effect |
| `BulletinOverride` | Mid-edition modification to a base rule from a TDI bulletin |
| `CarrierSOP` | Carrier-specific operating procedure refining a base rule |
| `HITLTriggerRule` | Conditions under which a record routes to HITL (the 8 trigger types) |

#### Starter edge types

| Edge type | Meaning |
|---|---|
| `SUPERSEDES` | new version replaces old version |
| `REFINED_BY` | base rule refined by carrier SOP |
| `EFFECTIVE_FROM` | rule version → effective date |
| `CITES` | KG node → regulation document span (provenance) |
| `REQUIRES` | report template → field requirement |
| `APPLIES_TO` | rule → entity scope (e.g., `COLCodeRule[WH]` APPLIES_TO `HO-3`) |
| `OVERRIDES` | bulletin override → base rule it modifies |
| `DEPENDS_ON` | rule references another rule |

#### How RHS reads from LHS at runtime

All via the materialized tables in Snowflake — no direct Neo4j calls from the data path:

- **Bridge agent prompts** assembled from `gre_materialized_rules` (and `gre_materialized_templates`); response cites the node versions used (`"classified WH per COLCodeRule[WH]@v1.2.4 citing THSP_2024 §3.2"`).
- **Edit checks** in dbt are generated from `gre_materialized_rules` rows whose type is `FieldRequirement` (a small `dbt-gre` macro library reads the table and emits SQL).
- **Gold aggregation templates** read from `gre_materialized_templates`; the transmittal builder walks `REQUIRES` relationships (materialized as a join table) to assemble fields.
- **HITL routing** reads from `gre_materialized_triggers`; new triggers added by editing the KG and re-materializing — no code change.
- **Edition pinning** uses the `effective_from`/`effective_to` columns on materialized rows, computed by Cypher temporal query at materialization time.

#### How the KG is built and evolved (LHS)

- **Phase 1 (bootstrap)**: Sentinel agent ingests synthetic-but-realistic stat plan + HB 2067 documents → proposes the initial set of nodes/relationships → admin approves in side-by-side UI → committed to Neo4j as `v1` → first materialization runs.
- **Phase 4 (evolution)**: synthetic bulletins or admin manual edits → Sentinel proposes diffs → admin approves → versions bump in Neo4j → re-materialize → in-flight RHS records re-evaluate against new rules.
- Every node has a `CITES` relationship to a `RegulationDocument` node carrying `char_start`/`char_end`. Side-by-side UI surfaces this.

#### Side-by-side UI (extends `mock-ui-v2/ontology.html`)

Left pane: regulation text with extraction spans highlighted. Right pane: extracted/proposed KG nodes & edges, **rendered as a live graph view** (using `neovis.js` or similar against Neo4j), with citation chips linking back to spans. Uncited spans are flagged as coverage gaps. Admin can accept, edit citations, add missed nodes, reject. Approval commits versioned KG nodes to Neo4j → triggers materialization.

The completeness check is the **uncited-spans indicator**: every non-trivial regulation paragraph should produce at least one node, or be explicitly marked non-substantive.

The live graph rendering is a real demo moment — compliance folks see a *graph*, not a table pretending to be a graph.

### The nine replaceable seams (ports), organized by side

Every external dependency sits behind a `Protocol` interface. Synthetic adapter today, real-data adapter later, swap by config — no business-logic changes.

#### LHS ports (regulatory side)

| Port | POC adapter | Future adapter |
|---|---|---|
| `RegulationDocumentAdapter` | `SyntheticRegulationAdapter` (markdown stat plan + HB 2067 + bulletins) | `TDISourceAdapter` (TDI/TICO publication scraper) |
| `BulletinSourceAdapter` | `SyntheticBulletinAdapter` (markdown bulletin files) | `TDIBulletinFeedAdapter` |
| `GREStore` | `Neo4jGREAdapter` (native KG) | Same in production; possibly multi-tenant managed Neo4j |

`RegulationDocumentAdapter` ingests *full* sources (used to seed/enrich the KG). `BulletinSourceAdapter` ingests *change events* (used to evolve the KG). Both feed the Sentinel agent. Could collapse into one port later.

#### RHS ports (source-system side)

The three source adapters are split because real carriers integrate them differently — PolicyCenter and ClaimCenter are usually one Guidewire stack, but notices/declinations often come from a separate underwriting system. Splitting now means each can swap independently later, and accommodates future RHS sources (Workday GL, additional carriers, additional LOBs).

| Port | POC adapter | Future adapter |
|---|---|---|
| `PolicySourceAdapter` | `SyntheticPolicyAdapter` (reads JSON from disk) | `PolicyCenterCDAAdapter` |
| `ClaimSourceAdapter` | `SyntheticClaimAdapter` (reads JSON from disk) | `ClaimCenterCDAAdapter` |
| `NoticeSourceAdapter` | `SyntheticNoticeAdapter` (HB 2067 notice extract files) | `UnderwritingSystemAdapter` (carrier-specific) |
| `TransmittalSinkAdapter` | `DiskTransmittalAdapter` (writes file) | `ISOVeriskPortalAdapter` / `SFTPAdapter` |

#### Shared ports (used on both sides)

| Port | POC adapter | Future adapter |
|---|---|---|
| `LLMPort` | `ClaudeAPIAdapter` | Same in production. Future: `BedrockClaudeAdapter` if compliance demands AWS |
| `HITLNotifier` | `ConsoleNotifier` (stdout) | `EmailNotifier`, `SlackNotifier`, `TeamsNotifier` |

**Architectural rule**: `core/` and `pipeline/` import `ports/` only — never `adapters/` directly. Adapters are wired in at startup via a small `Container` (dependency injection). Swapping synthetic for real source systems is one line in the wiring code.

### Repo layout (organized by side)

```
regulAI/
├── docs/
│   └── poc-decisions.md                # this doc
├── references/                         # existing — confidential PDFs
├── mock-ui-v2/                         # existing design artifact
│
├── synthetic_data/                     # RHS seeds
│   ├── policy/                         # synthetic Guidewire CDA policies
│   ├── claim/                          # synthetic ClaimCenter claims
│   ├── notice/                         # synthetic HB 2067 notice extracts
│   └── samples/                        # committed JSON for reproducibility
│
├── synthetic_regulations/              # LHS seeds
│   ├── tico_residential_plan.md        # synthetic-but-realistic stat plan
│   ├── hb_2067.md                      # synthetic statute text
│   └── bulletins/                      # synthetic TDI bulletins
│
├── reference_data/                     # seed CSVs (TICO codes, territories...)
│
├── dbt/                                # RHS transformations
│   ├── models/{bronze,silver,gold}/
│   ├── seeds/
│   ├── tests/
│   └── dbt_project.yml
│
├── packages/
│   ├── core/                           # domain types — pure dataclasses, no IO
│   ├── ports/                          # Protocol classes — the interfaces
│   │   ├── lhs/                        # RegulationDocumentAdapter, BulletinSourceAdapter, GREStore
│   │   ├── rhs/                        # PolicySourceAdapter, ClaimSourceAdapter, NoticeSourceAdapter, TransmittalSinkAdapter
│   │   └── shared/                     # LLMPort, HITLNotifier
│   ├── adapters/
│   │   ├── lhs/
│   │   │   ├── regulation/             # SyntheticRegulationAdapter
│   │   │   ├── bulletin/               # SyntheticBulletinAdapter
│   │   │   └── gre/                    # Neo4jGREAdapter
│   │   ├── rhs/
│   │   │   ├── policy/                 # SyntheticPolicyAdapter
│   │   │   ├── claim/                  # SyntheticClaimAdapter
│   │   │   ├── notice/                 # SyntheticNoticeAdapter
│   │   │   └── transmittal/            # DiskTransmittalAdapter
│   │   └── shared/
│   │       ├── llm/                    # ClaudeAPIAdapter
│   │       └── notifier/               # ConsoleNotifier
│   ├── lhs/                            # LHS application logic
│   │   ├── sentinel/                   # Sentinel agent (regulation extraction)
│   │   ├── kg/                         # KG ops (Cypher queries, node/edge construction)
│   │   ├── extraction/                 # SentinelExtraction schema, citation logic
│   │   └── materialization/            # Cypher → Snowflake materialization job
│   ├── rhs/                            # RHS application logic
│   │   ├── bridge/                     # Bridge agent (record classifier)
│   │   ├── pipeline/                   # ingest → bronze → silver → bridge → hitl → gold → transmit
│   │   └── transmittal/                # TICO file builder (high fidelity)
│   └── contract/                       # types shared across the contract (KG read models)
│
├── api/                                # FastAPI
│   ├── lhs/                            # /regulations, /kg, /sentinel/review
│   └── rhs/                            # /hitl/queue, /hitl/decide, /transmittals
├── ui/                                 # extends mock-ui-v2 with live data fetch
│   ├── ontology.html                   # LHS side-by-side regulation ↔ KG
│   └── review.html                     # RHS HITL queue + record review
├── tests/
├── pyproject.toml
├── Makefile
└── README.md
```

The LHS/RHS split lives in the directory structure so it's impossible to accidentally couple sides. The only coupling point is `packages/contract/` (types shared across the boundary) plus the materialization job that writes from LHS to a place RHS can read.

---

## Build phases

Four phases, each independently demoable. Sequencing protects against "we built half of everything and have nothing to show."

### Phase 1: Skeleton + KG bootstrap (4–5 days, was 1–2)
- Repo scaffold: pyproject, Makefile, packages/ tree organized LHS/RHS, dbt project
- Nine ports defined (Protocol classes), organized LHS/RHS/shared; minimal adapters
- **Neo4j wiring**: connection, constraints, indexes, basic Cypher operations module
- **Closed-vocabulary node + edge types** defined as Pydantic models in `packages/core/`
- **Materialization job scaffold**: Cypher → Snowflake `gre_materialized_*` tables
- **KG bootstrap (LHS)**: Sentinel agent ingests synthetic-but-realistic TICO stat plan + HB 2067 statute → proposes initial node set → committed to Neo4j as v1 (admin approval can be a stub for Phase 1; full side-by-side UI lands in Phase 4) → first materialization run
- **One trivial scenario (RHS)** through Bronze → Silver → Gold → disk, where Silver edit checks **read at least one rule from `gre_materialized_rules`** (proves the LHS→RHS contract path works end-to-end)
- **Demoable as**: "the LHS-RHS architecture works AND rules already come from the graph"
- **Exit criterion**: `make all` produces a trivial TICO transmittal; Neo4j Browser shows the seeded regulatory canon; `gre_materialized_rules` reflects it; at least one Silver edit check derived from a materialized `FieldRequirement` node

### Phase 2: High-fidelity transmittal + scenarios (RHS-heavy, 3–5 days)
- All 8–10 synthetic RHS scenarios generated and committed
- Real TICO Texas Residential Stat Plan field-by-field for **Premium + Loss + Notice** reports. Notice Count is lowest priority.
- **Gold `ReportTemplate` nodes in KG** define each report's required fields; LHS materialization writes them to `gre_materialized_templates`; RHS transmittal builder walks `REQUIRES` relationships (in materialized form) to assemble output. The transmittal carries the template version it built against.
- Reference data seeded as LHS KG nodes (`COLCodeRule`, `TerritoryRule`, `NoticeReasonCode`) — visible to RHS via materialization.
- Edit checks → `MR_QUEUE`, generated from materialized `FieldRequirement` rows.
- **Demoable as**: "the output would pass TICO, and every field traces back through the KG to a regulation citation"
- **Exit criterion**: a compliance person could diff Premium, Loss, and Notice transmittals against the published spec without finding wrong/missing fields. Premium presence is non-negotiable. Every transmittal field has a citation chain through the KG to a regulation document span.

### Phase 3: Record-level loop — Bridge agent + RHS HITL UI (3–5 days)
- Bridge classifier (Claude API) on WH/WN, novel form, HB 2067 reason
- **Bridge prompts assembled from KG**: relevant `COLCodeRule`, `CarrierSOP`, `TerritoryRule` nodes pulled per record (via materialized rules + on-demand Cypher for full-detail SOPs); agent's response cites the node versions it relied on
- Confidence threshold; ambiguous → `MR_QUEUE` with agent draft + KG citations attached
- RHS HITL routing rules read from materialized `HITLTriggerRule` rows (the 8 trigger types)
- FastAPI endpoints: `GET /hitl/queue`, `GET /hitl/case/:id`, `POST /hitl/decide` (RHS surface)
- Extended `mock-ui-v2/review.html` page showing the cited KG nodes alongside the record
- `HITL_AUDIT_LOG` writes including the KG node versions the decision was made against (so future re-eval is meaningful)
- **Demoable as**: "the agent does the boring work, humans handle the judgment, every decision traces to a regulation"
- **Exit criterion**: the anchor record routes to RHS HITL with a defensible agent draft citing specific KG nodes; a human approves; decision is auditable and KG-version-pinned

### Phase 4: Rules-level loop — LHS Sentinel evolution + side-by-side UI (5–7 days)
- Synthetic TDI bulletin → Sentinel agent → **`SentinelExtraction`** with proposed KG node/relationship diffs + per-extraction citations + uncited spans
- **Side-by-side LHS review UI** extending `mock-ui-v2/ontology.html`:
  - Left pane: regulation text with extraction spans highlighted
  - Right pane: live Neo4j graph view (via `neovis.js`) of proposed nodes/relationships, with citation chips linking to spans
  - Uncited spans flagged as coverage gaps
  - Admin can accept, edit, add missed nodes, reject; commits versioned KG diffs to Neo4j
- Approval writes new node versions + `SUPERSEDES` relationships in Neo4j → triggers re-materialization → RHS reads new rules
- In-flight RHS records re-evaluated under new KG; previously-auto-tagged records now routing to RHS HITL is the demo moment
- **Adapter for admin manual edits** — same UI/approval flow can be initiated by admin without a new document, for corrections or additions
- **Demoable as**: "the system reads the regulation, shows you what it found, lets you confirm completeness, and adapts the entire pipeline accordingly"
- **Exit criterion**: bulletin lands → side-by-side UI shows extracted nodes with citations and any coverage gaps → admin approves → KG version-bumps in Neo4j → re-materialization → an in-flight RHS record's classification changes (or routes to HITL) under the new rules, with provenance through the KG to the bulletin span

**Total**: ~15–22 working days for a solo dev, assuming source-of-truth docs are in hand. Native Neo4j adds ~1 day vs. Snowflake-tables-as-KG, but unlocks the live graph viz and removes the "fake graph in SQL" tax.

---

## Open questions

### Must resolve before serious coding
- [ ] **Source-of-truth docs** — do we have, or can we obtain:
  - TICO Texas Residential Statistical Plan (the actual filing spec) — **biggest blocker**
  - HB 2067 implementation guidance from TDI
  - Guidewire CIM / CDA reference (official, or public samples)
  - TX HO-3 form text (ISO HO 00 03 + TX amendments)
- [ ] **Synthetic bulletin format** — what does a "TDI bulletin" look like as input? (PDF, markdown, structured JSON?) Affects Sentinel agent prompt design. Likely answer: markdown for POC, with a real-PDF stretch goal.

### Resolved (moved from open questions)
- ✅ **Transformations**: dbt-core (RHS)
- ✅ **Orchestration**: Makefile + Python entry scripts; defer real orchestrator
- ✅ **UI stack**: extend `mock-ui-v2/` static HTML with FastAPI endpoints
- ✅ **GRE in POC**: native **Neo4j** behind `GREStore` port; materialized into Snowflake (`gre_materialized_rules` / `_templates` / `_triggers`) for dbt to read.
- ✅ **Architecture pattern**: modular monolith, ports & adapters, organized LHS/RHS/shared in the directory tree.
- ✅ **LHS = RHS framing**: regulation side produces KG (the contract); source-system side reads from KG; HITL on both sides with different UIs and different humans.
- ✅ **KG positioning**: third differentiator alongside the two agentic+HITL loops; KG is the regulatory canon, seeded in Phase 1, read by every RHS component (via materialization).
- ✅ **KG schema**: closed vocabulary, ~12 starter node types, 8 starter relationship types; agent proposes within this schema. Schema extensions are out of POC scope.
- ✅ **Coverage check mechanism**: Sentinel self-reports cited spans; uncited spans flagged in side-by-side UI; admin marks substantive vs non-substantive. Second-pass coverage agent deferred.

### Open scope questions
- [ ] How many TICO report types at full fidelity? Currently leaning **all four high fidelity** — Notice report is the most differentiated (HB 2067 hook) so prioritize there if forced to choose.
- [ ] Edition pinning rule — exact pin date is policy effective date? Or claim loss date for claims? Different stat plans handle this differently; need to confirm against TICO plan.
- [ ] How are agent confidence thresholds set? Hardcoded for POC, or surfaced as configurable in UI?

### Open questions still to resolve
- [ ] **Neo4j hosting for POC**: AuraDB Free (managed, may pause on inactivity) vs Neo4j Community in Docker (offline-capable, requires `docker compose up`). Both work — pick when scaffolding.
- [ ] **Live graph viz library** for the side-by-side UI right pane: `neovis.js` (lightweight, free) vs Neo4j Bloom (heavier, polished, may need license).
- [ ] **dbt-gre macro shape**: how exactly do dbt models reference materialized rules? Probably a Jinja macro `{{ gre_field_requirements(report='Notice') }}` that emits the WHERE clauses. Tactical — defer to Phase 2.

### Deliberately deferred (not in POC)
- GL / Workday reconciliation (would be a future RHS source)
- Real ISO-Verisk Portal submission (we'll write the file but not transmit)
- Schema-extension HITL (admin proposing new node types) — POC schema is closed
- Full HITL Genie 7-section workspace (one or two surfaces is enough)
- Multi-carrier multi-tenancy (single carrier in POC)
- Auto / WC / commercial lines (single LOB in POC)
- Bloom-quality KG visualizations (`neovis.js` is enough)

---

## Acceptable cuts if we run out of time
In rough order of what to drop first:
1. Stretch scenario #10 (bulletin re-evaluation) — keep the rules-level loop but skip the record-by-record re-eval
2. Some of the 10 scenarios — protect anchor record, edition boundary, declination, and re-eval
3. UI polish — terminal output is acceptable for the agentic flow if needed
4. Side-by-side UI second-pass coverage agent — keep self-reported uncited spans + manual marking
5. **Notice Count** Gold report — protect Premium + Loss + Notice as the three core reports (Premium is the exposure denominator and signals "real statistical filing," not a compliance extract)
6. Sentinel agent's bulletin evolution flow — keep KG bootstrap in Phase 1 even if we don't get the full evolution loop

**Do not cut**: KG-as-spine (the Phase 1 bootstrap is non-negotiable), Bridge agent reading from KG, HITL routing on at least one scenario, real-format TICO transmittal, edition pinning concept, citation provenance on at least the Notice report, **Premium + Loss + Notice reports** (all three).

---

## Build status snapshot — 2026-04-26

LHS wire-format layer is operational. The KG is the executable contract for every TICO-prescribed report, not just a description of one.

**What's working end-to-end:**

| Capability | Command | Result |
|---|---|---|
| Reproducible rebuild from disk artifacts | `make rebuild-kg` | wipes Neo4j, replays all extractions, runs parser, cleans up — ~30s, no LLM tokens |
| Coverage check | `make validate-kg` | PASS: 6 RecordLayouts × 200/200 columns, no overlaps, no orphans |
| Sample-record generation | `make generate-sample` | 200-char Premium record produced from KG |
| Submission validation | `make validate-sample` | per-column errors with KG-traced detail |
| Pixel-perfect highlight provenance | `make compute-rects` | PyMuPDF rects on every CITES edge |
| Side-by-side review UI | `make ui` | PDF + entity cards + Wire Format Studio (3-pane cross-linking) |

**The six fully-covered layouts** (each at 200/200 column coverage):

| Layout | Source | Fields | Codes |
|---|---|---|---|
| Premium Record Layout | Stat Plan §C | 71 | 301 |
| Loss Record Layout | Stat Plan §D | 59 | 244 |
| Notice Record Layout | Stat Plan §E | 13 | 53 |
| Notice Count Record Layout | Stat Plan §G | 9 | 19 |
| Homeowners Premium Record Layout | TICO HO record-layout PDF | 52 | 244 |
| Homeowners Loss Record Layout | TICO HO record-layout PDF | 45 | 146 |

**Architectural shift validated**: deterministic parser owns tabular content; Sentinel LLM owns prose. Tested with the round-trip generator → validator. The KG's own output validates against itself with the same KG facts. Pre-split: 138 orphan fields, 0 layouts complete. Post-split: 0 orphans, 6 layouts complete.

**Known cosmetic parser nits** (architecture sound; data needs scrubbing): code abbreviations like `1-9` are stored as a single code rather than expanded; footnote markers like `*1`, `**7`, `7*` cause spurious validator errors on round-trip. ~30 LOC fix in `scripts/parse_record_layout.py`.

**LHS work still open** (per `docs/lhs-build-plan.md`):
- LHS-4: live-graph rendering in side-by-side UI (`neovis.js`); current UI shows cards
- LHS-4: synthetic bulletin re-evaluation flow (versions + `SUPERSEDES`)
- LHS-4: Snowflake materialization sink (deliberately deferred until RHS begins)

---

## Decision log
- **2026-04-25** — initial scope locked from "End to End Simple Use case" doc: TX HO + TICO + Bronze/Silver/Gold
- **2026-04-25** — expanded to two-loop differentiator (record + rules)
- **2026-04-25** — fidelity bar set: high-where-it-matters
- **2026-04-25** — Snowflake + Claude API direct (rejected Cortex LLM functions)
- **2026-04-25** — synthetic data over real Guidewire access
- **2026-04-25** — architecture: modular monolith with ports & adapters; rejected microservices for POC scale
- **2026-04-25** — stack locked: Python+uv, dbt-core, FastAPI, extend mock-ui-v2, Makefile orchestration, Anthropic SDK direct
- **2026-04-25** — six replaceable seams defined: SourceAdapter, BulletinSourceAdapter, TransmittalSinkAdapter, LLMPort, GREStore, HITLNotifier
- **2026-04-25** — 4-phase build plan: skeleton → high-fidelity transmittal → record-level loop → rules-level loop
- **2026-04-25** — Premium report priority corrected: Premium + Loss + Notice are the three protected reports; Notice Count drops first. Premium is the exposure denominator that makes the demo look like a true statistical filing rather than a standalone compliance extract.
- **2026-04-25** — Anchor record concept adopted from source-of-truth doc: one HO-3 carrying both the wind/hail claim AND the HB 2067 nonrenewal (same policy) is the Phase 2 demo headliner — touches all four reports with fewest moving parts. Other 8 scenarios layer edge cases on top.
- **2026-04-25** — Source ports split into three (Policy / Claim / Notice) instead of one combined `SourceAdapter`, mirroring how real carriers integrate these (PC + CC usually one Guidewire stack; notices often a separate underwriting system).
- **2026-04-25** — Source-doc gap pass: added explicit monthly filing cadence; called out `TX_REF_CLASS_CODES_B` (Bronze) and `TX_CLASSIFICATION_S` (Silver) by name; clarified `TX_CLASSIFICATION_S` is where the TX overlay (ZIP→County→Territory→Classification) lives; documented that `TX_HO_NOTICE_COUNT_G` is reconciliation against `TX_HO_NOTICE_STAT_G`, not just a count — mismatches fail to MR_QUEUE.
- **2026-04-25** — **KG promoted to core differentiator** (third, alongside the two agentic+HITL loops). Architecture reframed: KG is the regulatory canon, seeded in Phase 1, read by every downstream component (dbt edit checks, Bridge prompts, Gold templates, HITL trigger rules). Added 9th port (`RegulationDocumentAdapter`). Defined closed-vocabulary schema: 12 starter node types, 8 starter edge types.
- **2026-04-25** — **LHS = RHS framing adopted** as the lead architectural picture. LHS = regulation side (Sentinel + KG + admin HITL); RHS = source-system side (Bridge + medallion + reviewer HITL); the KG is the contract between them. Two different HITL surfaces, two different humans. Repo organized LHS/RHS/shared in directory tree. Guidewire is one example of an RHS source — architecture accommodates multiple source systems on RHS (notice feed already separate; future: Workday, other carriers, other LOBs).
- **2026-04-25** — **Neo4j chosen for KG storage** (replacing prior Snowflake-tables-as-KG decision). Native graph operations, Cypher queries, live viz in side-by-side UI. RHS reads from KG via a small materialization job: Cypher → `gre_materialized_rules`/`_templates`/`_triggers` in Snowflake → dbt and edit checks read clean SQL. Neo4j is source of truth; Snowflake materialization is cache. Total POC budget: 15–22 days (was 14–21).
- **2026-04-26** — **PyMuPDF rect-based citation highlighting**. Replaced fragile frontend text-layer fuzzy search (multi-strategy regex against PDF.js spans) with PyMuPDF `search_for` at extract time. Each citation gets a list of `{page, x0, y0, x1, y1}` rectangles in PDF points; persisted on the CITES relationship as `rects_json` so the KG is self-contained for highlight provenance. Frontend overlays scale rect coords by the displayed page width to be robust to CSS shrinking. Files: `packages/lhs/citations/pdf_highlight.py`, `packages/core/relationships.py:CitesRelationship.rects_json`. Located rate: 93–95% of citations across all PDFs; remainder are markdown-header artifacts that don't exist in the source PDF.
- **2026-04-26** — **Idempotent `materialize()`**. `Neo4jGREAdapter.create_relationship` switched from `CREATE` to `MERGE` keyed on `(src, dst, char_start, char_end)` for CITES and `(src, dst, type)` for the rest. Re-running the parser/extract flow no longer accumulates duplicate edges. `id` excluded from props on match so original edge ids stay stable across re-runs.
- **2026-04-26** — **Deterministic parser for tabular wire-format PDFs** (`scripts/parse_record_layout.py`). Replaces LLM extraction for Stat Plan Sections C/D/E/G and the TICO Homeowners record-layout PDF. Uses PyMuPDF + a state machine that reads column-position headers (`1 (SP)`, `5–6 (RT)`), field names, and code/description pairs. Handles en-dash and hyphen separators (different PDFs use different conventions), filters page-number noise context-aware (only before first field-header per page), splits sub-fields like ACDT→MONTH/YEAR, and gap-fills implicit SKIP columns so cols 1..200 are always accounted for. Multi-target driver writes one extraction.json + rects.json per registry slug (matches existing tico-section-c/d/e/g and tico-record-layout-homeowners) and runs through the same `materialize()` pipeline as Sentinel output (dedup by name, citation snapshots, etc.).
- **2026-04-26** — **`make rebuild-kg`** — single command that wipes Neo4j, runs migrations, seeds the canon, replays all cached LLM extractions for prose docs, runs the deterministic parser for tabular ones, then runs `cleanup_kg.py`. Fully reproducible from disk; no LLM calls. Used to validate that `materialize()` is idempotent.
- **2026-04-26** — **Coverage validator** (`scripts/validate_kg_coverage.py`, `make validate-kg`). For each RecordLayout, walks FieldRequirement children and computes coverage of cols 1..200, lists overlap regions, lists orphans, lists fields with NULL position_start. Treats parent-with-sub-fields as expected (skips redundant overlaps). Exits non-zero if any populated layout has gaps or any orphans/null-pos. After parser runs, validator prints PASS for all 6 wire-format layouts. The validator IS the LHS contract completeness check.
- **2026-04-26** — **Sample-record generator + validator** (`scripts/generate_sample_submission.py`, `scripts/validate_submission.py`). The generator walks a RecordLayout from KG and emits a 200-character fixed-width line; code-list fields pick from CodeValue chain, free-form fields generate plausible values keyed off field name, SKIP fills with spaces. Validator does the inverse — column-by-column membership/format check. Round-trip test (generate → validate) is now the demo's "regulation is executable" moment AND a self-test for the KG: the KG's own output validates against itself when both scripts read the same facts.
- **2026-04-26** — **Wire Format Studio UI pane**. Third pane in `ui/regulations.html` that lights up when the user picks a record-layout doc (registry mapping in `api/registry.py:WIRE_LAYOUTS_FOR_SLUG`). Auto-generates a sample 200-char record on doc load; clicking a column cross-links to the matching FieldRequirement card (middle pane) AND the source PDF row (left pane). Paste-and-validate textarea with per-column error list, also clickable. Three-way provenance — prose ↔ KG node ↔ live byte — visible in one click. New API endpoints: `GET /api/layouts/{name}/sample`, `POST /api/layouts/{name}/validate`.
- **2026-04-26** — **Closed vocabulary boundary clarified**. Out of the 14 node types, FieldRequirement / RecordLayout / CodeList / CodeValue are now **parser-owned**; Sentinel LLM should not emit them (it produced phantom variants of the same layout under different LLM-named strings — "Cancellation, Nonrenewal, and Declination Notices Record Layout" vs "Cancellation/Nonrenewal/Declination Notice Record Layout" vs "Notice Record Layout" were three different nodes for the same concept). Followup task: tighten Sentinel prompt to forbid emitting these four types for documents whose slug is in `WIRE_LAYOUTS_FOR_SLUG`.

---

## RHS phase

- **2026-05-06** — **RHS vertical slice operational**. Snowflake medallion (Bronze → Silver → Gold) running end-to-end against synthetic Guidewire data. Reference schema generated from KG with full provenance. Validation engine running every rule from `REFERENCE.TSPR_VALIDATION_RULES`. Bulletin flow demonstrated end-to-end with KG version-bump + reference reload + flip-record validation. Six policies + four claims chosen to exercise distinct rules. See [`rhs-build-summary.md`](rhs-build-summary.md).
- **2026-05-15** — **Multi-filing scoping via non-contiguous `policy_id_ranges`**. The FILINGS registry was simple `(policy_id_min, policy_id_max)` until curated demo policies (POL-0001..0019) and bulk synthetic policies (POL-2100..2299) both needed to belong to the same filing. Switched to `policy_id_ranges: list[tuple[int,int]]`. `_scope_clause` emits `(id BETWEEN lo1 AND hi1 OR id BETWEEN lo2 AND hi2)` so curated + bulk both scope cleanly. Registry extracted to `packages/rhs/filings.py` so `api/rhs_demo.py` and `scripts/run_gold.py` import the same source.
- **2026-05-15** — **Cancellation cartesian fixed in Silver**. `SILVER.TSPR_CANCELLATION_STAGING` was producing 5,310 rows for 234 real cancellations because the Bronze→Silver INSERT joined on `GW_PC_ADDRESS.postalcode` (non-unique). Dropped the join entirely — `dw.zip` already carries the value from the same `POLICY_DETAILS` dict. Now 235 rows ≈ 1:1 with source jobs.
- **2026-05-15** — **`filing_batch_id` stamped on every Gold record**. Previous renderer used a ZIP-overlap heuristic to scope cancellation records to a filing (because Rule 34 aggregation lost the source policy). Added `FILING_BATCH_ID VARCHAR(64)` to the 3 Gold record tables; run_gold stamps it via a CASE expression built from `packages/rhs/filings.policy_id_to_filing_case()`. Per-filing record counts dropped from inflated 529/388/304 (cross-filing ZIP leak) to clean 443/209/107.
- **2026-05-15** — **Approval workflow with strict state machine**. `FILING_BATCH.status` transitions: `draft → resolving → validated → analyst_signed → actuary_approved → officer_approved → submitted → acked`. Each transition writes a `USER_ACTION` row; sealing is hard-gated on `status='officer_approved' AND open_blockers=0` (returns 409 otherwise). `_record_validation_run` no longer auto-promotes to `'approved'` on zero blockers — it sets `'validated'` and lets the human chain take over.
- **2026-05-15** — **ASCII renderer with SHA-256 seal**. `GET /api/rhs/filing/{id}/file` produces the actual fixed-width 200-column TSPR ASCII output (header + P-records + L-records + C-records + footer). `?persist=true` inserts a `FILING_SUBMISSION` row with the SHA-256 of the byte stream and advances state to `submitted`. The Wire Preview button in the workstation now shows real bytes scoped by `filing_batch_id`.
- **2026-05-15** — **Anomaly detector + `TSPR_ANOMALY_FLAGS`**. Three deterministic detectors: premium spike (ZIP total > 3σ from corpus mean), hail cluster (>3 Hail claims in same ZIP within 7 days), freeze-in-summer (`losscause='Freeze' AND MONTH(lossdate) IN (6..9)`). Surfaced as a popout on the Filing screen with a re-run button. Now part of `make run-pipeline`.
- **2026-05-15** — **Numbered, idempotent migrations**. `materialized/migrations/001..006` replayable via `make migrate-snowflake`. All use `CREATE TABLE IF NOT EXISTS` / `ALTER ADD COLUMN IF NOT EXISTS` / `WHERE NOT EXISTS` so re-runs are safe. Replaces ad-hoc SQL files previously scattered in `materialized/audit/` and `materialized/reference/`.
- **2026-05-15** — **`BRONZE_REGDOCS` schema for citation drill-down**. New schema with `RAW_REG_DOCUMENT` + `RAW_REG_SECTION` + `RAW_REG_CHANGE_LOG`. Loader ingests the TX Statistical Plan, HB 2067, the TICO record layout, and three synthetic TDI bulletins; splits into 426 indexed citation sections. The Regulation Explorer's "View regulator text →" button does a fuzzy citation match and shows the actual prose inline.
- **2026-05-15** — **Three-pane Regulation Explorer + KG neighborhood graph**. `/workstation` Regulations screen split into rule tree (300px) / rule detail + SQL + KG neighborhood graph (fluid) / per-rule violators + bronze sample (360px). KG neighborhood rendered via vis-network from `/api/rhs/kg/neighborhood/{rule_id}` returning nodes+edges from a Cypher 1-hop slice; color-coded by node label (Rule / Citation / Section / CodeValue / root).
- **2026-05-15** — **Bulletin → KG flip on the Filing screen**. The LHS bulletin re-evaluation flow now runs inline from `POST /bulletin/apply`: materializes the bulletin, regenerates the reference, **re-runs validation for every filing**, tags every newly-closed `FILING_EXCEPTION` with `resolution_action='bulletin'`, and returns per-filing deltas. UI shows a 6-second toast naming the recovered policies + flashes the affected kanban tickets green.
- **2026-05-15** — **A–G section badges + claim violations on the kanban**. Seven badges above the kanban mirror the TSPR record layout (A General, B Premium, C Premium recs, D Loss recs, E Cancellation, F Add'l cancel, G Actual counts). Click a badge to filter the kanban tickets to that section. Claim-side rules (B.11, B.14, D.12, D.13) render in the kanban with a sky-blue `claim` pill instead of a reason code; "Review claim →" routes to the Claims popout focused on the offending CLM-XXXX.
- **2026-05-15** — **Critical-path regression tests**. `tests/test_critical_paths.py` covers (1) audit reconciliation idempotency, (2) exception closure carries `resolution_action`, (3) approval chain rejects premature officer signoff (409), (4) approval chain rejects unknown role (400), (5) `/bronze/fix` actually mutates the Bronze row. All five pass; auto-skip when Snowflake unreachable.
- **2026-05-18** — **TICO ACK persistence + chain-of-custody closure**. `POST /filing/{id}/ack` synthesizes a `TICO-ACK-XXXXXXXX` receipt id, advances `FILING_BATCH.status → acked`, writes `acked_at` to `FILING_SUBMISSION`, records a `USER_ACTION` row with `action_type='regulator_ack'`. Surfaces as a "Simulate TICO ACK →" button on the sign-off rail's `submitted` step. Closes the regulation→KG→reference→pipeline→ASCII→submission→ACK loop. Real implementation would replace the synthetic button with an inbound webhook.
- **2026-05-18** — **D2: bridged 4 more executable rules (D.13, F.0, B.6, B.18)**. Total executable rules now 14 (was 10). Each has SQL predicate in migration 002, `FIX_SPEC` entry in the per-rule manual-fix editor, and a permanent injection in `generate_bronze_data.py` so the violation survives a Bronze regen. Pattern: each new rule = ~10 lines of SQL + ~10 lines of UI fix descriptor + a data-injection one-liner.
- **2026-05-18** — **Filing comparison view**. "Compare filings" popout on the Filing screen renders a three-column snapshot of all known filings (TPA / RES / CL): pass-rate cards on top, then six rows (records, ASCII bytes, rules run, fails, violations, anomalies) with the best value per row highlighted in green. Real-time recomputation per open; trend-over-time would require persisting `FILING_BATCH` snapshots.
- **2026-05-18** — **Dashboard "Active filings" list populated**. Previously the dashboard hardcoded only the TPA row and left a `<div data-bind="other-filings">` placeholder empty. Now renders one row per filing with stage label / progress bar / blocker tag / due-date countdown, all driven by the cached `app.filingCounts`. Clicking any row switches active context via the new `switch-filing` action and jumps to the Filing screen.
