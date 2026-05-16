-- =============================================================================
-- SNOWFLAKE DDL: GOLD LAYER — TSPR Submission-Ready Record Tables
-- =============================================================================
-- Purpose  : Each row is one TSPR SDF record ready for the fixed-width ASCII
--            renderer. Assembled from Silver by the Gold assembly pipeline.
--            This is what the SDF renderer, validation agent, and reporting
--            queries read directly.
--
-- Key design principle:
--   Silver = one row per TSPR field group
--   Gold   = one row per TSPR SDF record (Section C, D, E, G line)
--
-- Snowflake translation notes:
--   GENERATED ALWAYS AS IDENTITY  -> AUTOINCREMENT  (Snowflake identity)
--   GENERATED ALWAYS AS (naic_company_no)  -> computed via view or pipeline
--                                   (stored as regular VARCHAR, set on INSERT)
--   GENERATED ALWAYS AS (CASE WHEN...) on DECIMAL -> stored column, populated
--                                   by aggregation pipeline
--   GENERATED ALWAYS AS (add_months(...)): -> stored DATE, pipeline-computed
--   ARRAY<STRING>   -> VARIANT
--   NOT ENFORCED primary key -> primary key with NOVALIDATE NORELY
--   CREATE OR REPLACE VIEW ... GROUP BY ALL -> GROUP BY explicit columns
--   TRANSLATE(...)  -> Snowflake: TRANSLATE() is supported natively
-- =============================================================================

CREATE DATABASE IF NOT EXISTS insurance_regulatory;

CREATE SCHEMA IF NOT EXISTS insurance_regulatory.gold
    COMMENT = 'Gold: TSPR submission-ready SDF records. One row = one SDF record. Source for SDF renderer, validation agent, and Snowflake Cortex queries.';

USE DATABASE insurance_regulatory;
USE SCHEMA gold;

CREATE TAG IF NOT EXISTS insurance_regulatory.gold.tspr_pii
    COMMENT = 'PII column — Dynamic Data Masking policy required';

-- ---------------------------------------------------------------------------
-- 1. TSPR Premium Records  (Section C)
--    One row = one Section C fixed-width SDF record (200 columns).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold.tspr_premium_records (

    -- Partition and routing keys
    accounting_month            VARCHAR(7)      NOT NULL
        COMMENT 'YYYY-MM. Cluster key. Drives 45-day submission deadline per Rule 21.',
    naic_company_no             VARCHAR(5)      NOT NULL
        COMMENT '5-digit NAIC. Cluster key. Governs per-company reporting per Rule 25.',
    record_seq                  NUMBER(19,0)    NOT NULL AUTOINCREMENT
        COMMENT 'Monotonic sequence for SDF file ordering within the month.',
    run_id                      VARCHAR(100)
        COMMENT 'Pipeline run ID. Links to gold.tspr_approval_log for sign-off audit.',
    source_policyperiod_id      NUMBER(19,0)
        COMMENT 'Source GW pc_policyperiod.id for lineage back to bronze.',

    -- cols 1-4
    stat_plan                   VARCHAR(1)      NOT NULL    DEFAULT '4',
    accounting_date_encoded     VARCHAR(3)      NOT NULL
        COMMENT 'ACDT in TSPR MMY encoding: 0=Oct,-=Nov,&=Dec. Derived from accounting_month at assembly time.',

    -- cols 5-6
    record_type                 VARCHAR(2)      NOT NULL
        COMMENT 'RT: 01=New/Renewal,02=Endorsement,03=Reinstatement,05=Flat Cancel,06=Pro Rata Cancel,07=TWIA AR Cancel,08=TWIA Assumption,12=Short-term,91/92/93/95=HO variants.',

    -- cols 7-16 (PII)
    policy_id                   VARCHAR(10)     NOT NULL
        COMMENT 'POLICY: 10-char alphanumeric unique per policy per Rule 26. PII.',

    -- col 17
    term                        VARCHAR(1)
        COMMENT 'TRM: 1=one year or less, 9=over one year.',

    -- cols 18-22
    effective_date              VARCHAR(5)
        COMMENT 'EFF: MMDDY format per Rule 8.',

    -- cols 23-25
    expiry_date                 VARCHAR(3)
        COMMENT 'EXP: MMY format per Rule 8.',

    -- cols 26-30
    place_code                  VARCHAR(5)
        COMMENT 'PLACE: TDI county-community code per Rule 18.',

    -- cols 33-37
    amt_insurance_dw            NUMBER(10,0)
        COMMENT 'INS: Dwelling limit in $1000s per Rule 6. Under $1500 = 1.',

    -- cols 41-42
    line_of_business            VARCHAR(2)      NOT NULL,

    -- cols 43-45
    tico_company_no             VARCHAR(3),

    -- col 50
    policy_form                 VARCHAR(1)      NOT NULL,

    -- col 51
    number_of_families          VARCHAR(1),

    -- col 52
    coverage_occupancy          VARCHAR(1),

    -- col 53
    construction                VARCHAR(1),

    -- cols 54-55
    ppc_split                   VARCHAR(2),

    -- col 56
    ppc_simple                  VARCHAR(1),

    -- col 57
    deductible_1                VARCHAR(1),

    -- col 58
    deductible_2                VARCHAR(1),

    -- cols 59-63
    fire_premium                NUMBER(15,2),

    -- cols 67-70
    ec_premium                  NUMBER(15,2),

    -- cols 71-72
    allied_lob                  VARCHAR(2)
        COMMENT 'ALOB: Allied Lines LOB code for records covering LOB 25-29,50,77.',

    -- cols 73-75
    allied_amt_insurance        NUMBER(10,0)
        COMMENT 'ALINS: Allied Lines amount of insurance in $1000s.',

    -- cols 76-79
    allied_premium              NUMBER(15,2)
        COMMENT 'APRM: Allied Lines premium.',

    -- col 83
    roof_covering               VARCHAR(1),

    -- col 84
    roof_credit                 VARCHAR(1),

    -- cols 85-88
    roof_install_year           NUMBER(4,0),

    -- col 89
    cosmetic_excl               VARCHAR(1),

    -- cols 91-99 (PII)
    zip9                        VARCHAR(9)
        COMMENT 'ZIP: 9-digit. PII.',

    -- col 100
    record_indicator            VARCHAR(1)      NOT NULL    DEFAULT 'P',

    -- cols 101-108
    optional_cov_code           VARCHAR(8),

    -- cols 109-114
    optional_cov_amount         NUMBER(15,2),

    -- cols 116-121
    deductible_1_amt            NUMBER(15,2),

    -- cols 122-127
    deductible_2_amt            NUMBER(15,2),

    -- col 128
    wind_coverage_included      VARCHAR(1)      NOT NULL    DEFAULT '0',

    -- cols 134-135
    building_code_credit        VARCHAR(2),

    -- col 136
    law_ordinance_pct           VARCHAR(1),

    -- col 138
    optional_credit_ppid        VARCHAR(1),

    -- col 140 (REQUIRED on ALL transactions per Rule 30)
    tenure_code                 VARCHAR(1)      NOT NULL,

    -- cols 141-142
    tenure_discount_pct         VARCHAR(2)      NOT NULL    DEFAULT '00',

    -- cols 146-150 (SDF renderer position copy of partition key)
    -- In Databricks this was GENERATED ALWAYS AS (naic_company_no)
    -- In Snowflake we store it as a regular column, populated on INSERT
    naic_company_no_sdf         VARCHAR(5)      NOT NULL
        COMMENT 'NAIC: Repeated at SDF position 146-150 for renderer. Equals naic_company_no; populated on INSERT.',

    -- cols 151-154
    replacement_cost_building   VARCHAR(1),
    replacement_cost_pp         VARCHAR(1),
    roof_coverage_type          VARCHAR(1),
    private_flood_indicator     VARCHAR(1),

    -- cols 155-161
    trop_cyclone_deductible     VARCHAR(1),
    trop_cyclone_deductible_amt NUMBER(15,2),

    -- cols 162-165
    year_of_construction        NUMBER(4,0),

    -- cols 166-168
    amt_insurance_alu           NUMBER(10,0)
        COMMENT 'ALE: Loss of Use in $1000s. % of Cov A already converted to dollars per Rule 6.',

    -- cols 169-172
    amt_insurance_pp            NUMBER(10,0)
        COMMENT 'HOPP: HO PP limit in $1000s. HO only.',

    -- col 173
    prior_claims_history        VARCHAR(1),

    -- cols 174-183 (ten rating variables, Section B.20)
    rv_alarm                    VARCHAR(1),
    rv_age_of_home              VARCHAR(1),
    rv_sprinkler                VARCHAR(1),
    rv_claims_exp               VARCHAR(1),
    rv_companion                VARCHAR(1),
    rv_credit_score             VARCHAR(1)      COMMENT 'RV6: PII.',
    rv_senior                   VARCHAR(1),
    rv_smart_home               VARCHAR(1),
    rv_new_home                 VARCHAR(1),
    rv_surcharges               VARCHAR(1),

    -- Gold metadata
    validation_status           VARCHAR(20)     NOT NULL    DEFAULT 'PENDING'
        COMMENT 'PENDING -> VALIDATED -> APPROVED -> SUBMITTED. Approval gate before SDF render.',
    validation_errors           VARIANT         COMMENT 'JSON array of field-level errors from validation agent.',
    anomaly_flags               VARIANT         COMMENT 'JSON array of trend anomalies from anomaly detection agent.',
    approved_by                 VARCHAR(100)    COMMENT 'Actuary/compliance user who approved this batch.',
    approved_timestamp          TIMESTAMP_NTZ,
    submission_id               VARCHAR(100)    COMMENT 'FK -> gold.tspr_submissions after TICO upload.',
    _created_timestamp          TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _pipeline_run_id            VARCHAR(100)
)
CLUSTER BY (accounting_month, naic_company_no, record_type)
COMMENT = 'Gold: TSPR Section C premium records. One row = one SDF record. All 200 columns pre-computed. Partitioned by accounting_month + naic_company_no. TSPR plan version: Effective January 1 2026. Governing body: Texas Department of Insurance. Statistical agent: TICO. Submission medium: Fixed ASCII SDF via TICO ShareFile. Retention: 2 years per Rule 21.';

ALTER TABLE gold.tspr_premium_records MODIFY COLUMN policy_id     SET TAG insurance_regulatory.gold.tspr_pii = 'true';
ALTER TABLE gold.tspr_premium_records MODIFY COLUMN zip9          SET TAG insurance_regulatory.gold.tspr_pii = 'true';
ALTER TABLE gold.tspr_premium_records MODIFY COLUMN rv_credit_score SET TAG insurance_regulatory.gold.tspr_pii = 'true';


-- ---------------------------------------------------------------------------
-- 2. TSPR Loss Records  (Section D)
--    One row = one Section D fixed-width SDF loss record.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold.tspr_loss_records (

    accounting_month            VARCHAR(7)      NOT NULL,
    naic_company_no             VARCHAR(5)      NOT NULL,
    record_seq                  NUMBER(19,0)    NOT NULL AUTOINCREMENT,
    run_id                      VARCHAR(100),
    source_claim_id             NUMBER(19,0),
    source_exposure_id          NUMBER(19,0),
    source_transaction_id       NUMBER(19,0),

    stat_plan                   VARCHAR(1)      NOT NULL    DEFAULT '4',
    accounting_date_encoded     VARCHAR(3)      NOT NULL,

    -- cols 7-16 (PII)
    policy_id                   VARCHAR(10)     NOT NULL,

    -- cols 17-22 (loss date, not effective date)
    occurrence_date             VARCHAR(6)      NOT NULL
        COMMENT 'OCC: MMDDYY. Proximate cause date per Rule 11.',

    -- cols 23-25
    policy_effective_date       VARCHAR(3)
        COMMENT 'MMY of policy period effective date.',

    -- cols 26-30
    place_code                  VARCHAR(5),

    -- col 31 (KEY FIELD)
    kind_code                   NUMBER(5,0)     NOT NULL
        COMMENT 'KIND: 1-3=no payment, 4-5=paid on reopened, 6=paid not reopened, 7-9=outstanding. Derived from tspr_claim_state SCD.',

    -- cols 33-37
    amt_insurance_dw            NUMBER(10,0),

    -- cols 41-42
    line_of_business            VARCHAR(2)      NOT NULL,

    -- cols 43-45
    tico_company_no             VARCHAR(3),

    -- cols 50-58
    policy_form                 VARCHAR(1),
    number_of_families          VARCHAR(1),
    coverage_occupancy          VARCHAR(1),
    construction                VARCHAR(1),
    ppc_split                   VARCHAR(2),
    ppc_simple                  VARCHAR(1),
    deductible_1                VARCHAR(1),
    deductible_2                VARCHAR(1),

    -- col 59 (Section D only)
    type_of_loss                VARCHAR(1)      NOT NULL
        COMMENT 'TYPE: 1=Section I/II basic, 2=additional endorsement, 3=enhancement endorsement.',

    -- col 60 (KEY FIELD)
    paid_claim_count            NUMBER(5,0)     NOT NULL
        COMMENT 'PCC: 1=first payment for this claim/exposure, 0=nonpayment or already paid, -1=reversal per Rule 14.',

    -- cols 61-67 (KEY FIELD)
    loss_amount                 NUMBER(15,2)
        COMMENT 'LOSS: Net of salvage/subrogation. NOT net of reinsurance per Rule 11. Negative = credit. Rule 12 encoding at render only.',

    -- cols 68-76 (PII)
    zip9                        VARCHAR(9)      COMMENT 'Loss location ZIP. PII.',

    -- col 100
    record_indicator            VARCHAR(1)      NOT NULL    DEFAULT 'L',

    optional_cov_code           VARCHAR(8),
    optional_cov_amount         NUMBER(15,2),
    deductible_1_amt            NUMBER(15,2),
    deductible_2_amt            NUMBER(15,2),
    wind_coverage_included      VARCHAR(1),
    building_code_credit        VARCHAR(2),
    law_ordinance_pct           VARCHAR(1),

    -- col 140 (REQUIRED per Rule 30)
    tenure_code                 VARCHAR(1)      NOT NULL,
    tenure_discount_pct         VARCHAR(2)      NOT NULL    DEFAULT '00',

    naic_company_no_sdf         VARCHAR(5)      NOT NULL
        COMMENT 'NAIC: At SDF position 146-150. Equals naic_company_no; populated on INSERT.',

    replacement_cost_building   VARCHAR(1),
    replacement_cost_pp         VARCHAR(1),
    roof_coverage_type          VARCHAR(1),
    private_flood_indicator     VARCHAR(1),
    trop_cyclone_deductible     VARCHAR(1),
    trop_cyclone_deductible_amt NUMBER(15,2),
    year_of_construction        NUMBER(4,0),
    amt_insurance_alu           NUMBER(10,0),
    amt_insurance_pp            NUMBER(10,0),

    -- col 173 (KEY FIELD)
    new_claim_count             NUMBER(5,0)     NOT NULL
        COMMENT 'NCC: 1=newly reported in month carrier first received, 0=previously reported, -1=reversal per Rule 13.',

    -- col 174 (KEY FIELD)
    claim_status                NUMBER(5,0)     NOT NULL
        COMMENT 'CS: 1=open never closed, 2=CWIP never closed, 3=CWOP never closed, 4=open prev closed, 5=CWIP prev closed, 6=CWOP prev closed per Rule 16.',

    -- cols 175-176 (PII)
    claim_id_tspr               VARCHAR(2)      NOT NULL
        COMMENT 'CLAIMID: 2-char alphanumeric, unique per policy per occurrence date per Rule 27. PII.',

    -- col 177 (KEY FIELD)
    reopened_claim_count        NUMBER(5,0)     NOT NULL
        COMMENT 'RCC: 1=newly reopened first record of month, 0=all others, -1=reversal per Rule 15.',

    -- cols 83-91
    roof_covering               VARCHAR(1),
    roof_credit                 VARCHAR(1),
    roof_install_year           NUMBER(4,0),
    cosmetic_excl               VARCHAR(1),
    cause_of_loss               VARCHAR(2)      NOT NULL
        COMMENT 'COL: 2-digit proximate cause code per Section B.12 and Rule 11.',
    roof_depreciation           NUMBER(15,2)
        COMMENT 'DEPREC: Roof losses only. ACV vs RC difference. Null for non-roof losses.',

    -- Rating variables
    rv_alarm                    VARCHAR(1),
    rv_age_of_home              VARCHAR(1),
    rv_sprinkler                VARCHAR(1),
    rv_claims_exp               VARCHAR(1),
    rv_companion                VARCHAR(1),
    rv_credit_score             VARCHAR(1),
    rv_senior                   VARCHAR(1),
    rv_smart_home               VARCHAR(1),
    rv_new_home                 VARCHAR(1),
    rv_surcharges               VARCHAR(1),

    -- Gold metadata
    validation_status           VARCHAR(20)     NOT NULL    DEFAULT 'PENDING',
    validation_errors           VARIANT,
    anomaly_flags               VARIANT,
    approved_by                 VARCHAR(100),
    approved_timestamp          TIMESTAMP_NTZ,
    submission_id               VARCHAR(100),
    _created_timestamp          TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _pipeline_run_id            VARCHAR(100)
)
CLUSTER BY (accounting_month, naic_company_no, cause_of_loss)
COMMENT = 'Gold: TSPR Section D loss records. One row = one SDF record. Kind code, claim counts, and net loss pre-computed from Silver state machine.';

ALTER TABLE gold.tspr_loss_records MODIFY COLUMN policy_id      SET TAG insurance_regulatory.gold.tspr_pii = 'true';
ALTER TABLE gold.tspr_loss_records MODIFY COLUMN zip9           SET TAG insurance_regulatory.gold.tspr_pii = 'true';
ALTER TABLE gold.tspr_loss_records MODIFY COLUMN claim_id_tspr  SET TAG insurance_regulatory.gold.tspr_pii = 'true';


-- ---------------------------------------------------------------------------
-- 3. TSPR Cancellation Records  (Sections E + G combined)
--    One row per Section E unique-combination record.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold.tspr_cancellation_records (

    accounting_month            VARCHAR(7)      NOT NULL,
    naic_company_no             VARCHAR(5)      NOT NULL,
    record_seq                  NUMBER(19,0)    NOT NULL AUTOINCREMENT,
    run_id                      VARCHAR(100),

    -- Section E fields
    notification_date_encoded   VARCHAR(3)      NOT NULL    COMMENT 'NDT: MMY encoded.',
    action_type                 VARCHAR(2)      NOT NULL    COMMENT '80=Cancel,81=Nonrenewal,82=Declination.',

    -- NAIC at SDF position (populated on INSERT)
    naic_company_no_sdf         VARCHAR(5)      NOT NULL
        COMMENT 'NAIC at SDF cols 7-11. Equals naic_company_no; populated on INSERT.',

    tico_company_no             VARCHAR(3),
    type_of_policy              VARCHAR(2)      NOT NULL    COMMENT '01=Tenant,02=Condo,03=HO,04=Dwelling,05=MHO,06=Private Flood.',
    reason_source_indicator     VARCHAR(1)      NOT NULL    COMMENT '0=no aerial/3P,1=aerial,2=3P,3=both.',
    within_60_days_indicator    VARCHAR(1)      NOT NULL    COMMENT 'Y/N/0.',

    -- PII
    zip5                        VARCHAR(5)      NOT NULL    COMMENT 'PII.',

    action_effective_date       VARCHAR(6)      NOT NULL    COMMENT 'YYYYMM.',

    recipient_count             NUMBER(10,0)    NOT NULL
        COMMENT 'Count of policies/applications sharing this exact unique combination. Left-zero-padded to 6 at render. This is what Rule 34 aggregation produces.',

    reason_code_list            VARCHAR(10)     NOT NULL
        COMMENT 'Alphabetically sorted concatenated codes, right-padded to 10. Validated: L not alone, J alone only.',

    -- Section G (actual count)
    actual_action_count         NUMBER(10,0)    NOT NULL
        COMMENT 'Count of actual cancellations/nonrenewals/declinations. Must reconcile with MCAS per Rule 35.',

    unique_combination_key      VARCHAR(200)    NOT NULL
        COMMENT 'Hash of all 8 Rule34 combination fields. Ensures one record per unique combination.',

    -- Validation flags (Databricks: GENERATED ALWAYS AS; Snowflake: populated by pipeline)
    -- Snowflake TRANSLATE() is natively supported so this logic can be kept as-is in pipeline code
    credit_score_alone          BOOLEAN
        COMMENT 'TRUE = credit score (L) is sole reason - violates Sec559.052(a)(2). Populated by assembly pipeline.',
    withdrawal_not_alone        BOOLEAN
        COMMENT 'TRUE = withdrawal code J appears with other codes - must appear alone. Populated by assembly pipeline.',

    validation_status           VARCHAR(20)     NOT NULL    DEFAULT 'PENDING',
    validation_errors           VARIANT,
    approved_by                 VARCHAR(100),
    approved_timestamp          TIMESTAMP_NTZ,
    submission_id               VARCHAR(100),
    _created_timestamp          TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _pipeline_run_id            VARCHAR(100)
)
CLUSTER BY (accounting_month, naic_company_no)
COMMENT = 'Gold: TSPR Sections E+G. One row per unique combination with recipient and actual counts. Rule 34 aggregation from Silver. HB2067 effective Jan 1 2026.';

ALTER TABLE gold.tspr_cancellation_records MODIFY COLUMN zip5 SET TAG insurance_regulatory.gold.tspr_pii = 'true';


-- ---------------------------------------------------------------------------
-- 4. Monthly Aggregates  (Section 29 transmittal form control totals)
--    One row per naic_company_no × accounting_month.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold.tspr_monthly_aggregates (

    accounting_month            VARCHAR(7)      NOT NULL,
    naic_company_no             VARCHAR(5)      NOT NULL,
    tico_company_no             VARCHAR(3),
    run_id                      VARCHAR(100),

    -- Section 29 record counts (Rule 29)
    premium_record_count        NUMBER(19,0)    NOT NULL    DEFAULT 0
        COMMENT 'Section 29C: Count of Section C premium records.',
    loss_record_count           NUMBER(19,0)    NOT NULL    DEFAULT 0
        COMMENT 'Section 29D: Count of Section D loss records.',
    cancellation_notice_count   NUMBER(19,0)    NOT NULL    DEFAULT 0
        COMMENT 'Section 29E: Count of Section E cancellation notice records.',
    actual_count_record_count   NUMBER(19,0)    NOT NULL    DEFAULT 0
        COMMENT 'Section 29G: Count of Section G actual count records.',

    -- Dollar totals
    total_written_premium       NUMBER(18,2)    NOT NULL    DEFAULT 0
        COMMENT 'Sum of fire_premium across all Section C records for this month/company.',
    total_paid_losses           NUMBER(18,2)    NOT NULL    DEFAULT 0
        COMMENT 'Sum of loss_amount where kind_code IN (4,5,6) across Section D records.',
    total_outstanding_losses    NUMBER(18,2)    NOT NULL    DEFAULT 0
        COMMENT 'Sum of loss_amount where kind_code IN (7,8,9) across Section D records.',

    -- Action counts
    total_recipient_count       NUMBER(19,0)    NOT NULL    DEFAULT 0,
    total_cancellations         NUMBER(19,0)    NOT NULL    DEFAULT 0
        COMMENT 'Sum of actual_action_count where action_type=80.',
    total_nonrenewals           NUMBER(19,0)    NOT NULL    DEFAULT 0
        COMMENT 'Sum of actual_action_count where action_type=81.',
    total_declinations          NUMBER(19,0)    NOT NULL    DEFAULT 0
        COMMENT 'Sum of actual_action_count where action_type=82.',

    -- Claim count cross-checks
    total_new_claims            NUMBER(19,0)    COMMENT 'Sum of new_claim_count=1 across Section D records.',
    total_paid_claims           NUMBER(19,0)    COMMENT 'Sum of paid_claim_count=1 across Section D records.',
    total_reopened_claims       NUMBER(19,0)    COMMENT 'Sum of reopened_claim_count=1 across Section D records.',

    -- Prior period comparison (populated by anomaly detection agent)
    prior_month_written_premium NUMBER(18,2)    COMMENT 'Prior month total written premium for trend comparison.',
    prior_month_paid_losses     NUMBER(18,2)    COMMENT 'Prior month total paid losses.',

    -- Variance columns
    -- Databricks: GENERATED ALWAYS AS (CASE WHEN ...) on DECIMAL
    -- Snowflake: stored columns populated by assembly pipeline
    premium_variance_pct        NUMBER(8,4)
        COMMENT 'MoM written premium change %. Populated by assembly pipeline: (total_written_premium - prior_month_written_premium) / prior_month_written_premium * 100. Anomaly agent flags if > 20% or < -20%.',
    loss_variance_pct           NUMBER(8,4)
        COMMENT 'MoM paid loss change %. Populated by assembly pipeline. Anomaly agent flags if > 3 std deviations from 12-month mean.',

    -- Transmittal verification
    transmittal_balanced        BOOLEAN         COMMENT 'TRUE when all Gold record counts match these aggregates.',
    approval_status             VARCHAR(30)     DEFAULT 'PENDING'
        COMMENT 'PENDING -> ACTUARY_APPROVED -> COMPLIANCE_APPROVED.',
    actuary_approved_by         VARCHAR(100),
    actuary_approved_ts         TIMESTAMP_NTZ,
    compliance_approved_by      VARCHAR(100),
    compliance_approved_ts      TIMESTAMP_NTZ,
    submission_id               VARCHAR(100),
    _created_timestamp          TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _pipeline_run_id            VARCHAR(100),

    PRIMARY KEY (accounting_month, naic_company_no)
)
COMMENT = 'Gold: Section 29 transmittal form control totals. One row per company per month. Validation agent verifies these match individual record sums. SDF renderer reads to build transmittal form.';


-- ---------------------------------------------------------------------------
-- 5. Validation Results  (per-run field-level errors)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold.tspr_validation_results (

    run_id                      VARCHAR(100)    NOT NULL,
    accounting_month            VARCHAR(7)      NOT NULL,
    naic_company_no             VARCHAR(5)      NOT NULL,
    validation_timestamp        TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),

    -- Error detail
    record_type_tspr            VARCHAR(1)
        COMMENT 'C=Premium, D=Loss, E=Cancellation, G=ActualCount.',
    source_record_id            NUMBER(19,0)
        COMMENT 'gold.tspr_premium_records or tspr_loss_records record_seq.',
    field_name                  VARCHAR(20)
        COMMENT 'TSPR field abbreviation (e.g. TENURE, DED1, COL).',
    col_start                   NUMBER(5,0),
    col_end                     NUMBER(5,0),
    rule_id                     VARCHAR(30)
        COMMENT 'Rule reference (e.g. Rule30, SectionB10).',
    field_value                 VARCHAR(200)
        COMMENT 'Actual value that failed validation.',
    error_message               VARCHAR(500)    NOT NULL,
    severity                    VARCHAR(10)     NOT NULL
        COMMENT 'ERROR (blocks submission) or WARNING (review required).',

    -- Remediation
    remediation_suggestion      VARCHAR(500)    COMMENT 'Agent-generated fix recommendation.',
    resolved                    BOOLEAN         DEFAULT FALSE,
    resolved_by                 VARCHAR(100),
    resolved_timestamp          TIMESTAMP_NTZ
)
CLUSTER BY (accounting_month, naic_company_no)
COMMENT = 'Gold: Per-field validation errors from the validation agent. Actuary reviews before approving gold.tspr_monthly_aggregates.';


-- ---------------------------------------------------------------------------
-- 6. Anomaly Flags  (trend deviation alerts)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold.tspr_anomaly_flags (

    run_id                      VARCHAR(100)    NOT NULL,
    accounting_month            VARCHAR(7)      NOT NULL,
    naic_company_no             VARCHAR(5)      NOT NULL,
    flagged_timestamp           TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),

    anomaly_type                VARCHAR(50)     NOT NULL
        COMMENT 'HAIL_SPIKE, FREEZE_SUMMER, ZERO_CLAIMS_TERRITORY, PREMIUM_DROP, etc.',
    cause_of_loss_code          VARCHAR(2)
        COMMENT 'Relevant TSPR cause code if anomaly is cause-specific.',
    territory_zip               VARCHAR(9)
        COMMENT 'ZIP or territory where anomaly detected.',
    current_month_value         NUMBER(18,2),
    rolling_12m_mean            NUMBER(18,2),
    rolling_12m_stddev          NUMBER(18,2),
    std_deviations_from_mean    NUMBER(8,2)
        COMMENT 'How many std devs the current value is from the 12-month mean.',
    anomaly_description         VARCHAR(500)    NOT NULL,

    -- Review outcome
    reviewed_by                 VARCHAR(100),
    reviewed_timestamp          TIMESTAMP_NTZ,
    disposition                 VARCHAR(30)
        COMMENT 'CONFIRMED_DATA_ERROR, CONFIRMED_REAL_EVENT, FALSE_POSITIVE.',
    disposition_notes           VARCHAR(500)
)
CLUSTER BY (accounting_month, naic_company_no)
COMMENT = 'Gold: Trend anomalies detected by the anomaly agent. Actuary reviews before submission approval.';


-- ---------------------------------------------------------------------------
-- 7. Submission Log  (immutable audit trail)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gold.tspr_submissions (

    submission_id               VARCHAR(100)    NOT NULL
        COMMENT 'UUID generated at submission time.',
    accounting_month            VARCHAR(7)      NOT NULL,
    naic_company_no             VARCHAR(5)      NOT NULL,
    submitted_timestamp         TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),

    file_type                   VARCHAR(20)     NOT NULL
        COMMENT 'PREMIUM_C, LOSS_D, CANCEL_E, ACTUAL_G, TRANSMITTAL.',
    file_name                   VARCHAR(200)    NOT NULL
        COMMENT 'Exact filename submitted to TICO ShareFile.',
    file_hash_sha256            VARCHAR(64)     NOT NULL
        COMMENT 'SHA-256 of submitted SDF file. Supports two-year retention audit per Rule 21.',
    record_count                NUMBER(19,0)    NOT NULL,
    file_size_bytes             NUMBER(19,0),

    -- Both approvals required
    actuary_approved_by         VARCHAR(100)    NOT NULL,
    actuary_approved_ts         TIMESTAMP_NTZ   NOT NULL,
    compliance_approved_by      VARCHAR(100)    NOT NULL,
    compliance_approved_ts      TIMESTAMP_NTZ   NOT NULL,

    -- TICO receipt
    tico_confirmation_id        VARCHAR(100)
        COMMENT 'Confirmation reference from TICO ShareFile receipt.',
    tico_receipt_timestamp      TIMESTAMP_NTZ,
    tico_acceptance_status      VARCHAR(20)
        COMMENT 'ACCEPTED, REJECTED, PENDING.',

    -- Retention
    -- Databricks: GENERATED ALWAYS AS (add_months(to_date(concat(accounting_month,'-01')),25))
    -- Snowflake: stored DATE column populated by pipeline (DATEADD(MONTH,25,TO_DATE(accounting_month||'-01','YYYY-MM-DD')))
    retention_expiry_date       DATE
        COMMENT 'Underlying data must be retained until this date per Rule 21 (accounting_month + 25 months). Populated by pipeline.',

    PRIMARY KEY (submission_id)
)
COMMENT = 'Gold: Immutable submission audit log. One row per TICO file submission. SHA-256 hash enables two-year retention verification per Rule 21. This table is append-only — no updates permitted.';


-- ---------------------------------------------------------------------------
-- 8. Section G View  (derived from cancellation records)
--    Section G is the same underlying data as Section E, grouped differently.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.tspr_section_g_actual_counts
    COMMENT = 'Derived view: Section G actual cancellation/nonrenewal/declination counts. Grouped by effective_date+action_type+type_of_policy+ZIP per Rule 35. Must reconcile with MCAS.'
AS
SELECT
    accounting_month,
    naic_company_no,
    tico_company_no,
    action_effective_date                       AS action_effective_date_g,
    action_type                                 AS action_type_g,
    naic_company_no                             AS naic_company_no_sdf_g,
    tico_company_no                             AS tico_company_no_g,
    type_of_policy                              AS type_of_policy_g,
    zip5                                        AS zip5_g,
    SUM(actual_action_count)                    AS actual_action_count,
    run_id
FROM gold.tspr_cancellation_records
WHERE validation_status IN ('VALIDATED', 'APPROVED')
GROUP BY
    accounting_month,
    naic_company_no,
    tico_company_no,
    action_effective_date,
    action_type,
    type_of_policy,
    zip5,
    run_id;
