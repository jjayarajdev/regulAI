# RegulAI

Regulation → Knowledge Graph → executable filing schema, for US property/casualty
statistical reporting (currently scoped to Texas residential property → TICO).

The system reads regulation PDFs (statutes, statistical plans, commissioner
bulletins), extracts a closed-vocabulary KG of every report, every column,
every legal code value — with pixel-perfect citation provenance back to the
source PDF — and lets that KG drive submission generation and validation.

## What works today (LHS slice, 2026-04-26)

```
$ make e2e
... 6/6 layouts ✓ Fully covers cols 1..200 ...
REGRESSION TEST: PASS
```

| Capability | Command | Status |
|---|---|---|
| One-command reproducible KG rebuild from disk | `make rebuild-kg` | ✅ |
| Coverage validator for every wire-format layout | `make validate-kg` | ✅ |
| Generate a valid 200-char TICO submission *from the KG* | `make generate-sample` | ✅ |
| Validate any submission against the KG | `make validate-sample` | ✅ |
| Rules-level loop: bulletin → version-bump → re-evaluate | `make apply-bulletin ALL=1 && make demo-bulletin` | ✅ |
| Side-by-side review UI with Wire Format Studio | `make ui` → http://localhost:8765 | ✅ |
| Round-trip regression test | `make e2e` | ✅ |

## Reading order

For a developer:
1. [`docs/solution-architecture.md`](docs/solution-architecture.md) — what problem and why
2. [`docs/how-it-works.md`](docs/how-it-works.md) — operational runbook (start here to actually run it)
3. [`docs/technical-architecture.md`](docs/technical-architecture.md) — how it's built
4. [`docs/poc-decisions.md`](docs/poc-decisions.md) — chronological decision log
5. [`docs/kg-schema.md`](docs/kg-schema.md) — closed-vocabulary catalogue (14 node types, 12 rel types)

For a product / strategy reviewer: read just `docs/solution-architecture.md`.

## Quickstart

```bash
make install                # uv sync
cp .env.example .env        # add your OPENAI_API_KEY
make up                     # Neo4j in Docker
make migrate
make rebuild-kg             # ~30s, fully reproducible from on-disk extractions; no LLM tokens
make e2e                    # round-trip regression
make ui                     # open http://localhost:8765
```

Then in the UI, pick **TICO Stat Plan — Section C**, click any FieldRequirement
on the right → the source PDF rectangle is highlighted on the left, and the
**Wire Format Studio** at the top right shows a generated 200-char Premium
record with column-by-column annotation.

## Architecture in one paragraph

LHS = RHS, with the KG as contract.

**LHS (this repo)**: regulation PDFs → Sentinel LLM (for prose) + deterministic
PyMuPDF parser (for tabular wire layouts) → proposal JSON on disk → idempotent
`materialize()` → Neo4j KG with closed vocabulary, citation provenance, and
append-only versioning. Side-by-side review UI for compliance officers; sample-
record generator and validator for proving the KG is operationally complete.

**RHS (future)**: source-system data (Guidewire, etc.) → Snowflake medallion
(Bronze/Silver/Gold) → Bridge agent classifies records, consulting the KG →
edit-checked Gold marts → real TICO transmittal file.

The KG is read by every other component and authored only through review;
hardcoded regulatory rules anywhere in the pipeline are an antipattern.

## Status

LHS slice: operational. RHS: next. Open work tracked in
[`docs/poc-decisions.md`](docs/poc-decisions.md) "Build status snapshot."
