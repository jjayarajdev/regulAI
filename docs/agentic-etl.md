# Agentic ETL — Source Onboarding

How RegulAI onboards an arbitrary insurer's data file onto its canonical model
using an LLM to **propose** the mapping and deterministic code to **run** it.

- **Code:** `packages/rhs/mapper/`, `api/mapping_demo.py`, `ui/mapping-review.html`,
  `scripts/propose_mapping.py`
- **UI:** `/admin/mapping` · **CLI:** `python -m scripts.propose_mapping`
- **Sample data:** `data/samples/*.csv`

## The problem it solves

Onboarding a new insurer's data used to mean an engineer hand-writing an
`INSERT INTO SILVER.TSPR_* SELECT …` in `scripts/run_silver.py` — a bespoke
mapping per source schema. Any carrier whose columns aren't already
Guidewire-shaped can't be onboarded without code.

Agentic ETL turns that into a **generated, reviewable artifact**: point it at a
file, and an agent proposes how each source column maps onto the canonical
target — with confidence scores, auto-repairs, and the risky bits flagged for a
human. The 80% that's mechanical is automated; the 20% that needs judgment is
escalated, never guessed.

## Design philosophy

Three principles, all deliberate:

1. **The LLM authors config, not data.** The agent produces a *mapping spec*
   (which source column → which target column, with a SQL transform). It never
   sees or transforms the actual rows. Deterministic code compiles and runs the
   spec. This keeps the data plane cheap, reproducible, and auditable — the same
   "rules-as-data" discipline the validation engine already uses.

2. **It mirrors the LHS Sentinel.** `packages/lhs/sentinel` turns a messy
   *regulation document* into a structured, confidence-scored extraction. This is
   the same shape on the *data* plane: a messy *source dataset* → a structured,
   confidence-scored mapping. Same `extract_structured` LLM port, same
   propose→review→materialize flow.

3. **Fail-closed.** A required target the agent couldn't confidently map is left
   unaccepted; the validator then **rejects the load** rather than shipping a
   filing with missing regulatory fields. A partial mapping must not pass as
   complete.

## The pipeline

```
 ┌──────────┐   ┌───────────┐   ┌──────────┐   ┌───────────┐   ┌────────────┐
 │ 1 PROFILE│──▶│ 2 PROPOSE │──▶│ 3 REVIEW │──▶│ 4 COMPILE │──▶│ 5 VALIDATE │
 │ (determin│   │  (agent)  │   │ (human)  │   │ (determin │   │(fail-closed│
 │  -istic) │   │           │   │          │   │  -istic)  │   │  DuckDB)   │
 └──────────┘   └───────────┘   └──────────┘   └───────────┘   └────────────┘
  columns,       MappingSpec:     accept /       INSERT…SELECT    row parity,
  types, null    src→target +     override        (accepted        required
  rate, samples  transform +      each row        rows only)       non-null,
                 confidence +                                      numeric
                 needs_review                                      conformance
```

Only **stages 2 and 3 involve a human or a model.** Stages 1, 4, 5 are pure,
deterministic code.

## Components

| File | Stage | Role |
|---|---|---|
| `mapper/profiler.py` | 1 | Reads CSV/Parquet (via pyarrow), returns a `SourceProfile`: per-column inferred type, null rate, distinct count, sample values. Caps the scan at 5,000 rows so a huge file stays cheap. **No LLM.** |
| `mapper/target_schema.py` | — | The canonical **target contract** as data: `TSPR_PREMIUM_STAGING` columns with human-readable semantics and `required` / `domain_encoded` / `system_populated` flags. This is what makes good mapping possible — the agent maps *to* a described target. |
| `mapper/schema.py` | — | Pydantic contracts: `SourceProfile`, `MappingSpec` (`ProposedMapping[]`, `UnmappedSourceColumn[]`). Flat and default-free so they round-trip through strict structured-output parsing. |
| `mapper/prompts.py` | 2 | The constrained system prompt: bridge an arbitrary source to a *known* target; never invent columns; flag domain-encoded/low-confidence targets for review; list unmapped columns. |
| `mapper/agent.py` | 2 | `SchemaMapper` — LLM-agnostic (depends only on an `LLMPort.extract_structured` protocol). `map(profile) → MappingSpec`. |
| `mapper/compiler.py` | 4 | `compile_spec(spec, source)` → `INSERT INTO target (...) SELECT <transforms> FROM <source>`. Compiles **accepted, non-NULL** rows only; reports the excluded ones. |
| `mapper/validator.py` | 5 | `validate_compiled(compiled)` runs the projection on an **ephemeral in-memory DuckDB** and checks it fail-closed. |
| `api/mapping_demo.py` | all | FastAPI router wiring the stages to the UI. |
| `ui/mapping-review.html` | 2–5 | The `/admin/mapping` review page. |
| `scripts/propose_mapping.py` | 1–2 | CLI mirror of `scripts/extract.py`. |

### Stage 1 — Profile (`profiler.py`)

Deterministic. Given a file it returns:

```
SourceProfile
├─ source_label, row_count, sampled_rows
└─ columns: [ ColumnProfile{ name, inferred_type, null_rate, distinct_count, sample_values } ]
```

The profile — **not the raw rows** — is what the agent reasons over. This bounds
token cost and keeps the data plane out of the model.

### Stage 2 — Propose (`agent.py` + `prompts.py` + `target_schema.py`)

`SchemaMapper.map(profile)` sends the system prompt (which embeds the rendered
target contract) plus the profile JSON to the LLM's structured-output endpoint,
and gets back a validated `MappingSpec`:

```
MappingSpec
├─ source_label, target_table
├─ mappings: [ ProposedMapping{
│      target_column, source_column|null, transform_sql,
│      confidence (0..1), rationale, needs_review } ]
├─ unmapped_source_columns: [ { name, reason } ]
└─ notes
```

Guardrails baked into the prompt:
- **Domain-encoded** targets (e.g. the TSPR MMDDY/MMY date encodings) → identify
  the source column but set `needs_review=true`; don't guess the encoding.
- **Required target, no clear source** → `source_column=null`, `transform="NULL"`,
  low confidence, `needs_review=true`.
- **System-populated** targets (run id, accounting month, …) are excluded from the
  contract, so the agent never maps them.
- Every unmapped source column is listed with a reason.

### Stage 3 — Review (`ui/mapping-review.html`)

The spec renders as an editable table: confident rows pre-ticked, `needs_review`
rows highlighted. A human accepts/overrides each row (source column + transform),
then saves. The reviewed spec persists to
`materialized/mappings/<label>.reviewed.json` — versioned, auditable config.

### Stage 4 — Compile (`compiler.py`)

`compile_spec` emits two SQL forms:
- `insert_sql` — the portable `INSERT INTO <target> (...) SELECT …` for the real
  pipeline, run through the `query()` engine seam (Databricks/DuckDB/Snowflake).
- `select_sql` — a self-contained projection over the source file that the
  validator dry-runs locally.

Only **accepted, non-NULL** mappings are compiled. Excluded rows (unaccepted, or
`NULL` transforms) are returned in `excluded` with a reason — never silently
defaulted.

### Stage 5 — Validate (`validator.py`)

Runs `select_sql` on an ephemeral in-memory DuckDB (a small Spark→DuckDB shim
adapts the few dialect differences, e.g. `STRING`→`VARCHAR`) and checks:

- **`row_count_parity`** — output rows == source rows (no silent drop/fan-out).
- **`required:<col>`** — every required, non-system target is present and non-null.
  A required target excluded in review **fails here by design.**
- **`numeric:<col>`** — number-typed targets actually landed numeric.

`ok` is true only if every check passes.

## API (`/api/mapping`)

| Method · Path | Purpose |
|---|---|
| `GET /samples` | List onboardable files in `data/samples`. |
| `GET /preview?source=&limit=` | First N rows of a file (blank cells shown as `∅`). |
| `POST /propose {source}` | Profile + agent → `{profile, spec}`; persists the raw spec. |
| `POST /save {label, spec}` | Persist a human-reviewed spec. |
| `GET /spec/{label}` | Reviewed spec if present, else the raw proposed one. |
| `POST /compile {label}` | Reviewed spec → SQL (`sql`, `select_sql`, `columns`, `excluded`). |
| `POST /validate {label}` | Dry-run the compiled load and return the fail-closed report. |

## CLI

```bash
# deterministic profile only — no API key needed
uv run python -m scripts.propose_mapping data/samples/acme_home_policies.csv --profile-only

# full: profile → agent → spec (writes materialized/mappings/<label>.mapping.json)
uv run python -m scripts.propose_mapping data/samples/acme_home_policies.csv
```

Requires `OPENAI_API_KEY` (and `OPENAI_MODEL`) in `.env` for the agent call.

## Worked example

The sample datasets exercise the pipeline across a quality gradient:

| File | Quality | Behaviour |
|---|---|---|
| `northstar_home_good.csv` | good | near-canonical names, complete → **21 mapped, 3 review, 0 unmapped** |
| `harborpoint_ok.csv` | ok | abbreviations, one combined premium, free-text notes → more review + unmapped |
| `legacy_dump_bad.csv` | bad | cryptic headers, `$325,000` money-as-strings, blank required NAIC, junk cols → low confidence; validator **fails hard** |
| `acme_home_policies.csv` | — | the original demo file |

Observed agent judgement on the good file (not prompted for):
- `zip` read as `int64` → auto-repaired with `lpad(CAST(zip AS STRING), 9, '0')`,
  flagged for review (dropped leading zeros).
- `protection_class` → `PPC_SIMPLE` (correctly declined `PPC_SPLIT`).
- `underwriting_notes` → unmapped free-text.

And the validate result on `acme` is a **correct fail-closed**:

```
overall ok: FALSE
  PASS  row_count_parity — source=8 output=8
  PASS  required:NAIC_COMPANY_NO — populated, no nulls
  PASS  required:POLICY_ID — populated, no nulls
  FAIL  required:EFFECTIVE_DATE — excluded in review, needs curation/SME sign-off
  FAIL  required:EXPIRY_DATE  — excluded in review, needs curation/SME sign-off
  PASS  numeric:* (9 columns landed BIGINT)
```

The FAIL is the system working: the agent confidently mapped 16 columns but
refused to guess the TSPR date encodings, so the gate blocked a filing missing
required regulatory fields. Curate those two transforms, re-validate, and it
goes green.

## Extending it

- **New target table** — add a contract list in `target_schema.py` (columns +
  semantics + flags) and point the mapper at it. The rest is unchanged.
- **Swap the model** — implement the `LLMPort.extract_structured` protocol
  (e.g. an Anthropic/Claude adapter) and pass it to `SchemaMapper`.
- **New source format** — extend `profiler._read_table` (CSV/Parquet today).

## Limits & production notes

- Proven on **small, synthetic files**. Real sources bring dirty types,
  inconsistent codes, and multi-table joins — the profiler and prompt need
  hardening for those.
- The validator dry-runs on **DuckDB**; production runs the portable `insert_sql`
  through the `query()` seam on the real engine.
- The agent maps **schema**, not domain encodings. Domain logic (TSPR date
  encodings, unit conventions, code translations) stays curated and human-approved.
- Human-in-the-loop review is **non-negotiable** for a compliance product — the
  agent proposes, a person approves, and that approval is the audited artifact.
```
