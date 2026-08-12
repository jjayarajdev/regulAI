// Mapping-review fixture — generated verbatim from the real artifacts at
// materialized/mappings/guidewire_fl_fhcf.{mapping,reviewed,compiled}.json,
// assembled exactly the way api/rhs_demo.py's /mappings + /mapping/{name}
// endpoints assemble them. All 26 columns and all 7 review overrides are real.
import type { MappingDetail, MappingsResponse } from '../api/types';

export const mappingDetail: MappingDetail = {
  "name": "guidewire_fl_fhcf",
  "source_label": "guidewire_fl_fhcf",
  "target": "FHCF_EXPOSURE",
  "target_table": "INSURANCE_REGULATORY.SILVER.FHCF_EXPOSURE_STAGING",
  "columns": [
    {
      "target_column": "insurer_naic",
      "source_column": "uw.naiccode",
      "transform_type": "lookup",
      "confidence": 0.98,
      "needs_review": false,
      "accepted": true,
      "overridden": false,
      "accepted_sql": "(SELECT LPAD(TRIM(MAX(uw.naiccode)), 10, '0') FROM INSURANCE_REGULATORY.BRONZE.GW_PC_UWCOMPANY uw)",
      "proposed_sql": "(SELECT LPAD(TRIM(MAX(uw.naiccode)), 10, '0') FROM INSURANCE_REGULATORY.BRONZE.GW_PC_UWCOMPANY uw)",
      "override_reason": null,
      "rationale": "Reporting carrier NAIC is in the single-row underwriting-company reference table; FHCF requires 10-character left-padded code.",
      "review_note": null
    },
    {
      "target_column": "policy_number",
      "source_column": "p.policynumber",
      "transform_type": "direct",
      "confidence": 0.99,
      "needs_review": false,
      "accepted": true,
      "overridden": false,
      "accepted_sql": "TRIM(p.policynumber)",
      "proposed_sql": "TRIM(p.policynumber)",
      "override_reason": null,
      "rationale": "Guidewire policy number is the policy identifier for the exposure row.",
      "review_note": null
    },
    {
      "target_column": "risk_zip",
      "source_column": "dw.zip",
      "transform_type": "direct",
      "confidence": 0.75,
      "needs_review": true,
      "accepted": true,
      "overridden": false,
      "accepted_sql": "LPAD(TRIM(CAST(dw.zip AS STRING)), 5, '0')",
      "proposed_sql": "LPAD(TRIM(CAST(dw.zip AS STRING)), 5, '0')",
      "override_reason": null,
      "rationale": "Dwelling ZIP is the risk-location ZIP, but profiled sample values are non-FL despite the fixed FL filter; confirm filtered values are valid FL 5-digit ZIPs.",
      "review_note": "Accepted. Zero-pad guard is a no-op on this book; profile samples looked non-FL because the full Bronze table also holds the TX book — the FL filter scopes the load."
    },
    {
      "target_column": "risk_zip4",
      "source_column": "dw.ziplus4",
      "transform_type": "direct",
      "confidence": 0.9,
      "needs_review": false,
      "accepted": true,
      "overridden": false,
      "accepted_sql": "CASE WHEN dw.ziplus4 IS NULL OR TRIM(CAST(dw.ziplus4 AS STRING)) = '' THEN NULL ELSE LPAD(TRIM(CAST(dw.ziplus4 AS STRING)), 4, '0') END",
      "proposed_sql": "CASE WHEN dw.ziplus4 IS NULL OR TRIM(CAST(dw.ziplus4 AS STRING)) = '' THEN NULL ELSE LPAD(TRIM(CAST(dw.ziplus4 AS STRING)), 4, '0') END",
      "override_reason": null,
      "rationale": "Dwelling ZIP+4 add-on matches risk-location ZIP+4.",
      "review_note": null
    },
    {
      "target_column": "county_fips",
      "source_column": "dw.countyfips",
      "transform_type": "direct",
      "confidence": 0.45,
      "needs_review": true,
      "accepted": true,
      "overridden": true,
      "accepted_sql": "TRIM(dw.countyfips)",
      "proposed_sql": "LPAD(RIGHT(TRIM(CAST(dw.countyfips AS STRING)), 2), 2, '0')",
      "override_reason": "OVERRIDE: proposal took RIGHT(...,2) assuming a full 5-digit FIPS; Bronze already carries the 2-digit FL county sub-code, so plain TRIM is correct.",
      "rationale": "Source is named countyfips but samples look like 5-digit full FIPS, while target expects a 2-digit Florida/FHCF county code; expression takes rightmost two digits pending SME confirmation.",
      "review_note": "OVERRIDE: proposal took RIGHT(...,2) assuming a full 5-digit FIPS; Bronze already carries the 2-digit FL county sub-code, so plain TRIM is correct."
    },
    {
      "target_column": "state_code",
      "source_column": "dw.state",
      "transform_type": "direct",
      "confidence": 0.95,
      "needs_review": false,
      "accepted": true,
      "overridden": false,
      "accepted_sql": "UPPER(TRIM(dw.state))",
      "proposed_sql": "UPPER(TRIM(dw.state))",
      "override_reason": null,
      "rationale": "Fixed join filters dwelling state to FL; normalize source state to two-letter uppercase code.",
      "review_note": null
    },
    {
      "target_column": "policy_form",
      "source_column": "line.holineform",
      "transform_type": "direct",
      "confidence": 0.55,
      "needs_review": true,
      "accepted": true,
      "overridden": false,
      "accepted_sql": "TRIM(line.holineform)",
      "proposed_sql": "TRIM(line.holineform)",
      "override_reason": null,
      "rationale": "HO line form appears to be the closest policy-form field, but sample codes A/B do not look like FHCF form codes such as HO3/HO5/DP1.",
      "review_note": "Accepted. A/B samples in the profile are the TX book; FL rows carry HO3/HO5."
    },
    {
      "target_column": "effective_date",
      "source_column": "line.effectivedate",
      "transform_type": "direct",
      "confidence": 0.98,
      "needs_review": false,
      "accepted": true,
      "overridden": false,
      "accepted_sql": "CAST(line.effectivedate AS DATE)",
      "proposed_sql": "CAST(line.effectivedate AS DATE)",
      "override_reason": null,
      "rationale": "HO policy line effective date is the policy period start; cast timestamp string to DATE.",
      "review_note": null
    },
    {
      "target_column": "expiry_date",
      "source_column": "line.expirationdate",
      "transform_type": "direct",
      "confidence": 0.98,
      "needs_review": false,
      "accepted": true,
      "overridden": false,
      "accepted_sql": "CAST(line.expirationdate AS DATE)",
      "proposed_sql": "CAST(line.expirationdate AS DATE)",
      "override_reason": null,
      "rationale": "HO policy line expiration date is the policy period end; cast timestamp string to DATE.",
      "review_note": null
    },
    {
      "target_column": "occupancy_type",
      "source_column": "line.occupancytype",
      "transform_type": "composite",
      "confidence": 0.75,
      "needs_review": true,
      "accepted": true,
      "overridden": true,
      "accepted_sql": "CASE WHEN line.occupancytype = 'OwnerOccupied' THEN 'O1' ELSE 'O2' END",
      "proposed_sql": "CASE WHEN UPPER(TRIM(line.occupancytype)) IN ('OWNEROCCUPIED','OWNER_OCCUPIED') AND CAST(dw.numberoffamilies AS INT) = 1 THEN 'O1' ELSE 'O2' END",
      "override_reason": "OVERRIDE: dropped the proposal's extra numberoffamilies=1 clause — the implemented FHCF encoding keys on occupancy only (HO book is single-family; a NULL family count must not demote O1 to O2).",
      "rationale": "Guidewire occupancy plus dwelling family count can derive O1/O2, but FHCF occupancy is domain-encoded and should be confirmed.",
      "review_note": "OVERRIDE: dropped the proposal's extra numberoffamilies=1 clause — the implemented FHCF encoding keys on occupancy only (HO book is single-family; a NULL family count must not demote O1 to O2)."
    },
    {
      "target_column": "construction_type",
      "source_column": "dw.constructiontype",
      "transform_type": "direct",
      "confidence": 0.55,
      "needs_review": true,
      "accepted": true,
      "overridden": false,
      "accepted_sql": "TRIM(CAST(dw.constructiontype AS STRING))",
      "proposed_sql": "TRIM(CAST(dw.constructiontype AS STRING))",
      "override_reason": null,
      "rationale": "Dwelling construction type is the closest field, but sample numeric codes may require translation to FHCF construction classes such as F/M.",
      "review_note": null
    },
    {
      "target_column": "year_built",
      "source_column": "dw.yearbuilt",
      "transform_type": "direct",
      "confidence": 0.98,
      "needs_review": false,
      "accepted": true,
      "overridden": false,
      "accepted_sql": "CAST(dw.yearbuilt AS INT)",
      "proposed_sql": "CAST(dw.yearbuilt AS INT)",
      "override_reason": null,
      "rationale": "Dwelling year built directly matches target year_built.",
      "review_note": null
    },
    {
      "target_column": "protection_class",
      "source_column": "dw.ppccode",
      "transform_type": "direct",
      "confidence": 0.9,
      "needs_review": false,
      "accepted": true,
      "overridden": false,
      "accepted_sql": "CAST(NULLIF(TRIM(CAST(dw.ppccode AS STRING)), '') AS INT)",
      "proposed_sql": "CAST(NULLIF(TRIM(CAST(dw.ppccode AS STRING)), '') AS INT)",
      "override_reason": null,
      "rationale": "Dwelling PPC code matches Public Protection Class; cast string code to integer.",
      "review_note": null
    },
    {
      "target_column": "coverage_a",
      "source_column": "cov.coverageamount",
      "transform_type": "direct",
      "confidence": 0.98,
      "needs_review": false,
      "accepted": true,
      "overridden": false,
      "accepted_sql": "CAST(cov.coverageamount AS BIGINT)",
      "proposed_sql": "CAST(cov.coverageamount AS BIGINT)",
      "override_reason": null,
      "rationale": "Joined coverage is dwelling Coverage A per fixed relation/profile coverage type A; amount is the dwelling limit.",
      "review_note": null
    },
    {
      "target_column": "hurricane_deductible",
      "source_column": "cov.tropicalcyclonedeductible",
      "transform_type": "direct",
      "confidence": 0.8,
      "needs_review": true,
      "accepted": true,
      "overridden": true,
      "accepted_sql": "CAST(cov.tropicalcyclonedeductible AS INT)",
      "proposed_sql": "CAST(cov.tropicalcyclonedeductible AS BIGINT)",
      "override_reason": "OVERRIDE: BIGINT → INT to match the target DDL (values are whole-dollar deductibles).",
      "rationale": "FHCF hurricane deductible should use Guidewire tropical-cyclone deductible, but source is sparse in the profile; confirm whether wind/hail fallback is needed.",
      "review_note": "OVERRIDE: BIGINT → INT to match the target DDL (values are whole-dollar deductibles)."
    },
    {
      "target_column": "written_premium",
      "source_column": "cov.writtenpremium",
      "transform_type": "direct",
      "confidence": 0.95,
      "needs_review": false,
      "accepted": true,
      "overridden": false,
      "accepted_sql": "CAST(ROUND(cov.writtenpremium) AS BIGINT)",
      "proposed_sql": "CAST(ROUND(cov.writtenpremium) AS BIGINT)",
      "override_reason": null,
      "rationale": "Coverage written premium matches target written premium; round to whole dollars.",
      "review_note": null
    },
    {
      "target_column": "wind_mitigation",
      "source_column": "dw.windmitigation",
      "transform_type": "composite",
      "confidence": 0.9,
      "needs_review": true,
      "accepted": true,
      "overridden": false,
      "accepted_sql": "CASE WHEN UPPER(TRIM(dw.windmitigation)) = 'Y' THEN 'Y' ELSE 'N' END",
      "proposed_sql": "CASE WHEN UPPER(TRIM(dw.windmitigation)) = 'Y' THEN 'Y' ELSE 'N' END",
      "override_reason": null,
      "rationale": "Wind mitigation flag is explicitly present; FHCF domain requires Y only when inspection is on file and all other values normalized to N.",
      "review_note": "Accepted. NULL falls through the CASE to 'N', equivalent to the COALESCE in the hand-written reference."
    },
    {
      "target_column": "opening_protection",
      "source_column": "dw.openingprotection",
      "transform_type": "direct",
      "confidence": 0.9,
      "needs_review": false,
      "accepted": true,
      "overridden": true,
      "accepted_sql": "dw.openingprotection",
      "proposed_sql": "CASE WHEN UPPER(TRIM(dw.windmitigation)) = 'Y' THEN TRIM(dw.openingprotection) ELSE NULL END",
      "override_reason": "OVERRIDE: Direct from the OIR-B1-1802 extension column — the carrier only populates companions when an inspection is on file, so the proposal's CASE gate is redundant.",
      "rationale": "Opening protection is an OIR-B1-1802 companion value and should be reported only when wind mitigation is Y.",
      "review_note": "OVERRIDE: Direct from the OIR-B1-1802 extension column — the carrier only populates companions when an inspection is on file, so the proposal's CASE gate is redundant."
    },
    {
      "target_column": "roof_cover_type",
      "source_column": "line.roofcoveringtype",
      "transform_type": "composite",
      "confidence": 0.8,
      "needs_review": true,
      "accepted": true,
      "overridden": false,
      "accepted_sql": "CASE WHEN UPPER(TRIM(dw.windmitigation)) = 'Y' THEN TRIM(line.roofcoveringtype) ELSE NULL END",
      "proposed_sql": "CASE WHEN UPPER(TRIM(dw.windmitigation)) = 'Y' THEN TRIM(line.roofcoveringtype) ELSE NULL END",
      "override_reason": null,
      "rationale": "Guidewire HO line roof covering type is the closest roof cover type, but FHCF roof-cover code domain requires review; report only with wind mitigation Y.",
      "review_note": "Accepted. The one genuinely gated companion: roof cover rides the HO line and is reported only when wind_mitigation = 'Y'."
    },
    {
      "target_column": "roof_deck_attachment",
      "source_column": "dw.roofdeckattachment",
      "transform_type": "direct",
      "confidence": 0.9,
      "needs_review": false,
      "accepted": true,
      "overridden": true,
      "accepted_sql": "dw.roofdeckattachment",
      "proposed_sql": "CASE WHEN UPPER(TRIM(dw.windmitigation)) = 'Y' THEN TRIM(dw.roofdeckattachment) ELSE NULL END",
      "override_reason": "OVERRIDE: Direct from the extension column (see opening_protection).",
      "rationale": "Roof deck attachment is an OIR-B1-1802 companion value and should be reported only when wind mitigation is Y.",
      "review_note": "OVERRIDE: Direct from the extension column (see opening_protection)."
    },
    {
      "target_column": "roof_to_wall_connection",
      "source_column": "dw.rooftowallconnection",
      "transform_type": "direct",
      "confidence": 0.9,
      "needs_review": false,
      "accepted": true,
      "overridden": true,
      "accepted_sql": "dw.rooftowallconnection",
      "proposed_sql": "CASE WHEN UPPER(TRIM(dw.windmitigation)) = 'Y' THEN TRIM(dw.rooftowallconnection) ELSE NULL END",
      "override_reason": "OVERRIDE: Direct from the extension column (see opening_protection).",
      "rationale": "Roof-to-wall connection is an OIR-B1-1802 companion value and should be reported only when wind mitigation is Y.",
      "review_note": "OVERRIDE: Direct from the extension column (see opening_protection)."
    },
    {
      "target_column": "secondary_water_resistance",
      "source_column": "dw.secondarywaterresistance",
      "transform_type": "direct",
      "confidence": 0.9,
      "needs_review": false,
      "accepted": true,
      "overridden": true,
      "accepted_sql": "dw.secondarywaterresistance",
      "proposed_sql": "CASE WHEN UPPER(TRIM(dw.windmitigation)) = 'Y' THEN UPPER(TRIM(dw.secondarywaterresistance)) ELSE NULL END",
      "override_reason": "OVERRIDE: Direct from the extension column (see opening_protection).",
      "rationale": "Secondary water resistance is an OIR-B1-1802 companion Y/N value and should be reported only when wind mitigation is Y.",
      "review_note": "OVERRIDE: Direct from the extension column (see opening_protection)."
    },
    {
      "target_column": "latitude",
      "source_column": "dw.latitude",
      "transform_type": "direct",
      "confidence": 0.95,
      "needs_review": false,
      "accepted": true,
      "overridden": false,
      "accepted_sql": "CAST(dw.latitude AS BIGINT)",
      "proposed_sql": "CAST(dw.latitude AS BIGINT)",
      "override_reason": null,
      "rationale": "Dwelling latitude is already profiled as integer micro-degrees.",
      "review_note": null
    },
    {
      "target_column": "longitude",
      "source_column": "dw.longitude",
      "transform_type": "direct",
      "confidence": 0.95,
      "needs_review": false,
      "accepted": true,
      "overridden": false,
      "accepted_sql": "CAST(dw.longitude AS BIGINT)",
      "proposed_sql": "CAST(dw.longitude AS BIGINT)",
      "override_reason": null,
      "rationale": "Dwelling longitude is already profiled as integer micro-degrees with negative Florida values.",
      "review_note": null
    },
    {
      "target_column": "reporting_year",
      "source_column": null,
      "transform_type": "composite",
      "confidence": 0.65,
      "needs_review": true,
      "accepted": true,
      "overridden": false,
      "accepted_sql": "2025",
      "proposed_sql": "2025",
      "override_reason": null,
      "rationale": "Per-cycle constant inferred from FHCF-A-2026 context as filing-period start year; confirm for the actual data-call run.",
      "review_note": "Accepted constant 2025 — confirmed as the year of the FHCF-A-2026 filing period start."
    },
    {
      "target_column": "source_file",
      "source_column": null,
      "transform_type": "composite",
      "confidence": 0.65,
      "needs_review": true,
      "accepted": true,
      "overridden": false,
      "accepted_sql": "'FHCF_D1A_GUIDEWIRE_2025.txt'",
      "proposed_sql": "'FHCF_D1A_GUIDEWIRE_2025.txt'",
      "override_reason": null,
      "rationale": "Per-cycle fixed extract name uses the reporting year constant; confirm year before production.",
      "review_note": "Accepted constant extract name."
    }
  ],
  "overridden": 7,
  "needs_review_flags": 10,
  "avg_confidence": 0.844,
  "proposed_by": "openai:gpt-5.5",
  "tokens": 21783,
  "reviewed_by": "human-in-the-loop review, 2026-08-12",
  "review_summary": "26 proposed · 7 overridden in review · rest accepted as proposed. Compiled output verified row-identical to the hand-written FHCF_SILVER_SQL reference (tests/test_fhcf_mapping_compile.py).",
  "compiled": true,
  "compiled_at": "2026-08-12T05:45:25+00:00",
  "source_relation": "INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY p\n    JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_HOPOLICYLINE line ON line.policy_id = p.id\n    JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_HOCOVERAGE cov ON cov.policyline_id = line.id\n    JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_HODWELLING dw ON dw.policyline_id = line.id",
  "source_filter": "UPPER(TRIM(dw.state)) = 'FL'",
  "notes": "Core Guidewire fields map cleanly for policy number, period dates, dwelling limits, premium, PPC, construction/year, mitigation companions, and geocodes. Items needing SME review: county_fips because source appears to be full 5-digit FIPS while target expects 2-digit FHCF/Florida county code; policy_form because source samples are A/B rather than HO form names; occupancy_type and wind/roof-cover/reporting_year because they are domain-encoded; risk_zip because profile samples are non-FL although the pipeline applies an FL dwelling-state filter; tropical-cyclone deductible sparsity may require a business-approved fallback to wind/hail deductible.",
  "unmapped_source_columns": [
    {
      "name": "p.gwcbi___operation",
      "reason": "CDC/ingestion metadata; no FHCF target."
    },
    {
      "name": "p.gwcdac___timestampfolder",
      "reason": "CDC/ingestion metadata; no FHCF target."
    },
    {
      "name": "p.gwcdac___fingerprintfolder",
      "reason": "CDC/ingestion metadata; no FHCF target."
    },
    {
      "name": "p.gwcbi___seqval_hex",
      "reason": "CDC sequencing metadata; no FHCF target."
    },
    {
      "name": "p._ingestion_timestamp",
      "reason": "Bronze ingestion provenance; target source_file is a fixed generated extract name."
    },
    {
      "name": "p._source_file",
      "reason": "Bronze source provenance; target source_file is a fixed generated extract name."
    },
    {
      "name": "p.id",
      "reason": "Internal Guidewire key used for joins only; no FHCF target."
    },
    {
      "name": "p.publicid",
      "reason": "Internal Guidewire public id; policy_number uses p.policynumber."
    },
    {
      "name": "p.account_id",
      "reason": "Account key; no FHCF target."
    },
    {
      "name": "p.producercode_id",
      "reason": "Producer key; no FHCF target."
    },
    {
      "name": "p.issuedate",
      "reason": "Issue date is not policy period start; line.effectivedate mapped instead."
    },
    {
      "name": "p.originalinceptiondate",
      "reason": "Original inception is not current policy period start; line.effectivedate mapped instead."
    },
    {
      "name": "p.createtime",
      "reason": "Audit timestamp; no FHCF target."
    },
    {
      "name": "p.updatetime",
      "reason": "Audit timestamp; no FHCF target."
    },
    {
      "name": "p.retiredvalue",
      "reason": "Guidewire soft-delete flag; no FHCF target."
    },
    {
      "name": "line.gwcbi___operation",
      "reason": "CDC/ingestion metadata; no FHCF target."
    },
    {
      "name": "line.gwcdac___timestampfolder",
      "reason": "CDC/ingestion metadata; no FHCF target."
    },
    {
      "name": "line.gwcdac___fingerprintfolder",
      "reason": "CDC/ingestion metadata; no FHCF target."
    },
    {
      "name": "line.gwcbi___seqval_hex",
      "reason": "CDC sequencing metadata; no FHCF target."
    },
    {
      "name": "line._ingestion_timestamp",
      "reason": "Bronze ingestion provenance; target source_file is a fixed generated extract name."
    },
    {
      "name": "line._source_file",
      "reason": "Bronze source provenance; target source_file is a fixed generated extract name."
    },
    {
      "name": "line.id",
      "reason": "Internal Guidewire key used for joins only; no FHCF target."
    },
    {
      "name": "line.publicid",
      "reason": "Internal Guidewire public id; no FHCF target."
    },
    {
      "name": "line.branchid",
      "reason": "Internal branch/version key; no FHCF target."
    },
    {
      "name": "line.policy_id",
      "reason": "Join key to policy; no FHCF target."
    },
    {
      "name": "line.policylinepatterncodeidentifier",
      "reason": "Line pattern constant/provenance; no FHCF target."
    },
    {
      "name": "line.linecategory",
      "reason": "HO line category is implicit in the extract; no FHCF target."
    },
    {
      "name": "line.numberofunits",
      "reason": "Unit count not selected; occupancy derivation used dwelling number of families instead."
    },
    {
      "name": "line.roofcoveringcreditclass",
      "reason": "Roof credit class has no direct FHCF target; roof_cover_type uses roofcoveringtype."
    },
    {
      "name": "line.roofinstallationyear",
      "reason": "Roof installation year has no target in FHCF exposure staging."
    },
    {
      "name": "line.cosmeticdamageexclusion",
      "reason": "Coverage exclusion/rating attribute; no FHCF target."
    },
    {
      "name": "line.roofcoveragetype",
      "reason": "Coverage valuation/rating attribute; no FHCF target."
    },
    {
      "name": "line.dwellingcoveragetype",
      "reason": "Coverage valuation/rating attribute; no FHCF target."
    },
    {
      "name": "line.personalpropertycovtype",
      "reason": "Coverage valuation/rating attribute; no FHCF target."
    },
    {
      "name": "line.priorclaimscount",
      "reason": "Claims/rating attribute; no FHCF target."
    },
    {
      "name": "line.priorclaimsused",
      "reason": "Rating indicator; no FHCF target."
    },
    {
      "name": "line.rv_alarm",
      "reason": "Rating variable; no FHCF target."
    },
    {
      "name": "line.rv_age_of_home",
      "reason": "Rating variable; no FHCF target."
    },
    {
      "name": "line.rv_sprinkler",
      "reason": "Rating variable; no FHCF target."
    },
    {
      "name": "line.rv_claims_experience",
      "reason": "Rating variable; no FHCF target."
    },
    {
      "name": "line.rv_companion_policy",
      "reason": "Rating variable; no FHCF target."
    },
    {
      "name": "line.rv_credit_score",
      "reason": "Rating variable; no FHCF target."
    },
    {
      "name": "line.rv_senior_citizen",
      "reason": "Rating variable; no FHCF target."
    },
    {
      "name": "line.rv_smart_home",
      "reason": "Rating variable; no FHCF target."
    },
    {
      "name": "line.rv_new_home",
      "reason": "Rating variable; no FHCF target."
    },
    {
      "name": "line.rv_additional_surcharges",
      "reason": "Rating variable; no FHCF target."
    },
    {
      "name": "line.tenurewithinsurer",
      "reason": "Insured tenure/rating attribute; no FHCF target."
    },
    {
      "name": "line.tenurediscountpct",
      "reason": "Rating discount; no FHCF target."
    },
    {
      "name": "line.tenureusedforrating",
      "reason": "Rating indicator; no FHCF target."
    },
    {
      "name": "line.tenureusedfortiering",
      "reason": "Rating indicator; no FHCF target."
    },
    {
      "name": "line.privatefloodcoverage",
      "reason": "Flood coverage indicator; no FHCF exposure target."
    },
    {
      "name": "line.lawordcompct",
      "reason": "Law/ordinance percentage; no target in this staging contract."
    },
    {
      "name": "line.createtime",
      "reason": "Audit timestamp; no FHCF target."
    },
    {
      "name": "line.updatetime",
      "reason": "Audit timestamp; no FHCF target."
    },
    {
      "name": "line.retiredvalue",
      "reason": "Guidewire soft-delete flag; no FHCF target."
    },
    {
      "name": "line._partition_month",
      "reason": "Warehouse partition column; no FHCF target."
    },
    {
      "name": "cov.gwcbi___operation",
      "reason": "CDC/ingestion metadata; no FHCF target."
    },
    {
      "name": "cov.gwcdac___timestampfolder",
      "reason": "CDC/ingestion metadata; no FHCF target."
    },
    {
      "name": "cov.gwcdac___fingerprintfolder",
      "reason": "CDC/ingestion metadata; no FHCF target."
    },
    {
      "name": "cov.gwcbi___seqval_hex",
      "reason": "CDC sequencing metadata; no FHCF target."
    },
    {
      "name": "cov._ingestion_timestamp",
      "reason": "Bronze ingestion provenance; target source_file is a fixed generated extract name."
    },
    {
      "name": "cov._source_file",
      "reason": "Bronze source provenance; target source_file is a fixed generated extract name."
    },
    {
      "name": "cov.id",
      "reason": "Internal Guidewire key used for joins only; no FHCF target."
    },
    {
      "name": "cov.publicid",
      "reason": "Internal Guidewire public id; no FHCF target."
    },
    {
      "name": "cov.branchid",
      "reason": "Internal branch/version key; no FHCF target."
    },
    {
      "name": "cov.fixedid",
      "reason": "Internal fixed/version id; no FHCF target."
    },
    {
      "name": "cov.policyline_id",
      "reason": "Join key to policy line; no FHCF target."
    },
    {
      "name": "cov.coveragepatterncode",
      "reason": "Coverage pattern metadata; dwelling Coverage A amount is mapped from coverageamount."
    },
    {
      "name": "cov.coveragecategory",
      "reason": "Coverage category is implicit in fixed join/profile; no direct FHCF target."
    },
    {
      "name": "cov.coveragetype",
      "reason": "Coverage type A is implicit for coverage_a; no separate target."
    },
    {
      "name": "cov.personalpropertylimit",
      "reason": "Coverage C limit; no target in this FHCF staging contract."
    },
    {
      "name": "cov.lossofuselimit",
      "reason": "Loss of use limit; no target in this FHCF staging contract."
    },
    {
      "name": "cov.lossofusepct",
      "reason": "Loss of use percentage; no target in this FHCF staging contract."
    },
    {
      "name": "cov.deductibletype",
      "reason": "Generic deductible type; hurricane_deductible uses tropical-cyclone deductible amount."
    },
    {
      "name": "cov.allperilsdeductible",
      "reason": "All-perils deductible is not the FHCF hurricane deductible."
    },
    {
      "name": "cov.windhailddeductible",
      "reason": "Wind/hail deductible not mapped because target guidance prefers tropical-cyclone deductible; possible fallback requires SME approval."
    },
    {
      "name": "cov.windhailddeductiblepct",
      "reason": "All values null and hurricane deductible mapped from tropical-cyclone amount."
    },
    {
      "name": "cov.tropicalcyclonedeductibletype",
      "reason": "All values null; amount field mapped instead."
    },
    {
      "name": "cov.windexcluded",
      "reason": "Wind exclusion indicator; no target in this staging contract."
    },
    {
      "name": "cov.optionalcovcode",
      "reason": "All values null/optional coverage; no target."
    },
    {
      "name": "cov.optionalcovamount",
      "reason": "All values null/optional coverage; no target."
    },
    {
      "name": "cov.ecpremium",
      "reason": "Earthquake/other coverage premium; written_premium uses cov.writtenpremium."
    },
    {
      "name": "cov.effectivedate",
      "reason": "Coverage effective date duplicates policy-line period for this extract; line.effectivedate mapped."
    },
    {
      "name": "cov.expirationdate",
      "reason": "Coverage expiration date duplicates policy-line period for this extract; line.expirationdate mapped."
    },
    {
      "name": "cov.createtime",
      "reason": "Audit timestamp; no FHCF target."
    },
    {
      "name": "cov.updatetime",
      "reason": "Audit timestamp; no FHCF target."
    },
    {
      "name": "cov.retiredvalue",
      "reason": "Guidewire soft-delete flag; no FHCF target."
    },
    {
      "name": "cov._partition_month",
      "reason": "Warehouse partition column; no FHCF target."
    },
    {
      "name": "dw.gwcbi___operation",
      "reason": "CDC/ingestion metadata; no FHCF target."
    },
    {
      "name": "dw.gwcdac___timestampfolder",
      "reason": "CDC/ingestion metadata; no FHCF target."
    },
    {
      "name": "dw.gwcdac___fingerprintfolder",
      "reason": "CDC/ingestion metadata; no FHCF target."
    },
    {
      "name": "dw.gwcbi___seqval_hex",
      "reason": "CDC sequencing metadata; no FHCF target."
    },
    {
      "name": "dw._ingestion_timestamp",
      "reason": "Bronze ingestion provenance; target source_file is a fixed generated extract name."
    },
    {
      "name": "dw._source_file",
      "reason": "Bronze source provenance; target source_file is a fixed generated extract name."
    },
    {
      "name": "dw.id",
      "reason": "Internal Guidewire key used for joins only; no FHCF target."
    },
    {
      "name": "dw.publicid",
      "reason": "Internal Guidewire public id; no FHCF target."
    },
    {
      "name": "dw.branchid",
      "reason": "Internal branch/version key; no FHCF target."
    },
    {
      "name": "dw.policyline_id",
      "reason": "Join key to policy line; no FHCF target."
    },
    {
      "name": "dw.policyaddress_id",
      "reason": "Address join key; no address-id target."
    },
    {
      "name": "dw.territory",
      "reason": "Rating territory; no FHCF target in this staging contract."
    },
    {
      "name": "dw.placecodetdi",
      "reason": "Texas/TDI place code-like field; no FHCF target."
    },
    {
      "name": "dw.ppccodesplit",
      "reason": "PPC split detail; protection_class uses dw.ppccode."
    },
    {
      "name": "dw.buildingcodecredit",
      "reason": "All values null and no direct FHCF target."
    },
    {
      "name": "dw.intwiazone",
      "reason": "Texas wind zone indicator; no FHCF target."
    },
    {
      "name": "dw.coastalterritory",
      "reason": "Coastal territory/rating indicator; no FHCF target."
    },
    {
      "name": "dw.createtime",
      "reason": "Audit timestamp; no FHCF target."
    },
    {
      "name": "dw.updatetime",
      "reason": "Audit timestamp; no FHCF target."
    },
    {
      "name": "dw.retiredvalue",
      "reason": "Guidewire soft-delete flag; no FHCF target."
    },
    {
      "name": "uw.gwcbi___operation",
      "reason": "CDC/ingestion metadata; no FHCF target."
    },
    {
      "name": "uw.gwcdac___timestampfolder",
      "reason": "CDC/ingestion metadata; no FHCF target."
    },
    {
      "name": "uw.gwcdac___fingerprintfolder",
      "reason": "CDC/ingestion metadata; no FHCF target."
    },
    {
      "name": "uw.gwcbi___seqval_hex",
      "reason": "CDC sequencing metadata; no FHCF target."
    },
    {
      "name": "uw._ingestion_timestamp",
      "reason": "Bronze ingestion provenance; no FHCF target."
    },
    {
      "name": "uw._source_file",
      "reason": "Bronze source provenance; target source_file is a fixed generated extract name."
    },
    {
      "name": "uw.id",
      "reason": "Underwriting company internal key; no FHCF target."
    },
    {
      "name": "uw.publicid",
      "reason": "Underwriting company public id; no FHCF target."
    },
    {
      "name": "uw.code",
      "reason": "Company code/name; insurer_naic uses uw.naiccode."
    },
    {
      "name": "uw.ticocompanynumber",
      "reason": "Non-NAIC company number; no FHCF target."
    },
    {
      "name": "uw.createtime",
      "reason": "Audit timestamp; no FHCF target."
    },
    {
      "name": "uw.updatetime",
      "reason": "Audit timestamp; no FHCF target."
    },
    {
      "name": "uw.retiredvalue",
      "reason": "Guidewire soft-delete flag; no FHCF target."
    }
  ],
  "compiled_sql": "SELECT\n  (SELECT LPAD(TRIM(MAX(uw.naiccode)), 10, '0') FROM INSURANCE_REGULATORY.BRONZE.GW_PC_UWCOMPANY uw) AS insurer_naic,\n  TRIM(p.policynumber) AS policy_number,\n  LPAD(TRIM(CAST(dw.zip AS STRING)), 5, '0') AS risk_zip,\n  CASE WHEN dw.ziplus4 IS NULL OR TRIM(CAST(dw.ziplus4 AS STRING)) = '' THEN NULL ELSE LPAD(TRIM(CAST(dw.ziplus4 AS STRING)), 4, '0') END AS risk_zip4,\n  TRIM(dw.countyfips) AS county_fips,\n  UPPER(TRIM(dw.state)) AS state_code,\n  TRIM(line.holineform) AS policy_form,\n  CAST(line.effectivedate AS DATE) AS effective_date,\n  CAST(line.expirationdate AS DATE) AS expiry_date,\n  CASE WHEN line.occupancytype = 'OwnerOccupied' THEN 'O1' ELSE 'O2' END AS occupancy_type,\n  TRIM(CAST(dw.constructiontype AS STRING)) AS construction_type,\n  CAST(dw.yearbuilt AS INT) AS year_built,\n  CAST(NULLIF(TRIM(CAST(dw.ppccode AS STRING)), '') AS INT) AS protection_class,\n  CAST(cov.coverageamount AS BIGINT) AS coverage_a,\n  CAST(cov.tropicalcyclonedeductible AS INT) AS hurricane_deductible,\n  CAST(ROUND(cov.writtenpremium) AS BIGINT) AS written_premium,\n  CASE WHEN UPPER(TRIM(dw.windmitigation)) = 'Y' THEN 'Y' ELSE 'N' END AS wind_mitigation,\n  dw.openingprotection AS opening_protection,\n  CASE WHEN UPPER(TRIM(dw.windmitigation)) = 'Y' THEN TRIM(line.roofcoveringtype) ELSE NULL END AS roof_cover_type,\n  dw.roofdeckattachment AS roof_deck_attachment,\n  dw.rooftowallconnection AS roof_to_wall_connection,\n  dw.secondarywaterresistance AS secondary_water_resistance,\n  CAST(dw.latitude AS BIGINT) AS latitude,\n  CAST(dw.longitude AS BIGINT) AS longitude,\n  2025 AS reporting_year,\n  'FHCF_D1A_GUIDEWIRE_2025.txt' AS source_file\nFROM INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY p\n    JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_HOPOLICYLINE line ON line.policy_id = p.id\n    JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_HOCOVERAGE cov ON cov.policyline_id = line.id\n    JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_HODWELLING dw ON dw.policyline_id = line.id\nWHERE UPPER(TRIM(dw.state)) = 'FL'"
};

export const mappingsList: MappingsResponse = {
  mappings: [
    {
      name: mappingDetail.name,
      source_label: mappingDetail.source_label,
      target: mappingDetail.target,
      target_table: mappingDetail.target_table,
      columns: mappingDetail.columns.length,
      overridden: mappingDetail.overridden,
      needs_review_flags: mappingDetail.needs_review_flags,
      avg_confidence: mappingDetail.avg_confidence,
      proposed_by: mappingDetail.proposed_by,
      tokens: mappingDetail.tokens,
      reviewed_by: mappingDetail.reviewed_by,
      review_summary: mappingDetail.review_summary,
      compiled: mappingDetail.compiled,
      compiled_at: mappingDetail.compiled_at,
    },
  ],
};
