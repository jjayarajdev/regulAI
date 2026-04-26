# RegulAI — What Is an Ontology and Why Does RegulAI Need One?

"Ontology" gets thrown around loosely. This document grounds the term and explains why ontology-level modeling is non-optional for RegulAI.

---

## The Short Definition

An **ontology** is a formal, shared specification of:

1. The **concepts** in a domain (what things exist)
2. Their **properties** (what attributes those things have)
3. The **relationships** between them (how things connect)
4. The **rules and invariants** that constrain valid states (what combinations are possible)

Critically, it captures **meaning**, not just structure. A database schema says *"this column is a varchar(50)."* An ontology says *"a Policy is a contractual agreement between one Insurer and one or more NamedInsureds, covering one or more Risks, during a specific EffectivePeriod, subject to a set of Coverages — and a Policy cannot exist without at least one Coverage."*

---

## The Spectrum of Semantic Richness

Think of data modeling as a spectrum:

```
Taxonomy  →  Schema  →  Data Model  →  Ontology
(a list)    (tables     (entities     (entities +
            + columns)   + keys +      relationships
                         relations)    + axioms +
                                       inference rules)
```

- **Taxonomy**: "Here is a hierarchy of perils: Fire → Wildfire, Structure Fire, Lightning Fire."
- **Schema**: "The `peril` table has columns `id`, `code`, `description`, `parent_id`."
- **Data Model**: "A `Peril` belongs to a `Coverage`, which belongs to a `Policy`. Foreign keys enforce integrity."
- **Ontology**: "A `Peril` is a `CausationClass` that triggers loss events. Every `CoveredPeril` implies a `CausalPath` from event to claim. Two perils are `MutuallyExclusive` if they cannot both apply to the same loss event (e.g., `Flood` and `WindDrivenRain` in a single claim require disambiguation by `PrimaryProximateCause`)."

The last layer is what regulators reason about. The database schema alone cannot.

---

## Why RegulAI Specifically Needs an Ontology

Because the whole business is about preserving and applying **semantic knowledge** that currently lives only in retiring experts' heads. If you encode only structure, you rebuild the same brittle systems the industry already has.

### 1. The same word means different things across carriers

Every carrier's system has a "premium" field. But:

- Carrier A: `premium` = written premium (the full contract value at bind)
- Carrier B: `premium` = earned premium (prorated by time elapsed)
- Carrier C: `premium` = collected premium (net of cancellations and returns)
- Carrier D: `premium` varies by module — policy admin says written, billing says collected

A schema cannot disambiguate this. An ontology can — because `WrittenPremium`, `EarnedPremium`, and `CollectedPremium` are three distinct concepts with defined relationships (`EarnedPremium ≤ WrittenPremium` as a temporal invariant, etc.), and each carrier's source `premium` field gets classified into one of the three during mapping.

### 2. Regulators reason semantically, not structurally

A TICO rule says: *"Report the Cause of Loss code corresponding to the proximate cause of the loss event, where proximate cause is defined as the primary efficient cause initiating an unbroken chain of events."*

You cannot encode "proximate cause" as a column. It is a concept with:

- A definition
- Inference rules (how to derive it from a loss narrative + claim facts)
- Edge cases (concurrent causation, anti-concurrent causation clauses)
- Jurisdictional variance (Texas uses a different proximate cause doctrine than California)

That is ontology-level reasoning.

### 3. Rules and data must live in the same model

The GRE isn't just "here are the valid codes." It's: *"If `Coverage.Type = HO3` AND `State = TX` AND `EffectiveDate ≥ 2026-04-01`, then `CauseOfLoss` must be drawn from code set {01, 02, 03, ... 47} AND `Territory` must be a valid post-2026 TCLSP territory AND `ActionDate ≥ LossDate` unless an exception flag is set."*

Those constraints span rules, codes, dates, and hierarchies. In a relational schema, this gets scattered across triggers, check constraints, application code, and stored procs. In an ontology, the axioms live alongside the concepts — and an agent can *reason* over them rather than execute imperative validation code.

---

## A Concrete Comparison

The same concept expressed at three levels:

**As a schema (what most systems have):**
```sql
CREATE TABLE coverage (
  id INT PRIMARY KEY,
  policy_id INT REFERENCES policy(id),
  type VARCHAR(20),
  limit_amount DECIMAL
);
```
Tells you nothing about what a coverage *is*.

**As a data model:**
```
Coverage {
  id, policy_id, type, limit_amount
  relationships: belongs_to Policy, has_many Perils
}
```
Slightly better — cardinality is present. Still silent on meaning.

**As an ontology fragment:**
```
Concept: Coverage
  Definition: A contractual undertaking by the Insurer to indemnify
              the Insured against loss from specified Perils,
              subject to stated Limits and Conditions.

  Properties:
    - limit: Money (required, > 0)
    - deductible: Money (optional, ≥ 0)
    - type: CoverageType (required, from controlled vocabulary)

  Relationships:
    - belongsTo: exactly 1 Policy
    - covers: 1..n Perils
    - appliesTo: 1..n Risks (inherited from Policy)
    - subordinateTo: 0..1 Coverage  // for sub-coverages / endorsements

  Axioms:
    - limit ≥ deductible
    - EffectivePeriod(Coverage) ⊆ EffectivePeriod(Policy)
    - If type = "HO3.DwellingLimit" then covers must include "Fire"
    - A Coverage cannot outlive its parent Policy

  Regulatory Mappings:
    - TICO.CoverageCode ← derivedFrom(type, state, effectiveDate)
    - NAIC.LineOfBusiness ← classifiedBy(type)
```

Now an agent reading the graph knows what a Coverage *means*, what's allowed, what's required, and how it maps to regulatory codes. A carrier's source field claiming to be a "coverage" can be checked against these axioms before it is accepted into the CIOM.

---

## What the RegulAI Ontology Needs to Cover (Phase 0 Scope)

Minimum viable ontology for residential property:

1. **Core entities**: `Policy`, `Coverage`, `Peril`, `Risk`, `Location`, `Party` (Insurer, NamedInsured, AdditionalInsured), `Loss`, `Claim`, `Transaction`, `Endorsement`
2. **Value types**: `Money` (amount + currency + basis — written/earned/collected), `DateRange`, `GeographicTerritory`, `PolicyForm`
3. **Code systems**: `CauseOfLossCode`, `CoverageCode`, `TerritoryCode`, `ActionDateCode` — each with source authority (TICO, NAIC, ISO) and temporal validity
4. **Invariants**: temporal (dates must nest correctly), financial (sums must reconcile), referential (every claim maps to a policy in force on the loss date)
5. **Classification rules**: how to derive regulatory codes from canonical properties (the `CIOM → Regulatory` mapping)
6. **Inference rules**: what you can deduce without being told (e.g., if `LossDate` is between `PolicyEffectiveDate` and `PolicyExpirationDate`, the policy is "in force for this loss")

---

## How Formal to Go — A Practical Recommendation

There is a temptation to go full academic: OWL, SHACL, SPARQL, Description Logic reasoners. **Don't.** That path leads to beautiful ontologies that nobody can maintain.

Pragmatic middle ground:

- **Model in Neo4j as a labeled property graph** — concepts as node types, relationships as typed edges, constraints as Cypher schema + validation queries
- **Express axioms in a lightweight DSL** under RegulAI's control — not OWL. Something that compiles to validation queries and dbt tests.
- **Keep definitions human-readable** — every concept node has a plain-English definition reviewed by the Head of Regulatory Science. This is what SMEs read and edit, not developers.
- **Version everything** — concepts evolve as regulations change. `PolicyForm.HO3` in 2025 is not the same as in 2027.
- **Make the ontology introspectable by agents** — Cortex, Bridge, and Sentinel read it at runtime to do their jobs. It is not a design-time artifact locked in a Confluence page; it is a live runtime dependency.

---

## The One-Line Version

**An ontology is a schema that knows what its data means.** For RegulAI, the ontology is how the retiring expert's *judgment* is preserved — not just their data. Without it, the result is a rebuilt PAS with nicer tooling. With it, the result is captured institutional knowledge the business plan promises.
