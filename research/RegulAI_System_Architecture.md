# RegulAI — System Architecture: Pipeline, Mapping UI, Agents, HITL, and Reasoning

This document responds to a design discussion about how the end-to-end system should be built:

> "How can we use data pipeline... can we build ETL layer with UI for mapping, then pipeline goes through Agents... HITL review, filing, ERP... where HITL is applicable. The agents should have reasoning, probably couple of different LLMs to question one against each other."

It takes those instincts, validates the ones that survive contact with reality, refines the ones that need adjustment, and sketches a concrete architecture.

---

## 1. Which Instincts Survive

| Instinct                                               | Verdict  | Notes                                                                                 |
|--------------------------------------------------------|----------|---------------------------------------------------------------------------------------|
| ETL layer with a mapping UI                            | Keep     | Highest-leverage product surface. Gives SMEs direct control without code deploys.     |
| Pipeline goes through agents                           | Keep     | Right frame — but agents act at defined stages, not continuously.                     |
| HITL review where applicable                           | Keep     | HITL is a **gate**, not a station at every hop. Reserve it for judgment calls.        |
| ERP integration at the end                             | Keep     | Read-side only. Do not write back to carrier systems of record.                        |
| Agents should reason                                   | Keep     | Use reasoning models for classification and causation. Not for deterministic lookups. |
| Multiple LLMs questioning each other                   | Refine   | Naïve adversarial debate is expensive and often fake. Proposer-Critic pattern works.  |

---

## 2. The Five-Plane Architecture

The system has five separable planes that communicate through contracts:

```
┌─────────────────────────────────────────────────────────────────┐
│ HUMAN PLANE                                                      │
│  • Mapping Workbench (ETL UI)                                    │
│  • HITL Review Queues (by task type)                             │
│  • Ontology Governance (SME curation)                            │
│  • Filing Ops Dashboard                                          │
└─────────────────────────────────────────────────────────────────┘
                            ▲
                            │ reads/writes
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ AGENT PLANE                                                      │
│  • Cortex  (pre-validation, classification)                      │
│  • Bridge  (reconciliation, GL cross-check)                      │
│  • Sentinel (regulatory change detection)                        │
│  • Scout   (schema discovery, mapping proposals)                 │
│  • Auditor (critic pattern, challenges other agents)             │
└─────────────────────────────────────────────────────────────────┘
              ▲                                ▲
              │ queries                        │ orchestrates
              ▼                                ▼
┌───────────────────────────┐   ┌───────────────────────────────────┐
│ KNOWLEDGE PLANE (Neo4j)   │   │ DATA PLANE (Snowflake)            │
│  • Regulatory subgraph    │   │  • Bronze (raw, lineage-tagged)   │
│  • Canonical subgraph     │   │  • Silver (CIOM, axiom-validated) │
│  • Mapping subgraph       │   │  • Gold  (regulatory records)     │
│  • Axioms / inference     │   │  • Archive (immutable filing log) │
└───────────────────────────┘   └───────────────────────────────────┘
                            ▲
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ INTEGRATION PLANE                                                │
│  Inbound: Guidewire, Duck Creek, Majesco, Oracle GL, SAP, flat   │
│  Outbound: TICO, NAIC, NCCI, carrier exception queues            │
└─────────────────────────────────────────────────────────────────┘
```

**Critical design principle: the Knowledge Plane is the source of truth for semantics.** The UI edits it. The Agents read and write to it. The Data Plane transformations are compiled from it. No business logic lives outside the graph.

---

## 3. The Mapping Workbench (ETL UI)

The product surface that SMEs and carrier analysts live in. Four main workspaces.

### 3.1 Schema Explorer

- Left pane: carrier source schema — tables, columns, sample values, null rates, cardinalities. Crawled automatically by the **Scout** agent during onboarding.
- Right pane: the CIOM — concepts, properties, relationships, rendered as a browsable graph.
- Middle: search, faceted filters — "show me unmapped source fields," "show me CIOM concepts with no source data," "show me all fields that might represent premium."

### 3.2 Mapping Canvas

A visual canvas (think React Flow) where the mapping work actually happens:

- Drag a source field onto a canonical concept → creates a **candidate mapping**
- Scout pre-fills candidates with confidence scores derived from schema + sample analysis + LLM classification
- Inline transform editor: `Direct` | `Lookup(table)` | `Composite(expression)` | `SMEDefined(notes)`
- Live preview: run this mapping against sample rows → show what the CIOM object looks like
- Every saved mapping writes to Neo4j as a graph node with reviewer, timestamp, confidence, and status (`proposed` → `approved` → `deprecated`)

### 3.3 Validation Lab

- Pick a sample batch → run it through the pipeline with current mappings
- Show CIOM objects produced, axiom pass/fail results, regulatory records emitted
- Diff against prior runs to catch regressions
- Reviewer sign-off promotes mappings from `proposed` to `approved`

### 3.4 Diff & Approval Queue

- When **Sentinel** detects a regulatory change (e.g., new TICO bulletin) it proposes mapping edits
- Reviewer sees a side-by-side diff: "this is how a Texas freeze loss was coded under the old rule vs. the new one"
- Approved changes version the mapping; prior versions remain replayable for historical restatements

### 3.5 Non-Negotiable Implementation Rule

**The UI never writes Python, SQL, YAML, or configuration files. It writes graph mutations.** Any other approach splits the source of truth and destroys auditability. The dbt models, the Snowflake SQL, the agent prompts — all are *compiled* from the graph at runtime or at deploy, never hand-edited.

---

## 4. The Agentic Pipeline & HITL Gates

The pipeline is a DAG with HITL gates at specific judgment points, not at every step.

```
[Source PAS/GL]
      │
      ▼
(1) INGEST ──────────────────  [Bronze]       no HITL
      │                        pure pull + lineage tagging
      ▼
(2) MAP ─── Scout + mappings── [Silver CIOM]  HITL if:
      │                                       • new source field unmapped
      │                                       • mapping confidence < 0.85
      │                                       • axiom violation on object
      ▼
(3) CLASSIFY ── Cortex ──────  [enriched]     HITL if:
      │         (+ reasoning)                 • classification confidence < 0.90
      │                                       • ambiguous causation chain
      │                                       • novel coverage form
      ▼
(4) RECONCILE ── Bridge ─────  [reconciled]   HITL if:
      │                                       • GL variance > tolerance
      │                                       • Policy_ID match fails
      ▼
(5) TRANSFORM ── mappings ──── [Gold]         no HITL
      │                        pure rule application
      ▼
(6) VALIDATE ── Cortex ──────  [submission-   HITL on ANY failure
      │         axiom battery   ready]        (strict gate)
      ▼
(7) FILE ──────────────────── [Regulator]     no HITL
      │                        + immutable archive
      ▼
(8) ACKNOWLEDGE ────────────── [confirm/      HITL if rejection
                                reject]       + feedback to graph
```

### 4.1 Why HITL Is a Gate, Not a Station

HITL at every stage = humans babysitting data flow = you've built a services company.
HITL at specific judgment gates = humans make the 3% of calls axioms can't settle = economic leverage.

At steady state, the vast majority of records flow through without human touch. The HITL queue is where the value of retired experts gets captured — because each adjudication resolves into a new axiom or mapping edge in the graph, preventing the next similar case from needing human review. **The system gets smarter with every HITL event.** That compounding is the business model.

### 4.2 HITL Queue Design

HITL work is typed and routed:

- **Mapping Review queue** — ambiguous source→CIOM mappings (carrier SME + RegulAI specialist)
- **Classification Review queue** — ambiguous causation / cause-of-loss calls (RegulAI specialist)
- **Reconciliation queue** — variance investigations (carrier data team + RegulAI specialist)
- **Exception queue** — novel cases needing SOP extension (Head of Regulatory Science)
- **Rejection queue** — regulator-rejected filings requiring correction (RegulAI filing ops)

Each queue has SLA targets, audit trails, and feeds resolved cases back into the graph as versioned rule additions.

---

## 5. The Multi-LLM Reasoning Question

The intuition "have LLMs question each other" reaches for something real — robustness through disagreement. But naïve multi-model debate fails in practice because:

1. **Same-family models agree too much.** RLHF trains agreeableness. "Check this answer" almost always returns "looks right to me."
2. **Cost scales linearly.** Double inference, double latency, marginal accuracy gain.
3. **The important adversary is formal rules, not another LLM.** The axioms in the ontology are already the adversarial check.

### 5.1 What Actually Works: Proposer-Critic-Arbiter

```
Cortex (Proposer)     ──►  proposes: "CauseOfLoss = 15, confidence 0.92"
      │                         │
      │                         ▼
      │                ┌──────────────────┐
      │                │ Axiom Engine     │ ──► deterministic checks
      │                │ (Neo4j queries)  │     ✓ / ✗
      │                └──────────────────┘
      │                         │
      │                         ▼
      │                ┌──────────────────┐
Auditor (Critic) ◄────│ adversarial prompt│   DIFFERENT model family
 "find the flaw"      │ + different frame │   or DIFFERENT prompt frame
      │                └──────────────────┘   ("as TDI examiner",
      │                                        not "as code checker")
      ▼
Verdict:  agree      → proceed
          disagree   → route to HITL with both arguments presented
          axiom fail → hard fail, HITL with rule citation
```

### 5.2 Three Things That Make the Pattern Work

1. **The critic has a different frame.** Not "check this answer" (biases toward agreement) but "you are a TDI market-conduct examiner looking for the flaw in this classification; cite a specific rule if you find one."
2. **Use genuine model diversity.** Claude + GPT + one open-weight model. Their failure modes are uncorrelated enough to be useful. Claude + Claude is not diversity.
3. **Reserve the pattern for the middle band.** Confidence > 0.90 → ship. Confidence < 0.70 → straight to HITL. Confidence 0.70–0.90 → Proposer-Critic. This keeps compute cost bounded and focuses the expensive pattern where it adds the most value.

### 5.3 Reasoning Model Usage — Where and Where Not

| Task type                                  | Reasoning LLM? | Rationale                                              |
|--------------------------------------------|----------------|--------------------------------------------------------|
| Narrative → Causation chain                | Yes            | Genuine ambiguity; chain-of-thought helps              |
| Proximate-cause determination (edge cases) | Yes            | Legal doctrine application requires reasoning          |
| Ambiguous mapping candidate generation     | Yes            | Semantic judgment over schema                          |
| Direct field-to-field mapping              | No             | Deterministic, lookup-based                            |
| Axiom validation                           | No             | Boolean logic, runs as Cypher query                    |
| Code lookups (TICO, NAIC)                  | No             | Graph traversal, no interpretation needed              |
| Proposer-Critic on middle-confidence cases | Yes (both)     | The arbitration is the whole point                     |

---

## 6. ERP / Carrier Integration Boundaries

### 6.1 Inbound (Read)

- Connectors to PAS (Guidewire, Duck Creek, Majesco, Insurity, Sapiens, mainframe)
- Connectors to GL / ERP (Oracle, SAP, NetSuite) for reconciliation
- Standard options: Fivetran, Airbyte, Snowflake-native connectors, or custom CDC for legacy systems
- Scheduling: nightly for most; near-real-time for carriers that want it (at higher tier)

### 6.2 Outbound to Carrier Systems (Write)

- **To the carrier's PAS: almost never.** Carriers will refuse. Instead emit a **Data Quality Exception Queue** — a dashboard their data team reads, with concrete "fix this upstream" items tied to specific records. Delivers value without touching their system of record.
- **To the carrier's GL: never.** Read-only.

### 6.3 Outbound to Regulators

This is the last-mile that carriers pay for:

- TICO: SFTP with PGP-signed files per TCLSP schedule
- NAIC: Model Audit Rule filings, market conduct data calls
- NCCI: workers' comp statistical plan
- FLOIR, CDI, state DOIs: each with their own protocol

Each regulator is a separate connector module. Filing submissions are logged immutably in the Archive tier — regulators routinely ask to see 7-year-old submissions.

---

## 7. Tech Stack Sketch (Opinionated, Not Prescriptive)

| Layer               | Recommendation                                       | Why                                                      |
|---------------------|------------------------------------------------------|----------------------------------------------------------|
| Ontology & mappings | Neo4j (or Memgraph if open-source/speed matters)     | Graph-native; Cypher queries = axiom checks              |
| Data pipeline       | Snowflake + dbt (compiled from mapping graph)        | Serverless scale; SQL-native; ecosystem                   |
| Orchestration       | Dagster (or Prefect)                                 | Asset-centric DAG fits pipeline stages                   |
| Agent runtime       | LangGraph + structured output (Instructor / JSON)    | State machines; typed outputs; observability             |
| LLM providers       | Claude (primary) + GPT (critic) + small open model   | Real diversity; avoid single-vendor risk                 |
| Mapping UI          | Next.js + React Flow + TanStack Query                | Modern, visual canvas, fast iteration                    |
| HITL / ops UI       | Same Next.js app, different routes                   | One product, not three                                   |
| Ops metadata        | Postgres                                             | Standard                                                 |
| Filing archive      | Snowflake Iceberg tables (immutable, queryable)      | 7-year regulatory retention                              |
| Auth / multi-tenant | Auth0 or Okta + per-carrier Snowflake schema isolate | Carriers will audit your tenant-isolation story           |
| Observability       | Datadog or Grafana + OpenTelemetry                   | Agent runs, pipeline runs, HITL queue metrics            |

---

## 8. Build Order — The 90-Day Spine

With one engineer + Head of Regulatory Science post-funding:

| Days   | Focus                                                              | Deliverable                                                   |
|--------|--------------------------------------------------------------------|---------------------------------------------------------------|
| 1–20   | Ontology v0 in Neo4j (Coverage + Peril + CauseOfLoss slice)        | Hand-loaded graph. No UI yet. Axiom queries validated.         |
| 15–40  | Snowflake pipeline with hand-written mappings for one carrier      | End-to-end flow for ONE loss record, source → TICO file.      |
| 30–55  | Cortex v0 — narrative → CausationChain + axiom engine              | Proposer-Critic pattern built. Axiom battery running.         |
| 45–75  | **Mapping Workbench v0** — Schema Explorer + Mapping Canvas        | SMEs can author mappings without engineer involvement.        |
| 60–90  | HITL queue UI + Bridge agent v0 + first shadow run on pilot data   | End-to-end demo for first pilot carrier.                      |

The mapping workbench is deliberately **not first**. You need the graph, the axioms, and one hand-built pipeline working before building a UI to edit them — otherwise you're building an editor with nothing to edit. But the workbench is the product surface that unlocks scaling past the first carrier.

---

## 9. The One-Line Version

**A graph is the source of truth. A UI writes to the graph. A pipeline reads from the graph. Agents reason within guardrails defined by the graph. Humans resolve the cases the graph can't settle — and their resolutions go back into the graph.** Everything else is plumbing.
