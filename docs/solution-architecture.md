# RegulAI — Solution Architecture

**Last updated**: 2026-05-18
**Companion docs**: [`technical-architecture.md`](technical-architecture.md) (LHS-side, how it's built), [`rhs-build-summary.md`](rhs-build-summary.md) (RHS-side, the medallion pipeline + workflow + ASCII renderer), [`how-it-works.md`](how-it-works.md) (operational runbook), [`business-showcase.md`](business-showcase.md) (executive framing).
**Audience**: product owners, compliance stakeholders, sales/strategy reviewers, future technical leads onboarding.

---

## 1. The business problem

US property/casualty insurers must file periodic statistical reports to designated state agents (in Texas: TICO — Texas Insurance Checking Office). Each filing is a fixed-width data submission whose schema is dictated by the state's Statistical Plan and amended by legislation, bulletins, and regulator interpretations.

The work that goes into producing one of these filings has three persistent failure modes:

1. **The regulation is prose; the filing is bytes.** Today, compliance teams hand-translate "the statistical plan says column 5–6 carries Record Type from {05, 06, 91…}" into ETL code, edit checks, and reference tables — once, and then again every time the regulation changes. The translation is high-judgment, low-leverage, and undocumented.
2. **Source-system data is messy.** Carrier systems (Guidewire, etc.) capture facts in carrier-specific shapes that drift from regulator-required classifications. The most consequential drifts (e.g. Wind/Hail vs Named-Storm-Wind classification under HB 2067) are exactly where regulator scrutiny lands.
3. **Every classification, edit-check, and aggregate is a compliance artifact.** Auditors ask "why did you code this claim WH and not WN?" The answer needs to trace back to a specific clause in a specific dated edition of the Statistical Plan. Today the audit answer is "ask Carol; she remembers."

RegulAI's bet: **make the regulation an executable artifact** — a knowledge graph the rest of the pipeline reads from — and put a human at exactly the two judgment points where humans should be (regulation interpretation, ambiguous record classification), not at every step.

---

## 2. Solution intent — three differentiators

All three are load-bearing. None is optional. (See `docs/poc-decisions.md` for the decision history.)

### 2.1 Knowledge Graph as regulatory canon

A closed-vocabulary, citation-grounded, versioned KG (Neo4j) holds **the authoritative representation of what the regulation requires**:
- Every report's record layout, column-by-column.
- Every legal code value for every coded field.
- Every rule's effective date window and the bulletins that override it.
- A pixel-perfect rectangle on the source PDF that anchors every fact.

Every other component reads from the KG. Hard-coded regulatory rules anywhere else in the system are an antipattern. **This is the source-of-reporting-requirement claim** RegulAI is built on.

### 2.2 Rules-level agentic + HITL loop (LHS)

When a regulation changes — new bulletin, amendment, edition — Sentinel (the LHS agent) ingests it, proposes a graph diff (new nodes, `SUPERSEDES` edges, citation spans), and the compliance officer reviews the diff in a side-by-side UI: regulation text on the left, proposed KG changes on the right, with coverage-gap indicators for any prose Sentinel didn't extract from. Approval bumps versions; in-flight downstream content re-evaluates under the new rules.

This is *regulation change as a code review*, not a six-month re-implementation project.

### 2.3 Record-level agentic + HITL loop (RHS — future)

When source-system data flows in, the Bridge agent classifies each record (Wind/Hail vs Named-Storm-Wind, etc.), citing the specific KG node version it relied on. Confidence-thresholded ambiguous cases route to a record reviewer with the agent's draft pre-populated. The HITL queue is itself driven by `HITLTriggerRule` nodes in the KG — adding a new trigger is a graph edit, not code.

This is *the boring 95% automated, the judgment 5% routed to a human, every decision traceable*.

---

## 3. The lead picture: LHS = RHS

The system is two halves meeting at a contract:

```
       LHS                                          RHS
  ┌─────────────────────┐                ┌─────────────────────┐
  │ Regulation docs     │                │ Source systems      │
  │ (TICO Stat Plan,    │                │ (Guidewire PC + CC, │
  │  HB 2067, bulletins,│                │  notice/UW feed,    │
  │  TICO record-layout │                │  + future systems)  │
  │  PDFs)              │                │       ↓             │
  │       ↓             │                │   Bronze (raw)      │
  │   Sentinel LLM      │                │       ↓             │
  │       +             │                │   Silver (canonical │
  │   Deterministic     │                │   TX overlay)       │
  │   parser            │                │       ↓             │
  │       ↓             │                │   Gold (filing marts│
  │     KG (Neo4j)      │ ←── contract ─→│   templated from KG)│
  │       ↓             │                │       ↓             │
  │  side-by-side       │                │   TICO transmittal  │
  │  admin reviews +    │                │   file              │
  │  approves           │                │                     │
  └─────────────────────┘                └─────────────────────┘
   "what the regulation                    "what the system
    requires"                                produces"
```

- **LHS — regulatory demand side**: regulation docs → extraction (LLM for prose, parser for tabular) → Neo4j KG → admin approves diffs in side-by-side UI. **Built today.**
- **RHS — source-system supply side**: source-system data → Snowflake medallion → templated assembly → TICO transmittal. **Future work.**
- **The contract is the KG.** RHS reads the KG (today: directly via Neo4j; later: via a Snowflake materialization for dbt-friendly access).

Two HITL surfaces, two different humans:

| | LHS HITL | RHS HITL |
|---|---|---|
| Who | Compliance officer / regulatory analyst | Claim-data analyst / record reviewer |
| What they approve | Rule extractions, rule changes | Ambiguous record classifications |
| Cadence | Per regulation event (rare, high-stakes) | Per ambiguous record (frequent, lower stakes) |
| UI surface | `ui/regulations.html` | (RHS — future) |
| Built | yes | future |

---

## 4. Stakeholders / actors

| Actor | Role | Touchpoints |
|---|---|---|
| **Compliance officer** | Authoritative reviewer of regulation interpretations | Side-by-side UI; approves Sentinel/parser proposals; rejects/edits |
| **Compliance engineer** | Maintains the system, adds new regulation docs, owns the KG | All `make` workflows; Neo4j Browser; CLI scripts |
| **Statistical reviewer** | Reviews the produced filing before submission | Wire Format Studio (sample/validate); Gold reports (future) |
| **Auditor** | External; questions specific decisions years later | Provenance chain: filing field → KG node version → CITES edge → PDF rectangle |
| **Record reviewer** *(future)* | Approves ambiguous record classifications | RHS HITL queue (future) |
| **Carrier IT** *(future)* | Operates the source-system feed | Source adapters, RHS pipeline (future) |
| **Regulator** | TDI / TICO; receives filings | TICO transmittal file (future) |

The two judgment roles — **compliance officer** (interpreting the regulation) and **record reviewer** (classifying ambiguous records) — are the only places humans must intervene. Everything else is automated.

---

## 5. Solution capabilities

### 5.1 Built (LHS)

| Capability | Surface | Status |
|---|---|---|
| Browse regulation source PDFs side-by-side with KG entities | `make ui` | ✅ |
| Click a KG entity → highlight cited PDF region | UI (citation chips, rect overlays) | ✅ |
| Run LLM extraction on a regulation doc | `/api/regulations/{slug}/extract` (or `make batch-extract`) | ✅ |
| Approve / materialize an extraction into the KG | `/api/regulations/{slug}/approve` | ✅ |
| Run deterministic parser on tabular wire-format docs | `make parse-wire-layout` | ✅ |
| One-command reproducible KG rebuild from disk | `make rebuild-kg` | ✅ |
| Validate KG coverage (every wire-format byte accounted for) | `make validate-kg` | ✅ |
| Generate a TICO sample submission *from the KG* | `make generate-sample` | ✅ |
| Validate any 200-char submission against the KG | `make validate-sample` | ✅ |
| Wire Format Studio (interactive generate + validate in browser) | UI third pane | ✅ |
| Cross-pane click highlighting (column ↔ field card ↔ PDF row) | UI | ✅ |
| KG self-cleanup (drop phantoms / orphans) | `make cleanup-kg` | ✅ |

### 5.2 Open in LHS

| Capability | Status |
|---|---|
| Synthetic bulletin → diff → admin approval → version bump → re-evaluation of in-flight content | Schema ready (`BulletinOverride`, `SUPERSEDES`, `effective_from/to`); UI/diff flow is the LHS-4 headliner |
| `neovis.js` live-graph rendering in side-by-side UI | Optional polish; entity cards convey same provenance |

### 5.3 Future (RHS, Phases 2–4 per `docs/poc-decisions.md`)

| Capability | Phase |
|---|---|
| Synthetic Guidewire CDA-shaped data ingestion (Bronze) | RHS Phase 2 |
| Silver canonical entities with TX classification overlay (ZIP→County→Territory) | RHS Phase 2 |
| Gold filing marts templated from `ReportTemplate` KG nodes | RHS Phase 2 |
| TICO transmittal builder, would-pass-validation fidelity | RHS Phase 2 |
| Bridge agent (claim/policy/notice classifier) | RHS Phase 3 |
| Record-level HITL UI + audit log with KG version pins | RHS Phase 3 |
| Edit-check generation from materialized `FieldRequirement` rows | RHS Phase 2 |
| Snowflake materialization sink (Cypher → flat tables) | RHS Phase 2 |

---

## 6. Reference architecture

### 6.1 Component view (today)

```
┌─────────────────────────────────────────────────────────────────────┐
│                      USER (compliance officer / engineer)           │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                          Browser (HTTP, JSON)
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│  HTTP                                                                │
│  ui/regulations.html  ← static, ES modules, PDF.js                   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ FastAPI  api/main.py  :8765                                  │   │
│  │ /api/regulations*  /api/layouts*  /api/kg/stats              │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────┬──────────────────┬──────────────────┬─────────────────────┘
       │                  │                  │
       ▼                  ▼                  ▼
┌────────────┐    ┌────────────────┐    ┌──────────────────────────┐
│  Sentinel  │    │  Deterministic │    │ Materialize /            │
│  agent     │    │  parser        │    │ generate / validate /    │
│  (OpenAI)  │    │  (PyMuPDF +    │    │ rect computation         │
│            │    │   state mach.) │    │                          │
└─────┬──────┘    └────────┬───────┘    └────────┬─────────────────┘
      │                    │                     │
      └─────────┬──────────┴─────────────────────┘
                │ same materialize() pipeline
                ▼
       ┌──────────────────────────┐         ┌───────────────────────┐
       │  Neo4jGREAdapter         │ ◄────── │  Filesystem           │
       │  (single seam to KG)     │         │  materialized/        │
       └────────────┬─────────────┘         │  ├── extractions/     │
                    │                       │  ├── approved/        │
                    ▼                       │  └── validation/      │
       ┌──────────────────────────┐         └───────────────────────┘
       │  Neo4j (Docker)          │                  ▲
       │  bolt :7687, http :7474  │                  │
       │  ~1500 nodes, ~1900 rels │                  │
       └──────────────────────────┘                  │
                    ▲                                │
                    │ PDFs read by parser/PyMuPDF    │
                    │                                │
                    └──────── references/regulations/┘  (canonical PDFs)
                              synthetic_regulations/    (extracted text)
```

### 6.2 Logical layers

```
┌────────────────────────────────────────────────────────────────────┐
│ EXPERIENCE LAYER                                                   │
│  Side-by-side review UI · Wire Format Studio · KG Browser ·        │
│  CLI scripts                                                       │
├────────────────────────────────────────────────────────────────────┤
│ ORCHESTRATION LAYER                                                │
│  FastAPI endpoints · scripts/* · Makefile                          │
├────────────────────────────────────────────────────────────────────┤
│ DOMAIN LAYER                                                       │
│  packages/lhs/sentinel · packages/lhs/citations ·                  │
│  packages/lhs/materialization · packages/lhs/kg ·                  │
│  packages/core (closed-vocabulary types)                           │
├────────────────────────────────────────────────────────────────────┤
│ PORT LAYER                                                         │
│  GREStore · LLMPort · (future: RHS source ports, transmittal sink) │
├────────────────────────────────────────────────────────────────────┤
│ ADAPTER LAYER                                                      │
│  Neo4jGREAdapter · OpenAIAdapter · PyMuPDF (citation rects + parser)│
├────────────────────────────────────────────────────────────────────┤
│ INFRASTRUCTURE                                                     │
│  Neo4j Community (Docker) · OpenAI API · Filesystem                │
└────────────────────────────────────────────────────────────────────┘
```

The architectural rule (`docs/technical-architecture.md` §10): the domain layer and orchestration layer import from the port layer only — never directly from adapters. This keeps Neo4j and OpenAI swappable.

---

## 7. End-to-end story (today)

> A compliance officer wants to know: "When TICO publishes the new bulletin amending wind classification, can I confidently update the system in an afternoon?"

### Today's answer (LHS only)

1. **Engineer adds the bulletin PDF** to `references/regulations/` and registers it in `api/registry.py`.
2. **`make ui`** — opens the side-by-side UI. The compliance officer picks the bulletin from the dropdown.
3. **Click "Run Sentinel"** — Sentinel reads the bulletin, proposes new `BulletinOverride` + `Rule` (new version) + `CITES` edges. Coverage indicator shows ~95% of the bulletin text is cited; uncited spans are flagged.
4. **Compliance officer reviews** entity cards on the right; clicks each → highlights the cited PDF region on the left. Edits any extraction that's wrong; marks any uncited span as non-substantive.
5. **Click "Approve → materialize"** — KG updates. New rule version takes effect; `SUPERSEDES` edge to the old rule.
6. **Wire Format Studio re-runs**: the validator now rejects records using the old code; the generator emits records using the new code. The change is visible immediately as "the regulation is now executable in this new way."
7. **Audit trail** lives in Neo4j (`MATCH (r:Rule)-[:SUPERSEDES*]->...`), `materialized/approved/<bulletin>.materialized.json`, and the unchanged source PDFs under `references/`.

### Tomorrow's answer (with RHS)

8. Source-system records re-run through Bridge agent under the new KG; previously auto-classified records routing to HITL is the demo's concrete proof.
9. Next month's TICO transmittal automatically uses the new column structure because the templates *are* the KG.

---

## 8. Where this fits in the broader insurance reg-tech landscape

| Approach | What it is | Where it falls down |
|---|---|---|
| Hand-coded ETL | Per-state, per-report mapping in SQL/Python | Regulation changes cost weeks of engineering; provenance is folklore |
| Mapping-tool vendors | Visual schema mappers (Dell Boomi, Talend, etc.) | Treats regulation as a target schema; loses semantic grounding (why a field exists) |
| Snowflake + dbt-only | Medallion + tests | Has no opinion about the regulation — rules are SQL strings, not graph nodes |
| In-house compliance KG | Carrier-built ontology over compliance documents | Per-carrier, not productized; usually read-only — doesn't drive runtime |
| **RegulAI** | Productized KG with extraction + admin loop + RHS contract | The full stack is the differentiator: extraction → review → executable schema → traceable filings |

The novel claim is the **two-loop, KG-as-spine** architecture. The mapping-tools win on UI polish; the dbt-only stacks win on operational simplicity for a single carrier. RegulAI wins on **traceability and change-management velocity** — neither of which the alternatives even attempt.

---

## 9. Phased roadmap

### Done (as of 2026-04-26)

- LHS-0 Research → `docs/lhs-research.md`, `docs/kg-schema.md`
- LHS-1 Foundation → Neo4j Docker, migrations, Pydantic models
- LHS-2 KG operations → `Neo4jGREAdapter`, idempotent `materialize()`
- LHS-3 Sentinel agent → OpenAI Structured Outputs, all prose docs extracted
- LHS-3.5 Deterministic parser → all tabular wire-format docs at 200/200 coverage
- LHS-4 Side-by-side review UI + Wire Format Studio
- LHS-4 Sample-record generator + validator (round-trip self-test)

### In progress / next

- Synthetic bulletin re-evaluation flow (LHS-4 headliner) — the demo moment that ties the rules-level loop closed.
- Sentinel prompt hardening (forbid parser-owned types per slug).
- Parser quality polish (range-codes, footnote markers).

### Phase 2 — RHS data path

- Synthetic Guidewire CDA + Notice extracts.
- Bronze → Silver → Gold (dbt) reading from KG-derived rules.
- TICO transmittal file emission (Premium, Loss, Notice, Notice Count).

### Phase 3 — Record-level loop

- Bridge agent + RHS HITL queue UI.
- KG-driven HITL routing rules.

### Phase 4 — Full bulletin → re-eval cycle

- Synthetic bulletin in → side-by-side review → approve → re-materialization → in-flight RHS records re-classify.

Total POC budget through Phase 4: 15–22 working days. See `docs/poc-decisions.md` decision log for the budget history.

---

## 10. Success criteria

| Layer | Pass criterion (POC) | Status |
|---|---|---|
| KG fidelity | Every TICO-prescribed report layout: 200/200 column coverage, no orphan fields. | ✅ `make validate-kg` PASSES today |
| Provenance | Every node traces to a PDF rectangle via CITES + `rects_json`. | ✅ 93–95% rect coverage |
| Reproducibility | `make rebuild-kg` produces deterministic state, no LLM tokens. | ✅ ~30s |
| Round-trip | Generate sample → validate → identical KG facts on both sides. | ✅ working; quality nits open |
| Demo-readiness | A compliance person can sit through a 10-minute walkthrough without dismissing it as a toy. | ✅ for LHS; RHS still future |
| Audit traceability | "Why is column 5–6 RT? Why this list of codes?" answered with a graph walk. | ✅ |

The North-Star success criterion (per `docs/poc-decisions.md`): "JSON on disk and shown on screen — actual TICO transmittal file plus a small UI surface showing the agentic+HITL flow." LHS half is met. RHS half (the actual transmittal file) is Phase 2.

---

## 11. Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| LLM regression on Sentinel extractions | Medium | All extractions cached on disk; `rebuild-kg` doesn't re-call LLM. Re-run only when the prompt or model changes. |
| Regulation PDF format drift (next year's edition) | Medium | Parser is regex-based and brittle to layout changes; LLM extraction provides fallback for prose. New tabular docs may need parser tweaks. |
| Neo4j licensing / hosting in production | Low | Adapter pattern keeps storage swappable; Aura, self-hosted enterprise, and community all behind same `GREStore`. |
| Closed-vocabulary too narrow for adjacent jurisdictions | Medium | Adding a node type is a 4-file PR (deliberate change, not LLM whim). The 14/12 vocabulary is sized for TX residential — Auto / WC / Commercial would extend it. |
| OpenAI dependency / cost | Low for POC | Cached extractions; LLMPort makes Anthropic/Bedrock/local model swap mechanical. |
| HITL bottleneck (compliance officer review backlog) | Medium for production | LHS HITL is rare-event; the design avoids putting humans on every record. RHS HITL is high-volume but handled per-record by reviewers. |

---

## 12. References and reading order

For a new technical contributor:
1. `docs/solution-architecture.md` (this doc)
2. `docs/technical-architecture.md` — the formal "how it's built"
3. `docs/how-it-works.md` — operational runbook, the fastest path to producing an output
4. `docs/poc-decisions.md` — the chronological decision log
5. `docs/kg-schema.md` — the closed-vocabulary catalogue
6. `docs/lhs-build-plan.md` — the phased execution plan
7. `docs/skills.md` — operational know-how

For a product / strategy reviewer:
1. This doc end-to-end.
2. `docs/poc-decisions.md` §"North Star" through §"Architecture: LHS = RHS".
3. `references/RegulAI_Business_Plan_2026.pdf`, `references/End to End Simple Use case.docx` for the original vision.
