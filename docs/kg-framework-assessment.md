# RegulAI — Neo4j KG Framework Assessment

**Last updated**: 2026-05-19
**Purpose**: an honest audit of the knowledge-graph framework — what it does well, where it's thin, and what would need to change to scale beyond the demo. Based on direct inspection of the running graph, the materialization layer, and the validators.

**Companion docs**: [`kg-schema.md`](kg-schema.md) (formal schema), [`technical-architecture.md`](technical-architecture.md) (LHS architecture), [`enterprise-readiness.md`](enterprise-readiness.md) (production gaps).

---

## Headline assessment

**The KG framework is the strongest part of the platform.** It got the hard design decisions right (closed vocabulary, citation grounding, versioning primitives, deterministic + LLM hybrid extraction, idempotent materialization). The architectural thesis — *regulation as queryable data with provenance* — is provable and reproducible end-to-end via `make rebuild-kg`.

**Where it's thin**: every node is labeled `GRENode` with a type *property* rather than being typed via Neo4j labels. Citation grounding is uneven (100% on Rule nodes, 4% on CodeValue). Versioning is implemented but never pressure-tested (every node is v1 today). There's no audit log on the KG itself. Multi-tenancy isn't designed in. No graph algorithms are used.

For a demo and architectural proof: **A-grade**. For production at multiple carriers: **B-minus** — load-bearing weaknesses are addressable but real.

---

## Inventory (live numbers as of today)

### Nodes — 1,538 total

| Type | Count | Notes |
|---|---|---|
| `CodeValue` | 956 | Individual valid codes (reason codes, cause-of-loss codes, etc.) |
| `FieldRequirement` | 254 | Wire-format column requirements from record-layout PDFs |
| `CodeList` | 179 | Named groupings of CodeValues |
| `Rule` | 88 | Plan-rule canon. **Every one has a citation.** |
| `CoverageType` | 11 | Coverage taxonomy (HO-3, HO-5, etc.) |
| `Organization` | 11 | TICO, TDI, NAIC, Texas Legislature, etc. |
| `ReportTemplate` | 11 | TSPR + related reports |
| `RegulationDocument` | 9 | Source PDFs |
| `RecordLayout` | 6 | 200-column fixed-width layouts |
| `StatPlanEdition` | 3 | Plan versions over time |
| `EndorsementRule` | 3 | Endorsement coding rules |
| `BulletinOverride` | 2 | Bulletin-driven canon overrides |
| `ReconciliationRule` | 2 | Cross-report reconciliation rules |
| `HITLTriggerRule` | 2 | Conditions that pause for human review |

15 typed node classes total (the `NULL`-type row in the live count is a single anomalous node — worth investigating in a cleanup pass).

### Relationships — 1,854 total

| Type | Count | Purpose |
|---|---|---|
| `HAS_VALUE` | 956 | `CodeList → CodeValue` (1:1 with CodeValues — perfect coverage) |
| `CITES` | 358 | Anything → `RegulationDocument` (or `Citation` text snippet) |
| `CONTAINED_IN` | 343 | `FieldRequirement → RecordLayout` (and `Rule → Section`) |
| `CODED_BY` | 172 | `FieldRequirement → CodeList` |
| `APPLIES_TO` | 10 | `Rule → CoverageType` |
| `OVERRIDES` | 4 | `BulletinOverride → Rule/CodeList/CodeValue` |
| `CONTAINS_LAYOUT` | 4 | `ReportTemplate → RecordLayout` |
| `REQUIRES` | 3 | `Rule → Rule` (companionship) |
| `RECONCILES_WITH` | 2 | `ReconciliationRule → RecordLayout` |
| `DESIGNATED_BY` | 2 | `RegulationDocument → Organization` |

### Constraints + indexes

- **Constraints (2)**: `node_id_unique` (GRENode.id), `document_hash_unique` (RegulationDocument.hash)
- **Indexes (8)**: range on `(type, version)`, `effective_from`, `rule_lookup (section, rule_number)`, `codelist_lookup (code_list_name)`, plus token-lookup automatics

The constraint + index inventory is **lean but right** — covers the hot paths (id lookup, type queries, rule navigation) without index sprawl.

---

## What the framework does well

### 1. Closed vocabulary, enforced via Pydantic

Every typed node is a `BaseModel` subclass in `packages/core/nodes.py` (15 classes). Extraction is gated on these types — Sentinel can't emit "RecordLayoutVariant" or "FieldDef" because they don't exist in the schema. This is the single most important design choice: it eliminates the failure mode where LLM extraction produces semantically-identical but textually-different node names ("Cancellation Notice Record Layout" vs "Notice Record Layout" vs "Cancellation/Nonrenewal/Declination Notice Record Layout").

The parser-owned vs Sentinel-owned boundary (clarified 2026-04-26) further reduces drift: tabular record-layout PDFs go to the deterministic parser; prose goes to Sentinel. Mixing them produced 138 orphan fields before the split. **(See `feedback_parser_vs_llm.md` in the memory store.)**

### 2. Citation grounding — perfect where it matters most

| Type | Citation coverage |
|---|---|
| `Rule` | **100%** (88/88) |
| `RegulationDocument` | 100% (9/9) |
| `FieldRequirement` | 58% (148/254) |
| `RecordLayout` | 50% (3/6) |
| `CodeValue` | 4% (36/956) |
| `CodeList` | 4% (8/179) |

The 100% on Rule is the load-bearing claim of the platform — every rule that can ever flag a record traces to a citation. The lower numbers on CodeValue / CodeList are mostly fine: an individual code's "citation" is typically the parent CodeList's citation, and the chain is reachable via `CodeValue ← HAS_VALUE → CodeList → CITES`. But it'd be cleaner to materialize the parent's citation onto each CodeValue, or to express it as a path query, rather than leaving the column null.

The PyMuPDF rect-based citation system (`rects_json` on CITES) means citations carry the actual PDF page coordinates — you can render the highlighted region in the source PDF. That's far better than text-search-based provenance.

### 3. Versioning + supersession

Every typed node has a `version` property and an `effective_from / effective_until` range. The `BulletinOverride` mechanism + `OVERRIDES` edges + `apply_bulletin.py` give a working canon-versioning story:

```cypher
MATCH (b:GRENode {type: 'BulletinOverride'})-[r:OVERRIDES]->(target)
RETURN b.name AS bulletin, target.name AS overrides, target.type
```

Returns 4 active overrides today (named storm cause of loss override, B-0008-25 reason-code update). The flow is demonstrably end-to-end: bulletin → KG version bump → reference SQL regenerate → next pipeline run sees the change.

**Caveat**: every node is currently `version=1`. The versioning machinery exists and is tested *in code paths*, but the **graph itself has never carried a v2 node alongside its v1 predecessor**. When a real bulletin lands and creates v2, edge cases around "which version do I read?" will surface that today's tests don't exercise.

### 4. Coverage validator is a real correctness gate

`make validate-kg` confirms every wire-format layout has its 200 columns fully accounted for, no overlaps, no orphans:

```
✓ Homeowners Premium Record Layout — 52 fields, 41 with code-lists (235 total codes)
✓ Loss Record Layout — 59 fields, 39 with code-lists (212 total codes)
✓ Notice Count Record Layout — 10 fields, 7 with code-lists (19 total codes)
✓ Notice Record Layout — 14 fields, 12 with code-lists (50 total codes)
✓ Premium Record Layout — 71 fields, 41 with code-lists (265 total codes)
```

This is the KG's contract: *if you ask for the layout of a Notice record, every byte 1..200 is described*. Validator exits non-zero on any gap. **This is the single best correctness gate in the entire codebase**, RHS included.

### 5. Idempotent `materialize()`

`Neo4jGREAdapter.create_relationship` uses MERGE keyed on natural identifiers (`(src, dst, char_start, char_end)` for CITES; `(src, dst, type)` for the rest). Re-running extraction doesn't accumulate duplicate edges. `make rebuild-kg` wipes + reseeds + replays cached extractions + reparses; deterministic re-runs from disk in ~30 seconds with no LLM calls.

This is what makes the KG *the* source of truth defensibly. Everything downstream (REFERENCE SQL, validation rules, BRONZE_REGDOCS) can be regenerated from the KG, and the KG can be regenerated from disk. End-to-end reproducibility.

### 6. Deterministic + LLM hybrid extraction

- **Sentinel** (LLM) handles prose: bulletins, statute text, plan introductions
- **Parser** (PyMuPDF state machine) handles tabular wire-format PDFs: stat plan Sections C/D/E/G, TICO record layout

Both flow through the **same** `materialize()` pipeline. This means the contract (closed vocabulary, idempotent merge, citation grounding) holds regardless of source. Most LLM-KG projects fail at this boundary; RegulAI got it right.

---

## What's thin or missing

### 1. Type-as-property vs type-as-label

Every node is labeled just `GRENode` and carries a `type` property. So queries that should be:

```cypher
MATCH (r:Rule) WHERE r.section = 'A' RETURN r
```

Are actually:

```cypher
MATCH (r:GRENode {type: 'Rule'}) WHERE r.section = 'A' RETURN r
```

The index `node_type_version` covers the lookup, so performance isn't catastrophic. But this loses Neo4j's native label-based query optimizer and makes Cypher queries harder to read. Every consumer of the graph (RHS scripts, validators, the workstation API) has to know to filter on `type`.

**Why it was done this way**: it simplifies the materialization layer — one CREATE statement for all node types, with `type` as a discriminator. The 246-line `neo4j_adapter.py` is part of the reward.

**What it would take to fix**: change `CREATE (n:GRENode {…})` to `CREATE (n:GRENode:Rule {…})` (dual-label, preserving the existing query path while enabling cleaner native queries). One-line change in `node_factory.py`, plus a re-seed. Backward-compatible.

### 2. No KG-side audit log

The RHS side has `GOLD_AUDIT.USER_ACTION` capturing every state change, every fix, every approval. The KG side has **nothing equivalent**. If someone runs `apply_credit_score_bulletin.py`, the only record is the resulting `BulletinOverride` node + the modified `CodeValue` version — no "who, when, why" entry.

For a regulator asking "when did Rule A.34 change, and who approved the change?", the answer requires correlating git history with file timestamps. Not enterprise-defensible.

**Fix**: introduce a `KGAuditEntry` typed node + `MUTATED_BY` edge, captured by `materialize()` whenever a non-idempotent operation runs.

### 3. Versioning untested under pressure

As noted: every node is v1. The version model is *designed correctly* (version + effective_from + effective_until + OVERRIDES edges), but the runtime behavior under "two versions of the same Rule coexist" hasn't been exercised. Specifically:
- Does the reference-SQL builder pick the right one (presumably the one with `effective_until IS NULL`)?
- What happens to FILING_EXCEPTIONS that reference the old version?
- Can a customer query "what was Rule A.34 on 2025-12-01"?

These should all work given the schema, but they're hypothetical until tested.

### 4. Citation grounding uneven on CodeValue/CodeList

4% citation coverage on CodeValue (36/956) and CodeList (8/179) is fine if the **parent** carries the citation and the chain is queryable. But the workstation's "View regulator text →" button works best when the rule's `citation_pattern` matches a section in the regulation, and a CodeValue-level citation would be more precise.

**Fix**: in the materializer, propagate parent CodeList's citation onto each CodeValue at extraction time. Cosmetic but improves drill-down precision.

### 5. No graph algorithms used

The KG is rich enough for real graph queries:
- **Impact analysis** — "if I change Rule A.34, what FieldRequirements, CodeLists, RecordLayouts, and downstream Snowflake tables are affected?"
- **Companion-rule traversal** — "find all rules that REQUIRE Rule A.34"
- **Citation density** — "which paragraphs of the plan are most cited?"

Today these are written as ad-hoc Cypher in scripts. Neo4j Graph Data Science library (free for community edition) gives a clean API for traversal, PageRank, shortest-path analysis. Worth wiring up.

### 6. Multi-tenancy not designed in

Today: one Neo4j instance, one global canon. For customer #2 (a different carrier), there are three options:
1. **Same canon, customer-scoped overrides** — only works if every customer files the exact same TX plan. Probably true for TSPR; not for LOB-specific filings.
2. **Per-customer database** in Neo4j (Aura supports this).
3. **Label scoping** — `(:Rule:Tenant_acme)` vs `(:Rule:Tenant_widget)`.

The schema doesn't enforce any of these. Picking the wrong path now creates painful migration later.

### 7. No GraphQL / GQL surface

The KG is consumed via vanilla Cypher embedded in Python scripts. Each script knows how to query for what it needs:
- `build_reference_reason_codes.py` knows how to walk `CodeList → HAS_VALUE → CodeValue`
- `build_validation_rules_reference.py` knows how to walk `Rule → CITES → RegulationDocument`
- API endpoints like `/kg/neighborhood/{rule_id}` write Cypher inline

This is fine for trusted scripts. For a customer-facing API surface or third-party integration (auditor's tool reading the KG), a GraphQL layer (Neo4j has built-in GraphQL support via `@neo4j/graphql`) would be cleaner.

### 8. Test coverage on adapter is thin

`tests/test_neo4j_adapter.py` exists. Coverage of `Neo4jGREAdapter` is incomplete — happy-path is exercised but rollback/conflict cases aren't.

### 9. No diff viewer

When a bulletin lands and the KG changes, the only way to inspect the diff is to query before/after states manually. A `/kg/diff?from=v1&to=v2` endpoint that returns the structured change set would make audit trivial.

### 10. The "NULL type" node

The inventory shows one node with `type=NULL`. Probably an extraction error or a partially-materialized node. Worth a cleanup pass.

---

## Comparison: how this stacks up against typical KG projects

For context — most LLM + KG projects fail at specific predictable points. Here's where RegulAI stands:

| Common KG failure mode | RegulAI status |
|---|---|
| LLM emits semantically-equivalent but textually-different node names | ✅ Solved via closed vocabulary + parser/Sentinel split |
| Citation grounding is decorative, not navigable | ✅ Solved — citations carry PDF rects, every Rule has one |
| Schema drift between extractions | ✅ Pydantic enforces; `make rebuild-kg` proves idempotency |
| No way to update without re-extracting | ✅ Solved via bulletin override + version supersession |
| Graph queries embedded in app code, brittle to refactor | ⚠️ Partially — Cypher is centralized in scripts but not abstracted into a query layer |
| Type-as-label not used; uniform supertype | ⚠️ Present — uniform `GRENode` label, type in property |
| No audit log on the graph itself | ❌ Missing |
| Multi-tenancy not designed in | ❌ Missing |
| Graph algorithms never used despite the graph structure | ❌ Missing |
| Brittle to "v2 of an existing entity exists" | ⚠️ Designed but untested |

5 of 10 solid, 3 partial, 2 missing — well above the median for LLM+KG projects.

---

## Where I'd invest next

If you gave me a week to harden the KG, in order:

1. **Add KG audit log** (1-2 days) — `KGAuditEntry` typed node + `MUTATED_BY` edge captured by `materialize()`. Closes the biggest enterprise gap.
2. **Pressure-test versioning end-to-end** (2 days) — create a fictional v2 of Rule A.34, exercise every consumer (reference SQL builder, validation engine, workstation API) to find what breaks. Likely 1-2 bugs to fix.
3. **Add dual-labels** (half day) — `(:GRENode:Rule)` etc. Backward-compatible, enables native-label queries.
4. **Diff endpoint** (1 day) — `GET /api/lhs/kg/diff?from_canon=v1&to_canon=v2` returning structured node + edge changes.
5. **Fix the NULL-type node + propagate parent citations to CodeValue** (half day) — hygiene pass.
6. **Wire neo4j-graphql** (1 day) — exposes the KG as a typed GraphQL surface for the workstation and any future consumers.

After those: multi-tenant strategy is a 2-3 week project; graph algorithms (impact analysis, companionship traversal) is another 1-2 weeks. Both are scale issues, not v1.

---

## Bottom line

The KG framework is **the single best-designed piece of the platform**. It's the architectural choice that makes everything else defensible — the regulation is queryable data, with provenance, with versioning, and the graph can be regenerated from disk. The thing it was built to prove (regulation drives the data plane, not the other way around) is provable.

The gaps are real but tractable. Most are about *closing the loop on enterprise concerns* (audit log, multi-tenancy, version pressure) rather than redesigning anything fundamental. The schema, materialization layer, and validator are sound — none of them needs to change to fix the gaps.

**Recommendation**: harden the six items above before the first customer pilot. Defer multi-tenancy + graph algorithms until customer #2.
