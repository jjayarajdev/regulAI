# ISO Statistical Reporting — Implementation Impact Analysis

**Branch:** `feature/iso-report`
**Scope requested:** understand the changes required to implement ISO statistical
reporting alongside the current codebase — **shared core for both plans**.

## Source documents

Two Verisk / Insurance Services Office (ISO) statistical plans — the rulebooks +
record layouts insurers follow to report premium/loss statistics to ISO. They are
structurally twins.

| Plan | Notice | Pages | Lines of business |
|---|---|---|---|
| **Personal Lines Statistical Plan – Other Than Automobile (PLSP-OTA), 2024** | `SP-PL-2023-PLSP-003` | 694 | Homeowners, Dwelling, Mobilehomes, Earthquake, Inland Marine, Liability-OTA, Broad Form Theft (+ tenants, condos, watercraft, farms) |
| **Commercial Statistical Plan (CSP), 2024** | `SP-CL-2024-CSP-001` | 2,287 | Fire, Allied, Businessowners, GL, Commercial Auto, Farm, Inland Marine, Med Prof Liability, Crime, Boiler/Equipment Breakdown, Cyber, … |

Both organise as **General Rules** (Section A premiums & losses, B premiums,
C losses, **D = record layout**) then per-line **coding modules**. Data is emitted
as **fixed-width, positional records** with mainframe-style domain encodings.

### Technical elements a report engine must handle

- **Two record types** — Premium & Loss — each a positional field spec (Section D).
- **Transaction Type** — `1` fully coded, `2` limited coded.
- **Single-char month codes** (CSP): `1–9` = Jan–Sep, `0` = Oct, `-` = Nov, `&` = Dec.
- **Over-punched signed amounts** (CSP GR-2.1/2.2) — zoned-decimal: the sign rides
  the units digit (`{`=+0…`I`=+9; `}`=−0…`R`=−9), right-justified, leading zeros.
- **Coded dimensions** — classification, territory, ZIP (mandatory/optional *by line*),
  coverage, deductible, construction, BCEG class code, Company Program Exception.
- **CSP-i "Intermediate" level** — Statistical Plan Indicator `M` at premium
  position 76 / loss position 16.
- **State exceptions** (e.g. Texas carve-outs) and per-line claim-count /
  salvage-subrogation / ALAE rules.

## Verdict

**RegulAI already built this engine — for Texas.** The existing TICO/TX pipeline is
the same pattern end to end, so this is a *generalization*, not a new subsystem.
Estimated **~80% reuse**.

### What already exists (reusable as-is or with light change)

| Component | File | Role |
|---|---|---|
| KG record-layout model | closed KG vocabulary | `RecordLayout` → `FieldRequirement` (position/length/format) → `CodeList` → `CodeValue`. Structurally = an ISO Section-D + coding module. |
| Layout ingest (deterministic) | `scripts/parse_record_layout.py` | PyMuPDF + state machine turns a fixed-width layout PDF into those nodes. |
| Rulebook ingest (LLM) | `packages/lhs/sentinel/*` | Sentinel extracts GR prose → KG. |
| Report generator | `scripts/generate_sample_submission.py` | Walks `FieldRequirement`s in column order → fixed-width line. |
| Report validator | `scripts/validate_submission.py` | length / unknown-code / bad-format / dirty-skip checks. |
| Doc registry | `api/registry.py` | `DocEntry` list + `WIRE_LAYOUTS_FOR_SLUG`; already juggles TICO-TX **and** FL-FHCF **and** FL-CRS layouts. |
| Canonical model + mapper | `SILVER.TSPR_*`, `packages/rhs/mapper/*` | Medallion staging + the agentic source→canonical mapper. |
| Rules-as-data | `REFERENCE.*` | Validation rules stored as data. |

## Layer-by-layer impact

| Layer | Exists today | Change for ISO (shared core) | Size |
|---|---|---|---|
| Doc registry `api/registry.py` | `DocEntry` list + slug→layout map, multi-source | Add `DocEntry` rows for PLSP-OTA & CSP + slugs; add a `(plan, line, record_type)` key so a layout isn't implicitly "the TICO one". | S |
| Layout ingest `parse_record_layout.py` | State machine for the TICO HO table | Generalize to ISO's Section-D table shape; run per module. Sentinel handles GR prose. | M–L |
| KG vocabulary | `FieldRequirement` has position/length/`format` | Add an **`encoding`** attribute (identity / zero-pad / date-MMDDY / iso-month-char / overpunch-signed / code-map). | S |
| Encoder/codec layer | encodings implicit inside the generator | **Net-new: a pluggable codec registry** keyed off `encoding`. TSPR's MMDDY/MMY and ISO's month-char + overpunch all become registered codecs. | M |
| Report generator `generate_sample_submission.py` | emits, but `RECORD_LENGTH = 200` is **hardcoded** | Take record length from the layout; insert the codec step per field; drive by `(plan,line)`. | M |
| Report validator `validate_submission.py` | length/code/format checks, 200 hardcoded | Same de-hardcoding + a **decode** step so encoded fields validate (overpunch amount must decode before range checks). | M |
| Canonical → ISO mapping | SILVER `TSPR_*` is TX-shaped; mapper exists | Map canonical fields → ISO field positions per module. Reuse the **mapper**, targeting ISO layouts instead of `TSPR_PREMIUM_STAGING`. | L |
| Rules-as-data `REFERENCE.*` | TX validation rules | Add ISO conditional rules (ZIP-by-line, CSP-i indicator, state exceptions) as data. | M |

## The three genuinely new things

1. **A codec registry** — the one real new abstraction. Today an encoding like MMDDY
   lives inline; ISO forces field encoding to become first-class (because of overpunch
   signed amounts and single-char month codes, which TX doesn't use). Once
   `FieldRequirement.encoding` + a codec table exist, generator and validator both just
   look up the codec. This turns "TICO tool" into "statistical-reporting engine".
2. **The plan/line/record-type key** — replacing the implicit "there is one layout"
   with a real dimension, so TICO-TX, ISO-PLSP-Homeowners, ISO-CSP-GL coexist.
3. **Canonical-model divergence** — ISO field semantics ≠ TSPR. SILVER is Texas-shaped;
   feeding ISO means extending the canonical model or mapping SILVER→ISO. The agentic
   mapper is the tool, but the ISO field-spec target contracts must exist first.

## Blockers hiding in the code

- `RECORD_LENGTH = 200` (`generate_sample_submission.py`) and the same assumption in
  `validate_submission.py` — ISO records are a different width; must come from the layout.
- Naming/paths hard-wired to `tico-*` / `TSPR_*` — the shared core needs neutral naming.
- `_STAT_PLAN_PDF` / `_HO_PDF` constants point at TX files — should be registry-driven.

## Recommended phasing (shared core first)

1. **Shared core, no ISO yet:** introduce `FieldRequirement.encoding` + codec registry,
   de-hardcode record length, add the `(plan,line,record_type)` key — and **re-express
   the existing TICO path through it** (proves the refactor is behavior-preserving; the
   existing submission scripts/tests are the safety net).
2. **Ingest one ISO module** (Homeowners in PLSP — closest to current data) via the
   generalized parser + Sentinel → KG.
3. **Round-trip it:** canonical → generate ISO record → validate fail-closed, exactly
   like the TSPR / agentic-mapping flow.
4. **Add a Commercial module** (GL or Cyber) to exercise CSP-i + overpunch.

## Risks to manage

- **Scale & copyright of the plans** — 694 + 2,287 pages, and ISO code lists are
  proprietary Verisk content. Ingest **only the modules in use**, and treat code values
  as licensed reference data (do not check the raw tables into the repo wholesale).
- **Encoder correctness is compliance-critical** — an off-by-one on overpunch or a wrong
  month char silently produces a rejected filing. These codecs need golden-record unit
  tests before anything downstream trusts them.

## Net

The engine, KG model, generator, validator, registry, Sentinel, and mapper all already
exist. The additions are **one new abstraction (codecs)**, **one de-hardcoding pass**,
and **the ISO layout ingestion**.
