-- =============================================================================
-- SNOWFLAKE DDL: SILVER LAYER — TSPR Field-Mapped Staging Tables
-- =============================================================================
-- Purpose  : Transform Guidewire raw CDC events into TSPR-compliant field
--            structures. All TSPR column mappings, rule applications, and
--            coding translations happen here.
-- Source   : bronze.gw_pc_* and bronze.gw_cc_* tables
-- Database : insurance_regulatory
-- Schema   : silver
--
-- Snowflake translation notes:
--   ARRAY<STRING>    -> VARIANT  (Snowflake semi-structured type)
--   ARRAY<BIGINT>    -> VARIANT
--   GENERATED ALWAYS AS (concat_ws(...)) -> stored as regular VARCHAR,
--            populated by the transformation pipeline (Snowflake virtual
--            columns are expression-only and cannot reference other columns
--            in the same table the same way; use a computed-column view
--            or populate in the ELT pipeline)
--   BOOLEAN GENERATED ALWAYS AS (expr) -> BOOLEAN, populated by pipeline
--   DEFAULT current_timestamp() -> DEFAULT CURRENT_TIMESTAMP()
--   INTEGER          -> NUMBER(10,0)
--   BIGINT           -> NUMBER(19,0)
--   DECIMAL(p,s)     -> NUMBER(p,s)
--   PARTITIONED BY   -> CLUSTER BY on Snowflake
-- =============================================================================

CREATE DATABASE IF NOT EXISTS insurance_regulatory;

CREATE SCHEMA IF NOT EXISTS insurance_regulatory.silver
    COMMENT = 'Silver: TSPR field-mapped staging. One row per TSPR field group. Fields named by their TSPR abbreviation and column position.';

USE DATABASE insurance_regulatory;
USE SCHEMA silver;

-- Shared tags for Silver layer
CREATE TAG IF NOT EXISTS insurance_regulatory.silver.tspr_pii
    COMMENT = 'PII column — Dynamic Data Masking policy required';

CREATE TAG IF NOT EXISTS insurance_regulatory.silver.tspr_section
    ALLOWED_VALUES 'C', 'D', 'E', 'G', 'A'
    COMMENT = 'TSPR plan section this table primarily serves';

-- ---------------------------------------------------------------------------
-- 1. TSPR Premium Staging (Section C)
--    One row per TSPR premium record per coverage transaction per month.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS silver.tspr_premium_staging (

    -- Identity and partition
    accounting_month            VARCHAR(7)      NOT NULL
        COMMENT '[TSPR C|ACDT|cols 2-4|Rule23] YYYY-MM. Month encoded 0=Oct,-=Nov,&=Dec at SDF render only.',
    naic_company_no             VARCHAR(5)      NOT NULL
        COMMENT '[TSPR C|NAIC|cols 146-150|Rule25] 5-digit NAIC. MANDATORY on all records.',
    tico_company_no             VARCHAR(3)
        COMMENT '[TSPR C|CNO|cols 43-45|Rule22] 3-char TICO-assigned company number.',
    run_id                      VARCHAR(100)
        COMMENT 'Pipeline run ID for audit lineage',
    source_policyperiod_id      NUMBER(19,0)
        COMMENT 'Source GW pc_policyperiod.id for lineage',

    -- col 1: Stat Plan
    stat_plan                   VARCHAR(1)      NOT NULL    DEFAULT '4'
        COMMENT '[TSPR C|SP|col 1|Rule1] Always 4 for Residential. Validated: reject if != 4.',

    -- cols 5-6: Record Type
    record_type                 VARCHAR(2)      NOT NULL
        COMMENT '[TSPR C|RT|cols 5-6|Rule7] 01=New/Renewal,02=Endorsement,05=Flat Cancel,06=Pro Rata Cancel,07=TWIA AR Cancel,08=TWIA Assumption,12=Short-term,91-93/95=HO variants.',

    -- cols 7-16: Policy Identifier (PII)
    policy_id                   VARCHAR(10)     NOT NULL
        COMMENT '[TSPR C|POLICY|cols 7-16|Rule26] PII. 10-char alphanumeric. Unique per policy across all periods.',

    -- col 17: Term
    term                        VARCHAR(1)
        COMMENT '[TSPR C|TRM|col 17] 1=one year or less, 9=over one year.',

    -- cols 18-22: Effective Date
    effective_date              VARCHAR(5)
        COMMENT '[TSPR C|EFF|cols 18-22|Rule8] MMDDY format. Required on new business, renewals, endorsements, pro-rata cancellations.',

    -- cols 23-25: Expiry Date
    expiry_date                 VARCHAR(3)
        COMMENT '[TSPR C|EXP|cols 23-25|Rule8] MMY format. Required on new business and short-term endorsements.',

    -- cols 26-30: Place Code
    place_code                  VARCHAR(5)
        COMMENT '[TSPR C|PLACE|cols 26-30|Rule18] TDI county-community place code.',

    -- cols 33-37: Amount of Insurance - Dwelling ($1000s)
    amt_insurance_dw            NUMBER(10,0)
        COMMENT '[TSPR C|INS|cols 33-37|Rule6] Dwelling limit in $1000s (nearest thousand). Under $1500 -> code 01.',

    -- cols 41-42: Line of Business
    line_of_business            VARCHAR(2)      NOT NULL
        COMMENT '[TSPR C|LOB|cols 41-42|SectionB4] 02=HO Tenants/Condo,03=HO excl Tenants,10=DW Fire,11=DW Misc,12=DW Liability,13=TWIA Wind,14=Vol Wind AR,15=Vol Wind Other,16=DW Theft,35=Stand-alone Flood.',

    -- col 50: Policy Form
    policy_form                 VARCHAR(1)      NOT NULL
        COMMENT '[TSPR C|FM|col 50|SectionB5] 1=HO-A,2=HO-B,3=HO-C,4=Tenants B,5=Tenants C,9=HO-A+. A-Z 6-8 for ISO/AAIS/Independent forms.',

    -- col 51: Number of Families
    number_of_families          VARCHAR(1)
        COMMENT '[TSPR C|FAM|col 51|SectionB6] 1=DW only,2=PP only,8=Tenants with $250 theft ded,9=DW+PP.',

    -- col 52: Coverage - Occupancy
    coverage_occupancy          VARCHAR(1)
        COMMENT '[TSPR C|COV|col 52|SectionB7] 1=Owner Occ HO,2=Non-owner,3=Tenants DW,4=Apt Owner Occ,5=Tenants Other,6=Condo Contents,7=Vacant,8=Liability Only,9=Other endorsements.',

    -- col 53: Construction
    construction                VARCHAR(1)
        COMMENT '[TSPR C|CT|col 53|SectionB8] 1=Frame,2=Brick Veneer,3=Brick/Stone/Masonry,4=Fire Resistive,5=Mobile/Manufactured,8=Stucco/Asbestos,9=N/A.',

    -- cols 54-55: Split PPC
    ppc_split                   VARCHAR(2)
        COMMENT '[TSPR C|SPPC|cols 54-55|SectionB9A] 2-digit split PPC.',

    -- col 56: Simple PPC
    ppc_simple                  VARCHAR(1)
        COMMENT '[TSPR C|PPC|col 56|SectionB9] 1-9,A (PPC=10),B (PPC=8B). Actual ISO PPC used to rate the risk.',

    -- col 57: Deductible 1 (Wind/Hail)
    deductible_1                VARCHAR(1)
        COMMENT '[TSPR C|DED1|col 57|SectionB10] HO Clause 1 Wind/Hail. Code 7 ONLY in territories 8,9,10 and TWIA area of Territory 1.',

    -- col 58: Deductible 2
    deductible_2                VARCHAR(1)
        COMMENT '[TSPR C|DED2|col 58|SectionB10] HO Clause 2 Other-than-W/H or Clause 3 Tenants/Condo.',

    -- cols 59-63: Fire/HO Premium
    fire_premium                NUMBER(15,2)
        COMMENT '[TSPR C|FRPM|cols 59-63|Rule7] Dollars only (no cents). HO=total premium. Negative=credit. Rule12 symbol encoding at SDF render only.',

    -- cols 67-70: Extended Coverage Premium
    ec_premium                  NUMBER(15,2)
        COMMENT '[TSPR C|EPRM|cols 67-70|Rule7] Extended Coverage premium. Separate from fire premium.',

    -- col 83: Roof Covering
    roof_covering               VARCHAR(1)
        COMMENT '[TSPR C|ROOFCOV|col 83|SectionB8A] A=Comp Shingle,B=Wood,C=Alum,D=Steel,E=Copper,F=Roll,G=Tar+Gravel,H=Tile,I=Slate,J=Fiber Cement,K=Plastic,L=Recycled,M=Single-Ply,N=Other,O=Metal unknown,P=Unknown/not used.',

    -- col 84: Roof Credit
    roof_credit                 VARCHAR(1)
        COMMENT '[TSPR C|ROOFCRED|col 84|SectionB8A] 0=None,1-4=UL2218 Class 1-4.',

    -- cols 85-88: Roof Year
    roof_install_year           NUMBER(4,0)
        COMMENT '[TSPR C|ROOFYEAR|cols 85-88|SectionB8A] YYYY. Report 0000 if not used in underwriting or rating.',

    -- col 89: Cosmetic Exclusion
    cosmetic_excl               VARCHAR(1)
        COMMENT '[TSPR C|COSMETIC|col 89|SectionB8B] 0=endorsement not attached,1=endorsement attached.',

    -- cols 91-99: ZIP Code (PII)
    zip9                        VARCHAR(9)
        COMMENT '[TSPR C|ZIP|cols 91-99|Rule24] PII. 9-digit ZIP. First 5 mandatory.',

    -- col 100: Record indicator
    record_indicator            VARCHAR(1)      NOT NULL    DEFAULT 'P'
        COMMENT '[TSPR C|col 100] P=Premium record.',

    -- cols 101-108: Optional Coverage Code
    optional_cov_code           VARCHAR(8)
        COMMENT '[TSPR C|cols 101-108|SectionB18] Endorsement number without dashes.',

    -- cols 109-114: Optional Coverage Amount
    optional_cov_amount         NUMBER(15,2)
        COMMENT '[TSPR C|cols 109-114|SectionB19] Percent or dollar amount for optional coverage endorsement.',

    -- cols 116-121: DED1 dollar amount
    deductible_1_amt            NUMBER(15,2)
        COMMENT '[TSPR C|cols 116-121] Actual dollar amount of DED1.',

    -- cols 122-127: DED2 dollar amount
    deductible_2_amt            NUMBER(15,2)
        COMMENT '[TSPR C|cols 122-127] Actual dollar amount of DED2.',

    -- col 128: Wind Coverage
    wind_coverage_included      VARCHAR(1)      NOT NULL    DEFAULT '0'
        COMMENT '[TSPR C|WIND|col 128] 0=wind included,1=wind excluded.',

    -- cols 134-135: Building Code Credit
    building_code_credit        VARCHAR(2)
        COMMENT '[TSPR C|BCC|cols 134-135|SectionB15] 01-09. TWIA only.',

    -- col 136: Law and Ordinance
    law_ordinance_pct           VARCHAR(1)
        COMMENT '[TSPR C|LOC|col 136|SectionB16] 0=none,1=10%,2=15%,3=25%,4=other approved.',

    -- col 138: Optional Credit PPID
    optional_credit_ppid        VARCHAR(1)
        COMMENT '[TSPR C|OC10|col 138|SectionB17] 0=does not apply,1=applies.',

    -- col 140: Tenure Code (REQUIRED on ALL transactions per Rule 30)
    tenure_code                 VARCHAR(1)      NOT NULL
        COMMENT '[TSPR C|TENURE|col 140|Rule30] REQUIRED on ALL transactions including endorsements and cancellations. 0=not used,1=0-2yr,2=3-5yr,3=6-8yr,4=9-10yr,5=11-15yr,6=16-19yr,7=20+yr.',

    -- cols 141-142: Tenure Discount
    tenure_discount_pct         VARCHAR(2)
        COMMENT '[TSPR C|TENUREDISCT|cols 141-142|Rule30] 2-digit integer (10=10%). 00 if no discount or tiering only.',

    -- col 151: Replacement Cost Building
    replacement_cost_building   VARCHAR(1)
        COMMENT '[TSPR C|RCB|col 151|Rule33] 0=ACV,1=RC,2=no dwelling coverage.',

    -- col 152: Replacement Cost PP
    replacement_cost_pp         VARCHAR(1)
        COMMENT '[TSPR C|RCPP|col 152|Rule33] 0=ACV,1=RC,2=no PP coverage.',

    -- col 153: Roof Coverage Type
    roof_coverage_type          VARCHAR(1)
        COMMENT '[TSPR C|RCT|col 153|Rule33] 0=ACV roof,1=ACV W&H only/RC other,2=RC roof,3=no DW coverage,4=no roof coverage,5=no roof coverage W&H only.',

    -- col 154: Private Flood
    private_flood_indicator     VARCHAR(1)
        COMMENT '[TSPR C|FLOOD|col 154|Rule32] 0=no flood,1=flood covered. Federal NFIP policies NOT reported.',

    -- col 155: Tropical Cyclone Deductible code
    trop_cyclone_deductible     VARCHAR(1)
        COMMENT '[TSPR C|TCDED|col 155] HO and Tenants/Condo only.',

    -- cols 156-161: Tropical Cyclone Deductible Amount
    trop_cyclone_deductible_amt NUMBER(15,2)
        COMMENT '[TSPR C|TCDEDAMT|cols 156-161] Actual dollar amount of tropical cyclone deductible.',

    -- cols 162-165: Year of Construction
    year_of_construction        NUMBER(4,0)
        COMMENT '[TSPR C|YOC|cols 162-165] YYYY. Report 0000 for tenant/contents-only forms.',

    -- cols 166-168: ALE in $1000s
    amt_insurance_alu           NUMBER(10,0)
        COMMENT '[TSPR C|ALE|cols 166-168|Rule6] Loss of Use in $1000s. Convert % of Cov A to dollars first. Max 999 if >$998,499.',

    -- cols 169-172: HO PP in $1000s
    amt_insurance_pp            NUMBER(10,0)
        COMMENT '[TSPR C|HOPP|cols 169-172|Rule6] HO PP limit in $1000s. HO policies only. Max 9999.',

    -- col 173: Prior Claims History
    prior_claims_history        VARCHAR(1)
        COMMENT '[TSPR C|CLM|col 173|Rule20] 0=none,1-5=count,6=not used in rating/tiering.',

    -- cols 174-183: Rating Variables (Section B.20)
    rv_alarm                    VARCHAR(1)      COMMENT '[TSPR C|RV1|col 174|SectionB20] 1=used no factor,2=discount,3=surcharge,4=tier only,5=not used.',
    rv_age_of_home              VARCHAR(1)      COMMENT '[TSPR C|RV2|col 175|SectionB20]',
    rv_sprinkler                VARCHAR(1)      COMMENT '[TSPR C|RV3|col 176|SectionB20]',
    rv_claims_exp               VARCHAR(1)      COMMENT '[TSPR C|RV4|col 177|SectionB20]',
    rv_companion                VARCHAR(1)      COMMENT '[TSPR C|RV5|col 178|SectionB20]',
    rv_credit_score             VARCHAR(1)      COMMENT '[TSPR C|RV6|col 179|SectionB20] PII. Credit-based insurance score.',
    rv_senior                   VARCHAR(1)      COMMENT '[TSPR C|RV7|col 180|SectionB20]',
    rv_smart_home               VARCHAR(1)      COMMENT '[TSPR C|RV8|col 181|SectionB20]',
    rv_new_home                 VARCHAR(1)      COMMENT '[TSPR C|RV9|col 182|SectionB20]',
    rv_surcharges               VARCHAR(1)      COMMENT '[TSPR C|RV10|col 183|SectionB20] Additional risk surcharges.',

    -- Validation
    validation_status           VARCHAR(20)     DEFAULT 'PENDING'
        COMMENT 'PENDING, CLEAN, EXCEPTION, CORRECTED',
    validation_errors           VARIANT
        COMMENT 'Array of validation error messages if status=EXCEPTION. Stored as Snowflake VARIANT (JSON array).',

    -- Audit
    _created_timestamp          TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _pipeline_run_id            VARCHAR(100),
    _source_system              VARCHAR(50)     DEFAULT 'Guidewire PolicyCenter'
)
CLUSTER BY (accounting_month, naic_company_no)
COMMENT = 'Silver: TSPR Section C premium records. All fields mapped from Guidewire PolicyCenter. TSPR plan version: Effective January 1 2026. Governing body: Texas Department of Insurance.';

ALTER TABLE silver.tspr_premium_staging MODIFY COLUMN policy_id    SET TAG insurance_regulatory.silver.tspr_pii = 'true';
ALTER TABLE silver.tspr_premium_staging MODIFY COLUMN zip9         SET TAG insurance_regulatory.silver.tspr_pii = 'true';
ALTER TABLE silver.tspr_premium_staging MODIFY COLUMN rv_credit_score SET TAG insurance_regulatory.silver.tspr_pii = 'true';


-- ---------------------------------------------------------------------------
-- 2. TSPR Claim State Machine  (Rules 13-15-16 SCD Type 2)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS silver.tspr_claim_state (

    claim_id                    NUMBER(19,0)    NOT NULL
        COMMENT 'GW cc_claim.id',
    exposure_id                 NUMBER(19,0)    NOT NULL
        COMMENT 'GW cc_exposure.id. TSPR records one entry per exposure (Rule 11 multi-coverage).',
    claimnumber                 VARCHAR(30)
        COMMENT 'Human-readable claim number',
    accounting_month            VARCHAR(7)      NOT NULL
        COMMENT 'YYYY-MM reporting month',
    naic_company_no             VARCHAR(5)
        COMMENT '5-digit NAIC for partitioning',

    -- TSPR state machine outputs
    new_claim_count             NUMBER(5,0)     NOT NULL    DEFAULT 0
        COMMENT '[TSPR D|NCC|col 173|Rule13] 1=newly reported in month carrier first received claim. 0=previously reported. -1=reversal.',
    paid_claim_count            NUMBER(5,0)     NOT NULL    DEFAULT 0
        COMMENT '[TSPR D|PCC|col 60|Rule14] 1=first payment record for claim/exposure. 0=nonpayment or already paid. -1=error reversal.',
    reopened_claim_count        NUMBER(5,0)     NOT NULL    DEFAULT 0
        COMMENT '[TSPR D|RCC|col 177|Rule15] 1=newly reopened (first record of month after last closed). 0=all others. -1=reversal.',
    claim_status                NUMBER(5,0)     NOT NULL
        COMMENT '[TSPR D|CS|col 174|Rule16] 1=open/never closed,2=CWIP/never closed,3=CWOP/never closed,4=open/prev closed,5=CWIP/prev closed,6=CWOP/prev closed.',
    kind_code                   NUMBER(5,0)     NOT NULL
        COMMENT '[TSPR D|KIND|col 31|SectionB3] 1-3=no payment. 4-5=paid on reopened. 6=paid not reopened. 7-9=outstanding.',

    -- State flags
    is_first_report_this_period BOOLEAN
        COMMENT 'This is the first time this claim appears in this accounting_month',
    was_previously_closed       BOOLEAN
        COMMENT 'Claim/exposure was closed in a prior accounting_month',
    has_any_payment             BOOLEAN
        COMMENT 'Claim/exposure has at least one indemnity payment in any period',
    has_payment_this_period     BOOLEAN
        COMMENT 'New indemnity payment recorded in this accounting_month',
    is_newly_reopened_this_period BOOLEAN
        COMMENT 'Claim/exposure was closed last reported and now active',
    is_first_rcc_record_this_month BOOLEAN
        COMMENT 'First loss record of month for newly reopened claim',

    -- SCD metadata
    scd_effective_month         VARCHAR(7)
        COMMENT 'YYYY-MM from which this state record is valid',
    scd_version                 NUMBER(10,0)
        COMMENT 'Version number for this claim in this month',

    -- Source linkage (stored as VARIANT JSON arrays in Snowflake)
    source_claim_event_ids      VARIANT
        COMMENT 'JSON array of GW cc_claim CDC event IDs that drove this state record',
    source_transaction_ids      VARIANT
        COMMENT 'JSON array of GW cc_transaction IDs that drove payment/reserve state',

    _created_timestamp          TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _pipeline_run_id            VARCHAR(100)
)
CLUSTER BY (accounting_month, naic_company_no)
COMMENT = 'Silver: TSPR Rules 13-15-16 claim state machine (SCD Type 2). One row per claim x exposure x accounting_month. Drives all Section D count fields NCC PCC RCC CS KIND.';


-- ---------------------------------------------------------------------------
-- 3. TSPR Loss Staging (Section D)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS silver.tspr_loss_staging (

    -- Identity and partition
    accounting_month            VARCHAR(7)      NOT NULL    COMMENT '[TSPR D|ACDT|cols 2-4|Rule23] YYYY-MM',
    naic_company_no             VARCHAR(5)      NOT NULL    COMMENT '[TSPR D|NAIC|cols 146-150|Rule25]',
    tico_company_no             VARCHAR(3),
    run_id                      VARCHAR(100),
    source_claim_id             NUMBER(19,0)    COMMENT 'Source GW cc_claim.id for lineage',
    source_exposure_id          NUMBER(19,0)    COMMENT 'Source GW cc_exposure.id for lineage',
    source_transaction_id       NUMBER(19,0)    COMMENT 'Source GW cc_transaction.id for lineage',

    stat_plan                   VARCHAR(1)      NOT NULL    DEFAULT '4',
    record_type                 VARCHAR(2)      COMMENT 'Not used on loss records (col 5-6 skipped in Section D)',

    -- cols 7-16 (PII)
    policy_id                   VARCHAR(10)     NOT NULL    COMMENT '[TSPR D|POLICY|cols 7-16|Rule26] PII.',

    -- cols 17-22: Occurrence Date
    occurrence_date             VARCHAR(6)      NOT NULL
        COMMENT '[TSPR D|OCC|cols 17-22|Rule8 Rule11] MMDDYY. Date of loss. Must reflect ORIGINAL AND PROXIMATE cause (Rule11). Not report date.',

    -- cols 23-25: Policy Effective Date
    policy_effective_date       VARCHAR(3)      COMMENT '[TSPR D|cols 23-25] MMY.',

    -- cols 26-30: Place Code
    place_code                  VARCHAR(5)      COMMENT '[TSPR D|PLACE|cols 26-30|Rule18]',

    -- col 31: Kind Code
    kind_code                   NUMBER(5,0)     NOT NULL
        COMMENT '[TSPR D|KIND|col 31|SectionB3] 1-3=no payment. 4-5=paid on reopened. 6=paid not reopened. 7-9=outstanding. Derived from tspr_claim_state.',

    -- cols 33-37: Amount of Insurance
    amt_insurance_dw            NUMBER(10,0)    COMMENT '[TSPR D|INS|cols 33-37] As per original premium coding.',

    -- cols 41-42: LOB
    line_of_business            VARCHAR(2)      NOT NULL    COMMENT '[TSPR D|LOB|cols 41-42|SectionB4] Same coding as premium record.',

    -- col 50: Policy Form
    policy_form                 VARCHAR(1)      COMMENT '[TSPR D|FM|col 50|SectionB5]',

    -- cols 51-58: shared with Section C
    number_of_families          VARCHAR(1)      COMMENT '[TSPR D|FAM|col 51]',
    coverage_occupancy          VARCHAR(1)      COMMENT '[TSPR D|COV|col 52]',
    construction                VARCHAR(1)      COMMENT '[TSPR D|CT|col 53]',
    ppc_split                   VARCHAR(2)      COMMENT '[TSPR D|SPPC|cols 54-55]',
    ppc_simple                  VARCHAR(1)      COMMENT '[TSPR D|PPC|col 56]',
    deductible_1                VARCHAR(1)      COMMENT '[TSPR D|DED1|col 57]',
    deductible_2                VARCHAR(1)      COMMENT '[TSPR D|DED2|col 58]',

    -- col 59: Type of Loss
    type_of_loss                VARCHAR(1)      NOT NULL
        COMMENT '[TSPR D|TYPE|col 59|SectionB11] 1=Section I/II basic. 2=additional endorsement. 3=enhancement endorsement.',

    -- col 60: Paid Claim Count
    paid_claim_count            NUMBER(5,0)     NOT NULL
        COMMENT '[TSPR D|PCC|col 60|Rule14] 1=first payment for this claim/exposure. 0=nonpayment or already paid. -1=reversal or full recovery. NEVER >1 per claim.',

    -- cols 61-67: Amount of Loss
    loss_amount                 NUMBER(15,2)
        COMMENT '[TSPR D|LOSS|cols 61-67|Rule11] Dollars only. Net of salvage/subrogation/other recoveries. EXPLICITLY NOT net of reinsurance. Negative=credit. Rule12 encoding at render only.',

    -- cols 68-76: ZIP (PII)
    zip9                        VARCHAR(9)      COMMENT '[TSPR D|ZIP|cols 68-76|Rule24] PII. 9-digit ZIP of loss location.',

    -- col 100: Record indicator
    record_indicator            VARCHAR(1)      NOT NULL    DEFAULT 'L'
        COMMENT '[TSPR D|col 100] L=Loss record.',

    optional_cov_code           VARCHAR(8)      COMMENT '[TSPR D|cols 101-108]',
    optional_cov_amount         NUMBER(15,2)    COMMENT '[TSPR D|cols 109-114]',
    deductible_1_amt            NUMBER(15,2),
    deductible_2_amt            NUMBER(15,2),
    wind_coverage_included      VARCHAR(1)      COMMENT '[TSPR D|WIND|col 128]',
    building_code_credit        VARCHAR(2)      COMMENT '[TSPR D|BCC|cols 134-135]',
    law_ordinance_pct           VARCHAR(1)      COMMENT '[TSPR D|LOC|col 136]',

    -- col 140: Tenure (REQUIRED on ALL loss transactions per Rule 30)
    tenure_code                 VARCHAR(1)      NOT NULL    COMMENT '[TSPR D|TENURE|col 140|Rule30] REQUIRED on ALL loss transactions.',
    tenure_discount_pct         VARCHAR(2)      COMMENT '[TSPR D|TENUREDISCT|cols 141-142]',

    replacement_cost_building   VARCHAR(1)      COMMENT '[TSPR D|RCB|col 151]',
    replacement_cost_pp         VARCHAR(1)      COMMENT '[TSPR D|RCPP|col 152]',
    roof_coverage_type          VARCHAR(1)      COMMENT '[TSPR D|RCT|col 153]',
    private_flood_indicator     VARCHAR(1)      COMMENT '[TSPR D|FLOOD|col 154]',
    trop_cyclone_deductible     VARCHAR(1)      COMMENT '[TSPR D|TCDED|col 155]',
    trop_cyclone_deductible_amt NUMBER(15,2),
    year_of_construction        NUMBER(4,0)     COMMENT '[TSPR D|YOC|cols 162-165]',
    amt_insurance_alu           NUMBER(10,0)    COMMENT '[TSPR D|ALE|cols 166-168|Rule6] Loss of Use in $1000s.',
    amt_insurance_pp            NUMBER(10,0)    COMMENT '[TSPR D|HOPP|cols 169-172]',

    -- col 173: New Claim Count
    new_claim_count             NUMBER(5,0)     NOT NULL
        COMMENT '[TSPR D|NCC|col 173|Rule13] 1=newly reported. 0=previously reported. -1=reversal. Report in month of FIRST receipt to carrier.',

    -- col 174: Claim Status
    claim_status                NUMBER(5,0)     NOT NULL
        COMMENT '[TSPR D|CS|col 174|Rule16] 1=open/never closed,2=CWIP/never closed,3=CWOP/never closed,4=open/prev closed,5=CWIP/prev closed,6=CWOP/prev closed.',

    -- cols 175-176: Claim Identifier (PII)
    claim_id_tspr               VARCHAR(2)      NOT NULL
        COMMENT '[TSPR D|CLAIMID|cols 175-176|Rule27] PII. 2-char alphanumeric. Unique per policy per occurrence date.',

    -- col 177: Reopened Claim Count
    reopened_claim_count        NUMBER(5,0)     NOT NULL
        COMMENT '[TSPR D|RCC|col 177|Rule15] 1=newly reopened (first record of month only). 0=all others. -1=reversal.',

    -- cols 83-91: Section D-specific fields
    roof_covering               VARCHAR(1)      COMMENT '[TSPR D|ROOFCOV|col 83]',
    roof_credit                 VARCHAR(1)      COMMENT '[TSPR D|ROOFCRED|col 84]',
    roof_install_year           NUMBER(4,0)     COMMENT '[TSPR D|ROOFYEAR|cols 85-88]',
    cosmetic_excl               VARCHAR(1)      COMMENT '[TSPR D|COSMETIC|col 89]',

    -- cols 90-91: Cause of Loss (CRITICAL - proximate cause rule)
    cause_of_loss               VARCHAR(2)      NOT NULL
        COMMENT '[TSPR D|COL|cols 90-91|Rule11 SectionB12] 2-digit code. PROXIMATE cause only (not ensuing). Wind+subsequent water intrusion=code 25 NOT water. Freeze burst=code 70/71 NOT discharge.',

    -- cols 93-97: Roof Depreciation
    roof_depreciation           NUMBER(15,2)
        COMMENT '[TSPR D|DEPREC|cols 93-97] Roof losses only. ACV vs RC difference. RC=$3000 ACV=$2500 -> report 500.',

    -- Rating variables
    rv_alarm                    VARCHAR(1),
    rv_age_of_home              VARCHAR(1),
    rv_sprinkler                VARCHAR(1),
    rv_claims_exp               VARCHAR(1),
    rv_companion                VARCHAR(1),
    rv_credit_score             VARCHAR(1)      COMMENT '[TSPR D|RV6|col 179] PII.',
    rv_senior                   VARCHAR(1),
    rv_smart_home               VARCHAR(1),
    rv_new_home                 VARCHAR(1),
    rv_surcharges               VARCHAR(1),

    validation_status           VARCHAR(20)     DEFAULT 'PENDING',
    validation_errors           VARIANT         COMMENT 'JSON array of validation error messages.',
    _created_timestamp          TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _pipeline_run_id            VARCHAR(100),
    _source_system              VARCHAR(50)     DEFAULT 'Guidewire ClaimCenter'
)
CLUSTER BY (accounting_month, naic_company_no)
COMMENT = 'Silver: TSPR Section D loss records. All fields mapped from Guidewire ClaimCenter. Cause of loss uses proximate cause rule. Claim counts from tspr_claim_state SCD.';

ALTER TABLE silver.tspr_loss_staging MODIFY COLUMN policy_id     SET TAG insurance_regulatory.silver.tspr_pii = 'true';
ALTER TABLE silver.tspr_loss_staging MODIFY COLUMN zip9          SET TAG insurance_regulatory.silver.tspr_pii = 'true';
ALTER TABLE silver.tspr_loss_staging MODIFY COLUMN claim_id_tspr SET TAG insurance_regulatory.silver.tspr_pii = 'true';
ALTER TABLE silver.tspr_loss_staging MODIFY COLUMN rv_credit_score SET TAG insurance_regulatory.silver.tspr_pii = 'true';


-- ---------------------------------------------------------------------------
-- 4. TSPR Cancellation Notice Staging (Sections E + G)
--    New requirement effective January 1, 2026 (HB 2067)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS silver.tspr_cancellation_staging (

    -- Identity
    accounting_month            VARCHAR(7)      NOT NULL    COMMENT 'YYYY-MM notification month',
    naic_company_no             VARCHAR(5)      NOT NULL,
    tico_company_no             VARCHAR(3),
    run_id                      VARCHAR(100),
    source_job_id               NUMBER(19,0)    COMMENT 'GW pc_job.id for lineage',

    -- cols 2-4: Notification Date
    notification_date           VARCHAR(3)      NOT NULL
        COMMENT '[TSPR E|NDT|cols 2-4|Rule34] Date notice was sent to policyholder. MMY encoded (0=Oct,-=Nov,&=Dec) at render.',

    -- cols 5-6: Action Type
    action_type                 VARCHAR(2)      NOT NULL
        COMMENT '[TSPR E|AT|cols 5-6|Rule34] 80=Cancellation,81=Nonrenewal,82=Declination. Transfer between affiliated companies NOT refusal to renew per Sec551.004.',

    -- cols 15-16: Type of Policy
    type_of_policy              VARCHAR(2)      NOT NULL
        COMMENT '[TSPR E|TOP|cols 15-16|SectionF] 01=Tenants,02=Condo,03=HO,04=Dwelling,05=MHO,06=Private Flood. Derived from Section F crosswalk: form code + construction code + LOB code.',

    -- col 17: Reason Source Indicator
    reason_source_indicator     VARCHAR(1)      NOT NULL
        COMMENT '[TSPR E|RSI|col 17|SectionF] 0=no aerial/3P,1=aerial only,2=3P only,3=both. Insurer must disclose source in written notice per Sec551.002.',

    -- col 18: 60-Day Indicator
    within_60_days_indicator    VARCHAR(1)      NOT NULL
        COMMENT '[TSPR E|60D|col 18|SectionE] Y=within first 60 days of policy term,N=after 60 days,0=not a cancellation.',

    -- cols 19-23: ZIP (PII)
    zip5                        VARCHAR(5)      NOT NULL
        COMMENT '[TSPR E|ZIP|cols 19-23|SectionE] PII. 5-digit ZIP. Risk location.',

    -- cols 24-29: Action Effective Date
    action_effective_date       VARCHAR(6)      NOT NULL
        COMMENT '[TSPR E|AED|cols 24-29|SectionE] YYYYMM. Declinations: use notification date. Flat cancellations: policy effective date. All others: date coverage ends.',

    -- cols 30-35: Recipient Count
    recipient_count             NUMBER(10,0)    NOT NULL
        COMMENT '[TSPR E|RCC|cols 30-35|Rule34] Count of policies/applications with identical unique combination key. Left-zero-padded to 6 at render.',

    -- cols 36-45: Reason Code List
    reason_code_list            VARCHAR(10)     NOT NULL
        COMMENT '[TSPR E|RCL|cols 36-45|Rule34 SectionF] Alphabetically sorted concatenated reason codes right-padded to 10. Cancel: A=nonpayment,B=hazard increase,C=no inspection,X=TWIA AR,Y=insured request,Z=other. Nonrenew/Decline: D=claims,E=liability,F=wildfire,G=wind/hail,H=concentration,J=withdrawal(alone only),K=location,L=credit,M=roof,N=tree overhang,P=defensible space,Q=maintenance/vacancy,R=condition-other,S=value,T=agent unapp.,Z=other.',

    -- Unique combination key — populated by transformation pipeline
    -- (Databricks: GENERATED ALWAYS AS concat_ws)
    -- (Snowflake: computed and stored by the ELT pipeline on each INSERT)
    unique_combination_key      VARCHAR(200)
        COMMENT 'Concatenation of 8 Rule34 combination fields, pipe-delimited. Populated by transformation pipeline.',

    -- Section G: Actual action count
    actual_action_count         NUMBER(10,0)    NOT NULL
        COMMENT '[TSPR G|CNT|cols 22-29|Rule35] Count of actual cancellations/nonrenewals/declinations by (effective_date,action_type,type_of_policy,ZIP). Must reconcile with MCAS. Left-zero-padded to 8 at render.',

    -- Validation flags — populated by transformation pipeline
    -- (Databricks: GENERATED ALWAYS AS boolean expressions)
    credit_score_violation      BOOLEAN
        COMMENT 'TRUE if credit score code L is the only reason - violates Sec559.052(a)(2). Must have at least one other reason. Populated by transformation pipeline.',
    withdrawal_violation        BOOLEAN
        COMMENT 'TRUE if withdrawal code J appears with other codes - must appear alone per SectionF. Populated by transformation pipeline.',

    validation_status           VARCHAR(20)     DEFAULT 'PENDING',
    validation_errors           VARIANT         COMMENT 'JSON array of validation error messages.',
    _created_timestamp          TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _pipeline_run_id            VARCHAR(100),
    _source_system              VARCHAR(50)     DEFAULT 'Guidewire PolicyCenter',
    _effective_jan2026          BOOLEAN         DEFAULT TRUE
        COMMENT 'HB 2067 effective January 1 2026 - required for policies effective on/after this date'
)
CLUSTER BY (accounting_month, naic_company_no)
COMMENT = 'Silver: TSPR Sections E+G cancellation/nonrenewal/declination notice staging. HB2067 effective Jan 1 2026. Aggregates unique combinations with recipient and actual counts.';

ALTER TABLE silver.tspr_cancellation_staging MODIFY COLUMN zip5 SET TAG insurance_regulatory.silver.tspr_pii = 'true';
