# RegulAI

**The agentic regulatory workforce for U.S. P&C insurance.**

This repository contains the working artifacts of a design and architecture engagement for RegulAI — a B2B RegTech-as-a-Service platform that replaces the retiring manual compliance workforce at insurance carriers with a graph-native regulation engine, an agentic pipeline, and human specialists on standby for edge cases.

Two things live here:

1. **`research/`** — written analysis, architecture documents, ontology sketches, and an end-to-end worked example
2. **`mock-ui/`** — an interactive HTML/CSS mock of the product surfaces, designed to look like software a compliance officer would trust with a $20M filing

Nothing in this repository is production code. It exists to make the system concrete enough to pitch to investors, recruit the first SME, and align with a pilot carrier.

---

## Repository layout

```
regulAI/
├── README.md                                       ← you are here
│
├── research/
│   ├── RegulAI_Business_Plan_2026.pdf              Original source document (18 pages)
│   ├── RegulAI_Viability_And_Readiness.md          Viability assessment + investor/pilot/SME stress-test
│   ├── RegulAI_Technical_Architecture.md           N-to-1 schema architecture, CIOM, mapping DSL, onboarding playbook
│   ├── RegulAI_Ontology_Explained.md               What an ontology is and why RegulAI needs one
│   ├── RegulAI_Ontology_Slice_Coverage.md          Buildable slice: Coverage + Peril + CauseOfLoss
│   ├── RegulAI_End_To_End_Example.md               One loss event from Guidewire PAS to TICO filing
│   └── RegulAI_System_Architecture.md              5-plane architecture, mapping UI, HITL gates, multi-LLM reasoning
│
└── mock-ui/
    ├── index.html                                  Demo launcher
    ├── dashboard.html                              Surface 01 · Command Center
    ├── workbench.html                              Surface 02 · Mapping Workbench
    ├── review.html                                 Surface 03 · HITL Classification Review
    ├── pipeline.html                               Surface 04 · Pipeline Monitor
    ├── ontology.html                               Surface 05 · Ontology Explorer
    ├── filings.html                                Surface 06 · Filings & Submissions
    ├── styles/
    │   └── app.css                                 Single shared stylesheet
    └── scripts/
        ├── workbench.js                            Selection + tab behavior
        └── review.js                               Queue selection + candidate-code wiring
```

---

## The business context — one paragraph

Every U.S. P&C insurance carrier is legally required to file precise statistical data with state regulators (TICO in Texas, NAIC model plans elsewhere, NCCI for workers' comp). The humans who knew how to do this — stat coders, regulatory analysts, form experts — are retiring faster than they can be replaced; 400,000+ insurance professionals are projected to exit by 2026 against a 7–10 year apprenticeship curve. Policy administration systems (Guidewire, Duck Creek, Majesco) were designed for policy issuance, not regulatory reporting, so every quarter carriers spend weeks of manual work translating their raw operational data into the precise statistical codes the regulators demand. RegulAI owns that last mile as a managed service: Statistical Filing-as-a-Service (SFaaS).

The research documents in `research/` cover the problem, the technology approach, the ontology design, and a concrete end-to-end example of a single loss event flowing from a carrier's Guidewire tables to a TICO-compliant submission record.

---

## The mock UI — what it demonstrates

`mock-ui/` is a six-page interactive demo of the product. It is a static HTML mock — no build step, no framework, no backend. Open `index.html` in any modern browser.

### The six surfaces

| # | Surface | File | What it shows |
|---|---------|------|---------------|
| 01 | **Command Center** | `dashboard.html` | Executive filing-operations dashboard: Q1 2026 progress ribbon, 4 metric tiles with sparklines, 5-agent activity pulse, 8-event activity feed, HITL queue preview, carrier volume, 7×24 classification density heatmap |
| 02 | **Mapping Workbench** | `workbench.html` | Source-to-canonical mapping editor: Guidewire PolicyCenter schema tree (left), 16-row mapping table (center), rule detail with live preview + axiom checks (right) |
| 03 | **HITL Review** | `review.html` | Classification adjudication: 12-case queue (left), full case detail including adjuster narrative, Cortex/Auditor verdicts, 10 axiom checks, 3 candidate TICO codes (center), 7-hop lineage chain (right) |
| 04 | **Pipeline Monitor** | `pipeline.html` | Operational DAG monitor: 8-stage pipeline with live indicator on running stage, per-axiom progress, 10-run history table, failure post-mortem with resolution notes |
| 05 | **Ontology Explorer** | `ontology.html` | Knowledge Plane browser: concept tree (Regulatory / Canonical / Perils / Axioms / Doctrine) with 4,912 concepts, selected concept detail including properties, relationships, axioms, regulatory mappings, Cypher graph definition, version history |
| 06 | **Filings & Submissions** | `filings.html` | Outbound regulatory deliverables: 4 active filing cards, TICO Q1 per-carrier progress, cause-of-loss distribution, 10-row submission timeline, regulator connection health |

### Design language

The aesthetic is **editorial/regulatory** — think Bloomberg Terminal density with a legal brief's visual gravitas.

- **Color:** cream paper (`#F4F0E4`) + deep ink (`#141619`) + oxblood accent (`#7A2418`). Semantic statuses use forest green, dark amber, and crimson.
- **Typography:**
  - **Fraunces** (variable serif) for all display type, italicized for emphasis
  - **Geist** for UI chrome and body text
  - **JetBrains Mono** for data, codes, rule IDs, Cypher, and anywhere precision matters
- **Composition:** dense three-pane layouts for operational surfaces (workbench, review, ontology); full-width canvases for executive surfaces (dashboard, pipeline, filings). Thin rules as structural dividers. Tabular numbers everywhere financial data appears.

### Typography tiers (normalized)

Fraunces is tuned at exactly four tiers via variable-font `opsz` and `SOFT` axes. This was the inconsistency flagged during review and it has been reconciled across every page and every inline style:

| Tier | Size range | `opsz` | `SOFT` roman | `SOFT` italic | weight |
|------|-----------|--------|--------------|---------------|--------|
| Hero | 40–56 px | 96 | 20 | 75 | 350 |
| Display | 22–40 px | 36 | 30 | 65 | 400 |
| Title | 16–22 px | 20 | 40 | 60 | 400 |
| Small | 12–15 px | 14 | 50 | 65 | 400 |

Utility classes (`.fr-hero`, `.fr-display`, `.fr-title`, `.fr-small`) are defined in `styles/app.css` for future reuse. Italic emphasis always uses the accent oxblood color — this is the one visual motif that carries across every page.

### Data realism

Every piece of data on screen is domain-plausible:

- **Carriers:** ATIC (Acme Texas Insurance), TWC (Texas Western Casualty), NTP (NorthStar Texas Property), SRC (Southern Regional Carriers)
- **Forms:** HO-3, HO-5, DP-3, ISO HO 00 03, HO 15 (extended replacement cost), HO 04 90 (perils broadened)
- **Regulatory codes:** real TICO residential Cause-of-Loss codes (01 Fire, 03 Wind/Hail, 14 Accidental Discharge of Water, 15 Freezing of Plumbing, 21 Flood), with TCLSP section citations
- **Source schemas:** Guidewire PolicyCenter table names (pc_policy, pc_coverage, pc_policylocation, cc_claim, cc_incident, cc_exposure, cc_transaction)
- **Case law:** *Lundstrom v. United Services Auto Ass'n, 192 S.W.3d 78* referenced for Texas efficient proximate cause
- **Agent architecture:** Cortex (Claude Opus 4.7) as Proposer, Auditor (GPT-5) as Critic, following the Proposer-Critic-Arbiter pattern documented in `research/RegulAI_System_Architecture.md`
- **Pipeline:** Dagster-orchestrated 8-stage DAG matching the architecture document's stage taxonomy

---

## Running the mock

The mock is static HTML — no installation required. Two options:

**Option A — Double-click**
Open `mock-ui/index.html` directly in a browser. Works, but some browsers block Google Fonts on `file://` origins. If text looks fallback-rendered, use Option B.

**Option B — Local server** *(recommended)*
```bash
cd mock-ui
python3 -m http.server 8734
# then open http://localhost:8734
```

The demo is designed for 1440px+ viewports. On a MacBook 13″ it works but is dense; on a 27″ external monitor it sings.

---

## Interactivity in the mock

Minimal JS, intentionally. The mock is a design artifact, not a prototype. Working interactions:

- **Workbench:** mapping rows are selectable (visual echo). Tabs in the rule panel switch state. Segmented view controls toggle.
- **Review:** queue items are selectable. Candidate-code selection updates the Approve button label. Action buttons present but not wired to a backend.
- **Ontology:** concept rows in the left tree are selectable.
- **Dashboard:** the 7×24 heatmap is generated in JavaScript with a realistic weekday/weekend Cortex-activity pattern.
- **All pages:** rail navigation icons are working links.

Live interactions that would exist in a real build but are stubbed here: schema-tree expand/collapse drilldown, mapping-edit modal, approve workflow, search bar, filter popovers, time-range selector on the heatmap, DAG stage drill-down.

---

## What this repository is, and is not

**Is:**
- A design record of a serious product concept that could become a real company
- A concrete enough representation for investor meetings, SME recruiting, and pilot conversations
- A documented architectural opinion about how to build agentic compliance software

**Is not:**
- Production code
- A functioning pipeline (no Snowflake, no Neo4j, no real carrier data)
- A committed product roadmap

The distance from what's here to a working pilot is roughly 9 months with a qualified founding team of 4–5, assuming $1.5–2.5M seed funding — budgeted in `research/RegulAI_Viability_And_Readiness.md`.

---

## Contact

Internal working document. Not for external distribution without owner's permission.
