-- =============================================================================
-- SNOWFLAKE MASTER SETUP SCRIPT
-- TSPR Statistical Reporting Platform — Texas Residential Property
-- =============================================================================
-- Run this script as ACCOUNTADMIN or SYSADMIN to provision the full platform.
-- Execute sections in order: infrastructure, then schemas, then objects.
--
-- Prerequisites:
--   - Snowflake account provisioned
--   - S3/ADLS/GCS external stage configured (or Snowpipe from Guidewire GDP)
--   - Storage integration created (see Step 2)
--
-- Execution order:
--   Step 1  : Warehouses
--   Step 2  : Storage integration + external stage
--   Step 3  : Database and schemas
--   Step 4  : Roles and grants
--   Step 5  : Shared object tags
--   Step 6  : Bronze DDL   (01_bronze_policycenter.sql, 02_bronze_claimcenter.sql)
--   Step 7  : Reference DDL (01_reference_tables.sql)
--   Step 8  : Silver DDL   (01_silver_tspr_staging.sql)
--   Step 9  : Gold DDL     (01_gold_tspr_records.sql)
--   Step 10 : Snowpipe definitions
--   Step 11 : Dynamic Data Masking policies (PII)
--   Step 12 : Row Access Policies (NAIC company filter)
--   Step 13 : Streams and Tasks (Silver + Gold transformation)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Step 1: Warehouses
-- ---------------------------------------------------------------------------

-- Ingestion warehouse (Snowpipe + Bronze loads)
CREATE WAREHOUSE IF NOT EXISTS tspr_ingest_wh
    WAREHOUSE_SIZE     = 'SMALL'
    AUTO_SUSPEND       = 60
    AUTO_RESUME        = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'TSPR Bronze ingestion: Snowpipe + Auto Ingest from Guidewire GDP';

-- Transformation warehouse (Silver + Gold pipeline tasks)
CREATE WAREHOUSE IF NOT EXISTS tspr_transform_wh
    WAREHOUSE_SIZE     = 'MEDIUM'
    AUTO_SUSPEND       = 120
    AUTO_RESUME        = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'TSPR Silver + Gold transformation tasks. Schedule: monthly on day 1.';

-- Analytics / BI warehouse (read-only queries from actuaries and compliance)
CREATE WAREHOUSE IF NOT EXISTS tspr_analytics_wh
    WAREHOUSE_SIZE     = 'SMALL'
    AUTO_SUSPEND       = 60
    AUTO_RESUME        = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'TSPR read-only queries: actuarial review, BI, Streamlit app.';

-- ---------------------------------------------------------------------------
-- Step 2: Storage integration and external stage
-- (Replace <BUCKET>, <PREFIX>, <STORAGE_AWS_ROLE_ARN> with your values)
-- ---------------------------------------------------------------------------

-- AWS S3 example — swap for Azure Blob or GCS as appropriate
CREATE STORAGE INTEGRATION IF NOT EXISTS tspr_gdp_s3_integration
    TYPE                      = EXTERNAL_STAGE
    STORAGE_PROVIDER          = 'S3'
    ENABLED                   = TRUE
    STORAGE_AWS_ROLE_ARN      = 'arn:aws:iam::<ACCOUNT_ID>:role/<ROLE_NAME>'
    STORAGE_ALLOWED_LOCATIONS = ('s3://<BUCKET>/guidewire-cdc/')
    COMMENT = 'Storage integration for Guidewire Data Platform CDC export bucket';

-- After creating the integration, run:
--   DESC INTEGRATION tspr_gdp_s3_integration;
-- and grant the STORAGE_AWS_IAM_USER_ARN and STORAGE_AWS_EXTERNAL_ID
-- in your AWS IAM role trust policy.

CREATE DATABASE IF NOT EXISTS insurance_regulatory;
USE DATABASE insurance_regulatory;

CREATE SCHEMA IF NOT EXISTS insurance_regulatory.staging
    COMMENT = 'Staging: External stage pointing at Guidewire CDP S3 bucket';

CREATE STAGE IF NOT EXISTS staging.gdp_export_stage
    STORAGE_INTEGRATION = tspr_gdp_s3_integration
    URL                 = 's3://<BUCKET>/guidewire-cdc/'
    FILE_FORMAT         = (TYPE = 'PARQUET')
    COMMENT             = 'Guidewire Data Platform Parquet export. Partitioned by table/date.';

-- ---------------------------------------------------------------------------
-- Step 3: Database and schemas (idempotent — safe to re-run)
-- ---------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS insurance_regulatory.bronze
    COMMENT = 'Bronze: Raw CDC events from Guidewire. Append-only. No transformations.';

CREATE SCHEMA IF NOT EXISTS insurance_regulatory.silver
    COMMENT = 'Silver: TSPR field-mapped staging. One row per TSPR field group.';

CREATE SCHEMA IF NOT EXISTS insurance_regulatory.gold
    COMMENT = 'Gold: TSPR submission-ready SDF records. One row = one SDF record.';

CREATE SCHEMA IF NOT EXISTS insurance_regulatory.reference
    COMMENT = 'Reference: TSPR plan rules, code maps, crosswalk tables encoded as data.';

CREATE SCHEMA IF NOT EXISTS insurance_regulatory.tspr_security
    COMMENT = 'Security: Dynamic Data Masking policies and Row Access Policies for TSPR PII.';

-- ---------------------------------------------------------------------------
-- Step 4: Roles and grants
-- ---------------------------------------------------------------------------

-- Functional roles
CREATE ROLE IF NOT EXISTS tspr_compliance_admin
    COMMENT = 'Full access to all TSPR data including PII. Can approve submissions.';
CREATE ROLE IF NOT EXISTS tspr_actuary
    COMMENT = 'Read access to all TSPR Gold and Silver data including PII. Can flag anomalies.';
CREATE ROLE IF NOT EXISTS tspr_auditor
    COMMENT = 'Read access to Gold layer. PII partially masked (first 3 chars visible).';
CREATE ROLE IF NOT EXISTS tspr_pipeline
    COMMENT = 'Service account role for ingestion and transformation pipelines.';
CREATE ROLE IF NOT EXISTS tspr_readonly
    COMMENT = 'Read-only access to Gold layer with full PII masking.';

-- Role hierarchy
GRANT ROLE tspr_actuary          TO ROLE tspr_compliance_admin;
GRANT ROLE tspr_readonly         TO ROLE tspr_auditor;

-- Warehouse grants
GRANT USAGE ON WAREHOUSE tspr_ingest_wh    TO ROLE tspr_pipeline;
GRANT USAGE ON WAREHOUSE tspr_transform_wh TO ROLE tspr_pipeline;
GRANT USAGE ON WAREHOUSE tspr_analytics_wh TO ROLE tspr_actuary;
GRANT USAGE ON WAREHOUSE tspr_analytics_wh TO ROLE tspr_auditor;
GRANT USAGE ON WAREHOUSE tspr_analytics_wh TO ROLE tspr_readonly;
GRANT USAGE ON WAREHOUSE tspr_analytics_wh TO ROLE tspr_compliance_admin;

-- Database and schema usage
GRANT USAGE ON DATABASE insurance_regulatory TO ROLE tspr_pipeline;
GRANT USAGE ON DATABASE insurance_regulatory TO ROLE tspr_compliance_admin;
GRANT USAGE ON DATABASE insurance_regulatory TO ROLE tspr_actuary;
GRANT USAGE ON DATABASE insurance_regulatory TO ROLE tspr_auditor;
GRANT USAGE ON DATABASE insurance_regulatory TO ROLE tspr_readonly;

GRANT USAGE ON SCHEMA insurance_regulatory.bronze    TO ROLE tspr_pipeline;
GRANT USAGE ON SCHEMA insurance_regulatory.silver    TO ROLE tspr_pipeline;
GRANT USAGE ON SCHEMA insurance_regulatory.gold      TO ROLE tspr_pipeline;
GRANT USAGE ON SCHEMA insurance_regulatory.reference TO ROLE tspr_pipeline;

GRANT USAGE ON SCHEMA insurance_regulatory.bronze    TO ROLE tspr_compliance_admin;
GRANT USAGE ON SCHEMA insurance_regulatory.silver    TO ROLE tspr_compliance_admin;
GRANT USAGE ON SCHEMA insurance_regulatory.gold      TO ROLE tspr_compliance_admin;
GRANT USAGE ON SCHEMA insurance_regulatory.reference TO ROLE tspr_compliance_admin;

GRANT USAGE ON SCHEMA insurance_regulatory.silver    TO ROLE tspr_actuary;
GRANT USAGE ON SCHEMA insurance_regulatory.gold      TO ROLE tspr_actuary;
GRANT USAGE ON SCHEMA insurance_regulatory.reference TO ROLE tspr_actuary;

GRANT USAGE ON SCHEMA insurance_regulatory.gold      TO ROLE tspr_auditor;
GRANT USAGE ON SCHEMA insurance_regulatory.gold      TO ROLE tspr_readonly;

-- Table-level grants
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA insurance_regulatory.bronze    TO ROLE tspr_pipeline;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA insurance_regulatory.silver    TO ROLE tspr_pipeline;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA insurance_regulatory.gold      TO ROLE tspr_pipeline;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA insurance_regulatory.reference TO ROLE tspr_pipeline;

GRANT SELECT ON ALL TABLES IN SCHEMA insurance_regulatory.silver    TO ROLE tspr_compliance_admin;
GRANT SELECT ON ALL TABLES IN SCHEMA insurance_regulatory.gold      TO ROLE tspr_compliance_admin;
GRANT SELECT ON ALL TABLES IN SCHEMA insurance_regulatory.bronze    TO ROLE tspr_compliance_admin;
GRANT SELECT ON ALL TABLES IN SCHEMA insurance_regulatory.reference TO ROLE tspr_compliance_admin;

GRANT SELECT ON ALL TABLES IN SCHEMA insurance_regulatory.silver    TO ROLE tspr_actuary;
GRANT SELECT ON ALL TABLES IN SCHEMA insurance_regulatory.gold      TO ROLE tspr_actuary;
GRANT SELECT ON ALL TABLES IN SCHEMA insurance_regulatory.reference TO ROLE tspr_actuary;

GRANT SELECT ON ALL TABLES IN SCHEMA insurance_regulatory.gold      TO ROLE tspr_auditor;
GRANT SELECT ON ALL TABLES IN SCHEMA insurance_regulatory.gold      TO ROLE tspr_readonly;

-- Future grants (new tables automatically inherit)
GRANT SELECT, INSERT ON FUTURE TABLES IN SCHEMA insurance_regulatory.bronze TO ROLE tspr_pipeline;
GRANT SELECT, INSERT ON FUTURE TABLES IN SCHEMA insurance_regulatory.silver TO ROLE tspr_pipeline;
GRANT SELECT, INSERT, UPDATE ON FUTURE TABLES IN SCHEMA insurance_regulatory.gold TO ROLE tspr_pipeline;
GRANT SELECT ON FUTURE TABLES IN SCHEMA insurance_regulatory.gold   TO ROLE tspr_compliance_admin;
GRANT SELECT ON FUTURE TABLES IN SCHEMA insurance_regulatory.gold   TO ROLE tspr_actuary;
GRANT SELECT ON FUTURE TABLES IN SCHEMA insurance_regulatory.gold   TO ROLE tspr_auditor;
GRANT SELECT ON FUTURE TABLES IN SCHEMA insurance_regulatory.gold   TO ROLE tspr_readonly;

-- ---------------------------------------------------------------------------
-- Step 5: Object Tags (created individually in each schema DDL file,
--         repeated here for reference — safe to skip if already run)
-- ---------------------------------------------------------------------------

CREATE TAG IF NOT EXISTS insurance_regulatory.bronze.tspr_pii
    COMMENT = 'PII column — Dynamic Data Masking policy tspr_security.mask_pii applies';
CREATE TAG IF NOT EXISTS insurance_regulatory.silver.tspr_pii
    COMMENT = 'PII column — Dynamic Data Masking policy tspr_security.mask_pii applies';
CREATE TAG IF NOT EXISTS insurance_regulatory.gold.tspr_pii
    COMMENT = 'PII column — Dynamic Data Masking policy tspr_security.mask_pii applies';

-- Grant tag usage to pipeline role
GRANT APPLY TAG ON ACCOUNT TO ROLE tspr_pipeline;

-- ---------------------------------------------------------------------------
-- Steps 6-9: Run individual DDL files in this order
-- ---------------------------------------------------------------------------
--   !source bronze/01_bronze_policycenter.sql
--   !source bronze/02_bronze_claimcenter.sql
--   !source reference/01_reference_tables.sql
--   !source silver/01_silver_tspr_staging.sql
--   !source gold/01_gold_tspr_records.sql
--
-- Or in SnowSQL:
--   snowsql -a <account> -u <user> -d insurance_regulatory -f bronze/01_bronze_policycenter.sql
--   snowsql -a <account> -u <user> -d insurance_regulatory -f bronze/02_bronze_claimcenter.sql
--   etc.

-- ---------------------------------------------------------------------------
-- Step 10: Snowpipe definitions (auto-ingest from S3/ADLS)
-- ---------------------------------------------------------------------------
-- One pipe per Guidewire source table. Each pipe watches the external stage
-- for new Parquet files and auto-ingests into the corresponding Bronze table.
-- The COPY INTO statement strips Databricks-specific CDC envelope fields and
-- maps Parquet column names to Snowflake column names.

USE SCHEMA insurance_regulatory.bronze;

CREATE PIPE IF NOT EXISTS bronze.pipe_gw_pc_policyperiod
    AUTO_INGEST = TRUE
    COMMENT = 'Snowpipe: Guidewire PolicyCenter pc_policyperiod -> bronze.gw_pc_policyperiod'
AS
COPY INTO bronze.gw_pc_policyperiod (
    _cdc_operation, _cdc_timestamp, _cdc_source_db, _cdc_sequence,
    _ingestion_timestamp, _source_file, _partition_month,
    id, publicid, policy_id, account_id, producercode_id, policycontact_id,
    uwcompany_id, policyterm_id,
    periodstart, periodend, editeffectivedate, modelnumber, modeldate,
    status, jobtype, policytype, basestate, branchname,
    termtype, termnum, cancellationdate, cancellationsource, cancellationreason,
    nonrenewalcode, writtendate,
    totalpremium, writtenpremium, totalcost, fulltermamount, earnedpremium,
    uwcompanycode, naic_number, tico_company_number,
    createtime, updatetime, retiredvalue
)
FROM (
    SELECT
        $1:_cdc_operation::VARCHAR,
        $1:_cdc_timestamp::TIMESTAMP_NTZ,
        'gwpc'::VARCHAR,
        $1:_cdc_sequence::NUMBER(19,0),
        CURRENT_TIMESTAMP(),
        METADATA$FILENAME,
        TO_VARCHAR(DATE_TRUNC('MONTH', $1:periodstart::TIMESTAMP_NTZ), 'YYYY-MM'),
        $1:id::NUMBER(19,0),
        $1:publicid::VARCHAR,
        $1:policy_id::NUMBER(19,0),
        $1:account_id::NUMBER(19,0),
        $1:producercode_id::NUMBER(19,0),
        $1:policycontact_id::NUMBER(19,0),
        $1:uwcompany_id::NUMBER(19,0),
        $1:policyterm_id::NUMBER(19,0),
        $1:periodstart::TIMESTAMP_NTZ,
        $1:periodend::TIMESTAMP_NTZ,
        $1:editeffectivedate::TIMESTAMP_NTZ,
        $1:modelnumber::NUMBER(10,0),
        $1:modeldate::TIMESTAMP_NTZ,
        $1:status::VARCHAR,
        $1:jobtype::VARCHAR,
        $1:policytype::VARCHAR,
        $1:basestate::VARCHAR,
        $1:branchname::VARCHAR,
        $1:termtype::VARCHAR,
        $1:termnum::NUMBER(10,0),
        $1:cancellationdate::TIMESTAMP_NTZ,
        $1:cancellationsource::VARCHAR,
        $1:cancellationreason::VARCHAR,
        $1:nonrenewalcode::VARCHAR,
        $1:writtendate::TIMESTAMP_NTZ,
        $1:totalpremium::NUMBER(15,2),
        $1:writtenpremium::NUMBER(15,2),
        $1:totalcost::NUMBER(15,2),
        $1:fulltermamount::NUMBER(15,2),
        $1:earnedpremium::NUMBER(15,2),
        $1:uwcompanycode::VARCHAR,
        $1:naic_number::VARCHAR,
        $1:tico_company_number::VARCHAR,
        $1:createtime::TIMESTAMP_NTZ,
        $1:updatetime::TIMESTAMP_NTZ,
        $1:retiredvalue::NUMBER(10,0)
    FROM @staging.gdp_export_stage/policycenter/pc_policyperiod/
    (FILE_FORMAT => 'PARQUET')
);

CREATE PIPE IF NOT EXISTS bronze.pipe_gw_pc_policy
    AUTO_INGEST = TRUE
    COMMENT = 'Snowpipe: Guidewire PolicyCenter pc_policy -> bronze.gw_pc_policy'
AS
COPY INTO bronze.gw_pc_policy (
    _cdc_operation, _cdc_timestamp, _cdc_sequence,
    _ingestion_timestamp, _source_file,
    id, publicid, account_id, producercode_id, policynumber,
    issuedate, originalinceptiondate, createtime, updatetime, retiredvalue
)
FROM (
    SELECT
        $1:_cdc_operation::VARCHAR, $1:_cdc_timestamp::TIMESTAMP_NTZ,
        $1:_cdc_sequence::NUMBER(19,0), CURRENT_TIMESTAMP(), METADATA$FILENAME,
        $1:id::NUMBER(19,0), $1:publicid::VARCHAR,
        $1:account_id::NUMBER(19,0), $1:producercode_id::NUMBER(19,0),
        $1:policynumber::VARCHAR, $1:issuedate::TIMESTAMP_NTZ,
        $1:originalinceptiondate::TIMESTAMP_NTZ,
        $1:createtime::TIMESTAMP_NTZ, $1:updatetime::TIMESTAMP_NTZ,
        $1:retiredvalue::NUMBER(10,0)
    FROM @staging.gdp_export_stage/policycenter/pc_policy/ (FILE_FORMAT => 'PARQUET')
);

CREATE PIPE IF NOT EXISTS bronze.pipe_gw_cc_claim
    AUTO_INGEST = TRUE
    COMMENT = 'Snowpipe: Guidewire ClaimCenter cc_claim -> bronze.gw_cc_claim'
AS
COPY INTO bronze.gw_cc_claim (
    _cdc_operation, _cdc_timestamp, _cdc_sequence,
    _ingestion_timestamp, _source_file, _partition_month,
    id, publicid, claimnumber,
    policy_id, policynumber, policyperiod_id, uwcompany_id, naic_number,
    lossdate, losslocation_id, reporteddate,
    losscause, losscausesubtype, lobtypecode, coveragecategory,
    state, closedate, reopendate,
    hasindemnity, totalincurred, subrogationamount, salvageamount,
    isintwiazone, createtime, updatetime, retiredvalue
)
FROM (
    SELECT
        $1:_cdc_operation::VARCHAR, $1:_cdc_timestamp::TIMESTAMP_NTZ,
        $1:_cdc_sequence::NUMBER(19,0), CURRENT_TIMESTAMP(), METADATA$FILENAME,
        TO_VARCHAR(DATE_TRUNC('MONTH', $1:lossdate::TIMESTAMP_NTZ), 'YYYY-MM'),
        $1:id::NUMBER(19,0), $1:publicid::VARCHAR, $1:claimnumber::VARCHAR,
        $1:policy_id::NUMBER(19,0), $1:policynumber::VARCHAR,
        $1:policyperiod_id::NUMBER(19,0), $1:uwcompany_id::NUMBER(19,0),
        $1:naic_number::VARCHAR,
        $1:lossdate::TIMESTAMP_NTZ, $1:losslocation_id::NUMBER(19,0),
        $1:reporteddate::TIMESTAMP_NTZ,
        $1:losscause::VARCHAR, $1:losscausesubtype::VARCHAR,
        $1:lobtypecode::VARCHAR, $1:coveragecategory::VARCHAR,
        $1:state::VARCHAR, $1:closedate::TIMESTAMP_NTZ, $1:reopendate::TIMESTAMP_NTZ,
        $1:hasindemnity::BOOLEAN, $1:totalincurred::NUMBER(15,2),
        $1:subrogationamount::NUMBER(15,2), $1:salvageamount::NUMBER(15,2),
        $1:isintwiazone::BOOLEAN,
        $1:createtime::TIMESTAMP_NTZ, $1:updatetime::TIMESTAMP_NTZ,
        $1:retiredvalue::NUMBER(10,0)
    FROM @staging.gdp_export_stage/claimcenter/cc_claim/ (FILE_FORMAT => 'PARQUET')
);

-- Note: Equivalent pipes for gw_pc_hopolicyline, gw_pc_hocoverage,
-- gw_pc_hodwelling, gw_pc_job, gw_pc_uwcompany, gw_pc_address,
-- gw_bc_policyperiodpremium, gw_cc_exposure, gw_cc_transaction,
-- gw_cc_reserveline, gw_cc_address follow the same pattern above.
-- Each maps: @staging.gdp_export_stage/<system>/<table>/ -> bronze.<table>
-- with _partition_month computed from the relevant date column.

-- ---------------------------------------------------------------------------
-- Step 11: Dynamic Data Masking Policies (PII columns)
-- ---------------------------------------------------------------------------

USE SCHEMA insurance_regulatory.tspr_security;

-- Master PII masking function
CREATE OR REPLACE MASKING POLICY tspr_security.mask_pii
    AS (col_value VARCHAR)
    RETURNS VARCHAR ->
    CASE
        WHEN CURRENT_ROLE() IN ('TSPR_COMPLIANCE_ADMIN', 'TSPR_ACTUARY')
            THEN col_value                                  -- full plaintext
        WHEN CURRENT_ROLE() = 'TSPR_AUDITOR'
            THEN LEFT(col_value, 3) || '***'               -- partial (first 3 chars)
        ELSE '***MASKED***'                                 -- all others: fully masked
    END
COMMENT = 'TSPR PII masking: compliance_admin and actuary see plaintext; auditor sees first 3 chars; all others masked.';

-- Apply masking to all PII columns in Silver
ALTER TABLE silver.tspr_premium_staging
    MODIFY COLUMN policy_id      SET MASKING POLICY tspr_security.mask_pii;
ALTER TABLE silver.tspr_premium_staging
    MODIFY COLUMN zip9           SET MASKING POLICY tspr_security.mask_pii;
ALTER TABLE silver.tspr_premium_staging
    MODIFY COLUMN rv_credit_score SET MASKING POLICY tspr_security.mask_pii;

ALTER TABLE silver.tspr_loss_staging
    MODIFY COLUMN policy_id      SET MASKING POLICY tspr_security.mask_pii;
ALTER TABLE silver.tspr_loss_staging
    MODIFY COLUMN zip9           SET MASKING POLICY tspr_security.mask_pii;
ALTER TABLE silver.tspr_loss_staging
    MODIFY COLUMN claim_id_tspr  SET MASKING POLICY tspr_security.mask_pii;
ALTER TABLE silver.tspr_loss_staging
    MODIFY COLUMN rv_credit_score SET MASKING POLICY tspr_security.mask_pii;

ALTER TABLE silver.tspr_cancellation_staging
    MODIFY COLUMN zip5           SET MASKING POLICY tspr_security.mask_pii;

-- Apply masking to all PII columns in Gold
ALTER TABLE gold.tspr_premium_records
    MODIFY COLUMN policy_id      SET MASKING POLICY tspr_security.mask_pii;
ALTER TABLE gold.tspr_premium_records
    MODIFY COLUMN zip9           SET MASKING POLICY tspr_security.mask_pii;
ALTER TABLE gold.tspr_premium_records
    MODIFY COLUMN rv_credit_score SET MASKING POLICY tspr_security.mask_pii;

ALTER TABLE gold.tspr_loss_records
    MODIFY COLUMN policy_id      SET MASKING POLICY tspr_security.mask_pii;
ALTER TABLE gold.tspr_loss_records
    MODIFY COLUMN zip9           SET MASKING POLICY tspr_security.mask_pii;
ALTER TABLE gold.tspr_loss_records
    MODIFY COLUMN claim_id_tspr  SET MASKING POLICY tspr_security.mask_pii;

ALTER TABLE gold.tspr_cancellation_records
    MODIFY COLUMN zip5           SET MASKING POLICY tspr_security.mask_pii;

-- ---------------------------------------------------------------------------
-- Step 12: Row Access Policy (NAIC company filter on Gold layer)
-- Restricts each user to only the NAIC company codes they are authorised for.
-- Authorised codes stored in a mapping table; compliance_admin sees all.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS tspr_security.naic_user_access (
    snowflake_user  VARCHAR     NOT NULL    COMMENT 'Snowflake LOGIN_NAME or email',
    naic_company_no VARCHAR(5)  NOT NULL    COMMENT '5-digit NAIC code this user may access',
    granted_by      VARCHAR     NOT NULL,
    granted_at      TIMESTAMP_NTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP()
)
COMMENT = 'NAIC company code access control list. tspr_compliance_admin bypasses this table.';

CREATE OR REPLACE ROW ACCESS POLICY tspr_security.naic_row_filter
    AS (naic_company_no VARCHAR)
    RETURNS BOOLEAN ->
        CURRENT_ROLE() = 'TSPR_COMPLIANCE_ADMIN'
        OR EXISTS (
            SELECT 1
            FROM tspr_security.naic_user_access
            WHERE snowflake_user   = CURRENT_USER()
              AND naic_company_no  = naic_company_no
        )
COMMENT = 'Row access policy: restricts Gold table rows to authorised NAIC company codes per user. tspr_compliance_admin sees all rows.';

-- Apply row access policy to all Gold record tables
ALTER TABLE gold.tspr_premium_records
    ADD ROW ACCESS POLICY tspr_security.naic_row_filter ON (naic_company_no);
ALTER TABLE gold.tspr_loss_records
    ADD ROW ACCESS POLICY tspr_security.naic_row_filter ON (naic_company_no);
ALTER TABLE gold.tspr_cancellation_records
    ADD ROW ACCESS POLICY tspr_security.naic_row_filter ON (naic_company_no);
ALTER TABLE gold.tspr_monthly_aggregates
    ADD ROW ACCESS POLICY tspr_security.naic_row_filter ON (naic_company_no);

-- ---------------------------------------------------------------------------
-- Step 13: Streams (change tracking for Silver + Gold transformation tasks)
-- ---------------------------------------------------------------------------

USE SCHEMA insurance_regulatory.bronze;

-- Streams on Bronze tables: capture new CDC rows for Silver transformation
CREATE STREAM IF NOT EXISTS bronze.stream_gw_pc_policyperiod
    ON TABLE bronze.gw_pc_policyperiod
    APPEND_ONLY = TRUE
    COMMENT = 'Captures new policyperiod CDC events for Silver transformation task.';

CREATE STREAM IF NOT EXISTS bronze.stream_gw_pc_hopolicyline
    ON TABLE bronze.gw_pc_hopolicyline
    APPEND_ONLY = TRUE
    COMMENT = 'Captures new policy line CDC events for Silver transformation task.';

CREATE STREAM IF NOT EXISTS bronze.stream_gw_pc_hocoverage
    ON TABLE bronze.gw_pc_hocoverage
    APPEND_ONLY = TRUE
    COMMENT = 'Captures new coverage CDC events for Silver transformation task.';

CREATE STREAM IF NOT EXISTS bronze.stream_gw_pc_hodwelling
    ON TABLE bronze.gw_pc_hodwelling
    APPEND_ONLY = TRUE
    COMMENT = 'Captures new dwelling CDC events for Silver transformation task.';

CREATE STREAM IF NOT EXISTS bronze.stream_gw_cc_claim
    ON TABLE bronze.gw_cc_claim
    APPEND_ONLY = TRUE
    COMMENT = 'Captures new claim CDC events for Silver transformation task and status history derivation.';

CREATE STREAM IF NOT EXISTS bronze.stream_gw_cc_transaction
    ON TABLE bronze.gw_cc_transaction
    APPEND_ONLY = TRUE
    COMMENT = 'Captures new transaction rows for Silver claim state machine task.';

-- Stream on Silver tables: capture validated Silver rows for Gold assembly
USE SCHEMA insurance_regulatory.silver;

CREATE STREAM IF NOT EXISTS silver.stream_tspr_premium_staging
    ON TABLE silver.tspr_premium_staging
    APPEND_ONLY = TRUE
    COMMENT = 'Captures new/updated premium staging rows for Gold assembly task.';

CREATE STREAM IF NOT EXISTS silver.stream_tspr_loss_staging
    ON TABLE silver.tspr_loss_staging
    APPEND_ONLY = TRUE
    COMMENT = 'Captures new loss staging rows for Gold assembly task.';

CREATE STREAM IF NOT EXISTS silver.stream_tspr_cancellation_staging
    ON TABLE silver.tspr_cancellation_staging
    APPEND_ONLY = TRUE
    COMMENT = 'Captures new cancellation staging rows for Gold assembly task.';

-- ---------------------------------------------------------------------------
-- Step 14: Tasks (Silver transformation + Gold assembly scheduling)
-- ---------------------------------------------------------------------------

USE SCHEMA insurance_regulatory.silver;

-- Root task: triggers on Bronze stream activity (check every 5 minutes)
-- This is the Snowflake equivalent of the Databricks Auto Loader streaming trigger
CREATE TASK IF NOT EXISTS silver.task_silver_premium_transform
    WAREHOUSE  = tspr_transform_wh
    SCHEDULE   = '5 MINUTES'
    WHEN       SYSTEM$STREAM_HAS_DATA('insurance_regulatory.bronze.stream_gw_pc_policyperiod')
    COMMENT    = 'Transforms Bronze PolicyCenter CDC into Silver tspr_premium_staging. Equivalent to Databricks Silver DLT pipeline.'
AS
CALL insurance_regulatory.silver.sp_transform_premium();
-- sp_transform_premium is defined in 03_silver_procedures.sql

CREATE TASK IF NOT EXISTS silver.task_silver_claim_state
    WAREHOUSE  = tspr_transform_wh
    SCHEDULE   = '5 MINUTES'
    WHEN       SYSTEM$STREAM_HAS_DATA('insurance_regulatory.bronze.stream_gw_cc_claim')
               OR SYSTEM$STREAM_HAS_DATA('insurance_regulatory.bronze.stream_gw_cc_transaction')
    COMMENT    = 'Runs Rules 13-15-16 claim state machine and updates tspr_claim_state SCD.'
AS
CALL insurance_regulatory.silver.sp_transform_claim_state();

-- Monthly Gold assembly task (day 1 of each month at 06:00 UTC)
USE SCHEMA insurance_regulatory.gold;

CREATE TASK IF NOT EXISTS gold.task_gold_assembly_monthly
    WAREHOUSE  = tspr_transform_wh
    SCHEDULE   = 'USING CRON 0 6 1 * * UTC'
    COMMENT    = 'Monthly TSPR Gold assembly: Section C, D, E/G records + transmittal. Due to TICO by day 45.'
AS
CALL insurance_regulatory.gold.sp_gold_assembly(
    TO_VARCHAR(DATEADD(MONTH, -1, DATE_TRUNC('MONTH', CURRENT_DATE())), 'YYYY-MM'),
    NULL,    -- naic_codes: NULL = all companies
    FALSE    -- dry_run: FALSE for production
);

-- Resume tasks (tasks start SUSPENDED by default)
ALTER TASK silver.task_silver_premium_transform RESUME;
ALTER TASK silver.task_silver_claim_state       RESUME;
-- Gold monthly task: resume only after Silver validation completes in production
-- ALTER TASK gold.task_gold_assembly_monthly   RESUME;

-- ---------------------------------------------------------------------------
-- Completion summary
-- ---------------------------------------------------------------------------
SELECT
    'insurance_regulatory' AS database_name,
    s.schema_name,
    COUNT(t.table_name) AS table_count
FROM information_schema.schemata s
LEFT JOIN information_schema.tables t
    ON t.table_schema = s.schema_name
   AND t.table_catalog = 'INSURANCE_REGULATORY'
WHERE s.catalog_name = 'INSURANCE_REGULATORY'
  AND s.schema_name IN ('BRONZE','SILVER','GOLD','REFERENCE','TSPR_SECURITY','STAGING')
GROUP BY s.schema_name
ORDER BY s.schema_name;
