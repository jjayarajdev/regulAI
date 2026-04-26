# RegulAI — Technical Architecture: Solving the N-to-1 Schema Problem

The N-to-1 schema problem is the actual technical moat. If you solve it elegantly, you win. If you solve it with per-carrier custom ETL, you're a services company pretending to be SaaS.

---

## The Core Architectural Decision: Don't Map Source → Regulatory Directly

The naive approach is to write mappings from each carrier's source schema directly to each state's statistical plan. That's an N×M problem (N carriers × M regulatory plans) and it scales linearly with both dimensions. You'll drown.

Instead, use a **canonical intermediate model** and make it N+M:

```
[Carrier Source] → [CIOM] → [Regulatory Plan]
   N mappings       done    M mappings
                   per-carrier   done once
```

**CIOM = Canonical Insurance Object Model.** Your own tightly-specified object graph: `Policy`, `Coverage`, `Peril`, `Loss`, `Transaction`, `Party`, `Location`, `Claim`. ACORD-informed but tighter — you own the semantics and the invariants.

This gives you two separable problems:

1. **Source → CIOM**: per-carrier work, bounded by how weird their system is
2. **CIOM → Regulatory**: done once per state plan, reused across every carrier

The CIOM is the keystone. Everything downstream depends on it being right.

---

## The GRE Is Actually a Three-Layer Graph

The business plan describes the GRE as the regulatory rule store. That's underspecified. Model it as three linked subgraphs in Neo4j:

```
Regulatory Graph  ←→  Canonical Graph  ←→  Source Graph (per carrier)
(TICO, NAIC,          (CIOM — your         (Guidewire, Duck Creek,
 NCCI, ISO)            ontology)            mainframe, etc.)
```

- **Regulatory subgraph**: code lists, rule nodes, validation predicates, versioned with `valid_from`/`valid_to`
- **Canonical subgraph**: CIOM concepts with typed relationships and invariants
- **Source subgraph**: one per carrier, ingested from their schema

The **mappings between layers are themselves first-class graph nodes** — versioned, attributed with confidence, SME reviewer, audit trail. *The mappings are the product.* Not the data pipeline.

---

## Mappings as Declarative DSL, Not Code

Do not write per-carrier Python transformations. You'll end up with 50 untestable ETL scripts that rot.

Each mapping is a declarative rule living as a graph node:

```
Mapping {
  source_path: "PolicyCenter.Coverage[type='HO3'].limitA"
  canonical_concept: "Coverage.DwellingLimit"
  transform: Direct | Lookup(table) | Composite(expr) | SMEDefined(ref)
  valid_from: 2026-04-01
  reviewed_by: sme_id
  confidence: 0.98
  carrier_override: null | "acme_2026_rule_17"
}
```

At runtime, a compiler reads the mapping graph → emits dbt/SQL → Snowflake executes. Why this matters:

- **Versioning**: you can reprocess 2024 filings with 2024 mappings
- **Explainability**: regulators and internal audit can trace any coded value back to its rule
- **Reusability**: a Guidewire mapping template works for 40% of your pipeline, per carrier
- **Testability**: every mapping has a unit test that runs against sample data

---

## The PAS Template Library Is Your Real Leverage

This is the point the business plan underplays. Guidewire PolicyCenter has a standard schema. Duck Creek has a standard schema. Majesco, Insurity, Sapiens — each has a standard schema, with carrier-specific customization on top.

Build **five template mapping libraries**: Guidewire, Duck Creek, Majesco, Insurity, and "legacy mainframe flat file." Each template is 70–80% complete for a typical carrier. Onboarding a new Guidewire carrier then means:

- Run the template → 80% auto-mapped
- SME reviews the 20% carrier-specific deviations
- SOP layer captures the edge cases

Without these templates, every carrier is a 6-month services engagement. With them, onboarding drops to 8–12 weeks at steady state. This is what makes the "80% reduction in manual hours" claim credible — but only if you build them. Budget ~$1M of the Series A specifically for PAS template engineering.

---

## The Onboarding Playbook (10–12 weeks per carrier)

### Phase A — Discovery (weeks 1–2)
Automated source crawl: pull DDL, row counts, null rates, cardinalities, sample values. LLM-assisted concept classification generates a candidate mapping report: "here's what we think field X is, confidence 92%." This is where LLMs earn their keep — bulk classification with human review, not end-to-end automation.

### Phase B — SME Calibration (weeks 3–6)
Carrier's stat reporting lead + RegulAI's regulatory SME review the ambiguous mappings together. This is where you capture the carrier-specific exception rules — the stuff the retiring expert knows but never wrote down. Encode them into the graph, not into tribal notes.

### Phase C — Shadow Run (weeks 7–10)
Run your pipeline in parallel with the carrier's existing process on real data. Every discrepancy between your output and theirs is diagnostic: either (a) your mapping is wrong, (b) their historical process was wrong, or (c) ambiguous rule needing SME adjudication. All three cases improve the graph.

### Phase D — Cutover (weeks 11–12)
Live filing with HITL review on every submission. Reduce HITL coverage as confidence builds per data class.

Shadow-run data is your training corpus. Every carrier makes the next onboarding faster and the mapping templates richer.

---

## The Hard Problems Nobody Talks About

### 1. Historical restatements
Carriers will want to reprocess the last 3 years of filings with corrected mappings. This has to be a first-class operation, not an afterthought. It drives time-travel requirements into the entire architecture — mappings must be versioned and replayable, Snowflake tables must be temporal.

### 2. Procedural logic in mainframes
Some carriers compute coded values in COBOL or stored procs. You can't schema-map your way out of that — you have to reverse-engineer the logic. Budget for this explicitly. It's not data engineering, it's code archaeology.

### 3. Semantic reconciliation across Premium and Claims
Policy_ID matching between premium and claims subsystems is rarely clean — different systems, different IDs, different effective-dating rules. Solve this once at the CIOM layer with probabilistic entity resolution (policy number + named insured + state + effective date window). Don't punt it to per-filing logic.

### 4. Write-back boundary
When RegulAI detects that the source data is wrong (not just mis-mapped), what do you do? You almost certainly don't write back to the PAS — carriers will refuse. But you need a workflow: an "upstream data quality exception" queue that feeds back to the carrier's data team. This is a product surface, not just a log.

### 5. Pre-go-live validation
Before the first live filing, you need a formal validation: run RegulAI's output against the carrier's last year of actual submissions, reconcile every delta, get carrier internal audit sign-off. This is a 2–4 week exercise and it's where most insurance software deployments die. Plan for it.

---

## What to Build First (Phase 0 Technical Plan)

Rough order of operations, 6–9 months:

1. **CIOM v1** — residential property only, tight schema, formal contracts (weeks 1–4)
2. **GRE for TX TICO residential** — TCLSP, THSP ingested as graph (weeks 3–10, parallel)
3. **Mapping DSL + compiler** — graph → dbt → Snowflake (weeks 6–14)
4. **Guidewire PolicyCenter template** — your first and most-leveraged template (weeks 10–18)
5. **Validation harness** — shadow-run infrastructure against real carrier data (weeks 14–20)
6. **Cortex agent v1** — pre-submission validation, the lowest-complexity highest-trust signal (weeks 18–24)
7. **First pilot carrier onboarding** — end-to-end proof (weeks 22–32)

Skip Bridge and Sentinel agents until after the first pilot ships. Do not build them speculatively — they'll design better once you've seen one real carrier's filing lifecycle end to end.

---

## The One-Line Version

**The system's value isn't the pipeline — it's the mapping graph.** Build a canonical object model, make every mapping a versioned typed node, build per-PAS template libraries so carriers onboard from 80% complete, and let agents read the graph instead of executing hardcoded logic. Everything else — Snowflake, Neo4j, agents — is implementation detail that serves that core.
