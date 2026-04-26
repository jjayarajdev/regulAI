# LHS-0 Research — Texas Residential Reporting Regulations

**Date**: 2026-04-25
**Purpose**: Ground the KG schema in the actual structure of Texas residential reporting regulations before locking the closed vocabulary.
**Status**: complete enough for schema refinement and Phase 1 start. Deeper section reads (record layouts, reason codes) deferred to LHS-3 when we author synthetic data.

---

## Document inventory (in `references/regulations/`)

| Doc | Source | Pages | Status |
|---|---|---|---|
| `TX_Statistical_Plan_Residential_Risks_2026.pdf` | tdi.texas.gov/rules/2025/documents/statplanres.pdf | ~85 | **Public**, downloaded; pages 1–35 read |
| `HB02067I.pdf` | capitol.texas.gov/tlodocs/89R/billtext/pdf/HB02067I.pdf | 3 | **Public**, downloaded, fully read |
| Commissioner's Bulletin B-0008-25 | tdi.texas.gov/bulletins/2025/b-0008-25.html | HTML | Read via WebFetch |

**Bottom line on doc availability**: the full TICO Texas Statistical Plan for Residential Risks is **publicly downloadable** as a clean PDF — no paywalls, no registration required. **No user-supplied docs needed for LHS-0.** This was the largest open question; it's resolved.

---

## Key regulatory facts

### Identity
- **Plan title**: Texas Statistical Plan for Residential Risks
- **Effective date**: January 1, 2026 (revised; prior edition was July 1, 2022)
- **Governing authority**: Texas Department of Insurance (TDI)
- **Designated statistical agent**: TICO (Texas Insurance Checking Office) — designated by Commissioner of Insurance, per Rule 28
- **Statistical Plan Code**: 4 (Residential Risk – Dwellings – Homeowners)
- **State Code**: 42 (Texas)

### HB 2067 (signed into law, effective September 1, 2025)
The bill itself is short — 7 sections, ~3 pages — and authorizes the *commissioner* to adopt rules. The substantive field-level reporting requirements live in the revised **TICO Statistical Plan**, not in the statute. So the Stat Plan is the operationally important doc.

Key statute changes:
- §551.001(a): commissioner may adopt rules on declination/cancellation/nonrenewal notices
- §551.002(a): removes "on request" — written reasons now automatic, not on request
- §551.0521 (new): written notice of declination required for liability/commercial property applications
- §551.055: notices must state reason for declination/cancellation/nonrenewal
- §551.109: insurer statement obligation no longer "at request of"

### Required reports (Rule 28)
TICO requires four residential reports:
1. **Dwelling, HO Premiums**
2. **Dwelling, HO Losses**
3. **Dwelling, HO Cancellation, Nonrenewal, and Declination Notices** (NEW per HB 2067)
4. **Dwelling, HO Number of Actual Cancellations, Nonrenewals, and Declinations** (NEW per HB 2067)

### Reporting cadence (Rule 21)
- **Monthly** unit transaction reports for premiums and exposures + losses paid/outstanding
- **Monthly** reasons for cancellations/nonrenewals/declinations (by *notification month*)
- **Monthly** counts of cancellations/nonrenewals/declinations (by *effective month*)
- **45-day** deadline after close of experience month
- **Annual** reconciliation to TICO

### Transmittal form (Rule 29)
Every submission is accompanied by a transmittal containing:
- Company Name, NAIC Company Code
- Record count for each of 4 reports
- Totals: Written Premium, Paid Losses, Outstanding Losses, **Recipient Count**, **Number of Cancellations**, **Number of Nonrenewals**, **Number of Declinations**
- Format: Fixed ASCII Standard Data Format (SDF)
- Submission: electronic (formerly via ShareFile)
- Farm mutuals report 0 for premium/loss fields (still report notice/count fields)

### Notice reporting structure (Rule 34, key for HB 2067 demo)
For each cancellation/nonrenewal/declination:
- Insurer concatenates applicable reason codes **alphabetically** into a single string (e.g., reasons D, L, R → `"DLR"`)
- One record per **unique combination** of: notification date, action type, type of policy, **reason source indicator**, **60-day indicator**, ZIP code, action effective date, reason code list
- **Recipient count** field = number of policies/applications matching that combination

Reasons must be reported for notices effective on/after January 1, 2026. Transfer between admitted companies in the same insurance group is *not* a refusal to renew (per Insurance Code §551.004).

### Counts reporting structure (Rule 35)
- Counts by ZIP code
- Reconciliation requirement: counts **must reconcile** with NAIC Market Conduct Annual Statement (MCAS) figures for cancellations and nonrenewals
- 45 days after experience month

### Reconciliation note
The Notice Count report isn't just a count — Rule 35 explicitly requires it to reconcile against NAIC MCAS. Mismatches are real edit-check failures, not just rounding. **Implication for KG**: there's a `RECONCILES_WITH` relationship between `TX_HO_NOTICE_COUNT_G` and the conceptual "MCAS report" that we can model.

---

## Structural overview of the Stat Plan

Seven sections:

| Section | Title | Pages | Contents |
|---|---|---|---|
| A | General Rules | 1–20 | 35 numbered rules covering scope, recording methods, identifiers, designated agent, transmittal form, HB 2067 reasons + counts |
| B | Coding for Premiums and Losses | 21–35 | Code tables — the actual code values for every coded field |
| C | Record Layout for Premiums | 36–56 | Field-by-field layout of premium records |
| D | Record Layout for Losses | 57–72 | Field-by-field layout of loss records |
| E | Record Layout for Cancellation, Nonrenewal, and Declination Notices | 73–76 | NEW — record layout for HB 2067 notice report |
| F | Additional Instructions for Notices | 77–82 | NEW — full reason code list with definitions, source indicators, etc. |
| G | Record Layout for Number of Actual Cancellations, Nonrenewals, and Declinations | 83–85 | NEW — record layout for HB 2067 count report |

**Read deeply for LHS-0**: A (rules) + first half of B (code tables identified). Sufficient for schema.
**Deferred to LHS-3**: full B code value enumerations + C/D/E/F/G record layouts. LHS-3 will cherry-pick what's needed for the synthetic data and citation chains.

---

## Code lists identified (for the KG)

This is the dominant pattern in the regulation: nearly every coded field points to a named code list. The KG should treat `CodeList` and `CodeValue` as primary types.

| Code list | Source rule | Sample values |
|---|---|---|
| Statistical Plan Code | B§1 | `4` = Residential Risk |
| State Code | B§2 | `42` = Texas |
| Kind Codes — Losses | B§3 | `1`–`9` (no-payment / paid / outstanding combinations with prior-status) |
| Line of Business | B§4 | `02` HO Tenants, `03` HO, `10` Dwelling Fire, `13` TWIA Wind-Only, `14`/`15` Voluntary Wind-Only, `20` Extended Coverage, `28` All Risk, `29` Private Flood, `35` Standalone Flood, plus more |
| Policy Forms | B§5 | Numeric codes for HO/Dwelling forms; letter codes (`A`–`Z`, `6`–`8`) for ISO/AAIS/independent forms |
| Number of Families | B§6 | `1`/`2`/`8`/`9` |
| Coverage — Occupancy | B§7 | `1`–`9` (Owner Occupied, Tenant, Vacant, etc.). Code `7` (vacant) requires TICO approval |
| Construction | B§8 | `1` Frame, `2` Brick Veneer, `3` Brick/Stone, `4` Fire Resistive, `5` Mobile, `8` Stucco, `9` N/A |
| Roof Covering | B§8A | `A`–`P` (Composition, Wood, Aluminum, Steel, Tile, Slate, Metal, etc.) |
| Roof Credit (UL2218) | B§8A | `0`–`4` |
| ISO PPC | B§9, 9A | `1`–`B` (rural fire protection class) |
| Deductible Type/Amount | B§10 | `1`–`9`, `A`–`Z`, `*1` Full Coverage, `**7` No Wind Coverage. Multi-clause: Wind/Hail (Clause 1), Other (Clause 2), Tenants (Clause 3), Tropical Cyclone separate |
| Type of Loss | B§11 | `1`/`2`/`3` (HO Section I, Section II additional, enhancement endorsement) |
| **Cause of Loss** | **B§12** | `05` Fire Internal, `10` Fire External, `15` Fire Unknown, `20` Lightning, `25` Windstorm, `30` Hail, `32` Flood/Rising Water, `33` Explosion, `35` Smoke, `40` Aircraft/Vehicles, `45` Riot, `50` V&MM, `55` Collapse, `60`/`61` Water Damage (Slab/Other), `70`/`71` Freeze (Slab/Other), `75` Burglary/Theft, `80` Other Physical, `90` Other Liability/MedPay |
| Prior Claims History | B§13 | `0`–`6` (count of chargeable claims in last 5 yrs, `6` = not used) |
| Building Code Credits (TWIA) | B§15 | `01`–`09` (Seaward/Inland I/Inland II × New/Retrofit) |
| Law and Ordinance Coverage | B§16 | `0`–`4` |
| Optional Credit — Personal Property ID | B§17 | `0`/`1` |
| Use of Rating Variables | B§20 | `1`–`5` for each of: fire/smoke/burglar alarm, age of home, sprinkler, loss experience, companion policy, credit-based score, senior, smart home, new home, additional risk surcharges |
| Tenure | A§30 | `0`–`7` |
| TWIA Depopulation | A§31 | `13`/`14`/`15` |
| **HB 2067 Reason Codes** | F (deferred) | Letter codes; concatenated alphabetically (e.g., `"DLR"`) |
| Action Type | F (deferred) | Cancellation / Nonrenewal / Declination |
| Reason Source Indicator | F (deferred) | Used in deduplication key per Rule 34 |
| 60-Day Indicator | F (deferred) | Used in deduplication key per Rule 34 |

**Schema correction**: the prior assumption (mock-ui-v2 letter codes like `WH`, `WN`, `HA`) is wrong for the actual TICO regulation. Real Cause of Loss codes are integers (`25` Windstorm, `30` Hail). The agentic WH-vs-WN narrative reframes as "named storm wind vs other wind" — both are still Cause of Loss `25` (Windstorm), but the synthetic data will need a derived classifier flag rather than two separate COL codes. Worth re-checking before LHS-3 — there may be a separate "named storm" indicator I haven't located yet.

---

## What's not yet researched (deferred to later sub-phases)

- **Section B remaining items** (deductible code completeness, etc.)
- **Section C/D/E/G record layouts** — exact field positions, lengths, formats. Cherry-pick during LHS-3 for synthetic data; not needed for schema.
- **Section F reason codes** — complete enumeration for HB 2067 reasons. Needed before LHS-3 demo of the change-trigger bulletin. Read on demand.
- **Bulletin B-0012-25, B-0016-25** — referenced in search results, not yet fetched. May contain TX residential-specific guidance worth ingesting as additional bulletins.
- **Bulletin B-0008-25 actual full text** — WebFetch returned a summary; may want the verbatim text for the side-by-side demo.
- **The TDI rule adoption document** (`20269741.pdf`) — formal adoption notice for the revised plan; useful provenance for `EditionEffectiveDate` nodes.

These are all addressable as needed. None block LHS-1 (foundation) or schema definition.

---

## Implications for the KG schema

1. **`CodeList` and `CodeValue` are primary node types**, not afterthoughts. The bulk of regulatory expressivity lives in code-list definitions. Each `CodeList` has many `CodeValue` children via `HAS_VALUE` relationships.
2. **`Rule` is a meaningful node type** — the Stat Plan organizes content as numbered rules (A§1, A§28, B§12, etc.), and rules are the natural anchor for citations. Promoting Rule to a first-class node lets every other node (`CodeList`, `FieldRequirement`, `ReportTemplate`) cite a specific rule cleanly.
3. **`Organization` is needed** — TICO and TDI are entities with relationships (TICO `DESIGNATED_BY` TDI). Useful for transmittal recipient logic and downstream regulatory interactions.
4. **`ReportTemplate` already correct** — four reports identified (Premium / Loss / Notice / Count). Add a fifth: Transmittal Form (Rule 29 specifies its structure).
5. **`RecordLayout` is a meaningful intermediate** between `ReportTemplate` and `FieldRequirement` — Sections C/D/E/G are each a "Record Layout" with many fields. Templates `CONTAINS_LAYOUT` layouts; layouts `REQUIRES` fields.
6. **`ReconciliationRule`** — Rule 35 explicitly requires Count report to reconcile with NAIC MCAS. This is its own concept, distinct from `FieldRequirement`. Add to schema.
7. **`StatPlanEdition`** stays. The Jan 1, 2026 vs prior July 1, 2022 distinction is the reference example. Edition pinning by `EFFECTIVE_FROM` relationship.
8. **`BulletinOverride`** stays. B-0008-25 is the reference example.
9. **Drop `COLCodeRule` and `TerritoryRule` as separate types.** They're instances of the more general `CodeList` pattern. (`COLCodeRule[WH]` becomes `CodeValue[code='25', name='Windstorm']` within `CodeList[name='Cause of Loss']`.)
10. **`NoticeReasonCode` becomes `CodeList[name='HB 2067 Reason Codes']`** — same generic pattern.
11. **Add `Coverage` (or `CoverageType`)** — Dwelling / Personal Property / Loss of Use are explicit per Rule 6, and `FieldRequirement` nodes need to reference them.
12. **`HITLTriggerRule`** stays but is application-derived, not regulation-derived. Lives in KG but cited from internal SOPs, not regulations.

---

## Implications for the build plan

- **No user-supplied docs needed** for LHS-0/LHS-1/LHS-2. The public TICO Stat Plan covers everything for schema + bootstrap.
- **OpenAI Sentinel agent** has a tractable closed vocabulary (refined schema below in `docs/kg-schema.md`).
- **First synthetic change bulletin** (LHS-3) should target a real, demonstrably-impactful change. Strong candidate: a synthetic bulletin that adds a new Cause of Loss code (e.g., adds `26` for "Named Storm Wind" splitting from generic Windstorm `25`). Demonstrates the rules-level loop because it (a) adds a `CodeValue` to the `Cause of Loss` `CodeList`, (b) creates a `BulletinOverride` of the existing rule, (c) requires a re-classification capability in the (future) RHS Bridge agent. Grounded in the real WH-vs-WN regulatory tension that mock-ui-v2 modeled.

---

## Sources

- [Texas Statistical Plan for Residential Risks (eff. Jan 1, 2026)](https://www.tdi.texas.gov/rules/2025/documents/statplanres.pdf)
- [HB 2067 (89th Legislature)](https://capitol.texas.gov/tlodocs/89R/billtext/pdf/HB02067I.pdf)
- [Commissioner's Bulletin B-0008-25 (HB 2067 implementation)](https://www.tdi.texas.gov/bulletins/2025/b-0008-25.html)
- [TICO public site](https://ticostat.com/TICOCorpHome.action)
- [TDI Bulletins index 2025](https://www.tdi.texas.gov/bulletins/2025/index.html)
- [TDI Statistical Plan landing page](https://www.tdi.texas.gov/company/data-collection/dcspres.html)
