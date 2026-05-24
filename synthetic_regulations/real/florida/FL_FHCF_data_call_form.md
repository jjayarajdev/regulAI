# Florida Hurricane Catastrophe Fund — Annual Data Call Form

**Form**: FHCF-D1A (Personal Lines Residential)
**Reporting Period**: 12-month period ending September 30
**Issuing Authority**: Florida State Board of Administration (SBA), administering the Florida Hurricane Catastrophe Fund under Section 215.555, Florida Statutes
**Source**: RegulAI reconstruction based on public FHCF Data Call documentation
**Jurisdiction**: US-FL
**Document kind**: StatPlan (operational filing form for FHCF participation)

---

## Purpose and Scope

This Annual Data Call collects exposure data from each insurer participating in the Florida Hurricane Catastrophe Fund (FHCF). Participation is mandatory for any insurer authorized to write covered policies in Florida pursuant to Section 215.555(2)(a), F.S. The data submitted on this form is used by the Florida Hurricane Catastrophe Fund to:

1. Calculate each participating insurer's Reimbursement Premium for the contract year
2. Determine each insurer's Projected Payout Multiple for catastrophe events
3. Allocate FHCF capacity and reinsurance recoveries
4. Compute Emergency Assessments under Section 215.555(6), F.S.

## Authority

This data call is issued under:

- Section 215.555, Florida Statutes — Florida Hurricane Catastrophe Fund
- Rule 19-8.029, Florida Administrative Code — Insurer Reporting Requirements
- Section 215.555(5)(b), F.S. — Authority to require uniform exposure data

## Reporting Cadence

The Annual Data Call Form shall be submitted no later than **December 31** of each year, covering the 12-month exposure period ending September 30 of the same year. Late submissions trigger a $1,000-per-day penalty per Rule 19-8.029(7), F.A.C.

## Record Layout — Personal Lines Residential Detail

Each policy in force during the reporting period shall be reported as one fixed-width record of 320 characters. The record layout is:

| Cols | Field | Format | Description |
|---|---|---|---|
| 1–10 | INSURER_NAIC | NUMERIC(10) | NAIC company number of the reporting insurer |
| 11–20 | POLICY_NUMBER | ALPHANUM(10) | Carrier's internal policy identifier |
| 21–25 | RISK_ZIP | NUMERIC(5) | 5-digit ZIP code of the insured location |
| 26–30 | RISK_ZIP4 | NUMERIC(5) | ZIP+4 extension, or zeros if unknown |
| 31–32 | COUNTY_FIPS | NUMERIC(2) | FL county FIPS sub-code (01–67) |
| 33–34 | STATE_CODE | ALPHA(2) | Must be 'FL' for FHCF reporting |
| 35–36 | POLICY_FORM | ALPHANUM(2) | Coverage form per CodeList POLICY_FORM_CODES |
| 37–46 | EFFECTIVE_DATE | DATE(YYYYMMDD) | Policy effective date |
| 47–56 | EXPIRY_DATE | DATE(YYYYMMDD) | Policy expiration date |
| 57–58 | OCCUPANCY_TYPE | ALPHANUM(2) | Per CodeList OCCUPANCY_CODES |
| 59 | NUMBER_OF_FAMILIES | NUMERIC(1) | 1, 2, 3, or 4 |
| 60–61 | CONSTRUCTION_TYPE | ALPHANUM(2) | Per CodeList FHCF_CONSTRUCTION_CODES |
| 62–65 | YEAR_BUILT | NUMERIC(4) | Four-digit year |
| 66 | PROTECTION_CLASS | NUMERIC(1) | Public Protection Classification 1–9 |
| 67–76 | COVERAGE_A | NUMERIC(10) | Dwelling coverage amount, dollars |
| 77–86 | COVERAGE_B | NUMERIC(10) | Other structures coverage amount |
| 87–96 | COVERAGE_C | NUMERIC(10) | Personal property coverage amount |
| 97–106 | COVERAGE_D | NUMERIC(10) | Loss of use coverage amount |
| 107–110 | ALL_PERILS_DEDUCTIBLE | NUMERIC(4) | All-perils deductible in dollars |
| 111–114 | HURRICANE_DEDUCTIBLE | NUMERIC(4) | Hurricane deductible as percentage * 100 |
| 115–124 | WRITTEN_PREMIUM | NUMERIC(10) | Total written premium for the policy |
| 125–134 | EARNED_PREMIUM | NUMERIC(10) | Earned portion for reporting period |
| 135 | WIND_MITIGATION | ALPHA(1) | Y if wind mitigation credit applied, N otherwise |
| 136 | OPENING_PROTECTION | ALPHA(1) | Per CodeList OPENING_PROTECTION_CODES |
| 137 | ROOF_COVER_TYPE | ALPHA(1) | Per CodeList ROOF_COVER_CODES |
| 138 | ROOF_DECK_ATTACHMENT | ALPHA(1) | Per CodeList ROOF_DECK_CODES |
| 139 | ROOF_TO_WALL_CONNECTION | ALPHA(1) | Per CodeList ROOF_WALL_CONNECTION_CODES |
| 140 | SECONDARY_WATER_RESISTANCE | ALPHA(1) | Per CodeList SWR_CODES |
| 141 | TERRAIN_EXPOSURE | ALPHA(1) | B, C, or D per FBC wind exposure categories |
| 142–151 | LATITUDE | NUMERIC(10) | Decimal degrees * 10^6 (geocoded location) |
| 152–161 | LONGITUDE | NUMERIC(10) | Decimal degrees * 10^6 (signed, negative for FL) |
| 162–171 | FHCF_RETENTION | NUMERIC(10) | Insurer's retention contribution |
| 172–320 | RESERVED | SPACE-FILLED | Reserved for future use |

## Code Lists

### POLICY_FORM_CODES (Cols 35–36)

- HO3 — Special Form Homeowners
- HO5 — Comprehensive Form Homeowners
- HO6 — Condominium Unit Owners
- HO8 — Modified Coverage Form
- DP1 — Basic Form Dwelling
- DP3 — Special Form Dwelling
- MH — Mobile Homeowners

### OCCUPANCY_CODES (Cols 57–58)

- O1 — Owner-occupied primary residence
- O2 — Owner-occupied secondary or seasonal
- T1 — Tenant-occupied
- V — Vacant
- BU — Builder's risk during construction

### FHCF_CONSTRUCTION_CODES (Cols 60–61)

- F — Frame
- M — Masonry
- MV — Masonry Veneer
- S — Superior (steel, concrete)
- MH — Mobile Home / Manufactured Housing
- LF — Light Frame
- HM — Heavy Masonry

### OPENING_PROTECTION_CODES (Col 136)

- N — None
- B — Basic (intermediate impact protection)
- H — Hurricane (impact-resistant per FBC)
- A — All openings protected with hurricane-rated coverings

### ROOF_COVER_CODES (Col 137)

- A — Asphalt or fiberglass shingles
- C — Concrete tile
- M — Metal panels
- T — Clay tile
- W — Wood shake / shingle
- O — Other (specify in supplemental filing)

### ROOF_DECK_CODES (Col 138)

- A — 8d nails at 6"/6" spacing (standard)
- B — 8d nails at 6"/12" spacing
- C — Adhesive-secured per FBC Section 1504
- D — Reinforced concrete deck
- O — Other (specify)

### ROOF_WALL_CONNECTION_CODES (Col 139)

- T — Toe nails (legacy)
- C — Clips
- S — Single wraps (one straight strap)
- D — Double wraps (two straight straps)
- A — Adhesive plus mechanical (post-2008 FBC)

### SWR_CODES (Col 140)

- Y — Secondary Water Resistance present
- N — Not present
- U — Unknown / unverified

## Validation Rules

The following validation rules apply at submission time:

1. **NAIC_NUMERIC**: INSURER_NAIC must be exactly 10 digits, leading-zero padded. Reject record if non-numeric.

2. **ZIP_TX_PREFIX_INVALID**: RISK_ZIP must begin with '3' (Florida ZIP prefix). A first digit of '7' (Texas) or other non-FL prefix triggers a hard validation error.

3. **COUNTY_FIPS_VALID**: COUNTY_FIPS must be in the range 01–67 (all 67 Florida counties).

4. **STATE_CODE_FIXED**: STATE_CODE must equal 'FL' exactly. No other value accepted.

5. **HURRICANE_DEDUCTIBLE_RANGE**: HURRICANE_DEDUCTIBLE must be within range [200, 1000] representing 2.0% to 10.0%. Values outside this range trigger a soft warning requiring justification.

6. **COVERAGE_A_PLAUSIBLE**: COVERAGE_A must be between $50,000 and $5,000,000 inclusive. Outside this range triggers a warning.

7. **WIND_MITIGATION_FBC_REQUIRED**: When WIND_MITIGATION = 'Y', all of OPENING_PROTECTION, ROOF_COVER_TYPE, ROOF_DECK_ATTACHMENT, ROOF_TO_WALL_CONNECTION, SECONDARY_WATER_RESISTANCE must be populated (no spaces).

8. **DATE_ORDER**: EFFECTIVE_DATE must precede EXPIRY_DATE.

9. **YEAR_BUILT_RANGE**: YEAR_BUILT must be between 1900 and the current reporting year.

10. **GEOCODE_PRESENT_OR_NULL**: LATITUDE and LONGITUDE must both be populated or both be null. Mixed null state rejected.

## Submission Method

Submit the data file via the FHCF Insurer Reporting Portal at https://www.sbafla.com/fhcf/reporting, using SFTP transfer with PGP encryption. Files must be named:

`FHCF_D1A_{INSURER_NAIC}_{REPORTING_YEAR}.txt`

Companion materials required:

- A signed transmittal certificate from the insurer's responsible actuary
- A reconciliation worksheet showing how the form's aggregate exposure ties to the insurer's NAIC Annual Statement
- A list of any reinsurance ceded that affects FHCF reimbursement calculations

## Reconciliation Requirement

The aggregate of all COVERAGE_A values reported on this form shall reconcile within 0.5% to the insurer's TOTAL_COVERAGE_A reported on Schedule P of the NAIC Annual Statement. Discrepancies exceeding 0.5% trigger a follow-up data quality review by FHCF staff.

---

Contact: FHCF Insurer Reporting Office
Email: reporting@sbafla.com / FHCF
Phone: (850) 413-1340

Florida State Board of Administration
1801 Hermitage Boulevard, Tallahassee, FL 32308
