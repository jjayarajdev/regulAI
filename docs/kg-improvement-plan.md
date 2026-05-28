# RegulAI — KG Improvement & Multi-State Expansion Plan

**Last updated**: 2026-05-19
**Status**: proposal — not yet sequenced into engineering work
**Companion docs**: [`kg-framework-assessment.md`](kg-framework-assessment.md) (the audit this plan responds to), [`kg-schema.md`](kg-schema.md) (current schema), [`enterprise-readiness.md`](enterprise-readiness.md) (broader production gaps)

---

## Executive summary

The KG is the strongest piece of the platform but has six concrete gaps that need closing before customer #1 — and a larger structural shift required before the platform can credibly serve a second state.

This plan has four phases:

1. **Phase 1 — Harden Texas KG** (1-2 weeks). Close the six gaps from the framework assessment.
2. **Phase 2 — Multi-jurisdiction refactor** (3-4 weeks). Add `Jurisdiction` as a first-class node, scope everything by it, prove TX still works end-to-end.
3. **Phase 3 — Second-state pilot** (4-6 weeks). Pick one additional state, build out its canon, identify the friction points only a real second state surfaces.
4. **Phase 4 — Programmatic state onboarding** (ongoing). Templatize the intake so adding states 3 through N is days, not weeks.

Total to "ready for second customer in a second state": **~3 months of focused effort**, parallelizable with frontend / enterprise hardening work.

---

## North Star

> **The KG is the single registry of every US insurance-statistical-reporting obligation, queryable by jurisdiction, version, and effective-date. Adding a new state is a data operation, not an engineering project.**

What that means operationally:
- One Neo4j graph hosts the canon for all states (with jurisdiction-scoped subgraphs).
- A new state goes live by extracting its plan + statutes + bulletins into the existing schema — no new code.
- Cross-jurisdiction queries are first-class: "show me every rule that requires reporting wind/hail separately" returns TX, FL, and the GoM coastal states.
- Per-customer filings carry the jurisdiction stamp and pull the right canon slice at validation time.
- Bulletins from any state regulator (TDI, CDI, FL OIR, NY DFS) flow through the same Sentinel + materialize pipeline.

---

## Current state (one paragraph)

The KG has 1,538 nodes covering the Texas Statistical Plan (TICO), HB 2067, the TICO record layout, and three synthetic TDI bulletins. Every Rule carries a citation; every CodeList has its CodeValues; coverage validator confirms wire-format completeness. The bulletin override mechanism is exercised end-to-end (apply → propagate → reference reload → re-validate). The framework's missing pieces are an audit log, version-chain pressure testing, dual-labels for native Cypher queries, a diff endpoint, and citation propagation onto CodeValues. None require schema redesign.

There is no concept of "jurisdiction" in the schema today. Every node implicitly means "Texas". To add California, the schema would need to know which CodeList applies where — that's the Phase 2 work.

---

## Phase 1 — Harden Texas KG

**Goal**: close the six gaps from the audit. Texas is the only state in scope. No multi-state work yet.

**Duration**: 1-2 weeks (one engineer, full focus)

### 1.1 — KG audit log

**Problem**: RHS has `GOLD_AUDIT.USER_ACTION` capturing every state transition; the KG side has nothing equivalent. "Who applied bulletin B-2026-Q4-118 on which date and what changed?" is answerable only by correlating git history with file timestamps.

**Design**:
- New typed node: `KGAuditEntry` with properties `(action, actor, occurred_at, summary, details_json)`
- New relationship: `MUTATED_BY: GRENode → KGAuditEntry`
- Hook into `Neo4jGREAdapter.create_node` / `create_relationship` / supersede operations
- One entry per logical operation, not per primitive write (a bulletin apply = one entry referencing the bulletin + the override + the affected target rule)

**Acceptance**: `MATCH (r:GRENode {name: 'Rule A.34'})-[:MUTATED_BY]->(a:KGAuditEntry) RETURN a ORDER BY a.occurred_at DESC` returns the full history. The workstation's Audit screen surfaces it alongside the RHS audit log.

**Effort**: 1-2 days

### 1.2 — Pressure-test versioning end-to-end

**Problem**: every node is `version=1`. The versioning machinery exists but has never carried `v2` alongside `v1`. Specifically:
- Does the reference-SQL builder pick the right one (presumably `effective_until IS NULL`)?
- What happens to `FILING_EXCEPTION` rows that reference the old version's rule_id?
- Can a customer query "what was Rule A.34 on 2025-12-01"?

**Approach**:
- Create a fictional v2 of Rule A.34 via the bulletin flow (already capable)
- Exercise every downstream consumer in order:
  1. `build_validation_rules_reference.py` — does the generated SQL pick v2 or v1?
  2. `/api/rhs/validate` — does it use the right rule?
  3. `FILING_EXCEPTION` open rows — do they correctly carry forward or get reconciled?
  4. Workstation's "Regulation Explorer" — does it show v2 by default with a "show v1" toggle?
- Document expected behavior per consumer
- Add automated test: `tests/test_version_chain.py`

**Acceptance**: A v2 exists in graph + v1 still queryable; reference SQL has v2; validations use v2; exceptions reconcile; query-by-date works.

**Effort**: 2 days (mostly testing + likely fixing 1-2 bugs that surface)

### 1.3 — Dual labels on typed nodes

**Problem**: every node carries label `GRENode` with `type` as a property. Queries are `MATCH (n:GRENode {type: 'Rule'})` instead of `MATCH (n:Rule)`. The native Cypher optimizer is partially defeated; readability suffers.

**Approach**:
- One-line change in `packages/lhs/materialization/node_factory.py`: when creating a node, emit `CREATE (n:GRENode:{type} {…})` (Neo4j supports multi-label).
- Re-seed via `make rebuild-kg` to apply the new label to all nodes.
- Update existing Cypher queries gradually — both forms work simultaneously.
- Add new indexes for the most-queried labels: `(:Rule)`, `(:CodeList)`, `(:RegulationDocument)`.

**Acceptance**: `MATCH (r:Rule) WHERE r.section = 'A' RETURN r` works without specifying the `type` property. Existing queries still work (backward-compatible).

**Effort**: half day code + half day testing

### 1.4 — Diff endpoint

**Problem**: when a bulletin lands, the only way to see the change is to query before/after manually. No structured diff.

**Design**:
- New endpoint: `GET /api/lhs/kg/diff?from=<canon_version>&to=<canon_version>`
- Returns:
  ```json
  {
    "from": "v1", "to": "v2",
    "added_nodes":     [{node_id, type, name}, …],
    "modified_nodes":  [{node_id, type, name, changed_props: […]}, …],
    "superseded_nodes":[{node_id, type, name, superseded_by}, …],
    "added_edges":     [{src, dst, type}, …],
    "removed_edges":   [{src, dst, type}, …]
  }
  ```
- Backed by Cypher queries against the version + effective_from/until properties.
- Wire into the Bulletins screen so applying a bulletin shows a clean "what just changed" view.

**Acceptance**: applying bulletin B-2026-Q4-118 returns a diff with 1 modified CodeValue (Code L), 1 added BulletinOverride, 1 added OVERRIDES edge.

**Effort**: 1 day

### 1.5 — Citation hygiene

**Problem**: 4% citation coverage on CodeValue, 4% on CodeList. The parent's citation is the right answer but isn't materialized onto children.

**Approach**:
- In `materialize.py`, after creating a CodeValue, walk up `HAS_VALUE → CodeList → CITES` and copy the citation onto the CodeValue if it doesn't have its own.
- Run a one-time backfill script for existing nodes.
- Also clean up the one anomalous `type=NULL` node.

**Acceptance**: citation coverage on CodeValue rises from 4% to ~95%. NULL-type node removed.

**Effort**: half day

### 1.6 — Lightweight GraphQL surface

**Problem**: every consumer (RHS scripts, validators, API endpoints) writes Cypher inline. For an auditor's tool or a future customer integration, this isn't sustainable.

**Approach**:
- Wire `neo4j-graphql` (Neo4j's official GraphQL layer) onto the existing schema.
- Generate the SDL from the Pydantic node + relationship classes (or define it once and keep it in sync).
- Expose at `/api/lhs/kg/graphql` with read-only resolvers initially.
- Defer mutations (extraction stays via the Python pipeline).

**Acceptance**: a GraphQL query like `{ rules(section: "A") { name citation { fullCitation } violationSql } }` works.

**Effort**: 1 day (the Neo4j tooling does the heavy lift)

### Phase 1 totals

| Item | Effort |
|---|---|
| 1.1 KG audit log | 1-2 days |
| 1.2 Versioning pressure test | 2 days |
| 1.3 Dual labels | 1 day |
| 1.4 Diff endpoint | 1 day |
| 1.5 Citation hygiene | 0.5 day |
| 1.6 GraphQL surface | 1 day |
| **Total** | **~7-8 days** |

---

## Phase 2 — Multi-jurisdiction architecture refactor

**Goal**: introduce `Jurisdiction` as a first-class concept and scope every existing node and query by it. Texas continues to work end-to-end. No second state goes live in this phase — we just make the schema ready.

**Duration**: 3-4 weeks

### 2.1 — Schema extensions

**New node types**:

- `Jurisdiction` — `(jurisdiction_code, jurisdiction_name, jurisdiction_type, parent_jurisdiction)`. Values: `US-TX`, `US-CA`, `US-FL`, `US-NY`, …. Type ∈ `state | federal | regional`. Federal as parent for state-level overrides.
- `Regulator` — `(regulator_code, regulator_name, jurisdiction_code, contact_endpoint)`. Examples: `TDI` (Texas), `CDI` (California), `FL-OIR` (Florida).
- `StatisticalAgent` — `(agent_code, agent_name, jurisdiction_code, submission_channel)`. Examples: `TICO` (TX), `ISO-CL` (national commercial lines).
- `FilingObligation` — `(obligation_code, jurisdiction, regulator, cadence, due_offset_days, statute_authority)`. Replaces the hardcoded `FILINGS` registry.

**New relationships**:

- `APPLIES_IN: Rule | CodeList | CodeValue | RecordLayout → Jurisdiction`
- `ISSUED_BY: BulletinOverride | RegulationDocument → Regulator`
- `OBLIGATES: FilingObligation → Organization (the carrier)`
- `RECEIVES_SUBMISSION: FilingObligation → StatisticalAgent`

**Property additions**:
- `jurisdiction_code` on every existing node (default `US-TX` for the backfill)
- `is_federal_default` boolean on Rule/CodeList — true if the rule applies absent a state-specific override
- `supersedes_federal_rule_id` on state-specific Rules that override a federal default

### 2.2 — Federal vs state-specific canon

Some rules genuinely transcend state lines (NAIC-level standards, IRS-defined identifiers). Most are state-specific. The schema needs to express both cleanly.

**Design**:
- A `Rule` with `is_federal_default = true` and no `APPLIES_IN` edges → applies everywhere
- A `Rule` with `APPLIES_IN → Jurisdiction(US-TX)` → applies only in TX, optionally `supersedes_federal_rule_id` if it overrides a federal default
- Resolution at query time: for a given filing in TX, give me (federal defaults NOT superseded by TX-specific rules) UNION (TX-specific rules)

**Backfill plan**:
- Tag every existing Rule, CodeList, CodeValue, RecordLayout with `jurisdiction_code = 'US-TX'`
- Create `APPLIES_IN` edges to a single `Jurisdiction(US-TX)` node
- Identify the ~5-10 rules that are actually NAIC/federal (e.g., Rule A.22 NAIC company number is national) and re-tag those as federal defaults

### 2.3 — Multi-jurisdiction reference SQL

The reference-SQL builders (`build_reference_reason_codes.py`, `build_validation_rules_reference.py`) need to:

- Accept a `--jurisdiction` parameter
- Query for federal defaults + state-specific overrides
- Emit reference tables with a `jurisdiction_code` column
- Allow multi-jurisdiction reference tables (one row per (code, jurisdiction))

The RHS Snowflake reference tables get a `JURISDICTION_CODE VARCHAR(8)` column. Validation queries get `WHERE jurisdiction_code = :filing_jurisdiction`. All scoping is in SQL, not application code.

### 2.4 — FilingObligation as data

The hardcoded `FILINGS` registry in `packages/rhs/filings.py` becomes a `FilingObligation` query against the KG. Adding a new filing (different state, different LOB, different cadence) becomes a KG operation.

### 2.5 — Multi-jurisdiction workstation

Workstation UI needs:
- A jurisdiction picker (top-level: state selector, second-level: regulator/agent)
- "Cross-jurisdiction view" — see all the carrier's filings across states on one dashboard
- Rule explorer scoped by jurisdiction with "show federal defaults" toggle

### 2.6 — Acceptance criteria for Phase 2

- TX continues to work exactly as today — zero behavioral regressions
- Schema supports a hypothetical second state with no further code changes (verified by stubbing one)
- Validator runs `make validate-kg` on the TX subgraph and passes
- All 14 executable rules continue to fire with the same violation counts as before
- Workstation jurisdiction picker shows "Texas" with everything else greyed out

### Phase 2 effort

| Track | Effort |
|---|---|
| Schema extensions + backfill | 1 week |
| Reference-SQL builder refactor | 1 week |
| FilingObligation migration | 3 days |
| RHS table jurisdiction column + queries | 3 days |
| Workstation jurisdiction picker | 1 week |
| Testing + zero-regression validation | 3 days |
| **Total** | **3-4 weeks** |

---

## Phase 3 — Second state pilot

**Goal**: pick a second state, build out its canon, file at least one report end-to-end. Surface friction the architecture didn't anticipate.

**Duration**: 4-6 weeks

### 3.1 — State selection

Three candidate profiles, in rough order of strategic value:

1. **Florida (FL-OIR)** — similar HO catastrophe profile to TX (hurricanes, sinkholes, named-storm reporting). Same LOBs RegulAI already understands. Different statistical agent (no TICO equivalent — FL uses Citizens Property Insurance + private market reports). Different statute base. High customer demand if RegulAI sells to multi-state HO carriers. **Recommended.**
2. **California (CDI)** — large market, complex regulator, distinctive earthquake reporting, prop 103 ratemaking. Higher complexity, longer ramp. Save for state 3-4.
3. **A simple state (e.g., Idaho, Wyoming)** — smaller plans, faster to ingest, lower complexity. Good for proving the pipeline works; less customer impact.

**Recommendation**: Florida. Same architectural challenges as TX (HO + catastrophe), different regulatory body, real customer pull. If FL works, the platform's multi-state story is proven.

### 3.2 — FL intake checklist

- **Documents**: FL Statistical Plan (Citizens / OIR), FL Statute Title 627 (insurance code, sections on HO reporting), recent OIR Informational Bulletins, FL Hurricane Catastrophe Fund (FHCF) reporting requirements
- **Run Sentinel** against each PDF using the existing prompt + closed vocabulary
- **HITL review** every extraction before materialization (this is the slow part — first-time state intake will surface vocabulary gaps in the closed schema)
- **Identify federal defaults vs FL-specific**: NAIC standards apply; FHCF-specific data requirements are state-specific
- **Generate FL reference SQL** via the new multi-jurisdiction builders
- **Stand up a FL-specific filing batch** in `FILING_OBLIGATION` and a test customer in the workstation
- **Validate against FL synthetic data** (need a FL-shaped Bronze dataset — similar profile, different ZIPs/territories)
- **Render the FL filing as ASCII** in whatever format OIR requires (probably different from TICO's 200-column fixed-width)

### 3.3 — Expected friction points

These will be the lessons only doing a second state can teach:

- **Schema gaps**: FL probably has node types we don't have (e.g., `CatFundCession` for FHCF). Decide each: extend the closed vocabulary or model as properties.
- **Different submission format**: FL OIR likely doesn't use TICO's exact byte layout. Need a per-jurisdiction ASCII renderer plugin or a generalized template engine.
- **Different validation rules**: rules that look similar to TX rules but are subtly different (e.g., FL ZIP first-digit is 3, not 7). Decide each: parameterize the existing rule or write a separate FL-specific rule.
- **Coverage validator**: needs to run per-jurisdiction subgraph.
- **Bulletin flow**: FL bulletins come from OIR via a different RSS feed / website. The Sentinel pipeline + materialize is jurisdiction-agnostic, but the *intake* needs jurisdiction routing.

### 3.4 — Acceptance criteria

- FL canon loaded with full citations
- At least 3 validation rules executing against FL data
- One FL filing rendered end-to-end (Bronze → Silver → Gold → ASCII)
- Workstation correctly scopes the FL filing's rules, citations, and violations
- TX is **untouched** and continues to pass all existing tests
- A retrospective doc captures the lessons (`docs/lessons-second-state.md`)

### Phase 3 effort

| Activity | Effort |
|---|---|
| FL document acquisition + initial Sentinel extraction | 1 week |
| HITL review + closed-vocabulary extensions | 1-2 weeks |
| FL reference SQL + Snowflake table population | 1 week |
| FL-specific ASCII renderer | 1 week |
| FL synthetic Bronze dataset | 3 days |
| End-to-end testing + retrospective | 3 days |
| **Total** | **4-6 weeks** |

---

## Phase 4 — Programmatic state onboarding

**Goal**: by phase 4, adding state N takes days, not weeks. Most of the work is data, supervised by HITL.

**Duration**: ongoing; the first programmatic state onboarding should happen in week 12+

### 4.1 — State intake playbook

A documented, repeatable process:

```
For each new state:

1. INGEST  (1-2 days)
   ├── Collect: stat plan PDF, statute base, recent bulletins
   ├── Stand up jurisdiction node + regulator + agent in KG
   └── Add filing-obligation entries

2. EXTRACT  (3-5 days, mostly HITL-bound)
   ├── Run Sentinel against prose docs (LLM)
   ├── Run parser against tabular wire-format PDFs
   ├── HITL review of every extracted citation
   ├── Resolve closed-vocabulary tensions
   └── Materialize into jurisdiction-scoped subgraph

3. REFERENCE  (1 day)
   ├── Run multi-jurisdiction reference builders
   ├── Load into Snowflake REFERENCE schema
   └── Validate against existing Bronze synthetic data

4. RENDER  (2-5 days depending on state format complexity)
   ├── Identify the regulator's submission format
   ├── Configure or write the renderer plugin
   └── Test against synthetic data

5. VALIDATE  (1 day)
   ├── Run coverage validator on jurisdiction subgraph
   ├── Run executable rules against synthetic data
   └── Confirm zero TX regressions
```

Target: **7-15 days per state** depending on complexity. Reduces over time as patterns repeat.

### 4.2 — Automation opportunities

Things to invest in as the state count grows:

- **Bulletin auto-poller** — scheduled job per regulator's RSS feed; queues new bulletins for HITL approval.
- **Schema-drift detector** — alerts when Sentinel proposes a new node type or attribute, forcing a deliberate decision.
- **Cross-state rule clustering** — graph algorithm that finds rules with similar predicates across states; opportunity to consolidate or parameterize.
- **Per-state filing calendar** in the workstation top-bar — surfaces upcoming deadlines across the carrier's footprint.
- **Bulk regulator-text load** — extending `BRONZE_REGDOCS` to handle hundreds of source documents efficiently.

### 4.3 — Quality gates

For each new state going live, must pass:

- ☑ Coverage validator: every wire-format layout fully described
- ☑ Citation coverage: ≥95% on Rule, ≥80% on FieldRequirement
- ☑ End-to-end smoke test: synthetic Bronze → ASCII rendered → SHA-256 stable
- ☑ Zero regressions on previously-onboarded states
- ☑ Bulletin flow exercised at least once

### Phase 4 effort

Steady-state: 1-2 engineers maintaining the platform + 1 compliance analyst per state for HITL review, scaling with carrier customer demand.

---

## Cross-cutting concerns

### Governance

- **Closed vocabulary changes** require explicit approval — adding a new node type or relationship type is a schema change with backward-compatibility implications. PR template gates this.
- **Per-jurisdiction canon stewardship** — who's responsible for keeping FL's canon current? Probably a compliance analyst per state, supervised by a head-of-canon role.
- **Bulletin SLA** — when a new bulletin is published, how fast does it land in the KG? Target: within 5 business days of publication.

### Testing

- **Per-state regression suite** — `tests/test_state_<code>_canon.py` covering rule counts, citation coverage, executable-rule firing.
- **Cross-state isolation tests** — applying a FL bulletin must not change TX query results.
- **Version-chain integration tests** — apply a bulletin, query both versions, supersede, query again.

### Observability

- **Per-state KG metrics**: node count, citation coverage %, version-chain depth, last-bulletin-applied date.
- **Per-state validation latency** in Prometheus.
- **HITL queue depth** alerting (extractions pending review).

### Documentation

Each state gets its own subfolder in `docs/states/`:
- `docs/states/tx/canon-source.md` (where the PDFs came from)
- `docs/states/tx/quirks.md` (state-specific gotchas)
- `docs/states/tx/filing-calendar.md`

A meta-doc `docs/states/README.md` indexes them.

---

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Closed vocabulary doesn't fit a new state's regulator concepts | Medium | High | Phase 3 explicitly forces this question for FL; budget time for schema extensions |
| Different states' wire formats are incompatible enough to need full renderer rewrites per state | Medium | Medium | Design renderer as a plugin system in Phase 3; first plugin is FL |
| Bulletin volume across states overwhelms HITL capacity | Low (initially) → High (at 10+ states) | Medium | Invest in bulletin auto-poller + draft-extraction Phase 4; never auto-apply without HITL |
| Multi-tenant + multi-jurisdiction interact poorly (which canon does customer A see in state B?) | High | High | Decide policy explicitly in Phase 2: canon is shared across customers within a jurisdiction; only carrier-specific overrides are private |
| Performance degrades as graph grows from 1,500 to 50,000+ nodes | Medium | Medium | Native labels (Phase 1.3) + per-jurisdiction subgraph queries; Neo4j handles millions easily |
| Federal vs state-specific resolution logic produces wrong canon at query time | Medium | High | Phase 2.6 acceptance criteria specifically test this; Phase 3 validates against real second state |
| Versioning bugs surface only at production scale | Medium | High | Phase 1.2 pressure test before production; alerting on canon-version mismatch in Prometheus |

---

## Success metrics

### Phase 1 (Texas hardened)
- Citation coverage on CodeValue: 4% → ≥95%
- KG audit entries per bulletin apply: 0 → ≥3
- Cypher queries using native labels: 0% → 100% (in new code)

### Phase 2 (multi-jurisdiction architecture)
- TX regression count: 0
- New node types in schema: +4 (`Jurisdiction`, `Regulator`, `StatisticalAgent`, `FilingObligation`)
- Reference SQL builds parameterized by jurisdiction: 100%

### Phase 3 (second state)
- FL canon nodes: ≥500
- FL executable rules: ≥3
- FL end-to-end submission demonstrated: yes
- TX regression count: 0

### Phase 4 (programmatic onboarding)
- Days to onboard a new state (steady-state): ≤15
- States live: TX, FL, then +1 per quarter
- HITL queue depth at all times: <50 pending items

### Long-horizon (12+ months)
- 5-10 states live
- Multiple customer carriers using cross-state views
- One end-to-end "regulator publishes bulletin → RegulAI files corrected report" cycle proven without engineering intervention

---

## Estimated timeline

```
Week  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15
       │  │  │  │  │  │  │  │  │  │  │  │  │  │  │
P1     ████████                                       Texas hardening (Phase 1)
P2              ████████████                          Multi-jurisdiction refactor (Phase 2)
P3                          ████████████████          Florida pilot (Phase 3)
P4                                              ░░░░  Programmatic onboarding (Phase 4 ongoing)
```

**P1 ↔ P2**: P2 should not start until P1's audit log + version pressure test land, otherwise multi-state work compounds on shaky foundation.

**P2 ↔ P3**: P3 should not start until P2's TX-no-regression acceptance is signed off.

**P3 in parallel with frontend / enterprise hardening**: backend track A (KG + multi-jurisdiction) is independent of backend track B (auth + GuideWire integration) and frontend track C (TypeScript refactor). Run all three in parallel with a single engineer per track.

---

## Resourcing

Minimum to execute as described:
- **1 senior backend engineer** (Python, Cypher, Neo4j) — leads Phases 1-3
- **1 compliance analyst** (insurance regulation domain expert) — leads HITL review for Phase 3 onward
- **0.5 platform engineer** (CI/CD, observability) — supports cross-cutting concerns
- **0.25 frontend engineer** — workstation jurisdiction picker in Phase 2.5

Total: ~1.75 FTE for 3 months. Scales modestly thereafter.

---

## Open decisions

These need product/exec input before execution:

1. **Florida or California as state #2?** — Recommendation is FL (lower complexity, similar profile to TX, strong customer pull). Final call depends on customer pipeline.
2. **Per-tenant Neo4j or shared?** — Recommendation is shared graph with jurisdiction labels (operationally simpler; canon is genuinely shared across customers within a state). Final call depends on customer concerns about graph isolation.
3. **Acceptable HITL turnaround for new bulletins?** — Recommendation is 5 business days. Faster requires more analysts; slower risks falling behind regulators.
4. **Are we comfortable with the closed-vocabulary boundary growing as we add states?** — Recommendation is yes (governed via PR review); the alternative (open vocabulary) destroys the platform's defensibility.

---

## Bottom line

The KG is well-designed for one state. Extending to many is a tractable engineering project — three months of focused work to ready, then steady-state per-state addition in 1-2 weeks. The schema needs jurisdiction-as-data, the reference builders need parameterization, the renderer needs to become a plugin, and the closed vocabulary will grow modestly.

**None of this requires rebuilding the framework.** All of it preserves the architectural thesis (regulation drives data, with provenance, with version-controlled supersession). The work is to scale the thesis from "Texas" to "every US state's statistical reporting obligation".

Start with Phase 1 next week. Decide Florida-vs-California by end of Phase 1.
