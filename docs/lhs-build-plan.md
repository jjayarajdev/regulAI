# RegulAI LHS-Only Build Plan

**Status as of 2026-04-26**: LHS-0 through most of LHS-4 complete. KG operational, generates and validates every TICO-prescribed report.
**Architecture context**: see `docs/poc-decisions.md` (LHS = RHS framing, ports/adapters, KG-as-canon).
**This doc**: the concrete execution plan for the LHS-first slice.

## Progress checklist (2026-04-26)

- ✅ **LHS-0 — Research + data gathering** — `docs/lhs-research.md`, `docs/kg-schema.md` produced; 14 node types, 12 relationship types finalized.
- ✅ **LHS-1 — Foundation** — Neo4j Docker, Cypher migrations, Pydantic models, smoke test all in place.
- ✅ **LHS-2 — KG operations layer** — `Neo4jGREAdapter` with create/read/find/wipe; `materialize()` is idempotent (CITES MERGE on `(src, dst, char_start, char_end)`).
- ✅ **LHS-3 — Sentinel agent + extraction** — Sentinel runs over Sections A, B, F, HB 2067, the bulletin; OpenAI Structured Outputs against `SentinelExtraction`.
- ✅ **LHS-3.5 — Wire-format parser** (added 2026-04-26, not in original plan) — deterministic parser owns Sections C/D/E/G + the Homeowners record-layout PDF; LLM was unreliable for tabular content. Six layouts at 200/200 column coverage.
- ✅ **LHS-4 — UI side-by-side review** — `ui/regulations.html` shows PDF, entities, and Wire Format Studio (sample-record + validator). Cross-pane click highlighting: column ↔ FieldRequirement card ↔ PDF rect.
- 🟡 **LHS-4 — `neovis.js` live-graph render** — current UI shows entities as cards, not a live graph. Optional polish; entities + chips already provide the same provenance.
- ⬜ **LHS-4 — Synthetic bulletin re-evaluation flow** — `BulletinOverride` + `SUPERSEDES` exist as schema; the UI flow that bumps versions and re-evaluates in-flight content is the remaining headline demo step.
- ⬜ **LHS-4 — Snowflake materialization sink** — deliberately deferred until RHS work begins. JSON snapshots in `materialized/` are sufficient for now.

The two open items are scoped enough to demo without; the bulletin re-eval flow is the natural next milestone.

---

## Goal

Build the regulatory side end-to-end as a runnable, demoable standalone system. No RHS, no records, no transmittals. The artifact is: **regulation document → LLM extraction → KG → side-by-side admin review → versioned approval → JSON materialization**, with a synthetic-bulletin path that demonstrates "regulation changes → KG observes → admin approves → versions bump."

## Scope

### In
- Neo4j Community in Docker, locally hosted
- Real Texas regulations as the KG seed (publicly available + user-supplied)
- Synthetic change-trigger bulletins (we author these to demo the rules-level loop)
- Sentinel agent using OpenAI (model TBD by research, leaning GPT-5 with Structured Outputs)
- Closed-vocabulary KG schema, refined from regulation research (not assumed)
- FastAPI for LHS endpoints
- Side-by-side UI extending `mock-ui-v2/ontology.html` with `neovis.js` for live graph viz
- JSON materialization sink (Snowflake materialization deferred to RHS work)
- Manual edit flow (admin proposes a change without a new document)

### Out (deferred to RHS work)
- Snowflake account, dbt models, medallion pipeline
- Bridge agent (record classifier)
- RHS HITL / `MR_QUEUE`
- TICO transmittal generation
- Source adapters for Policy / Claim / Notice
- Real ISO-Verisk submission

## Choices locked

| Choice | Value | Source |
|---|---|---|
| KG storage | Neo4j Community in Docker, local | User decision |
| Hosting | Local Docker only for the database; Python/FastAPI run native | Implicit |
| LLM provider | OpenAI (user provides key) | User decision |
| LLM model | TBD — GPT-5 unless research suggests otherwise; using Structured Outputs for `SentinelExtraction` schema discipline | Recommended |
| Regulation seed | Real Texas regs (publicly available, hybrid fetch: I WebSearch+WebFetch what's public, user supplies any paywalled/registered docs) | User decision |
| Change demo | Synthetic bulletins authored to trigger KG diff against real-reg baseline | User decision |
| KG schema | 12 starter node types + 8 relationship types as the hypothesis; **refined in LHS-0 based on real-reg research** | User decision |
| Materialization | JSON files on disk for now; same `MaterializationSink` port swappable to Snowflake later | Plan decision |
| UI | Extends `mock-ui-v2/ontology.html`; preserves design language | Default |
| Defaults | All overridable via Pydantic settings (no buried hardcoded constants) | User constraint |

---

## Sub-phases

### LHS-0: Research + data gathering (1–2 days)

Research Texas residential reporting regulations to ground the KG schema in reality, not assumption.

- WebSearch for: TICO Texas Residential Statistical Plan, HB 2067 statute, recent TDI bulletins (2025–2026), Texas Department of Insurance designated statistical agent residential property
- WebFetch the public docs (TDI bulletins, HB 2067, stat plan summaries)
- Identify what's publicly accessible vs paywalled/registered
- Read structure of available docs; document required reporting fields
- Refine KG schema: confirm which of the 12 starter node types apply, drop ones that don't, propose additions
- Output: `docs/lhs-research.md` (findings) + `docs/kg-schema.md` (refined schema with citations to reg sections that justify each type)
- Identify what user must supply (any non-public docs)

**Exit criterion**: refined `KG_SCHEMA.md` exists with each node and relationship type justified by a real regulation reference; user knows what (if anything) they need to provide.

### LHS-1: Foundation (1–2 days)

- Repo scaffold: `pyproject.toml` (uv), `Makefile`, LHS-only `packages/` tree, `tests/`, `.env.example`
- `docker-compose.yml` with Neo4j Community (Bolt + HTTP, named volume for persistence, healthcheck)
- Cypher migration script: constraints + indexes per refined schema
- Pydantic models in `packages/core/`: refined node + relationship types as discriminated unions
- Pydantic settings in `packages/config/` reading from `.env` (Neo4j creds, OpenAI key, model name, confidence thresholds, coverage rigor — all overridable)
- Smoke test: `make up && make smoke` writes a node, reads it back

**Exit criterion**: `docker compose up -d neo4j && python -m smoke` writes/reads node successfully; Neo4j Browser at `http://localhost:7474` shows it.

### LHS-2: KG operations layer (1–2 days)

- `GREStore` port (`packages/ports/lhs/`)
- `Neo4jGREAdapter` (`packages/adapters/lhs/gre/`): create-node-version, supersede, query-active-as-of-date, write-citation, list-uncited-spans, fetch-subgraph-for-proposal
- Cypher queries isolated in `packages/lhs/kg/queries.py` — testable, replaceable
- Seed script: `python -m seed` writes ~10 hand-crafted nodes (one per major type) covering the anchor-record domain (HO-3 + WH/WN + HB 2067 nonrenewal)
- pytest coverage on KG ops

**Exit criterion**: `make seed` populates Neo4j with hand-crafted regulatory canon; Neo4j Browser shows the graph; tests pass.

### LHS-3: Sentinel agent + synthetic change bulletins (3–4 days)

- `synthetic_regulations/` directory:
  - Real regs (downloaded in LHS-0) under `synthetic_regulations/real/`
  - Synthetic change bulletins under `synthetic_regulations/synthetic/bulletins/` (we author 1–2 to trigger schema-relevant changes against the real baseline)
- `RegulationDocumentAdapter` + `BulletinSourceAdapter` (synthetic-mode impls reading from disk)
- `LLMPort` + `OpenAIAdapter` using **Structured Outputs** with the `SentinelExtraction` Pydantic schema
- Sentinel agent in `packages/lhs/sentinel/`: takes a `RegulationDocument`, returns proposed nodes/relationships + citations + uncited spans + per-node confidence
- Closed-vocabulary system prompt (the schema is the contract; agent extracts only into permitted types)
- Caching strategy: regulation text + schema cached for repeated queries
- CLI: `make extract DOC=tico_residential_plan` dumps `SentinelExtraction` JSON

**Exit criterion**: extraction against a real reg produces a structurally valid, schema-conformant `SentinelExtraction` with sensible citations; spot-check 5 nodes manually.

### LHS-4: Side-by-side UI + materialization (3–4 days)

- FastAPI app under `api/lhs/`:
  - `GET /regulations` — list available docs
  - `POST /regulations/{id}/extract` — runs Sentinel
  - `POST /kg/proposals/{id}/edit` — edit proposed node before approval
  - `POST /kg/proposals/{id}/approve` — commit versioned nodes + relationships, trigger materialization
  - `POST /kg/manual-edit` — admin-initiated rule edit (no new document)
  - `GET /kg/nodes`, `GET /kg/active-as-of/{date}`
- UI page extending `mock-ui-v2/ontology.html`:
  - Left pane: regulation rendered with extraction spans highlighted (covered vs uncited)
  - Right pane: live Neo4j subgraph via `neovis.js`; citation chips; per-node controls (accept / edit / reject; mark uncited span as non-substantive)
  - Coverage indicator
  - Approve button (advisory gate, not enforced)
- `MaterializationSink` port + `JSONMaterializationSink` adapter: writes `materialized/gre_rules.jsonl`, `_templates.jsonl`, `_triggers.jsonl` after every approval
- Manual edit flow exercises the same approval surface

**Exit criterion**: end-to-end demo from clean `docker compose up`:
1. `make up && make seed`
2. UI → "Ingest TICO Stat Plan" → side-by-side appears
3. Review, edit one node, mark a span non-substantive, approve
4. Neo4j Browser shows new versions + `SUPERSEDES`
5. `materialized/*.jsonl` updated
6. Repeat with synthetic change bulletin → see proposals as a delta against existing KG
7. Admin manual edit → same approval flow

---

## Demo (the ~10-minute story at LHS-4 exit)

1. Open the UI on a clean Neo4j with starter seed.
2. Ingest the real TICO Stat Plan. Watch the KG populate — graph view on the right renders ~30–60 nodes with citations to specific stat-plan sections. Coverage indicator shows ~85% with a few advisory uncited spans (preamble, signature). Approve.
3. Ingest HB 2067. KG grows; observe `OVERRIDES` relationships forming. Approve.
4. Ingest a synthetic change bulletin: "Effective 2026-Q3, COL code WH requires `NAMED_STORM_NWS_ID` field." Side-by-side shows: small diff (one new `FieldRequirement` + a `SUPERSEDES` on the existing rule). Approve.
5. Show Neo4j Browser: trace a path from `FieldRequirement[NAMED_STORM_NWS_ID]@v1` → `CITES` → `Bulletin 2026-Q3-014` → §2 lines 4–9. Provenance is real.
6. Show `materialized/gre_rules.jsonl`: the new rule appears, ready for RHS to consume when we build it.
7. Bonus: admin manual edit — propose a CarrierSOP refining a base rule, no document needed. Same approval surface.

---

## Tracking conventions

- **Tasks**: each sub-phase is a top-level task. Mark `in_progress` at start, `completed` at exit-criterion satisfaction. Sub-tasks created as discovered.
- **Memory**: durable architectural decisions go in `~/.claude/projects/-Users-jjayaraj-workspaces-studios-regulAI/memory/`. Execution status (current sub-phase, blockers) gets a short pointer there.
- **Living docs in repo**:
  - `docs/poc-decisions.md` — full architecture (rarely changes now)
  - `docs/lhs-build-plan.md` — this doc (sub-phase plan, exit criteria)
  - `docs/lhs-research.md` — output of LHS-0 (regulation findings)
  - `docs/kg-schema.md` — refined KG schema (created in LHS-0, edited as schema evolves)
  - `docs/skills.md` — accumulated operational know-how (Cypher patterns, OpenAI quirks, neovis.js gotchas) — created when we have content
- **Decision changes**: any deviation from this plan gets a one-line entry in `docs/poc-decisions.md` decision log AND, if scope-altering, a note in this doc's "Deviations" section (added when first deviation occurs).

---

## What I'm doing right now

LHS-0: research the regulations. Findings will land in `docs/lhs-research.md`; refined schema in `docs/kg-schema.md`.
