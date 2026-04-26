# RegulAI — End-to-End Example: One Loss Event from Carrier PAS to TICO Filing

This document walks a single loss event through the entire RegulAI pipeline — from raw Guidewire PolicyCenter / ClaimCenter tables, through the Bronze → Silver → Gold Snowflake pipeline, through the ontology-driven classification, to the final TICO statistical plan submission record.

The intent is to make the architecture concrete and testable, and to show how every value in the output record is traceable back to a source field plus a versioned rule.

Values and formats are representative. Actual TICO field positions, code tables, and rule citations must be confirmed against the current TCLSP/THSP document of record by the Head of Regulatory Science.

---

## Scenario

### Carrier

**Acme Texas Insurance Company (ATIC)**
- Mid-market Texas residential carrier, ~$180M Direct Written Premium
- Source systems:
  - Guidewire **PolicyCenter** (policy administration)
  - Guidewire **ClaimCenter** (claims)
  - Oracle **General Ledger** (financial system of record)
- Reporting obligation: TICO Q1 2026 Residential Statistical Plan
- Filing deadline: 2026-06-15

### The Policy

| Field                    | Value                                              |
|--------------------------|----------------------------------------------------|
| Policy Number            | ATX-HO-002938                                      |
| Policyholder             | Maria Garcia (primary), Juan Garcia (additional)   |
| Property                 | 4521 Oakwood Ln, Austin, TX 78745 (Travis County)  |
| Form                     | HO-3                                               |
| Effective Period         | 2026-01-01 → 2027-01-01                            |
| Coverage A (Dwelling)    | $385,000 limit / $2,500 deductible                 |
| Coverage B (Other Str.)  | $38,500                                            |
| Coverage C (Personal)    | $192,500                                           |
| Coverage D (Loss of Use) | $77,000                                            |
| Coverage E (Liability)   | $300,000                                           |
| Coverage F (Med Pay)     | $5,000                                             |
| Annual Premium (Written) | $2,840                                             |

### The Loss

- **2026-02-10 → 2026-02-12**: Sub-zero weather event across Central Texas.
- **2026-02-12**: Uninsulated copper pipe in exterior kitchen wall freezes, thaws, and bursts. Water floods kitchen and adjacent living room. Drywall and hardwood flooring damaged.
- **2026-02-14**: Maria Garcia reports the claim.
- **2026-02-17**: Adjuster inspection. Scope agreed.
- **2026-03-08**: Indemnity paid: **$47,822** (net of $2,500 deductible).
- **2026-03-15**: Claim closed.

---

## Step 1 — Raw Source Data (Carrier's Operational Systems)

Data as it exists in ATIC's Guidewire tables, pre-RegulAI.

### 1.1 PolicyCenter — `pc_policy` and `pc_coverage`

```
pc_policy
PolicyID  | PolicyNumber    | ProductCode | AccountID | EffectiveDate | ExpirationDate
----------|-----------------|-------------|-----------|---------------|----------------
p_8847291 | ATX-HO-002938   | HO3         | a_22910   | 2026-01-01    | 2027-01-01

pc_coverage
CovID    | PolicyID  | PatternCode     | Limit_A  | Deduct_A | ExpDate
---------|-----------|-----------------|----------|----------|------------
cv_9001  | p_8847291 | HODW_Dwelling_A | 385000   | 2500     | 2027-01-01
cv_9002  | p_8847291 | HODW_OtherStr_B | 38500    | 2500     | 2027-01-01
cv_9003  | p_8847291 | HODW_Personal_C | 192500   | 2500     | 2027-01-01
cv_9004  | p_8847291 | HODW_LossUse_D  | 77000    | 0        | 2027-01-01
cv_9005  | p_8847291 | HODW_Liab_E     | 300000   | 0        | 2027-01-01
cv_9006  | p_8847291 | HODW_MedPay_F   | 5000     | 0        | 2027-01-01

pc_policylocation
LocID     | PolicyID  | AddressLine1      | City    | State | PostalCode | County
----------|-----------|-------------------|---------|-------|------------|---------
loc_4411  | p_8847291 | 4521 Oakwood Ln   | Austin  | TX    | 78745      | Travis

pc_policyperiod_premium (snapshot aggregates)
PolicyID  | WrittenPremium | AnnualPremium | TermLengthDays
----------|----------------|---------------|----------------
p_8847291 | 2840.00        | 2840.00       | 365
```

### 1.2 ClaimCenter — `cc_claim`, `cc_incident`, `cc_transaction`

```
cc_claim
ClaimID   | ClaimNumber    | PolicyNumber    | LossDate    | ReportedDate | Status
----------|----------------|-----------------|-------------|--------------|--------
cl_33827  | ATX-CL-044183  | ATX-HO-002938   | 2026-02-12  | 2026-02-14   | Closed

cc_incident
IncidentID | ClaimID  | IncidentType     | Description
-----------|----------|------------------|-----------------------------------------------------
inc_7721   | cl_33827 | PropertyDamage   | "Burst pipe in exterior kitchen wall following freeze
           |          |                  | event 2026-02-10 thru 2026-02-12. Water damage to
           |          |                  | kitchen drywall, cabinets, hardwood flooring, and
           |          |                  | living room flooring. No mold. No structural damage.
           |          |                  | Photos on file. Plumbing repair completed 2026-02-18."

cc_exposure
ExposureID | ClaimID  | CoverageSubType | IncurredAmt | PaidAmt  | Reserve
-----------|----------|-----------------|-------------|----------|--------
exp_5501   | cl_33827 | Dwelling        | 39200.00    | 39200.00 | 0.00
exp_5502   | cl_33827 | PersonalProp    | 11122.00    | 11122.00 | 0.00

cc_transaction
TxnID     | ClaimID  | ExposureID | TxnType | TxnDate     | Amount   | CostType
----------|----------|------------|---------|-------------|----------|----------
txn_8801  | cl_33827 | exp_5501   | Payment | 2026-03-08  | 39200.00 | Indemnity
txn_8802  | cl_33827 | exp_5502   | Payment | 2026-03-08  | 11122.00 | Indemnity
txn_8803  | cl_33827 | NULL       | Deduct  | 2026-03-08  | -2500.00 | Deductible
```

### 1.3 Oracle General Ledger — `gl_entries` (relevant rows only)

```
GLID       | AccountCode | PostDate    | Amount    | Reference         | PolicyRef
-----------|-------------|-------------|-----------|-------------------|---------------
gl_221001  | 4100-WP     | 2026-01-01  | 2840.00   | WrittenPrem       | ATX-HO-002938
gl_221890  | 5100-LP     | 2026-03-08  | 50322.00  | LossPaidIndemnity | ATX-CL-044183
```

These are the raw artifacts. A retiring statistical coder would manually reconcile the claim narrative, determine the proximate cause, look up the TICO code, cross-check the coverage form, and hand-type the submission record. RegulAI replaces that with the pipeline below.

---

## Step 2 — Bronze Layer (Snowflake)

RegulAI's Snowflake connector pulls the tables above nightly via change-data-capture into ATIC's Bronze schema. No transformation — just typed, landed, catalogued. Each row gets lineage metadata.

```json
// bronze.pc_policy row as JSON
{
  "_ingested_at": "2026-04-01T03:14:22Z",
  "_source_system": "atic.pc.prod",
  "_source_table": "pc_policy",
  "_source_rowid": "p_8847291",
  "_ingest_batch": "batch_20260401_031402",
  "PolicyID": "p_8847291",
  "PolicyNumber": "ATX-HO-002938",
  "ProductCode": "HO3",
  "AccountID": "a_22910",
  "EffectiveDate": "2026-01-01",
  "ExpirationDate": "2027-01-01"
}
```

Bronze is the audit anchor. Every downstream value can be joined back to `_source_rowid` and `_ingest_batch` for full traceability.

---

## Step 3 — Source-to-CIOM Mapping (Bronze → Silver)

The Neo4j mapping graph contains the rules for transforming ATIC's Guidewire data into RegulAI's Canonical Insurance Object Model. Most rules come from the pre-built **Guidewire PolicyCenter mapping template**; a small set are ATIC-specific overrides captured during onboarding.

### 3.1 Mapping rules that fire for this policy (excerpt)

```
[Mapping M-GW-001]  (from Guidewire template)
  source:      pc_policy.ProductCode
  canonical:   Policy.formCode
  transform:   Direct
  confidence:  1.00
  reviewed_by: sme_head_of_reg_science
  valid_from:  2025-06-01

[Mapping M-GW-027]  (from Guidewire template)
  source:      pc_coverage[PatternCode="HODW_Dwelling_A"].Limit_A
  canonical:   Coverage[type=CoverageA_Dwelling].limit
  transform:   Direct(currency=USD, basis=Stated)
  confidence:  1.00

[Mapping M-GW-028]
  source:      pc_coverage[PatternCode="HODW_Dwelling_A"].Deduct_A
  canonical:   Coverage[type=CoverageA_Dwelling].deductible
  transform:   Direct(currency=USD)
  confidence:  1.00

[Mapping M-GW-104]
  source:      pc_policyperiod_premium.WrittenPremium
  canonical:   Policy.premium
  transform:   Direct(currency=USD, basis=Written)
  confidence:  1.00

[Mapping M-GW-201]  (from Guidewire template)
  source:      pc_policylocation.County
  canonical:   Location.county
  transform:   Direct

[Mapping M-ATIC-017]  (ATIC-specific override, captured in onboarding)
  source:      cc_transaction[TxnType="Payment", CostType="Indemnity"]
  canonical:   LossPayment
  transform:   Aggregate(by=ClaimID, sum=Amount)
  confidence:  0.98
  reviewed_by: sme_head_of_reg_science + atic_claims_director
  notes:       "ATIC splits indemnity across exposures; regulatory view
                requires claim-level aggregate. Confirmed 2026-Q1 with
                ATIC claims director."
```

### 3.2 Resulting CIOM objects (Silver layer)

```json
// silver.ciom.Policy
{
  "policyId": "ATIC::p_8847291",
  "policyNumber": "ATX-HO-002938",
  "formCode": "HO3",
  "effectivePeriod": {"start": "2026-01-01", "end": "2027-01-01"},
  "state": "TX",
  "premium": {"amount": 2840.00, "currency": "USD", "basis": "Written"},
  "coverages": ["cv_9001", "cv_9002", "cv_9003", "cv_9004", "cv_9005", "cv_9006"],
  "namedInsureds": [
    {"role": "Primary", "partyId": "ATIC::party_12",    "name": "Maria Garcia"},
    {"role": "Additional", "partyId": "ATIC::party_13", "name": "Juan Garcia"}
  ],
  "locations": ["ATIC::loc_4411"],
  "_lineage": {
    "sources": [
      {"table": "pc_policy", "rowid": "p_8847291"},
      {"table": "pc_policyperiod_premium", "rowid": "p_8847291"}
    ],
    "mappings": ["M-GW-001", "M-GW-104", "..."]
  }
}

// silver.ciom.Coverage (Coverage A)
{
  "coverageId": "ATIC::cv_9001",
  "policyId": "ATIC::p_8847291",
  "type": "CoverageA_Dwelling",
  "limit": {"amount": 385000.00, "currency": "USD"},
  "deductible": {"amount": 2500.00, "currency": "USD"},
  "effectivePeriod": {"start": "2026-01-01", "end": "2027-01-01"},
  "covers": ["FIRE", "LIGHTNING", "WIND", "HAIL", "EXPLOSION", "SMOKE",
             "VANDALISM", "THEFT", "FALLING_OBJECTS", "WEIGHT_ICE_SNOW",
             "ACCIDENTAL_DISCHARGE_WATER", "FREEZING_PLUMBING",
             "SUDDEN_TEARING", "FREEZING", "..."],
  "excludes": ["FLOOD", "EARTH_MOVEMENT", "WAR", "NUCLEAR"],
  "_lineage": {
    "sources": [{"table": "pc_coverage", "rowid": "cv_9001"}],
    "mappings": ["M-GW-027", "M-GW-028"],
    "perils_resolution": "from CoverageType.defaultCoveredPerils[HO3]
                          valid at Policy.effectivePeriod.start"
  }
}

// silver.ciom.Location
{
  "locationId": "ATIC::loc_4411",
  "address": "4521 Oakwood Ln, Austin, TX 78745",
  "county": "Travis",
  "state": "TX",
  "postalCode": "78745",
  "_lineage": {"sources": [{"table": "pc_policylocation", "rowid": "loc_4411"}]}
}
```

### 3.3 Axiom checks at Silver layer

As each CIOM object is constructed, the axioms from the ontology fire as validation queries:

```
✓ Coverage.limit ($385,000) ≥ Coverage.deductible ($2,500)
✓ Coverage.effectivePeriod ⊆ Policy.effectivePeriod
✓ Coverage.covers ∩ Coverage.excludes = ∅
✓ Policy has at least one Coverage
✓ Location.state matches Policy.state
```

All pass. Silver object is persisted.

---

## Step 4 — Loss Event Construction and Ontology Classification

The claim enters the same pipeline. Beyond mapping, the ontology's **classification axioms** fire to determine proximate cause — this is where the retiring expert's judgment is replaced by the graph.

### 4.1 LossEvent mapped from ClaimCenter

```json
// silver.ciom.LossEvent
{
  "lossEventId": "ATIC::cl_33827",
  "claimNumber": "ATX-CL-044183",
  "policyId": "ATIC::p_8847291",
  "occurrenceDate": {"start": "2026-02-10", "end": "2026-02-12"},
  "reportedDate": "2026-02-14",
  "location": "ATIC::loc_4411",
  "narrative": "Burst pipe in exterior kitchen wall following freeze event
                2026-02-10 thru 2026-02-12. Water damage to kitchen drywall,
                cabinets, hardwood flooring, and living room flooring.
                No mold. No structural damage...",
  "_lineage": {"sources": [{"table": "cc_claim", "rowid": "cl_33827"},
                           {"table": "cc_incident", "rowid": "inc_7721"}]}
}
```

### 4.2 Cortex agent constructs the CausationChain

Cortex reads the narrative (LLM-assisted extraction, constrained by the Peril taxonomy in the ontology) and produces a structured chain:

```json
// silver.ciom.CausationChain
{
  "chainId": "ATIC::cl_33827::chain_1",
  "lossEventId": "ATIC::cl_33827",
  "jurisdictionDoctrine": "EfficientProximateCause",
  "applicableState": "TX",
  "accClause": false,
  "causes": [
    {
      "sequenceOrder": 1,
      "peril": "FREEZE_EVENT",
      "perilClass": "WeatherHazard",
      "evidence": "sub-zero weather event 2026-02-10 thru 2026-02-12",
      "isPrimary": false
    },
    {
      "sequenceOrder": 2,
      "peril": "FROZEN_PIPE",
      "perilClass": "Water.FreezingOfPlumbing",
      "evidence": "burst pipe in exterior kitchen wall",
      "isPrimary": true
    },
    {
      "sequenceOrder": 3,
      "peril": "WATER_DISCHARGE",
      "perilClass": "Water.AccidentalDischarge",
      "evidence": "water damage to drywall, cabinets, flooring",
      "isPrimary": false
    }
  ],
  "primaryDeterminationRationale":
    "Under Texas efficient-proximate-cause doctrine (Lundstrom v. United
     Services Auto Ass'n, 192 S.W.3d 78), the efficient proximate cause is
     the primary force in motion. Freeze created the condition; burst pipe
     is the proximate mechanical cause of the water discharge.",
  "_confidence": 0.96,
  "_cortex_model_version": "cortex-tx-v2.3"
}
```

### 4.3 Classification: CausationChain → CauseOfLoss

The ontology's inference rule fires:

```
Inference Rule R-COL-015:
  IF CausationChain.primary.peril ∈ {FROZEN_PIPE, PIPE_BURST_FROM_FREEZE}
  AND policy.state = "TX"
  AND coverage.covers includes "FREEZING_PLUMBING"
  THEN LossEvent.classifiedAs = CauseOfLoss.Water_FreezingOfPlumbing
```

Result:

```json
// silver.ciom.LossEvent (classified)
{
  "lossEventId": "ATIC::cl_33827",
  "classifiedAs": {
    "canonicalCode": "Water.FreezingOfPlumbing",
    "canonicalLabel": "Freezing of Plumbing",
    "confidence": 0.96,
    "derivedFrom": {
      "chainId": "ATIC::cl_33827::chain_1",
      "primaryPeril": "FROZEN_PIPE",
      "rule": "R-COL-015"
    }
  }
}
```

### 4.4 Coverage applicability check (another axiom)

```
✓ LossEvent.occurrenceDate ⊂ Coverage.effectivePeriod
✓ CauseOfLoss.primary peril (FROZEN_PIPE) ∈ Coverage.covers via FREEZING_PLUMBING
✓ CausationChain.causes ∩ Coverage.excludes = ∅  (no flood, no earth movement)
✓ ACC clause: false, so concurrent causation analysis does not apply
→ Verdict: COVERED
```

### 4.5 Loss financials mapped

```json
// silver.ciom.LossPayment (aggregate)
{
  "paymentId": "ATIC::cl_33827::payment_agg",
  "lossEventId": "ATIC::cl_33827",
  "indemnityPaid": {"amount": 50322.00, "currency": "USD"},
  "deductibleApplied": {"amount": 2500.00, "currency": "USD"},
  "netPaid": {"amount": 47822.00, "currency": "USD"},
  "firstPaymentDate": "2026-03-08",
  "lastPaymentDate": "2026-03-08",
  "reserveRemaining": {"amount": 0.00, "currency": "USD"},
  "status": "Closed",
  "_lineage": {"sources": [
    {"table": "cc_transaction", "rowids": ["txn_8801", "txn_8802", "txn_8803"]}
  ]}
}
```

---

## Step 5 — Canonical-to-Regulatory Mapping (Silver → Gold)

Now RegulAI applies the second set of mapping edges: CIOM → TICO.

### 5.1 Relevant mapping edges

```
[Mapping R-TICO-COL-015]
  canonical:  CauseOfLoss.Water_FreezingOfPlumbing
  authority:  TICO
  code:       "15"
  description: "Freezing of Plumbing"
  effective:  [1990-01-01, null]
  citation:   "TCLSP §5.9503(b)(1)(M)"         ← illustrative
  confidence: 1.00
  reviewedBy: sme_head_of_reg_science

[Mapping R-TICO-FORM-HO3]
  canonical:  CoverageType.HO3
  authority:  TICO
  formTypeCode: "03"                             ← HO-3
  citation:   "TCLSP §5.9503(a)(3)"             ← illustrative
  confidence: 1.00

[Mapping R-TICO-TERR-TX-Travis]
  canonical:  GeographicTerritory.TX_TravisCounty_Austin
  authority:  TICO
  territoryCode: "251"                            ← illustrative post-2026-04-01 territory
  effective:  [2026-04-01, null]
  citation:   "TCLSP §5.9504 Territory Schedule (Apr-2026 revision)"
  confidence: 1.00

[Mapping R-TICO-COV-A]
  canonical:  Coverage.CoverageA_Dwelling
  authority:  TICO
  coverageCode: "01"                              ← Dwelling
  citation:   "TCLSP §5.9503(a)(1)"
  confidence: 1.00
```

### 5.2 Gold Layer record construction

Gold tables mirror the TICO record structure. Every filing produces two record types: **Premium Records** (one per policy term per coverage) and **Loss Records** (one per closed loss).

```
gold.tico_premium_record
```
| Field                | Value                  | Derivation                                      |
|----------------------|------------------------|------------------------------------------------|
| company_naic_code    | 12345                  | ATIC master data                                |
| record_type          | "P"                    | Premium Record                                  |
| policy_number        | "ATX-HO-002938"        | Policy.policyNumber                             |
| form_type            | "03"                   | CoverageType.HO3 → TICO form code via R-TICO-FORM-HO3 |
| coverage_code        | "01"                   | CoverageA → TICO 01 via R-TICO-COV-A            |
| territory            | "251"                  | Travis County Austin → TICO 251 via R-TICO-TERR-TX-Travis |
| effective_date       | 20260101               | Policy.effectivePeriod.start (YYYYMMDD)         |
| expiration_date      | 20270101               | Policy.effectivePeriod.end                      |
| written_premium      | 0000284000             | $2,840.00 encoded as integer cents, 10-pos      |
| amount_of_insurance  | 0000385000             | $385,000 Coverage A limit                       |
| deductible_code      | "02"                   | $2,500 deductible → TICO code 02 (illustrative) |
| construction_code    | "F"                    | Frame (from ATIC property data)                 |
| protection_class     | "03"                   | From ATIC property data                         |
| year_built           | 1998                   | From ATIC property data                         |

```
gold.tico_loss_record
```
| Field                  | Value                  | Derivation                                    |
|------------------------|------------------------|-----------------------------------------------|
| company_naic_code      | 12345                  | ATIC master data                              |
| record_type            | "L"                    | Loss Record                                    |
| policy_number          | "ATX-HO-002938"        | LossEvent.policyNumber                         |
| claim_number           | "ATX-CL-044183"        | LossEvent.claimNumber                          |
| form_type              | "03"                   | CoverageType.HO3 → TICO 03                     |
| coverage_code          | "01"                   | Primary coverage = Dwelling                    |
| territory              | "251"                  | Location → TICO 251                            |
| cause_of_loss          | "15"                   | **CauseOfLoss.Water_FreezingOfPlumbing → TICO 15 via R-TICO-COL-015** |
| loss_date              | 20260212               | LossEvent.occurrenceDate.end                   |
| report_date            | 20260214               | LossEvent.reportedDate                         |
| close_date             | 20260315               | LossPayment.status=Closed date                 |
| paid_loss_amount       | 0000478220             | $47,822 net paid (integer cents)               |
| deductible_amount      | 0000025000             | $2,500                                         |
| loss_reserve_amount    | 0000000000             | $0 (closed)                                    |
| catastrophe_code       | "00"                   | Not catastrophe-coded (below threshold)        |
| action_date            | 20260331               | Filing period close date                       |

---

## Step 6 — Cortex Pre-Submission Validation

Before the Gold record ships, Cortex runs the full axiom battery as a final checkpoint.

```
Cortex Pre-Validation Report — Filing Batch TICO-2026-Q1
Loss Record: ATX-CL-044183
───────────────────────────────────────────────────────────────
CHECK                                          RESULT   SOURCE
───────────────────────────────────────────────────────────────
action_date ≥ loss_date                        ✓ PASS   R-TICO-DQIP-01
report_date ≥ loss_date                        ✓ PASS   R-TICO-DQIP-02
close_date ≥ report_date                       ✓ PASS   R-TICO-DQIP-03
cause_of_loss ∈ valid_TICO_set_for_form_03     ✓ PASS   R-TICO-FORM-CAUSE-MATRIX
territory valid on effective_date              ✓ PASS   R-TICO-TERR-251@2026-04-01
coverage_code valid for form_type              ✓ PASS   R-TICO-FORM-COV-MATRIX
paid_loss > 0 AND loss_reserve = 0 → status    ✓ PASS   R-TICO-CLOSED-CONSISTENCY
                                  Closed
deductible_code matches deductible_amount      ✓ PASS   R-TICO-DEDUCT-LOOKUP
policy in-force on loss_date                   ✓ PASS   C-COVERAGE-APPLICABILITY
cross-field: form=03 + cause=15 is legal       ✓ PASS   R-TICO-FORM-CAUSE-15
───────────────────────────────────────────────────────────────
RESULT: 10/10 PASS — CLEAR FOR SUBMISSION
```

If any check fails, the record is **not** submitted. Instead it is routed to the HITL queue for a RegulAI specialist to adjudicate. The record stays blocked until resolved — the plan's promise that "zero rejections" is credible rests on this gate.

---

## Step 7 — Bridge Agent Reconciliation

Bridge reconciles the filing against ATIC's General Ledger — the final check before submission.

```
Bridge Reconciliation Report
───────────────────────────────────────────────────────────────
METRIC               TICO FILING    ATIC GL        VARIANCE
───────────────────────────────────────────────────────────────
Written Premium      $2,840.00      $2,840.00      0.00   (0.00%)
Paid Losses          $50,322.00     $50,322.00     0.00   (0.00%)
                     (gross)        (gl_221890)
Loss Reserve Δ       $0.00          $0.00          0.00   (0.00%)
───────────────────────────────────────────────────────────────
Tolerance threshold: 0.1% on any material line
Result: WITHIN TOLERANCE
```

---

## Step 8 — Final Submission (TICO Fixed-Width Flat File)

The Gold layer records are serialized into the TICO-mandated fixed-width flat file format and transmitted via TICO's secure upload.

### Premium Record (illustrative format; actual TICO positions authoritative)

```
P12345ATX-HO-002938  03 01 251 20260101 20270101 0000284000 0000385000 02 F 03 1998
│└─┬─┘└──────┬──────┘│  │  │   │        │        │          │          │  │ │  │
│ naic     policy #  │  │  │   │        │        │          │          │  │ │  year_built
│                   form │  │   eff      exp      premium    amount_ins deduct_code
record_type              cov terr                                              constr  prot_class
```

### Loss Record (illustrative format)

```
L12345ATX-HO-002938  ATX-CL-044183 03 01 251 15 20260212 20260214 20260315 0000478220 0000025000 0000000000 00 20260331
│└─┬─┘└──────┬──────┘└──────┬─────┘│  │  │   │  │        │        │        │          │          │          │  │
│ naic     policy #       claim #  │  │  │   │  │        │        │        │          │          │          │  action_date
│                                 form│  │   │  loss     report   close    paid       deduct     reserve    cat_code
record_type                          cov terr│
                                             │
                                             └─ TICO Cause of Loss = 15 (Freezing of Plumbing)
                                                ↑
                                                Provenance: derived from CausationChain primary peril
                                                FROZEN_PIPE → CauseOfLoss.Water_FreezingOfPlumbing
                                                → TICO code 15 via mapping edge R-TICO-COL-015
                                                (citation: TCLSP §5.9503(b)(1)(M))
                                                Cortex confidence 0.96, no HITL escalation required.
```

---

## Step 9 — The Audit Trail

Any field in the submitted record can be traced back to its source through a continuous chain of graph edges.

**"Why is `cause_of_loss = 15` on this record?"**

```
TICO record field: cause_of_loss
    └── emitted from gold.tico_loss_record.cause_of_loss
        └── derived via mapping R-TICO-COL-015
            └── which maps CauseOfLoss.Water_FreezingOfPlumbing → "15"
                └── assigned via inference rule R-COL-015
                    └── triggered by CausationChain.primary.peril = FROZEN_PIPE
                        └── extracted by Cortex v2.3 from incident narrative
                            └── narrative sourced from bronze.cc_incident[inc_7721]
                                └── originally written by ATIC adjuster
                                    on 2026-02-17 at ClaimCenter entry

Mapping R-TICO-COL-015:
  citation:   TCLSP §5.9503(b)(1)(M)
  reviewedBy: sme_head_of_reg_science
  reviewedAt: 2026-Q2
  valid_from: 1990-01-01
  valid_to:   null
```

Seven hops. Every hop is a versioned graph edge with a reviewer and a citation. That is what a TDI market-conduct examiner gets handed when they ask "how did you arrive at this code?"

---

## Step 10 — What This Example Demonstrates

1. **The pipeline works bidirectionally for audit.** Output field → source field in 7 hops, all traceable. The retiring expert's justification is now a queryable graph.

2. **Mappings are the real product.** The engineering content above is almost entirely declarative rules in Neo4j — not Python, not SQL. Rules can be added, versioned, and reviewed without code deploys.

3. **Template leverage is huge.** 80% of the CIOM mappings came from the Guidewire PolicyCenter template. Only one rule (M-ATIC-017) was ATIC-specific. Adding the next Guidewire carrier is mostly about capturing their specific overrides, not rebuilding the pipeline.

4. **Ontology axioms replace procedural validation.** No hand-written validation scripts. Every check is an axiom attached to a concept, executed as a query.

5. **Cortex earns its keep at classification.** LLM involvement is bounded and verifiable — extracting structured causation from free-text narrative, constrained by the Peril taxonomy. Cortex does not freewheel; it picks from a controlled vocabulary and cites its rationale.

6. **Failure modes are visible.** Any axiom failure, confidence score below threshold, or GL variance outside tolerance routes to HITL. The system is self-aware about what it does not know.

7. **Regulatory change is a graph update, not a code deploy.** When TICO issues a new territory schedule (as happens 2026-04-01), Sentinel walks the graph and flags every policy whose territory code needs re-resolution on the next filing. No IT cycle required.

---

## Step 11 — Open Questions This Example Surfaces

Things that need SME adjudication or further engineering before this is production-ready:

- **Exact TICO record format and field positions.** Above is representative. The Head of Regulatory Science must verify against the current TCLSP authoritative document.
- **Territory remapping rule for mid-term policies.** Policy incepted 2026-01-01 using pre-April territories; is the Q1 filing reported with pre-April territory or post-April? TCLSP transition guidance applies.
- **Deductible code mapping.** TICO encodes deductible by category, not exact value. The $2,500 → "02" mapping needs the current deductible schedule.
- **Catastrophe code threshold.** Freeze events of Feb 2026 may or may not be officially cat-coded depending on TICO's cat declaration. Needs runtime cat-event lookup.
- **Multi-coverage losses.** This example was clean — damage to dwelling and personal property both rolled up to one loss record. TCLSP may require separate loss records per coverage. Needs confirmation.

These are the kinds of questions the pilot will surface. Every answer becomes another axiom or mapping in the graph.
