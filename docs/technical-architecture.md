# RegulAI — Technical Architecture (LHS, as built)

**Last updated**: 2026-05-18
**Scope**: the LHS slice (Sentinel extraction → KG → reference SQL). The RHS slice (Snowflake medallion pipeline, validation engine, sign-off workflow, ASCII renderer, anomaly detector, audit chain) is now also built — see [`rhs-build-summary.md`](rhs-build-summary.md) for the engineering record. Together they form the end-to-end vertical described in [`solution-architecture.md`](solution-architecture.md).
**Audience**: developers, architects, future contributors to the codebase.

---

## 1. One-page picture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ FRONTEND  ui/regulations.html                                                │
│ ┌────────────────┐ ┌──────────────────┐ ┌──────────────────────────────────┐ │
│ │ Source PDF     │ │ Extracted KG     │ │ Wire Format Studio               │ │
│ │ (PDF.js,       │ │ entities         │ │ (sample record + validate +      │ │
│ │  PyMuPDF rect  │ │ grouped by node  │ │  cross-pane click highlighting)  │ │
│ │  overlays)     │ │ type             │ │                                  │ │
│ └────────────────┘ └──────────────────┘ └──────────────────────────────────┘ │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │ HTTP, JSON
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ API  api/main.py  (FastAPI, uvicorn :8765)                                   │
│  /api/regulations           /api/regulations/{slug}/extract                  │
│  /api/regulations/{slug}    /api/regulations/{slug}/approve                  │
│  /api/regulations/{slug}/pdf  /api/layouts/{name}/sample                     │
│  /api/kg/stats              /api/layouts/{name}/validate                     │
└─────┬──────────────────────────┬────────────────────────────┬────────────────┘
      │                          │                            │
      │ Sentinel + materialize   │ PyMuPDF for citation rects │ Direct read
      │                          │                            │
      ▼                          ▼                            ▼
┌──────────────────┐    ┌──────────────────┐         ┌────────────────────────┐
│ packages/lhs/    │    │ packages/lhs/    │         │ Neo4j (Docker, Bolt    │
│   sentinel/      │    │   citations/     │         │   :7687, Browser :7474)│
│   (LLM extract)  │    │   (PDF rects)    │         │ — closed-vocabulary    │
└──────────────────┘    └──────────────────┘         │   KG, ~1500 nodes,     │
      │                          │                   │   ~1900 rels           │
      │                          │                   └────────────────────────┘
      ▼                          ▼                            ▲
┌──────────────────────────────────────────────────────────────┘
│ packages/lhs/materialization/  (proposal → typed node → Neo4j)
│   - resolve temp_ids → UUIDs (dedup against existing by hash or (type, name))
│   - proposed_to_typed_node (flat ProposedNode → typed GRENode)
│   - idempotent CREATE (MERGE on natural keys)
└──────────────────────────────────────────────────────────────
       ▲              ▲                                        ▲
       │              │                                        │
       │              │                                        │
┌─────────────┐ ┌──────────────────────┐    ┌──────────────────────────────────┐
│ scripts/    │ │ scripts/             │    │ scripts/                         │
│ batch_      │ │ parse_record_layout  │    │ rebuild_kg                       │
│ extract     │ │ (deterministic       │    │ (wipe → migrate → seed →         │
│ (LLM, prose │ │  parser for tabular  │    │  replay LLM extractions →        │
│  docs)      │ │  wire-format PDFs)   │    │  parse → cleanup)                │
└─────────────┘ └──────────────────────┘    └──────────────────────────────────┘
```

Two extraction sources, both flowing through the same `materialize()` pipeline into the same Neo4j KG. The frontend reads from the API; the API reads from on-disk JSON snapshots and Neo4j.

---

## 2. Architectural style

**Modular monolith with hexagonal (ports & adapters) seams.**

- **One Python process, one Docker dependency** (Neo4j). No microservices. The complexity isn't in the deployment topology; it's in the regulatory data model.
- **Module boundaries are real but logical** — `packages/core`, `packages/ports`, `packages/adapters`, `packages/lhs`. Each package owns its concern; cross-package imports are constrained by an architectural rule (see §10).
- **Adapters wrap external systems** (Neo4j, OpenAI, PyMuPDF). Domain logic in `packages/lhs/*` and the orchestration layer in `api/` and `scripts/` import only from `packages/ports/*` and the typed Pydantic models in `packages/core/*`.
- **The KG is the contract**, not an internal detail. Every read of the KG (UI, scripts, future RHS) goes through the same `Neo4jGREAdapter`.

Why this style: at single-developer / POC scale the operational tax of microservices buys nothing. Modular monolith with clean seams gives the same future-extraction option without the up-front cost.

---

## 3. System decomposition

```
regulAI/
├── api/                              # HTTP entry points
│   ├── main.py                       # FastAPI app, all endpoints
│   └── registry.py                   # DOCS list, slug → DocEntry, wire_layouts_for(slug)
│
├── packages/
│   ├── core/                         # pure Pydantic — no IO
│   │   ├── enums.py                  # 14 NodeType + 12 RelationshipType (the closed vocabulary)
│   │   ├── nodes.py                  # 14 GRENode subclasses with Literal discriminator
│   │   └── relationships.py          # CitesRelationship (with rects_json), GRERelationship
│   │
│   ├── config/
│   │   └── settings.py               # Pydantic settings — every default overridable via .env
│   │
│   ├── ports/                        # Protocol classes (abstract interfaces)
│   │   ├── lhs/                      # GREStore (KG operations)
│   │   └── shared/                   # LLMPort
│   │
│   ├── adapters/                     # concrete implementations of ports
│   │   ├── lhs/gre/neo4j_adapter.py  # Neo4jGREAdapter — every KG read/write
│   │   └── shared/llm/openai_adapter.py  # OpenAIAdapter — Sentinel's LLM
│   │
│   └── lhs/                          # LHS application logic
│       ├── sentinel/                 # LLM extraction
│       │   ├── agent.py              # Sentinel agent (OpenAI Structured Outputs)
│       │   ├── prompts.py            # SYSTEM_PROMPT — vocabulary + citation discipline
│       │   └── schema.py             # SentinelExtraction Pydantic schema
│       ├── citations/
│       │   └── pdf_highlight.py      # PyMuPDF: char span → PDF rectangles
│       ├── materialization/
│       │   ├── materialize.py        # 5-phase: temp_id resolve → write nodes → write rels → cite → snapshot
│       │   └── node_factory.py       # flat ProposedNode → typed GRENode
│       └── kg/
│           └── queries.py            # canonical Cypher templates
│
├── scripts/                          # CLI orchestration (each is `make`-targeted)
│   ├── migrate.py                    # Cypher constraints/indexes
│   ├── seed.py                       # hand-crafted regulatory canon (3 docs, 7 rules, ...)
│   ├── batch_extract.py              # idempotent LLM run over all docs
│   ├── extract.py                    # one-doc LLM run
│   ├── extract_pdfs.py               # PDF text extraction (pypdf, with PAGE markers)
│   ├── split_sections.py             # split TICO Stat Plan into per-section files
│   ├── parse_record_layout.py        # deterministic parser (HO PDF + Stat Plan §C/D/E/G)
│   ├── compute_rects.py              # backfill PyMuPDF rects for cached extractions
│   ├── rebuild_kg.py                 # full reproducible rebuild from disk
│   ├── cleanup_kg.py                 # drop phantom layouts + orphan fields
│   ├── validate_kg_coverage.py       # KG coverage validator (must PASS)
│   ├── generate_sample_submission.py # KG → 200-char record
│   ├── validate_submission.py        # 200-char record → per-column errors
│   └── verify_openai.py              # smoke test for OpenAI key/model
│
├── ui/
│   └── regulations.html              # SPA: PDF.js + entity cards + Wire Format Studio
│
├── synthetic_regulations/            # extracted regulation text (Sentinel input)
│   ├── real/
│   │   ├── sections/                 # section_A_general.md ... section_G_record.md
│   │   ├── HB02067I.txt
│   │   └── wire_layouts/
│   │       └── tico_recordLayoutHomeOwners.txt
│   └── synthetic/
│       └── bulletins/B-2026-Q3-104.md
│
├── references/regulations/           # source PDFs (canonical authority)
│   ├── TX_Statistical_Plan_Residential_Risks_2026.pdf
│   ├── HB02067I.pdf
│   └── tico_recordLayoutHomeOwners.pdf
│
├── materialized/                     # persisted artifacts (audit trail)
│   ├── extractions/                  # <stem>.extraction.json + <stem>.rects.json per doc
│   ├── approved/                     # post-materialize snapshot per slug
│   └── validation/                   # KG coverage reports (kg_coverage.json)
│
├── docs/                             # living docs (this file lives here)
├── tests/
├── docker-compose.yml                # Neo4j Community
├── pyproject.toml                    # uv-managed deps
├── Makefile                          # all common workflows
└── .env / .env.example               # config (overrides settings.py defaults)
```

---

## 4. Data model

### 4.1 Closed vocabulary

**14 node types** (`packages/core/enums.py:NodeType`):
`RegulationDocument`, `StatPlanEdition`, `Rule`, `ReportTemplate`, `RecordLayout`,
`FieldRequirement`, `CodeList`, `CodeValue`, `CoverageType`, `EndorsementRule`,
`BulletinOverride`, `ReconciliationRule`, `Organization`, `HITLTriggerRule`.

**12 relationship types** (`RelationshipType`):
`SUPERSEDES`, `EFFECTIVE_FROM`, `CITES`, `CONTAINED_IN`, `CONTAINS_LAYOUT`,
`REQUIRES`, `HAS_VALUE`, `CODED_BY`, `OVERRIDES`, `DESIGNATED_BY`,
`RECONCILES_WITH`, `APPLIES_TO`.

Every node and edge in the KG is one of these. The vocabulary is enforced *thrice*: by the OpenAI Structured Outputs JSON Schema (LLM can't emit other types), by the typed Pydantic GRENode subclasses (Python validation on materialization), and by the parser (writes the same Pydantic models). See `docs/kg-schema.md` for the full property catalogue.

### 4.2 Common node properties

Every `GRENode`-labelled node carries: `id` (UUID4), `type` (Literal), `name`, `version` (int, default 1), `status` (`draft` | `approved` | `superseded`), `effective_from` / `effective_to` (ISO date), `created_at`. Type-specific properties (e.g., `position_start` on `FieldRequirement`, `code` on `CodeValue`) live on the Pydantic subclass.

### 4.3 The CITES relationship — provenance core

```python
class CitesRelationship(GRERelationshipBase):
    type: RelationshipType = RelationshipType.CITES
    char_start: int                    # offset in source text
    char_end: int
    kind: CitationKind = DEFINES       # defines | modifies | references
    rects_json: str | None = None      # JSON-serialized list of PDF rectangles
                                       # (page, x0, y0, x1, y1) in PDF points
```

`rects_json` is the pixel-perfect provenance: PyMuPDF's `page.search_for` is run against the cited text snippet at extraction time; the resulting rectangles are stored on the edge so the UI doesn't need to fuzzy-match at click time. Coverage on the corpus today is 93–95%; misses are markdown header artifacts that don't exist in the source PDF.

### 4.4 Versioning model (append-only)

Rules and other regulatory facts evolve. A change creates a *new node version* + a `SUPERSEDES` edge from new → old. Edition pinning is a temporal Cypher query:

```cypher
MATCH (n:GRENode {type: $t, name: $name})
WHERE n.effective_from <= $as_of
  AND (n.effective_to IS NULL OR n.effective_to > $as_of)
RETURN n
```

The bulletin re-evaluation flow (LHS-4, still TODO) bumps versions for nodes the bulletin overrides; in-flight content is re-evaluated under the new versions.

### 4.5 On-disk artifacts

| Path | Format | Authored by | Read by |
|---|---|---|---|
| `materialized/extractions/<stem>.extraction.json` | `SentinelExtraction` JSON | Sentinel agent OR parser | UI (`/api/regulations/{slug}`), `materialize()` |
| `materialized/extractions/<stem>.rects.json` | `CitationRectsBundle` JSON | `compute_rects_bundle()` | UI for highlight overlays |
| `materialized/approved/<slug>.materialized.json` | snapshot | `materialize()` after Neo4j writes | audit, future RHS |
| `materialized/validation/kg_coverage.json` | report | `validate_kg_coverage.py` | CI / human review |

These are the audit trail — drop any file into a PR and a reviewer can replay exactly what changed.

---

## 5. Process flows

### 5.1 LLM extraction (prose docs — Section A, B, F, HB 2067, bulletin)

```
regulation text (.md/.txt)
   │
   ▼
Sentinel.extract(text, document_label)      # packages/lhs/sentinel/agent.py
   │  uses OpenAI Structured Outputs against SentinelExtraction schema
   ▼
SentinelExtraction (Pydantic)
   │  proposed_nodes: [ProposedNode]   ← flat — all type-specific fields optional
   │  proposed_relationships: [...]    ← cross-references via temp_ids
   │  citations: [(node_temp_id, char_start, char_end, kind)]
   │  uncited_spans: [...]             ← coverage gap signal
   │  document_total_chars: N
   │
   ▼
write to materialized/extractions/<stem>.extraction.json   ← cached, idempotent
   │
   ▼
compute_rects_bundle(pdf_path, source_text, extraction, page_range)
   │  PyMuPDF page.search_for() with progressive prefix shortening
   ▼
write to materialized/extractions/<stem>.rects.json
   │
   ▼
materialize(extraction, gre, document_label, rects_bundle)
   │  Phase 1: _resolve_temp_ids — for each ProposedNode, look up by hash (docs)
   │           or (type, name) in Neo4j; reuse existing UUID or assign uuid4()
   │  Phase 2: for unmatched proposals, proposed_to_typed_node() validates,
   │           gre.create_node() writes
   │  Phase 3: proposed_relationships — gre.create_relationship() (idempotent MERGE)
   │  Phase 4: citations — CitesRelationship from cited node → primary doc,
   │                       carrying char_start/char_end + rects_json
   │  Phase 5: snapshot to materialized/approved/<slug>.materialized.json
   ▼
Neo4j has new typed nodes + edges
```

### 5.2 Deterministic parsing (tabular docs — Section C, D, E, G + Homeowners record-layout PDF)

```
PDF (e.g. references/regulations/TX_Statistical_Plan_Residential_Risks_2026.pdf)
   │
   ▼
parse_pdf(pdf_path, page_start, page_end, forced_layout_name)
   │  PyMuPDF text extraction
   │  state-machine walk:
   │    - filter noise lines (page banners, table headers; case-insensitive)
   │    - detect field headers via regex: ^(\d+)(?:[–\-](\d+))?\s*\(([A-Z0-9#&\-/]+)\)\s*$
   │    - detect SKIP headers: ^(\d+)[–\-](\d+)\s*$  (only if hi >= 10)
   │    - alternate code/description rows; multi-line descriptions append to
   │      the previous code rather than the field-level description
   │    - sub-field detection (ACDT cols 3-4 → MONTH at col 3 + YEAR at col 4)
   │    - gap-fill cols 1..200 with implicit SKIP fields
   ▼
list[ParsedField]
   │
   ▼
build_extraction(pdf_path, text_path, parsed_fields, doc_info)
   │  emits a SentinelExtraction-shaped object so it flows through the SAME
   │  materialize() pipeline as Sentinel output (same dedup, same provenance,
   │  same snapshots)
   ▼
[same writes as 5.1: extraction.json, rects.json, materialize → Neo4j]
```

The parser owns: `RegulationDocument`, `RecordLayout`, `FieldRequirement`, `CodeList`, `CodeValue`, plus the edges between them. The LLM owns: `Rule`, `BulletinOverride`, `ReconciliationRule`, `HITLTriggerRule`, `Organization`, prose-driven `Citations`. They never overlap because the slug → tool mapping is in `api/registry.py:WIRE_LAYOUTS_FOR_SLUG`.

### 5.3 Idempotent re-runs

`Neo4jGREAdapter.create_relationship` uses `MERGE` keyed on:
- For CITES: `(src, dst, char_start, char_end)` — same cited span = same edge.
- For everything else: `(src, dst, type)` — closed-vocabulary assumption.

`materialize()` itself dedupes via `find_existing_by_name(type, name)` (or `find_document_by_hash()` for documents) before issuing creates. Re-running `make rebuild-kg` produces a deterministic final state regardless of how many times it's run.

### 5.4 Cleanup pass

`scripts/cleanup_kg.py` runs as the final step of `rebuild_kg`:

- Phantom RecordLayouts (no `CONTAINED_IN` from any FieldRequirement) → DELETE
- Orphan FieldRequirements (no `CONTAINED_IN` to any RecordLayout) → DELETE
- Cascading: orphan CodeLists → DELETE, orphan CodeValues → DELETE

These are all artifacts of LLM extraction of tabular content. Once the parser owns those types, the cleanup is a one-liner.

### 5.5 Sample-record generator (KG → wire format)

```
RecordLayout name (e.g. "Premium Record Layout")
   │
   ▼
fetch_layout(name) → list[FieldDef] sorted by position_start
   │  excludes "parents-with-sub-fields" (their range is fully covered by smaller fields)
   ▼
fill_record(fields, scenario, rng):
   │  for each field:
   │    - SKIP            → spaces of length L
   │    - has CodeValues  → pick scenario-driven code (RT=91 for new-policy, etc.)
   │    - free-form       → generate by field-name keyword (POLICY/CLAIM/ZIP/DATE/...)
   │  pad each chunk to its declared length
   ▼
200-char string + per-column annotation
```

### 5.6 Submission validator (wire format → KG check)

```
200-char record + RecordLayout name
   │
   ▼
fetch_layout(name) (same as above)
   │
   ▼
validate_record():
   │  for each field, slice record[ps-1 : ps-1+pl]:
   │    - SKIP           → must be blank
   │    - has CodeValues → value must be in allowed set
   │                       (range codes like "1-9" expand: digit ∈ [1..9] is OK)
   │    - free-form      → light regex check based on declared format
   │  also: total length == 200
   ▼
ValidationResult — list of FieldError(column, kind, actual, detail)
```

The two scripts share `fetch_layout()` so they read identical KG facts. Round-trip test (generate → validate) is the demo's "regulation is executable" moment.

---

## 6. Tech stack

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Pydantic v2, `Literal`/`Annotated` polish, type-narrowing |
| Package mgmt | `uv` | fast, lockfile-aware |
| API | FastAPI + uvicorn | Pydantic-native, free OpenAPI, async-ready |
| Data validation | Pydantic v2 with `extra="forbid"` on agent schemas | LLM cannot smuggle extra fields |
| LLM | OpenAI (model = `gpt-5.5` default, see `.env`) | Structured Outputs (strict JSON Schema) — closes a class of agent bugs |
| Graph DB | Neo4j Community, Docker | native graph operations, Cypher, free Browser viz |
| PDF text + rects | PyMuPDF (`fitz`) | `search_for` returns coordinates directly; same library used in the reference contract project |
| PDF rendering (UI) | PDF.js v4.10.38 (CDN) | text layer + canvas, scriptable from JS |
| Frontend | static HTML + ES modules, no build step | one file, instant iteration; the data is interesting, not the UI framework |
| Migrations | Cypher scripts + `make migrate` | constraints + indexes only; no data migrations needed (append-only versioning) |
| Tests | pytest | model + adapter integration |
| Orchestration | Makefile + `uv run python -m scripts.X` | deferred Prefect/Airflow until RHS work |

External hosted services: **only OpenAI** (for Sentinel). Neo4j runs in local Docker; everything else is pure Python.

---

## 7. External integrations

### 7.1 OpenAI

- Adapter: `packages/adapters/shared/llm/openai_adapter.py` (behind `LLMPort`)
- Model: `OPENAI_MODEL` env var, default `gpt-5.5`
- Mode: Structured Outputs (`response_format=SentinelExtraction`) — strict JSON Schema
- Cost discipline: extractions are cached on disk; re-running `rebuild_kg` doesn't re-spend tokens

### 7.2 Neo4j

- Service: `docker-compose.yml` → `neo4j:5-community`
- Bolt: `neo4j://localhost:7687` (driver), Browser: `http://localhost:7474`
- Adapter: `packages/adapters/lhs/gre/neo4j_adapter.py` (behind `GREStore`)
- Constraints: `node_id_unique`, `document_hash_unique` (set by `make migrate`)
- Indexes: `(type, version)`, `effective_from`

### 7.3 PyMuPDF

- Used in two places: `packages/lhs/citations/pdf_highlight.py` (citation rect extraction) and `scripts/parse_record_layout.py` (text extraction for parsing).
- All coordinates in PDF points (72 DPI), top-left origin. Frontend scales by `displayedWidth / pdfPointWidth` to be robust to CSS-shrunken pages.

---

## 8. Deployment topology (today)

```
Developer laptop
├── Docker
│   └── neo4j:5-community  (bolt :7687, http :7474)
│       └── named volume "regulai_neo4j_data"  (persists between restarts)
└── Python venv (.venv)
    ├── uvicorn api.main:app  --reload  --port 8765
    └── scripts/* (make commands)
```

- **No multi-tenancy.** Single carrier, single regulator, single Neo4j database.
- **No cloud yet.** Snowflake materialization sink and any cloud Neo4j (Aura) are deferred to RHS phase.
- **All state is reproducible from disk.** `make rebuild-kg` regenerates the entire KG from `materialized/extractions/*.json` in ~30 seconds without LLM calls.

Future production topology: see `docs/solution-architecture.md` §7.

---

## 9. Cross-cutting concerns

### 9.1 Configuration

`packages/config/settings.py` — Pydantic `BaseSettings`. Every default overridable via `.env`:
- `OPENAI_API_KEY`, `OPENAI_MODEL`
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- `MATERIALIZED_DIR` (defaults to `./materialized/`)

Hard rule: no buried hardcoded constants. Adding a new tunable means adding a settings field, not a literal.

### 9.2 Logging

Currently stdout via `print()` in scripts and FastAPI default logger. Production logging is a TODO (structured logs + correlation ids when bulletin re-eval ships).

### 9.3 Error handling

- Validation errors (Pydantic) bubble up as 422 from FastAPI.
- KG state errors (e.g. missing layout) → 404 with descriptive message.
- LLM failures → propagated; cached extraction is the safety net.
- Parser failures → script exits non-zero; the failing target is named in the rebuild output.

### 9.4 Idempotency

- `materialize()` is idempotent (see §5.3).
- `compute_rects_bundle()` is pure — same inputs always produce same rects.
- `parse_pdf()` is pure — deterministic state machine over the PDF text.
- `batch_extract.py` skips docs whose extraction.json exists; `--force` re-runs.

So the entire pipeline can be safely re-run any number of times.

### 9.5 Testing

`tests/` exists as scaffold. The most operationally useful "test" today is the round-trip of `make generate-sample | make validate-sample` — a genuine self-check that the KG facts are consistent.

---

## 10. Architectural rules and constraints

These are load-bearing — breaking any of them would erode the value of the design:

1. **The closed vocabulary is closed.** Adding a node or relationship type is a 4-file PR (`enums.py` → `nodes.py` → `node_factory.py` → `prompts.py`). The LLM is not allowed to invent types per-document.
2. **Domain logic imports `ports/` only, never `adapters/`.** The actual KG implementation (Neo4j today, possibly Aura later) is swappable. No Cypher leakage outside `packages/adapters/lhs/gre/`.
3. **Every fact in the KG has provenance.** Every node has either a `CITES` edge to its source `RegulationDocument` or is a hand-seeded canonical entity (Organizations, edition headers). No free-floating facts.
4. **The deterministic parser owns tabular content.** Sentinel never emits `FieldRequirement` / `RecordLayout` / `CodeList` / `CodeValue` for documents in `WIRE_LAYOUTS_FOR_SLUG`. (Enforcement is a TODO — task #32 in the tracker.)
5. **Versioning is append-only.** Rules don't UPDATE; they get a new version + `SUPERSEDES`. This is what makes "what was the rule on 2024-06-15?" a query, not a guess.
6. **All defaults overridable via Pydantic settings + `.env`.** No buried hardcoded config.
7. **No data leaves the filesystem casually.** PDFs, extractions, snapshots all in `materialized/`. New side outputs go there too (e.g. `materialized/validation/`).
8. **The frontend is dumb.** UI does no business logic — just renders what the API gives it and hands user actions back. All judgment lives in `packages/lhs/`.

---

## 11. File-tree map by intent

If you want to change… | edit…
---|---
how a document is registered for the UI | `api/registry.py`
which docs are parser-owned | `api/registry.py:WIRE_LAYOUTS_FOR_SLUG`
the closed vocabulary | `packages/core/enums.py` then `nodes.py` then `node_factory.py` then `sentinel/prompts.py`
LLM extraction prompt | `packages/lhs/sentinel/prompts.py`
how Sentinel calls the LLM | `packages/lhs/sentinel/agent.py`
the deterministic parser | `scripts/parse_record_layout.py` (regexes near the top, state machine in `parse_pdf`)
how proposals materialize | `packages/lhs/materialization/materialize.py` (5 phases)
which Neo4j queries fire | `packages/adapters/lhs/gre/neo4j_adapter.py` (or `packages/lhs/kg/queries.py` for canonical templates)
how citations get PDF rects | `packages/lhs/citations/pdf_highlight.py`
the side-by-side UI | `ui/regulations.html` (single file, ES modules)
the API | `api/main.py`
how to validate a submission | `scripts/validate_submission.py` + `/api/layouts/{name}/validate`
how to generate a sample | `scripts/generate_sample_submission.py` + `/api/layouts/{name}/sample`
the rebuild orchestration | `scripts/rebuild_kg.py`
the cleanup logic | `scripts/cleanup_kg.py`
the coverage validator | `scripts/validate_kg_coverage.py`

---

## 12. Open architectural decisions

Tracked as tasks (see `make` output / `TaskList`):

- **#31 Bulletin re-evaluation flow** — the LHS-4 demo headliner. Schema (`BulletinOverride`, `OVERRIDES`, `effective_from/to`, `SUPERSEDES`) exists; the UI/diff flow that bumps versions and re-evaluates in-flight content is what's left.
- **#32 Tighten Sentinel prompt** to forbid emitting parser-owned types for parser-owned slugs.
- **#33 Parser quality nits** — expand range codes (`1-9` → `1..9`), strip footnote markers (`*1` → `1`).
- **#34 `neovis.js` live-graph render** in the side-by-side UI (currently entity cards only).

After RHS work begins (out of LHS scope):

- Snowflake materialization sink (currently JSON-on-disk).
- Bridge agent (record classifier consulting the KG).
- Multi-tenant deployment.

---

## 13. References

- `docs/poc-decisions.md` — running decision log (chronological)
- `docs/lhs-build-plan.md` — execution plan with sub-phases LHS-0..LHS-4
- `docs/kg-schema.md` — full property catalogue per node type
- `docs/lhs-research.md` — regulation research that justified the schema
- `docs/skills.md` — operational know-how (Cypher patterns, OpenAI quirks)
- `docs/solution-architecture.md` — business framing of this technical view
- `docs/how-it-works.md` — operational runbook
