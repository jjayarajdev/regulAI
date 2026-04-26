# RegulAI KG Schema (LHS) — Refined v0.2

**Status**: refined from real Texas regulation research (LHS-0). Each type cites the regulation reference that justifies it. Closed vocabulary — agent extracts only into these types in the POC. Schema extensions are out of POC scope.

**Source-of-truth research**: `docs/lhs-research.md`, plus PDFs in `references/regulations/`.

---

## Node types (14)

Each node has these common properties: `id` (UUID), `version` (int, ≥1), `status` (`draft` | `approved` | `superseded`), `created_at`, `created_by`, `effective_from` (date, nullable), `effective_to` (date, nullable). Type-specific properties listed below.

In Neo4j, every node carries the label `GRENode` plus its specific type label.

### 1. `RegulationDocument`
The source — a stat plan, statute, bulletin, or formal rule adoption. Anchor for all citations.

**Properties**: `kind` (`StatPlan` | `Statute` | `Bulletin` | `RuleAdoption`), `title`, `hash` (sha256 of content), `source_url`, `published_date`.

**Reference example**: `RegulationDocument(kind='StatPlan', title='Texas Statistical Plan for Residential Risks', published_date=2025-12-XX)`.

**Schema justification**: Rules 1, 21, 28, 29 of the Stat Plan all reference TDI-issued instructions and prior versions; Bulletin B-0008-25 is itself a regulation document.

### 2. `StatPlanEdition`
A specific version of a Stat Plan, with effective date.

**Properties**: `edition_name` (e.g., `THSP_2026`), `effective_date`, `supersedes_edition`.

**Reference**: Rule 1 (Scope) — "reporting periods on or after January 1, 2026" supersedes "July 1, 2022."

### 3. `Rule`
A numbered rule within a regulation document. Citations anchor here.

**Properties**: `section` (`A` | `B` | `C` | ...), `rule_number` (int), `title`.

**Reference**: Section A has 35 numbered rules; Section B has 20+; ubiquitous citation anchor.

### 4. `ReportTemplate`
A required report. Five in the POC: Premium, Loss, Notice, Notice Count, Transmittal.

**Properties**: `report_name`, `cadence` (`Monthly` | `Quarterly` | `Annual`), `deadline_days_after_close` (int).

**Reference**: Rule 28 (Designated Statistical Agent) lists the four data reports; Rule 29 (Transmittal Form) defines the transmittal as its own report.

### 5. `RecordLayout`
The layout of records within a report — Sections C/D/E/G of the plan are each a record layout. Intermediate between `ReportTemplate` and `FieldRequirement`.

**Properties**: `layout_name`, `record_format` (`Fixed-ASCII-SDF` for POC).

**Reference**: Sections C, D, E, G (literal section titles).

### 6. `FieldRequirement`
A specific required field on a record layout. Includes position/length for fixed-format layouts.

**Properties**: `field_name`, `position_start` (int, nullable), `position_length` (int, nullable), `format` (e.g., `numeric`, `alphanumeric`, `YYYYMM`), `is_required` (bool), `code_list_ref` (nullable — `CodeList.id` if the field's value comes from a code list).

**Reference**: Sections C–G (record layouts).

### 7. `CodeList`
A named enumeration of allowed values for a field. **Primary type** — most regulatory expressivity lives here.

**Properties**: `code_list_name` (e.g., `Cause of Loss`, `Line of Business`, `HB 2067 Reason Codes`), `description`.

**Reference**: Section B is structured as ~20 named code lists; Sections A§§30/31 add Tenure and TWIA Depopulation; Section F adds HB 2067 Reason Codes.

### 8. `CodeValue`
A single value within a `CodeList`. **Primary type.**

**Properties**: `code` (the actual code value, e.g., `25`, `WH`, `02`), `description`, `notes` (nullable, e.g., "code 7 requires TICO approval").

**Reference**: Every code table in Section B; Rule 28 lists; Rule 30 Tenure codes; Rule 31 TWIA codes; etc.

**Example**: `CodeValue(code='25', description='Windstorm')` within `CodeList(code_list_name='Cause of Loss')`.

### 9. `CoverageType`
A coverage part as defined in the plan: Dwelling, Personal Property, Loss of Use, etc. Field requirements reference these.

**Properties**: `coverage_name`, `applies_to_forms` (list of form codes).

**Reference**: Rule 6 — "for HO and dwelling forms: Dwelling, Personal Property, Loss of Use."

### 10. `EndorsementRule`
An endorsement form classification rule (HO-15, HO 04 90, etc.).

**Properties**: `form_code`, `form_name`, `coverage_effect` (free text).

**Reference**: Rule 18 (B§§) endorsement codes; Rule 33 Replacement Cost endorsements.

### 11. `BulletinOverride`
Mid-edition modification to a base rule, originating from a TDI bulletin.

**Properties**: `bulletin_ref` (a `RegulationDocument.id` of kind `Bulletin`), `effective_date`.

**Reference**: Bulletin B-0008-25 modifies Stat Plan implementation timing; future bulletins typical.

### 12. `ReconciliationRule`
A rule requiring one report to reconcile against another data source.

**Properties**: `from_report` (ref `ReportTemplate`), `against_target` (free text e.g., `NAIC MCAS Cancellations`), `tolerance` (nullable).

**Reference**: Rule 35 — "counts should reconcile with those provided to the NAIC for the Market Conduct Annual Statement (MCAS)."

### 13. `Organization`
A regulatory or industry organization referenced by the regs.

**Properties**: `org_name`, `org_kind` (`StatisticalAgent` | `Regulator` | `Insurer` | `RatingBureau`), `description`.

**Reference**: Rule 28 (TICO); whole plan published by TDI; NAIC referenced in Rule 35; ISO/AAIS in Section B§5; TWIA in Rule 31.

### 14. `HITLTriggerRule`
Application-internal rule defining when a record routes to RHS HITL. Lives in the KG (versioned, citable) but cited from internal SOPs, not regulations directly.

**Properties**: `trigger_name`, `condition_summary`, `severity` (`auto-handle` | `Tier1` | `Tier2` | `Tier3`).

**Reference**: derived from compliance practice; not a regulation node, but lives in the same graph for unified policy enforcement.

---

## Relationship types (10)

| Relationship | From → To | Meaning |
|---|---|---|
| `SUPERSEDES` | `GRENode` v.n → v.(n−1) | Versioning |
| `EFFECTIVE_FROM` | `GRENode` → date | When this version takes effect (for nodes lacking the `effective_from` property) |
| `CITES` | `GRENode` → `Rule` (carries `char_start`/`char_end`/`kind` properties) | Provenance back to a regulation rule |
| `CONTAINED_IN` | `Rule` → `RegulationDocument` | Rules belong to documents |
| `CONTAINS_LAYOUT` | `ReportTemplate` → `RecordLayout` | Report contains record layouts |
| `REQUIRES` | `RecordLayout` → `FieldRequirement` | Layout requires fields |
| `HAS_VALUE` | `CodeList` → `CodeValue` | Code list has values |
| `CODED_BY` | `FieldRequirement` → `CodeList` | Field's value comes from a code list |
| `OVERRIDES` | `BulletinOverride` → `Rule` (or `CodeValue`, `FieldRequirement`) | Bulletin overrides existing regulatory element |
| `DESIGNATED_BY` | `Organization` → `Organization` | TICO `DESIGNATED_BY` TDI; analog for other agency relationships |
| `RECONCILES_WITH` | `ReportTemplate` → `ReportTemplate` (or `Organization` for external targets) | Reconciliation requirement (Rule 35) |
| `APPLIES_TO` | `Rule` (or `CodeValue`) → `CoverageType` / `EndorsementRule` / scope | Scope restriction |

Properties on `CITES` are critical: `char_start`, `char_end` mark the span in the source document text; `kind` is one of `defines` | `modifies` | `references` to disambiguate why this node cites this rule.

---

## Cardinality and constraints

```cypher
// Uniqueness
CREATE CONSTRAINT node_id_unique IF NOT EXISTS
  FOR (n:GRENode) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT document_hash_unique IF NOT EXISTS
  FOR (d:RegulationDocument) REQUIRE d.hash IS UNIQUE;

CREATE CONSTRAINT rule_unique IF NOT EXISTS
  FOR (r:Rule) REQUIRE (r.section, r.rule_number, r.document_id, r.version) IS UNIQUE;

CREATE CONSTRAINT codelist_name_unique IF NOT EXISTS
  FOR (c:CodeList) REQUIRE (c.code_list_name, c.version) IS UNIQUE;

CREATE CONSTRAINT codevalue_within_list_unique IF NOT EXISTS
  FOR (v:CodeValue) REQUIRE (v.code, v.code_list_id, v.version) IS UNIQUE;

// Indexes for lookup
CREATE INDEX node_type_version IF NOT EXISTS
  FOR (n:GRENode) ON (n.type, n.version);

CREATE INDEX effective_date IF NOT EXISTS
  FOR (n:GRENode) ON (n.effective_from);

CREATE INDEX rule_lookup IF NOT EXISTS
  FOR (r:Rule) ON (r.section, r.rule_number);

CREATE INDEX codelist_lookup IF NOT EXISTS
  FOR (c:CodeList) ON (c.code_list_name);
```

---

## Versioning model

- All nodes are append-only. To "change" a rule, create a new node version (`version=n+1`) and add a `SUPERSEDES` relationship from the new node to the old.
- A node's effective window is `[effective_from, effective_to)`. `effective_to` is set at the moment a successor's `effective_from` arrives.
- Edition pinning at query time:
  ```cypher
  MATCH (n:GRENode {type: $type, name: $name})
  WHERE n.effective_from <= $as_of_date
    AND (n.effective_to IS NULL OR n.effective_to > $as_of_date)
    AND n.status = 'approved'
  RETURN n
  ```

---

## Initial bootstrap targets (LHS-2 seed script)

The hand-crafted seed should populate at least one instance of each node type, all anchored to the same Stat Plan edition for coherence:

1. `RegulationDocument(kind=StatPlan, title='Texas Statistical Plan for Residential Risks')`
2. `StatPlanEdition(edition_name='THSP_2026', effective_date=2026-01-01)`
3. `RegulationDocument(kind=Statute, title='HB 2067')`
4. `RegulationDocument(kind=Bulletin, title='Commissioner Bulletin B-0008-25')`
5. `Organization(org_name='TICO', org_kind=StatisticalAgent)`, `Organization(org_name='TDI', org_kind=Regulator)`, `Organization(org_name='NAIC', org_kind=Regulator)`
6. `Rule(section='A', rule_number=28, title='Designated Statistical Agent')`, plus Rules 21, 29, 34, 35
7. `ReportTemplate(report_name='HO Premiums', cadence=Monthly, deadline_days_after_close=45)` — and the other four
8. `RecordLayout` for each report
9. A few `FieldRequirement` nodes for each layout (just enough to demo `REQUIRES`)
10. `CodeList(code_list_name='Cause of Loss')` with ~5 `CodeValue` children: `25/Windstorm`, `30/Hail`, `05/Fire-Internal`, `10/Fire-External`, `32/Flood-Rising-Water`
11. `CodeList(code_list_name='Line of Business')` with `02`, `03`, `13` (TWIA Wind-Only)
12. `CodeList(code_list_name='HB 2067 Reason Codes')` — placeholder; populated in LHS-3
13. `CoverageType(coverage_name='Dwelling')`, `CoverageType(coverage_name='Personal Property')`, `CoverageType(coverage_name='Loss of Use')`
14. `EndorsementRule(form_code='HO-15')`
15. `ReconciliationRule(from_report=NoticeCount, against_target='NAIC MCAS Cancellations')`
16. A few `HITLTriggerRule` placeholders

All `CITES` relationships pointing at the appropriate `Rule` nodes with span placeholders (real spans land when LHS-3 extracts).

---

## Open schema questions (deferred)

- **`CarrierSOP`** — was in original starter set; dropped here because it's RHS-flavored. Could re-add when RHS work begins.
- **`Coverage` vs `CoverageType`** — using `CoverageType` here. If we later need carrier-specific coverages, may add `Coverage` as instance.
- **Reason source / 60-day indicators** (Rule 34) — these are field-level concepts; modeled as `FieldRequirement` nodes with reference `CodeList`s, not as their own type.
- **`PolicyForm`** — toyed with making this a primary type; instead modeling it as a `CodeList` (`Policy Forms`) per Rule B§5. Re-evaluate if endorsement-form classification logic gets complex.
- **`StateCode`** — could be its own type for multi-state work; for POC it's a `CodeList` with one value (`42 = Texas`).

---

## Changes from v0.1 (the starter set in `docs/poc-decisions.md`)

| v0.1 type | v0.2 disposition |
|---|---|
| `RegulationDocument` | Kept |
| `StatPlanEdition` | Kept |
| `ReportTemplate` | Kept (now 5 with Transmittal) |
| `FieldRequirement` | Kept |
| `COLCodeRule` | **Dropped** — collapsed into `CodeList` + `CodeValue` |
| `TerritoryRule` | **Dropped** — collapsed into `CodeList` (e.g., `Texas Place Codes`) |
| `EndorsementRule` | Kept |
| `NoticeReasonCode` | **Dropped** — collapsed into `CodeList(HB 2067 Reason Codes)` + `CodeValue`s |
| `EditionEffectiveDate` | **Dropped** — modeled as `effective_from` property + `EFFECTIVE_FROM` relationship, not a node |
| `BulletinOverride` | Kept |
| `CarrierSOP` | **Dropped from LHS** — re-add for RHS |
| `HITLTriggerRule` | Kept |
| — | **Added**: `Rule`, `RecordLayout`, `CodeList`, `CodeValue`, `CoverageType`, `ReconciliationRule`, `Organization` |

Net: 12 → 14 node types. Same closed-vocabulary discipline; better aligned to the regulation's actual structure.
