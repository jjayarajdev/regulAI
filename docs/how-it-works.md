# RegulAI — How It Works (Operational Runbook)

**Last updated**: 2026-05-18
**Companion docs**: [`technical-architecture.md`](technical-architecture.md) (LHS), [`rhs-build-summary.md`](rhs-build-summary.md) (RHS — medallion pipeline + workflow + ASCII renderer + audit), [`solution-architecture.md`](solution-architecture.md) (business framing).
**Audience**: anyone running, demoing, or extending RegulAI today.

This is the "open the laptop, do the thing" guide. If something here is wrong, the runbook is wrong — fix it here first.

For the RHS (Snowflake medallion + filing workflow + ASCII renderer), the canonical demo entry point is now the **integrated workstation at `/workstation`** — see [`rhs-build-summary.md`](rhs-build-summary.md) for the architecture and the API reference. The bring-up sequence below is for the LHS (KG extraction, materialization) side.

---

## 1. Prerequisites

- macOS / Linux (instructions are zsh / bash; Windows via WSL works too).
- Python 3.11+ (`python3 --version`).
- Docker + docker compose (for Neo4j).
- `uv` package manager — install with `curl -LsSf https://astral.sh/uv/install.sh | sh`.
- An OpenAI API key (Sentinel needs it for *new* LLM extractions; cached extractions don't).

Working directory: `/Users/jjayaraj/workspaces/studios/regulAI` (substitute your local clone path).

---

## 2. First-time setup

```bash
# 1) Install Python deps into .venv
make install                # = uv sync --extra dev

# 2) Provide config
cp .env.example .env
$EDITOR .env                # set OPENAI_API_KEY at minimum

# 3) Bring up Neo4j
make up                     # docker compose up -d neo4j; waits until http://localhost:7474 responds
                            # default creds: neo4j / regulai-dev-password

# 4) Migrate (constraints + indexes)
make migrate

# 5) Smoke test the round-trip (writes/reads a node)
make smoke

# 6) Bring up the API + UI
make ui                     # starts uvicorn at http://localhost:8765 (auto-reload)
```

If `make smoke` passes and `http://localhost:8765/api/health` returns `{"status":"ok",...}`, the foundation is up.

---

## 3. The one-shot reproducible bring-up

Once the prerequisites are in place, **the entire KG can be rebuilt from disk in ~30 seconds with no LLM calls**:

```bash
make rebuild-kg
```

What it does:
1. Wipes Neo4j (`gre.wipe_all()`).
2. Re-applies migrations.
3. Runs `scripts/seed.py` — the hand-crafted regulatory canon (3 RegulationDocuments, 7 Rules, organisations, edition, etc.).
4. Replays every cached LLM extraction in `materialized/extractions/*.extraction.json` for prose docs (Sections A, B, F, HB 2067, bulletin) — same `materialize()` path the API uses.
5. Runs `scripts/parse_record_layout.py` — the deterministic parser owns Sections C, D, E, G plus the Homeowners record-layout PDF.
6. Runs `scripts/cleanup_kg.py` — drops phantom layouts and orphan FieldRequirements left over from any earlier LLM-only run.

Final state, deterministic: ~1500 nodes, ~1900 relationships, 6 RecordLayouts at 200/200 column coverage.

```bash
make validate-kg            # must print "PASS — every byte of every populated layout is accounted for."
```

If `validate-kg` ever fails, the rebuild is the recovery: `make rebuild-kg && make validate-kg`.

---

## 4. The four primary workflows

### 4.1 Browse the regulatory KG (Neo4j Browser)

Go to **http://localhost:7474** (creds: `neo4j` / `regulai-dev-password`). Useful starter queries:

```cypher
// Everything (cap to keep browser responsive)
MATCH (n) RETURN n LIMIT 100

// Every Rule with its containing document
MATCH (d:RegulationDocument)<-[:CONTAINED_IN]-(r:Rule) RETURN d, r

// Premium record layout — full structure
MATCH (l:RecordLayout {name: "Premium Record Layout"})<-[:CONTAINED_IN]-(f:FieldRequirement)
OPTIONAL MATCH (f)-[:CODED_BY]->(cl:CodeList)-[:HAS_VALUE]->(cv:CodeValue)
RETURN l, f, cl, cv LIMIT 200

// What goes in column 5–6 of a Premium record?
MATCH (f:FieldRequirement {field_name: "Record Type"})-[:CODED_BY]->(cl:CodeList)-[:HAS_VALUE]->(cv:CodeValue)
RETURN f.position_start AS col, cv.code AS code, cv.notes AS meaning
ORDER BY cv.code

// Provenance: every field with PDF rectangles
MATCH (f:FieldRequirement)-[c:CITES]->(d:RegulationDocument)
WHERE c.rects_json IS NOT NULL
RETURN f.field_name, f.position_start, c.char_start, c.char_end, size(c.rects_json) AS rect_bytes
ORDER BY f.position_start LIMIT 20

// All rule versions ever seen for Rule A.28 (versioning view)
MATCH path = (newest:Rule {name: "Rule A.28 — Designated Statistical Agent"})-[:SUPERSEDES*0..]->(older:Rule)
RETURN newest, older, path
```

The Browser is the fastest tool for ad-hoc questions. Save useful ones.

### 4.2 Review a regulation in the side-by-side UI

```bash
make ui    # if not already running
open http://localhost:8765
```

In the dropdown, pick any document — the Stat Plan sections, HB 2067, the synthetic bulletin, or the Homeowners record-layout PDF.

You'll see three panes:

1. **Left (Source PDF)** — PDF.js renders the actual document. Auto-scrolls to the section's start page.
2. **Middle (Extracted Entities)** — KG nodes grouped by type (RegulationDocument, Rule, FieldRequirement, …). Each card has citation chips like `chars 245-470`. Click a card → highlights the cited PDF region (left). Click a chip → highlights that specific span.
3. **Right (Wire Format Studio)** — appears only for record-layout docs. Auto-generates a 200-character sample record from the KG. Click any column → cross-highlights to the matching FieldRequirement card (middle) and the source PDF row (left).

To re-extract a doc: click **Run Sentinel (GPT-5.5)** at the bottom. To approve into the KG: **Approve → materialize to KG**.

### 4.3 Generate a TICO sample submission

The KG is the spec; the script walks it and emits a record:

```bash
make generate-sample                                  # default: Premium Record Layout, new-policy
# or with options:
uv run python -m scripts.generate_sample_submission \
    --layout "Loss Record Layout" --scenario new-policy --n 3 --annotate
```

Output is exactly 200 characters per record. Add `--annotate` for the column-by-column breakdown.

### 4.4 Validate any submission

```bash
# inline
uv run python -m scripts.validate_submission \
    --layout "Premium Record Layout" \
    --record "<200-char string>"

# file (one record per line)
uv run python -m scripts.validate_submission \
    --layout "Premium Record Layout" --file submissions.txt

# pipe (e.g., feed the generator into the validator)
uv run python -m scripts.generate_sample_submission --layout "Premium Record Layout" --n 5 \
  | grep -E '^[^L]' | uv run python -m scripts.validate_submission --layout "Premium Record Layout"
```

Errors come with kind (`unknown_code`, `bad_format`, `length`, `skip_dirty`, `missing_required`), the actual value seen, the column range, and a human-readable detail.

---

## 5. Diagnostic and validation commands

| Command | Purpose | Pass condition |
|---|---|---|
| `make validate-kg` | KG coverage validator | "PASS — every byte of every populated layout is accounted for." |
| `make smoke` | Neo4j round-trip smoke test | exits 0 |
| `curl -s localhost:8765/api/health` | API liveness | `{"status":"ok",...}` |
| `curl -s localhost:8765/api/kg/stats \| jq` | KG node/rel counts | `total_nodes` ≥ 1500 after rebuild |
| `curl -s localhost:8765/api/regulations \| jq '.documents[].slug'` | Registered docs | 10 entries |
| `curl -s localhost:8765/api/regulations/tico-section-c \| jq '.wire_layouts'` | Wire-layout binding | `["Premium Record Layout"]` |
| `make test` | pytest suite | all green |

---

## 6. Adding a new regulation document

To register a new document:

1. **Drop the source PDF** into `references/regulations/`.
2. **Extract text** so Sentinel has something to read:
   ```bash
   make extract-pdfs    # converts PDFs in references/regulations/ to .txt
   ```
   Or write a plain-text / markdown version directly into `synthetic_regulations/`.
3. **Add a `DocEntry` to `api/registry.py:DOCS`**:
   ```python
   DocEntry(
       slug="my-new-regulation",
       label="My New Regulation",
       category="…appropriate category…",
       path=Path("synthetic_regulations/path/to/text.md"),
       blurb="One-sentence description for the dropdown.",
       pdf_path=REGULATIONS_DIR / "my_new_regulation.pdf",
       pdf_start_page=1,
       pdf_end_page=N,
   ),
   ```
4. **If the doc is a tabular wire-format spec**: add it to `api/registry.py:WIRE_LAYOUTS_FOR_SLUG` and add a corresponding `ParseTarget` to `scripts/parse_record_layout.py:PARSER_TARGETS`. The parser owns it.
5. **Otherwise (prose)**: add it to `scripts/batch_extract.py:DOCUMENTS`. Sentinel will handle it on `make batch-extract`.
6. **Run the extraction**:
   ```bash
   # for prose:
   uv run python -m scripts.extract path/to/text.md
   # for tabular:
   uv run python -m scripts.parse_record_layout
   ```
7. **Materialize**: in the UI, pick the doc and click **Approve → materialize to KG**, OR re-run `make rebuild-kg`.

The new doc will appear in the dropdown with its citation rectangles auto-computed.

---

## 7. Re-extracting after Sentinel/parser changes

Three patterns:

### 7.1 You changed the Sentinel prompt

```bash
make batch-extract-force      # re-runs LLM on every doc, writes new extraction.json files
make compute-rects-force      # re-computes PDF rects (PyMuPDF only — fast, no LLM)
make rebuild-kg               # replays everything into a clean Neo4j
make validate-kg
```

Cost: a full Sentinel run over the corpus is on the order of dollars at GPT-5.5. Don't do this casually.

### 7.2 You changed the parser

```bash
make rebuild-kg               # parser runs as part of the rebuild
make validate-kg
```

No LLM cost. Safe to iterate.

### 7.3 You only changed materialize() / cleanup logic

```bash
make rebuild-kg
```

No re-extraction. The cached extraction.json files are the source of truth.

---

## 8. Inspecting the on-disk artifacts

```
materialized/
├── extractions/                            # the LHS extraction layer
│   ├── section_C_record.extraction.json    # SentinelExtraction or parser output
│   ├── section_C_record.rects.json         # CitationRectsBundle (PyMuPDF rects)
│   └── …                                   # one pair per doc
├── approved/                               # after-materialize snapshots
│   └── tico-section-c.materialized.json    # what landed in Neo4j
└── validation/
    └── kg_coverage.json                    # latest validate-kg report
```

Each `*.extraction.json` is a complete `SentinelExtraction` — `proposed_nodes`, `proposed_relationships`, `citations`, `uncited_spans`, `document_total_chars`. Drop one into a PR and a reviewer can replay it bit-for-bit.

---

## 9. Common debugging recipes

### Neo4j won't start / port conflict

```bash
docker compose ps             # is neo4j up?
docker compose logs neo4j     # what's wrong?
lsof -nP -iTCP:7687           # is something else holding 7687?
make down && make up
```

### "Cannot find DocEntry 'X' or its PDF"

Either the slug isn't in `api/registry.py:DOCS` or the `pdf_path` doesn't exist on disk. Both must match exactly.

### Validator reports `unknown_code` for a value the regulation clearly allows

Most likely a parser quality nit (range codes, footnote markers — see open task #33). Workaround: edit the corresponding CodeList in Neo4j Browser to fix the data, or re-run the parser after applying a parser fix. Do *not* hand-edit `extraction.json` and check it in — the parser regenerates it.

### "Citation not located in PDF"

Either the cited text was a markdown header artifact (the parser/extractor produced text that doesn't exist verbatim in the PDF), or PDF text-layer ordering broke the search. Coverage is 93–95% by design; a few losses are acceptable. Check the console: the UI logs `[citation search]` lines.

### Generated record fails to validate (round-trip)

```bash
uv run python -m scripts.generate_sample_submission --layout "Premium Record Layout" --n 5 --seed 1 \
  | grep -E '^[^L]' | grep -v '^$' \
  > /tmp/samples.txt
uv run python -m scripts.validate_submission --layout "Premium Record Layout" --file /tmp/samples.txt
```

Today, expect 0–3 errors per record from the parser quality nits (`1-9` ranges, `*1` footnote markers). 5/5 PASS is the goal once task #33 is done.

### KG state looks wrong after experimentation

```bash
make rebuild-kg && make validate-kg
```

This is the panic button. It restores from cached extractions in seconds.

---

## 10. Useful Cypher snippets (KG-side)

```cypher
// Coverage for one layout
MATCH (l:RecordLayout {name: $layout})<-[:CONTAINED_IN]-(f:FieldRequirement)
RETURN sum(f.position_length) AS covered_columns,
       count(f) AS field_count

// Find a code value's source rule (CITES chain)
MATCH (cv:CodeValue {code: "WH"})-[:HAS_VALUE]-(cl:CodeList)<-[:CODED_BY]-(f:FieldRequirement)-[:CITES]->(d:RegulationDocument)
RETURN d.name, f.field_name

// All rules superseded since 2026-01-01
MATCH (newer)-[s:SUPERSEDES]->(older:Rule)
WHERE newer.effective_from >= date("2026-01-01")
RETURN older.name, newer.name, newer.effective_from

// Phantom layouts that should not exist (sanity check after rebuild)
MATCH (l:RecordLayout) WHERE NOT (l)<-[:CONTAINED_IN]-(:FieldRequirement) RETURN l.name
//   should return empty after `make rebuild-kg`
```

---

## 11. Glossary

| Term | Definition |
|---|---|
| **LHS** | Left-hand side. Regulatory demand side. What the regulation requires. |
| **RHS** | Right-hand side. Source-system supply side. What the carrier produces. (Future work.) |
| **KG** | Knowledge Graph — the closed-vocabulary, citation-grounded, versioned graph in Neo4j. The contract between LHS and RHS. |
| **GRE** | Governance / Regulation Engine. Synonym for the KG layer in some docs. |
| **Sentinel** | The LHS LLM agent that extracts a `SentinelExtraction` from a regulation document via OpenAI Structured Outputs. |
| **Bridge** | (Future) the RHS LLM agent that classifies records, consulting the KG. |
| **GREStore / Neo4jGREAdapter** | The port + adapter pair that all KG reads/writes go through. |
| **`SentinelExtraction`** | The Pydantic schema both Sentinel and the deterministic parser populate. Common input to `materialize()`. |
| **`materialize()`** | The 5-phase function that turns a `SentinelExtraction` into Neo4j writes. Idempotent. |
| **CITES** | The relationship type carrying span-level provenance. `(any node)-[:CITES {char_start, char_end, rects_json}]->(:RegulationDocument)`. |
| **Wire Format** | The 200-character fixed-width record TICO actually receives, defined column-by-column by the Stat Plan. |
| **Wire Format Studio** | The UI's third pane that generates and validates wire-format records from the KG. |
| **Parser-owned types** | `RecordLayout`, `FieldRequirement`, `CodeList`, `CodeValue` — produced by `scripts/parse_record_layout.py`, never by Sentinel. |
| **Closed vocabulary** | The 14 NodeType + 12 RelationshipType list. Cannot be extended without a deliberate 4-file PR. |
| **TICO** | Texas Insurance Checking Office. TDI's designated statistical agent for residential property. |
| **TDI** | Texas Department of Insurance. The state regulator. |
| **HB 2067** | Texas legislation requiring statistical reporting of cancellations / nonrenewals / declinations. |
| **Materialization snapshot** | `materialized/approved/<slug>.materialized.json` — written after a successful `materialize()` call; the audit trail of what landed in Neo4j. |
| **Coverage** | The percentage of source text covered by citations (`/extraction summary`), and separately the percentage of cols 1..200 covered by FieldRequirements per layout (`make validate-kg`). |

---

## 12. The fastest path to a clean state

If anything is confusing or broken, this restores order:

```bash
make down && make up && make migrate && make rebuild-kg && make validate-kg
```

Should print `PASS` and leave you with a clean reproducible KG. Five commands, ~45 seconds, no LLM calls.
