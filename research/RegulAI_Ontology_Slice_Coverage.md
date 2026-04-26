# RegulAI — Ontology Slice: Coverage, Peril, and Cause of Loss

A concrete, buildable slice of the RegulAI ontology focused on the region most central to statistical filing: **how a Coverage relates to the Perils it covers, how a real-world Loss Event gets classified to a regulatory Cause of Loss, and how the canonical model maps to TICO codes.**

Scope: U.S. residential property (HO-series, DP-series). Designed to be extended to auto and commercial later.

---

## 1. Scope and Design Principles

This slice covers:

- What a policy covers (Coverage + CoverageType)
- What can trigger coverage (Peril + PerilClass)
- What actually happened (LossEvent + CausationChain)
- How to classify what happened (CauseOfLoss)
- How to emit the regulatory code (TICO.CauseOfLossCode)

Design principles:

- **Every concept has a plain-English definition.** SMEs read and approve definitions before engineering uses them.
- **Every axiom has a stated rationale.** Explains *why* the constraint exists, not just what it is.
- **Code systems are first-class nodes** with temporal validity, not enum strings.
- **Mappings are versioned edges**, not hardcoded switch statements.

---

## 2. Core Concepts

### 2.1 Coverage

```
Concept: Coverage
  Definition: A contractual undertaking by the Insurer to indemnify
              the Insured against loss arising from specified Perils,
              subject to stated Limits, Deductibles, and Conditions.

  Properties:
    - coverageId: UUID                       (required, unique)
    - type: CoverageType                     (required, FK to CoverageType)
    - limit: Money                           (required, amount > 0)
    - deductible: Money                      (optional, amount ≥ 0)
    - effectivePeriod: DateRange             (required)
    - endorsements: List<Endorsement>        (optional)

  Relationships:
    - belongsTo → Policy                     (exactly 1)
    - covers → Peril                         (1..n)
    - excludes → Peril                       (0..n)
    - appliesTo → Risk                       (1..n, inherited from Policy)
    - subordinateTo → Coverage               (0..1, for endorsements / riders)
```

### 2.2 CoverageType

```
Concept: CoverageType
  Definition: A standardized classification of coverage, aligned to
              an industry-recognized policy form (HO-3, HO-5, DP-3, etc.)
              or a carrier-specific proprietary form mapped to one.

  Properties:
    - code: String                           (e.g., "HO3", "DP3", "HO6")
    - formFamily: enum{HO, DP, CP, PAP, ...}
    - isOpenPeril: Boolean                   (HO-3 dwelling = open; HO-3 contents = named)
    - defaultCoveredPerils: Set<Peril>
    - defaultExcludedPerils: Set<Peril>
    - regulatoryAuthority: enum{ISO, AAIS, carrierProprietary}
    - validFrom: Date
    - validTo: Date | null
```

### 2.3 Peril

```
Concept: Peril
  Definition: A class of cause that can give rise to a loss event.
              A Peril is a *category of causation*, not an occurrence.

  Properties:
    - code: String                           (e.g., "FIRE", "WIND", "HAIL")
    - name: String
    - class: PerilClass                      (FK)
    - isNaturalCatastrophe: Boolean
    - isHumanCaused: Boolean
    - typicalManifestation: Text             (SME-authored, used by LLM classifiers)

  Relationships:
    - memberOf → PerilClass                  (exactly 1)
    - mutuallyExclusiveWith → Peril          (0..n, symmetric)
    - commonlyCooccursWith → Peril           (0..n, symmetric)
```

### 2.4 PerilClass

```
Concept: PerilClass
  Definition: A high-level grouping of perils by causative mechanism.
              Used for hierarchical reporting and exclusion logic.

  Instances (residential):
    - FireAndLightning
    - WindAndHail
    - Water                  (sub-categorized: Plumbing, Weather, Flood)
    - Theft
    - Liability
    - Vandalism
    - WeightOfIceSnow
    - FallingObjects
    - Collapse
    - Earth                  (earthquake, sinkhole, landslide)
    - Other
```

### 2.5 LossEvent

```
Concept: LossEvent
  Definition: A specific real-world occurrence that caused, or is
              alleged to have caused, damage to an insured Risk.

  Properties:
    - lossEventId: UUID
    - reportedDate: Date
    - occurrenceDate: DateRange              (range when onset is uncertain)
    - narrative: Text                        (adjuster's description)
    - location: Location

  Relationships:
    - affects → Risk                         (1..n)
    - triggeredBy → CausationChain           (exactly 1)
    - classifiedAs → CauseOfLoss             (exactly 1, after classification)
    - generatesClaim → Claim                 (0..n)
```

### 2.6 CausationChain

```
Concept: CausationChain
  Definition: The ordered sequence of contributing causes that produced
              a LossEvent. Used to determine proximate cause under the
              applicable jurisdictional doctrine.

  Properties:
    - chainId: UUID
    - causes: OrderedList<ContributingCause>
    - jurisdictionDoctrine: enum{ProximateCause, EfficientProximateCause,
                                 AntiConcurrentCausation, DominantCause}

  Axioms:
    - Exactly one ContributingCause in the chain is flagged as primary.
    - The primary cause is the one reported to regulators as Cause of Loss.
    - If the policy has an Anti-Concurrent Causation (ACC) clause, any
      excluded ContributingCause in the chain excludes the entire loss.
```

### 2.7 ContributingCause

```
Concept: ContributingCause
  Definition: One link in a CausationChain — a specific Peril instance
              that contributed to the LossEvent.

  Properties:
    - peril: Peril                           (FK)
    - sequenceOrder: Integer                 (1 = first in chain)
    - isPrimary: Boolean                     (exactly one per chain)
    - evidence: Text                         (adjuster notes, photos, reports)
```

### 2.8 CauseOfLoss (Canonical)

```
Concept: CauseOfLoss
  Definition: The canonical classification of what caused a LossEvent,
              derived from the primary ContributingCause in the
              CausationChain under the applicable doctrine.

  Properties:
    - canonicalCode: String                  (RegulAI-internal code, stable)
    - description: Text
    - typicalPerils: Set<Peril>              (perils that usually map here)

  Relationships:
    - derivesFrom → Peril                    (1..n)
    - mapsToRegulatory → RegulatoryCode      (1..n, one per authority)
```

---

## 3. Code Systems (as first-class nodes)

### 3.1 Regulatory Code Systems

```
Concept: RegulatoryCode
  Abstract — specialized by authority.

  Subtypes:
    - TICOCauseOfLossCode    (Texas — TCLSP/THSP)
    - NAICLOBCode            (NAIC Line of Business)
    - ISOCauseOfLossCode     (ISO statistical plan)
    - NCCIInjuryCauseCode    (workers' comp)
```

### 3.2 TICO Cause of Loss Codes — Residential (Illustrative Subset)

Each code is a versioned node: `(code, description, validFrom, validTo, sourceAuthority)`.

| Code | Description                              | validFrom   | validTo |
|------|------------------------------------------|-------------|---------|
| 01   | Fire                                     | 1990-01-01  | null    |
| 02   | Lightning                                | 1990-01-01  | null    |
| 03   | Windstorm or Hail                        | 1990-01-01  | null    |
| 04   | Explosion                                | 1990-01-01  | null    |
| 05   | Riot or Civil Commotion                  | 1990-01-01  | null    |
| 09   | Smoke                                    | 1990-01-01  | null    |
| 11   | Theft                                    | 1990-01-01  | null    |
| 12   | Vandalism or Malicious Mischief          | 1990-01-01  | null    |
| 13   | Weight of Ice, Snow, or Sleet            | 1990-01-01  | null    |
| 14   | Accidental Discharge of Water            | 1990-01-01  | null    |
| 15   | Freezing of Plumbing                     | 1990-01-01  | null    |
| 17   | Falling Objects                          | 1990-01-01  | null    |
| 20   | Earth Movement                           | 1990-01-01  | null    |
| 21   | Flood                                    | 1990-01-01  | null    |
| 40   | Liability — Bodily Injury                | 1990-01-01  | null    |
| 41   | Liability — Property Damage              | 1990-01-01  | null    |
| 99   | All Other                                | 1990-01-01  | null    |

> Note: actual TICO code set is authoritative — above is illustrative. Every code node must carry `sourceCitation` pointing to the TCLSP/THSP section that defines it.

---

## 4. Axioms and Invariants

All axioms below are encoded as validation rules that run during pipeline execution.

### 4.1 Structural Axioms

| Axiom                                                                                 | Rationale                                                    |
|---------------------------------------------------------------------------------------|--------------------------------------------------------------|
| Every Coverage covers at least one Peril.                                             | A coverage with no perils is meaningless.                    |
| Coverage.limit ≥ Coverage.deductible.                                                 | Trivially true in practice; guards data entry errors.        |
| Coverage.effectivePeriod ⊆ Policy.effectivePeriod.                                    | A coverage cannot outlive its parent policy.                 |
| Endorsement.subordinateTo points to exactly one parent Coverage.                      | Endorsements modify a specific base coverage.                |
| Every LossEvent has exactly one CausationChain.                                       | One loss = one causation story.                              |
| Every CausationChain has exactly one primary ContributingCause.                       | Proximate cause doctrine requires a single primary cause.    |
| LossEvent.classifiedAs (CauseOfLoss) derives from CausationChain.primary.peril.       | Classification is a function of primary cause.               |

### 4.2 Temporal Axioms

| Axiom                                                                                 | Rationale                                                    |
|---------------------------------------------------------------------------------------|--------------------------------------------------------------|
| LossEvent.occurrenceDate ∈ Coverage.effectivePeriod.                                  | Policy must be in force for coverage to apply.               |
| Claim.reportedDate ≥ LossEvent.occurrenceDate.start.                                  | Reports cannot precede the event.                            |
| ActionDate ≥ LossDate on all filed transactions.                                      | TICO DQIP rule; violation triggers rejection.                |
| RegulatoryCode applied to a filing must be valid on Coverage.effectivePeriod.start.   | Use the code set that was in effect when the policy incepted.|

### 4.3 Exclusion Axioms

| Axiom                                                                                 | Rationale                                                    |
|---------------------------------------------------------------------------------------|--------------------------------------------------------------|
| If a Peril is in Coverage.excludes, it is not in Coverage.covers.                     | Cannot include and exclude the same peril.                   |
| If Policy has ACC clause AND any ContributingCause.peril is excluded, entire loss is excluded.  | Anti-concurrent causation doctrine.                 |
| Flood is excluded from HO-3 by default; requires separate Flood endorsement or NFIP.  | ISO HO-3 form language.                                      |
| Earth Movement is excluded from HO-3 by default; requires endorsement.                | ISO HO-3 form language.                                      |

### 4.4 Classification Axioms (Inference Rules)

| Axiom                                                                                 | Rationale                                                    |
|---------------------------------------------------------------------------------------|--------------------------------------------------------------|
| If primary peril = Fire, CauseOfLoss = Fire → TICO 01.                                | Direct mapping.                                              |
| If primary peril = Wind AND hail present, CauseOfLoss = WindOrHail → TICO 03.         | Combined peril code in TICO residential.                     |
| If primary peril = PlumbingLeak, CauseOfLoss = AccidentalDischargeOfWater → TICO 14.  | Canonical water sub-class mapping.                           |
| If primary peril = FrozenPipe, CauseOfLoss = FreezingOfPlumbing → TICO 15.            | Distinct from generic water damage.                          |
| If primary peril = Flood (from rising surface water), CauseOfLoss = Flood → TICO 21.  | Flood is a distinct regulatory category.                     |
| If no primary peril matches known classes, CauseOfLoss = AllOther → TICO 99, AND flag for SME review. | Safe default with escalation.                                |

---

## 5. Mapping Rules (Canonical → TICO)

Mappings are declarative graph edges. Example:

```
Mapping: CauseOfLoss → TICOCauseOfLossCode
  {
    canonical: "FireAndLightning.Fire",
    regulatoryAuthority: TICO,
    regulatoryCode: "01",
    effectiveFrom: "1990-01-01",
    effectiveTo: null,
    confidence: 1.00,
    reviewedBy: "sme_head_of_reg_science",
    reviewedAt: "2026-Q2",
    sourceCitation: "TCLSP §5.9503(b)(1)(A)"
  }

Mapping: CauseOfLoss → TICOCauseOfLossCode
  {
    canonical: "Water.AccidentalDischarge",
    regulatoryAuthority: TICO,
    regulatoryCode: "14",
    effectiveFrom: "1990-01-01",
    effectiveTo: null,
    confidence: 1.00,
    reviewedBy: "sme_head_of_reg_science",
    notes: "Plumbing leaks, appliance overflow, HVAC condensation.
            Does NOT include frozen pipe events (→ code 15) or
            flood-origin water (→ code 21)."
  }
```

Key property: mappings carry citations. Every regulatory code assignment is traceable back to a rule of record — the audit trail the business plan promises.

---

## 6. Worked Example: A Frozen Pipe Loss

Walking one loss event through the ontology end-to-end.

### Inputs

- Policy: HO-3 residential, TX, effective 2026-01-01 to 2027-01-01
- Coverage A (Dwelling): limit $450K, deductible $2.5K
- Endorsement: HO 15 (extended replacement cost)
- Loss reported 2026-02-14
- Adjuster narrative: *"Pipe froze in exterior wall during sub-zero weather event on 2026-02-10; water discharged when thawing began 2026-02-12; dwelling drywall and flooring damaged in kitchen and living room."*

### Ontology resolution

1. **LossEvent created**: `occurrenceDate = [2026-02-10, 2026-02-12]`, `reportedDate = 2026-02-14`.

2. **CausationChain constructed** by Cortex agent reading narrative:
   - ContributingCause #1: `Peril = FreezeEvent` (weather — sub-zero temps)
   - ContributingCause #2: `Peril = FrozenPipe` (mechanism — pipe burst) ← **primary**
   - ContributingCause #3: `Peril = WaterDischarge` (immediate damage mechanism)

3. **Primary cause determination**: Under Texas proximate cause doctrine, `FrozenPipe` is the efficient proximate cause. Flagged `isPrimary = true`.

4. **Classification**: `LossEvent.classifiedAs = CauseOfLoss.FreezingOfPlumbing`.

5. **Coverage applicability check**:
   - HO-3 Coverage A defaults include "Freezing of Plumbing" (ISO form language).
   - No ACC clause concerns — primary cause is a covered peril.
   - Policy was in force on both occurrence and report dates.
   - No exclusion triggers (freeze not classified as Earth Movement or Flood).
   - Verdict: covered.

6. **Regulatory code emission**:
   - Canonical `CauseOfLoss.FreezingOfPlumbing` → TICO code `15`.
   - Via mapping edge with citation `TCLSP §5.9503(b)(1)(M)` (illustrative).
   - Confidence 1.00 — no SME escalation needed.

7. **Pre-submission validation (Cortex)**:
   - ActionDate (2026-02-14) ≥ LossDate (2026-02-10). ✓
   - Territory code valid for TX residential post-2026-04-01. ✓ (or flag if filing is submitted after April 1 and policy uses pre-April territory).
   - Coverage form matches allowable form set for the code. ✓

8. **Filing**: Record flows through Snowflake Silver layer with TICO code 15 appended, then Gold layer aggregation.

**If the narrative had said** *"flood waters rose and burst frozen pipes"* — the CausationChain would show Flood as a contributing cause. Under ACC the entire loss would be excluded. Under non-ACC (rare for TX) the primary cause would still be determined by doctrine. The ontology forces this determination to be explicit and auditable.

---

## 7. Neo4j Representation (Sketch)

```cypher
// Concept nodes
CREATE (co:Concept:Coverage {name: "Coverage", definition: "..."})
CREATE (p:Concept:Peril {name: "Peril", definition: "..."})
CREATE (col:Concept:CauseOfLoss {name: "CauseOfLoss", definition: "..."})

// Code system nodes
CREATE (tico01:RegulatoryCode:TICO {
  code: "01",
  description: "Fire",
  validFrom: date("1990-01-01"),
  validTo: null,
  sourceCitation: "TCLSP §5.9503(b)(1)(A)"
})

// Peril instance
CREATE (fire:PerilInstance {
  code: "FIRE",
  name: "Fire",
  class: "FireAndLightning",
  isNaturalCatastrophe: false,
  isHumanCaused: true
})

// Canonical CauseOfLoss instance
CREATE (fireCOL:CauseOfLossInstance {
  canonicalCode: "FireAndLightning.Fire",
  description: "Direct fire damage to insured property"
})

// Relationships
CREATE (fire)-[:DERIVES_INTO]->(fireCOL)
CREATE (fireCOL)-[:MAPS_TO {
  confidence: 1.00,
  reviewedBy: "sme_id",
  effectiveFrom: date("1990-01-01"),
  effectiveTo: null
}]->(tico01)
```

Validation queries (axiom checks) are also stored as Cypher in the graph, attached to their concept:

```cypher
// Axiom: Coverage.limit ≥ Coverage.deductible
MATCH (c:CoverageInstance)
WHERE c.limit < c.deductible
RETURN c.coverageId AS violatingCoverage
```

These queries run automatically as part of the validation harness on every Silver→Gold transformation.

---

## 8. Gaps and Open Questions (To Close With SME)

Things the Head of Regulatory Science needs to adjudicate before this slice is production-ready:

1. **Full TICO code enumeration** — the code table above is illustrative. Need authoritative list with current (2026) validFrom/validTo dates.
2. **Edge cases in water perils** — TICO distinguishes Accidental Discharge (14), Freezing (15), and Flood (21). Sewer backup, sump pump failure, and ice damming require explicit classification.
3. **Windstorm vs. Named Storm** — TX has specific treatment for named-storm events (different deductibles, different coding). Needs ontology extension.
4. **Concurrent causation under TX law** — RegulAI's doctrine handling must match Texas Supreme Court precedent on efficient proximate cause.
5. **Multi-peril losses** — a single LossEvent can have multiple primary perils by jurisdiction. How does the ontology represent this for non-TX states?
6. **Endorsement-driven coverage changes** — HO 15 extends replacement cost; HO 04 90 adds peril coverage. Every endorsement must resolve to a modification of covers/excludes sets.

---

## 9. Extension Path

Once this slice is stable:

1. **Extend to Auto (PAP)** — different Peril classes (collision, comprehensive, liability), different regulatory plan (ISO PPA).
2. **Extend to Commercial (CP)** — adds Business Interruption, Equipment Breakdown, etc.
3. **Extend to Workers' Comp (NCCI)** — different concept graph entirely (Injury, BodyPart, NatureOfInjury).
4. **Cross-jurisdictional** — same ontology, additional mappings. TICO codes are TX; NAIC model is broader; CA CDI, FL FLOIR each have their own.

The principle: **the canonical model grows carefully; the regulatory mappings grow freely.** A well-modeled canonical ontology should require minimal changes when adding a new state — only new mapping edges.

---

## 10. The One-Line Version

**This slice says: a Coverage covers Perils; a real-world Loss is a chain of causes; the primary cause classifies the loss into a canonical CauseOfLoss; and a versioned mapping edge emits the TICO code — with every step traceable back to a rule of record.**

That traceability is what turns the system from "AI that guesses" into "managed workforce with an audit trail regulators accept."
