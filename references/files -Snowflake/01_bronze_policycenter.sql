-- =============================================================================
-- SNOWFLAKE DDL: BRONZE LAYER — Guidewire PolicyCenter Raw Ingestion Tables
-- =============================================================================
-- Translated from Databricks Delta Lake DDL.
-- Key Snowflake translations applied:
--   STRING           -> VARCHAR
--   BOOLEAN          -> BOOLEAN  (native in Snowflake)
--   GENERATED ALWAYS AS (expr) -> omitted (Snowflake virtual cols are views-only;
--                                  _partition_month populated by ingestion pipeline)
--   USING DELTA      -> removed (Snowflake is always columnar)
--   TBLPROPERTIES    -> converted to COMMENT on table + TAG assignments
--   DEFAULT current_timestamp() -> DEFAULT CURRENT_TIMESTAMP()
--   PARTITIONED BY   -> CLUSTER BY (Snowflake micro-partitioning is automatic;
--                       explicit CLUSTER BY improves pruning on large tables)
--   ARRAY<STRING>    -> VARIANT  (Snowflake semi-structured)
-- PII columns tagged with object-level Snowflake TAG for masking policies.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Setup: database, schemas, and shared tags
-- ---------------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS insurance_regulatory
    COMMENT = 'TSPR Statistical Reporting Platform — Texas Residential Property';

CREATE SCHEMA IF NOT EXISTS insurance_regulatory.bronze
    COMMENT = 'Bronze: Raw CDC events from Guidewire PolicyCenter and ClaimCenter. Append-only. No transformations.';

USE DATABASE insurance_regulatory;
USE SCHEMA bronze;

-- Shared object tags (applied per column where relevant)
CREATE TAG IF NOT EXISTS insurance_regulatory.bronze.tspr_pii
    COMMENT = 'Marks PII columns requiring masking policy under Unity Catalog / Snowflake Dynamic Data Masking';

CREATE TAG IF NOT EXISTS insurance_regulatory.bronze.source_system
    ALLOWED_VALUES 'Guidewire PolicyCenter', 'Guidewire ClaimCenter', 'Guidewire BillingCenter'
    COMMENT = 'Source system that originated the data';

CREATE TAG IF NOT EXISTS insurance_regulatory.bronze.tspr_relevance
    COMMENT = 'TSPR field mapping relevance note';

-- ---------------------------------------------------------------------------
-- 1. Policy Period  (GW: pc_policyperiod)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.gw_pc_policyperiod (

    -- CDC envelope
    gwcbi___operation          VARCHAR(10)     NOT NULL    COMMENT 'CDC operation: INSERT, UPDATE, DELETE',
    gwcdac___timestampfolder          VARCHAR(64)    NOT NULL    COMMENT 'Timestamp of CDC event from GW Data Platform',
    gwcdac___fingerprintfolder VARCHAR(64)                COMMENT 'CDA fingerprint folder id (Guidewire diagnostic)',
    gwcbi___sourcedb          VARCHAR(64)                 COMMENT 'Source database name from GW (e.g. gwpc)',
    gwcbi___seqval_hex           VARCHAR(40)                   COMMENT 'CDC sequence number for ordering within a microsecond',
    _ingestion_timestamp    TIMESTAMP_NTZ   NOT NULL
                                DEFAULT CURRENT_TIMESTAMP()
                                                        COMMENT 'Auto Loader / Snowpipe ingestion timestamp',
    _source_file            VARCHAR(512)                COMMENT 'Source file path (S3/ADLS/GCS)',
    _partition_month        VARCHAR(7)                  COMMENT 'YYYY-MM derived from periodstart — set by ingestion pipeline',

    -- GW internal keys
    id                      NUMBER(19,0)    NOT NULL    COMMENT 'GW internal policyperiod ID (primary key)',
    publicid                VARCHAR(100)                COMMENT 'GW public GUID e.g. pc:PolicyPeriod:1234',
    policy_id               NUMBER(19,0)                COMMENT 'FK -> pc_policy.id',
    account_id              NUMBER(19,0)                COMMENT 'FK -> pc_account.id',
    producercode_id         NUMBER(19,0)                COMMENT 'FK -> pc_producercode.id',
    policycontact_id        NUMBER(19,0)                COMMENT 'FK -> pc_policycontact.id (named insured)',
    uwcompany_id            NUMBER(19,0)                COMMENT 'FK -> pc_uwcompany.id',
    policyterm_id           NUMBER(19,0)                COMMENT 'FK -> pc_policyterm.id',

    -- Period dates
    periodstart             TIMESTAMP_NTZ               COMMENT 'Policy period effective date/time',
    periodend               TIMESTAMP_NTZ               COMMENT 'Policy period expiry date/time',
    editeffectivedate       TIMESTAMP_NTZ               COMMENT 'Date from which this period version is effective',
    modelnumber             NUMBER(10,0)                COMMENT 'GW model number - increments on each bind',
    modeldate               TIMESTAMP_NTZ               COMMENT 'Date/time of last model recalculation',

    -- Status and type
    status                  VARCHAR(50)                 COMMENT 'GW period status: Quoted, Bound, Canceled, Expired, NonRenewed',
    jobtype                 VARCHAR(50)                 COMMENT 'GW job type: Submission, Renewal, PolicyChange, Cancellation, Reinstatement',
    policytype              VARCHAR(50)                 COMMENT 'GW policy type: PersonalAuto, Homeowners, Dwelling etc.',
    basestate               VARCHAR(2)                  COMMENT 'Base state code (TX for Texas)',
    branchname              VARCHAR(100)                COMMENT 'GW branch name',

    -- Term details
    termtype                VARCHAR(30)                 COMMENT 'Annual, SixMonth, Monthly, FuturePolicyTerm',
    termnum                 NUMBER(10,0)                COMMENT 'Policy term number (1=first term, 2=first renewal, etc.)',
    cancellationdate        TIMESTAMP_NTZ               COMMENT 'If canceled: date coverage ended',
    cancellationsource      VARCHAR(50)                 COMMENT 'Insured, Carrier, NonPayment, Underwriting',
    cancellationreason      VARCHAR(100)                COMMENT 'GW cancellation reason code',
    nonrenewalcode          VARCHAR(100)                COMMENT 'GW nonrenewal reason code',
    writtendate             TIMESTAMP_NTZ               COMMENT 'Date policy was bound/written',

    -- Premium summary
    totalpremium            NUMBER(15,2)                COMMENT 'Total written premium for this period version',
    writtenpremium          NUMBER(15,2)                COMMENT 'Written premium amount',
    totalcost               NUMBER(15,2)                COMMENT 'Total cost including fees and taxes',
    fulltermamount          NUMBER(15,2)                COMMENT 'Full term premium amount',
    earnedpremium           NUMBER(15,2)                COMMENT 'Earned premium as of period end',

    -- UW company identifiers
    uwcompanycode           VARCHAR(20)                 COMMENT 'GW UW company code',
    naic_number             VARCHAR(5)                  COMMENT 'NAIC company number (5 digits) - maps to TSPR NAIC field cols 146-150',
    tico_company_number     VARCHAR(3)                  COMMENT 'TICO-assigned company number - maps to TSPR CNO field cols 43-45',

    -- Audit
    createtime              TIMESTAMP_NTZ               COMMENT 'GW row creation timestamp',
    updatetime              TIMESTAMP_NTZ               COMMENT 'GW row last update timestamp',
    retiredvalue            NUMBER(10,0)                COMMENT 'GW retired flag (0=active, 1=retired/soft-deleted)'
)
CLUSTER BY (_partition_month, naic_number)
COMMENT = 'Bronze: Raw CDC from Guidewire PolicyCenter pc_policyperiod. One row per policy period CDC event. Append-only. TSPR Sections A C D.';

-- ---------------------------------------------------------------------------
-- 2. Policy  (GW: pc_policy)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.gw_pc_policy (
    gwcbi___operation          VARCHAR(10)     NOT NULL,
    gwcdac___timestampfolder          VARCHAR(64)    NOT NULL,
    gwcdac___fingerprintfolder VARCHAR(64)                COMMENT 'CDA fingerprint folder id (Guidewire diagnostic)',
    gwcbi___seqval_hex           VARCHAR(40)   ,
    _ingestion_timestamp    TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _source_file            VARCHAR(512),

    id                      NUMBER(19,0)    NOT NULL    COMMENT 'GW policy ID',
    publicid                VARCHAR(100)                COMMENT 'GW public GUID',
    account_id              NUMBER(19,0)                COMMENT 'FK -> pc_account.id',
    producercode_id         NUMBER(19,0),
    policynumber            VARCHAR(30)                 COMMENT 'Human-readable policy number - maps to TSPR POLICY field (cols 7-16)',
    issuedate               TIMESTAMP_NTZ               COMMENT 'Date policy was first issued',
    originalinceptiondate   TIMESTAMP_NTZ               COMMENT 'Original inception (not renewal) date',

    createtime              TIMESTAMP_NTZ,
    updatetime              TIMESTAMP_NTZ,
    retiredvalue            NUMBER(10,0)
)
COMMENT = 'Bronze: Raw CDC from Guidewire PolicyCenter pc_policy. Master policy record. TSPR POLICY field cols 7-16 Rule26.';

-- ---------------------------------------------------------------------------
-- 3. HO Policy Line  (GW: pc_hopolicyline)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.gw_pc_hopolicyline (
    gwcbi___operation          VARCHAR(10)     NOT NULL,
    gwcdac___timestampfolder          VARCHAR(64)    NOT NULL,
    gwcdac___fingerprintfolder VARCHAR(64)                COMMENT 'CDA fingerprint folder id (Guidewire diagnostic)',
    gwcbi___seqval_hex           VARCHAR(40)   ,
    _ingestion_timestamp    TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _source_file            VARCHAR(512),

    id                      NUMBER(19,0)    NOT NULL    COMMENT 'GW policyline ID',
    publicid                VARCHAR(100),
    branchid                NUMBER(19,0)                COMMENT 'FK -> pc_policyperiod.id',
    policy_id               NUMBER(19,0)                COMMENT 'FK -> pc_policy.id',

    -- Line identifiers
    policylinepatterncodeidentifier VARCHAR(50)         COMMENT 'GW LOB code: HOPLine, DwellingLine, TWIAWindLine etc.',
    linecategory            VARCHAR(20)                 COMMENT 'Personal, Commercial',
    effectivedate           TIMESTAMP_NTZ,
    expirationdate          TIMESTAMP_NTZ,

    -- TSPR-relevant fields
    holineform              VARCHAR(20)                 COMMENT 'GW form code: HO_A, HO_B, HO_C, HO_A_Plus etc. Maps to TSPR FM field col 50',
    numberofunits           NUMBER(10,0)                COMMENT 'Number of dwelling units. Maps to TSPR FAM field col 51',
    occupancytype           VARCHAR(30)                 COMMENT 'OwnerOccupied, NonOwnerOccupied, Vacant etc. Maps to TSPR COV col 52',

    -- Roof (TSPR 2026 fields)
    roofcoveringtype        VARCHAR(30)                 COMMENT 'Maps to TSPR ROOFCOV col 83: CompShingle, Wood, Tile, Slate etc.',
    roofcoveringcreditclass NUMBER(10,0)                COMMENT 'Maps to TSPR ROOFCRED col 84: 0-4 UL2218 class',
    roofinstallationyear    NUMBER(4,0)                 COMMENT 'Maps to TSPR ROOFYEAR cols 85-88 (YYYY)',
    cosmeticdamageexclusion BOOLEAN                     COMMENT 'Maps to TSPR COSMETIC col 89: endorsement attached Y/N',

    -- Roof coverage type (RC vs ACV)
    roofcoveragetype        VARCHAR(30)                 COMMENT 'ReplacementCost, ActualCashValue, ACV_WH_Only. Maps to TSPR RCT col 153',
    dwellingcoveragetype    VARCHAR(30)                 COMMENT 'ReplacementCost, ActualCashValue. Maps to TSPR RCB col 151',
    personalpropertycovtype VARCHAR(30)                 COMMENT 'ReplacementCost, ActualCashValue. Maps to TSPR RCPP col 152',

    -- Prior claims history
    priorclaimscount        NUMBER(10,0)                COMMENT 'Number of chargeable prior claims in 5 years. Maps to TSPR CLM col 173',
    priorclaimsused         BOOLEAN                     COMMENT 'Whether carrier uses prior claims in rating/tiering',

    -- Rating variables (Section B.20)
    rv_alarm                VARCHAR(20)                 COMMENT 'Used/Discount/Surcharge/TierOnly/NotUsed. Maps to TSPR RV1 col 174',
    rv_age_of_home          VARCHAR(20)                 COMMENT 'Maps to TSPR RV2 col 175',
    rv_sprinkler            VARCHAR(20)                 COMMENT 'Maps to TSPR RV3 col 176',
    rv_claims_experience    VARCHAR(20)                 COMMENT 'Maps to TSPR RV4 col 177',
    rv_companion_policy     VARCHAR(20)                 COMMENT 'Maps to TSPR RV5 col 178',
    rv_credit_score         VARCHAR(20)                 COMMENT 'Maps to TSPR RV6 col 179. PII.',
    rv_senior_citizen       VARCHAR(20)                 COMMENT 'Maps to TSPR RV7 col 180',
    rv_smart_home           VARCHAR(20)                 COMMENT 'Maps to TSPR RV8 col 181',
    rv_new_home             VARCHAR(20)                 COMMENT 'Maps to TSPR RV9 col 182',
    rv_additional_surcharges VARCHAR(20)                COMMENT 'Maps to TSPR RV10 col 183',

    -- Tenure
    tenurewithinsurer       NUMBER(10,0)                COMMENT 'Years insured with this carrier. Maps to TSPR TENURE col 140',
    tenurediscountpct       NUMBER(5,2)                 COMMENT 'Tenure discount percentage. Maps to TSPR TENUREDISCT cols 141-142',
    tenureusedforrating     BOOLEAN                     COMMENT 'Carrier uses tenure in rating. Determines TENURE code 0 vs 1-7.',
    tenureusedfortiering    BOOLEAN                     COMMENT 'Tenure used for tiering only (report as TENUREDISCT 00)',

    -- Flood
    privatefloodcoverage    BOOLEAN                     COMMENT 'Policy includes private flood coverage. Maps to TSPR FLOOD col 154',

    -- Law and ordinance
    lawordcompct            VARCHAR(5)                  COMMENT '0/10/15/25/Other. Maps to TSPR LOC col 136',

    createtime              TIMESTAMP_NTZ,
    updatetime              TIMESTAMP_NTZ,
    retiredvalue            NUMBER(10,0),
    _partition_month        VARCHAR(7)                  COMMENT 'YYYY-MM from effectivedate — set by ingestion pipeline'
)
CLUSTER BY (_partition_month)
COMMENT = 'Bronze: Raw CDC from Guidewire PolicyCenter pc_hopolicyline. HO line-of-business data. TSPR FM FAM COV ROOFCOV-COSMETIC RCB RCPP RCT FLOOD LOC RV1-RV10 TENURE.';

-- PII tag on credit score field
ALTER TABLE bronze.gw_pc_hopolicyline
    MODIFY COLUMN rv_credit_score SET TAG insurance_regulatory.bronze.tspr_pii = 'true';

-- ---------------------------------------------------------------------------
-- 4. HO Coverage  (GW: pc_hocoverage)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.gw_pc_hocoverage (
    gwcbi___operation          VARCHAR(10)     NOT NULL,
    gwcdac___timestampfolder          VARCHAR(64)    NOT NULL,
    gwcdac___fingerprintfolder VARCHAR(64)                COMMENT 'CDA fingerprint folder id (Guidewire diagnostic)',
    gwcbi___seqval_hex           VARCHAR(40)   ,
    _ingestion_timestamp    TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _source_file            VARCHAR(512),

    id                      NUMBER(19,0)    NOT NULL    COMMENT 'GW coverage ID',
    publicid                VARCHAR(100),
    branchid                NUMBER(19,0)                COMMENT 'FK -> pc_policyperiod.id',
    fixedid                 NUMBER(19,0)                COMMENT 'Fixed ID - stable across versions',
    policyline_id           NUMBER(19,0)                COMMENT 'FK -> pc_hopolicyline.id',

    -- Coverage identification
    coveragepatterncode     VARCHAR(50)                 COMMENT 'GW coverage pattern: HOPA_DwCov, HOPA_PPCov, HOPA_ALECov etc.',
    coveragecategory        VARCHAR(30)                 COMMENT 'Building, PersonalProperty, LossOfUse, Liability, MedPay',
    coveragetype            VARCHAR(50)                 COMMENT 'DwellingCoverage, PersonalPropertyCoverage, LossOfUse etc.',

    -- Limits
    coverageamount          NUMBER(15,2)                COMMENT 'Coverage A limit (dwelling). Maps to TSPR INS cols 33-37 in $1000s',
    personalpropertylimit   NUMBER(15,2)                COMMENT 'Coverage B limit. Maps to TSPR HOPP cols 169-172 in $1000s',
    lossofuselimit          NUMBER(15,2)                COMMENT 'Coverage C limit. Maps to TSPR ALE cols 166-168 in $1000s',
    lossofusepct            NUMBER(5,2)                 COMMENT 'Loss of Use as % of Cov A (if applicable). Must convert to $ per Rule 6.',

    -- Deductibles
    deductibletype          VARCHAR(30)                 COMMENT 'PercentageOfDwelling, FixedDollar, FullCoverage, NoWindCoverage',
    allperilsdeductible     NUMBER(15,2)                COMMENT 'AOP deductible amount. Maps to TSPR DED2 (Other than W&H) col 58',
    windhailddeductible     NUMBER(15,2)                COMMENT 'Wind/hail deductible amount. Maps to TSPR DED1 col 57',
    windhailddeductiblepct  NUMBER(5,2)                 COMMENT 'Wind/hail deductible as % (if applicable). Maps to TSPR DED1',
    tropicalcyclonedeductible NUMBER(15,2)              COMMENT 'TC deductible amount. Maps to TSPR TCDEDAMT cols 156-161',
    tropicalcyclonedeductibletype VARCHAR(30)           COMMENT 'Maps to TSPR TCDED col 155',
    windexcluded            BOOLEAN                     COMMENT 'Wind coverage excluded. Maps to TSPR WIND col 128; DED1 code 7',

    -- Optional endorsements
    optionalcovcode         VARCHAR(20)                 COMMENT 'Endorsement code (HO161 etc.). Maps to TSPR cols 101-108',
    optionalcovamount       NUMBER(15,2)                COMMENT 'Endorsement coverage amount. Maps to TSPR cols 109-114',

    -- Premium components
    writtenpremium          NUMBER(15,2)                COMMENT 'Written premium for this coverage',
    ecpremium               NUMBER(15,2)                COMMENT 'Extended coverage premium component. Maps to TSPR EPRM cols 67-70',

    effectivedate           TIMESTAMP_NTZ,
    expirationdate          TIMESTAMP_NTZ,
    createtime              TIMESTAMP_NTZ,
    updatetime              TIMESTAMP_NTZ,
    retiredvalue            NUMBER(10,0),
    _partition_month        VARCHAR(7)                  COMMENT 'YYYY-MM from effectivedate — set by ingestion pipeline'
)
CLUSTER BY (_partition_month)
COMMENT = 'Bronze: Raw CDC from Guidewire PolicyCenter pc_hocoverage. Coverage limits and deductibles. TSPR INS HOPP ALE DED1 DED2 TCDED WIND EPRM FRPM Rule6.';

-- ---------------------------------------------------------------------------
-- 5. HO Dwelling  (GW: pc_hodwelling)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.gw_pc_hodwelling (
    gwcbi___operation          VARCHAR(10)     NOT NULL,
    gwcdac___timestampfolder          VARCHAR(64)    NOT NULL,
    gwcdac___fingerprintfolder VARCHAR(64)                COMMENT 'CDA fingerprint folder id (Guidewire diagnostic)',
    gwcbi___seqval_hex           VARCHAR(40)   ,
    _ingestion_timestamp    TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _source_file            VARCHAR(512),

    id                      NUMBER(19,0)    NOT NULL,
    publicid                VARCHAR(100),
    branchid                NUMBER(19,0)                COMMENT 'FK -> pc_policyperiod.id',
    policyline_id           NUMBER(19,0),
    policyaddress_id        NUMBER(19,0)                COMMENT 'FK -> pc_address.id',

    -- Location
    territory               VARCHAR(5)                  COMMENT 'TDI rating territory (1-11 for Texas). Used for deductible code 7 check.',
    countyfips              VARCHAR(5)                  COMMENT '5-digit county FIPS code',
    placecodetdi            VARCHAR(10)                 COMMENT 'TDI place code (county-community). Maps to TSPR PLACE cols 26-30 Rule18',
    zip                     VARCHAR(5)                  COMMENT '5-digit ZIP. Maps to TSPR ZIP cols 91-95',
    ziplus4                 VARCHAR(4)                  COMMENT 'ZIP+4 extension. Maps to TSPR ZIP cols 96-99',
    state                   VARCHAR(2)                  COMMENT 'State code. Must be TX for TSPR.',

    -- Construction
    constructiontype        VARCHAR(30)                 COMMENT 'Frame, BrickVeneer, BrickStoneMasonry, FireResistive, MobileManufactured, StuccoAsbestos. Maps to TSPR CT col 53',
    yearbuilt               NUMBER(4,0)                 COMMENT 'Year dwelling constructed. Maps to TSPR YOC cols 162-165 (YYYY)',
    numberoffamilies        NUMBER(10,0)                COMMENT 'Number of family units. Maps to TSPR FAM col 51',

    -- Protection
    ppccode                 VARCHAR(5)                  COMMENT 'ISO Public Protection Class used in rating. Maps to TSPR PPC col 56 and SPPC cols 54-55',
    ppccodesplit            VARCHAR(5)                  COMMENT 'Split PPC code (e.g. 5W, 8X). Maps to TSPR SPPC cols 54-55 SectionB9A',

    -- Building code
    buildingcodecredit      VARCHAR(5)                  COMMENT 'TWIA building code credit code. Maps to TSPR BCC cols 134-135',

    -- Wind / coastal
    intwiazone              BOOLEAN                     COMMENT 'Risk is in TWIA eligible coastal zone',
    coastalterritory        BOOLEAN                     COMMENT 'Risk is in seacoast territory (1,8,9,10,11) - affects deductible code 1',

    createtime              TIMESTAMP_NTZ,
    updatetime              TIMESTAMP_NTZ,
    retiredvalue            NUMBER(10,0)
)
COMMENT = 'Bronze: Raw CDC from Guidewire PolicyCenter pc_hodwelling. Physical property characteristics. TSPR PLACE ZIP CT YOC PPC SPPC BCC WIND territory Rule18 SectionB8 SectionB9.';

-- PII tags on ZIP fields
ALTER TABLE bronze.gw_pc_hodwelling MODIFY COLUMN zip     SET TAG insurance_regulatory.bronze.tspr_pii = 'true';
ALTER TABLE bronze.gw_pc_hodwelling MODIFY COLUMN ziplus4 SET TAG insurance_regulatory.bronze.tspr_pii = 'true';

-- ---------------------------------------------------------------------------
-- 6. Policy Job  (GW: pc_job)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.gw_pc_job (
    gwcbi___operation          VARCHAR(10)     NOT NULL,
    gwcdac___timestampfolder          VARCHAR(64)    NOT NULL,
    gwcdac___fingerprintfolder VARCHAR(64)                COMMENT 'CDA fingerprint folder id (Guidewire diagnostic)',
    gwcbi___seqval_hex           VARCHAR(40)   ,
    _ingestion_timestamp    TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _source_file            VARCHAR(512),

    id                      NUMBER(19,0)    NOT NULL    COMMENT 'GW job ID',
    publicid                VARCHAR(100),
    policy_id               NUMBER(19,0)                COMMENT 'FK -> pc_policy.id',
    basedon_id              NUMBER(19,0)                COMMENT 'FK -> pc_policyperiod.id the job is based on',

    subtype                 VARCHAR(50)                 COMMENT 'Submission, Renewal, PolicyChange, Cancellation, Reinstatement, NonRenewal',
    jobnumber               VARCHAR(50)                 COMMENT 'Human-readable job number',
    status                  VARCHAR(20)                 COMMENT 'Draft, Quoted, Bound, Withdrawn, Declined',

    createtime              TIMESTAMP_NTZ               COMMENT 'Job created date',
    closedate               TIMESTAMP_NTZ               COMMENT 'Date job was closed/bound',
    effectivedate           TIMESTAMP_NTZ               COMMENT 'Job effective date - maps to TSPR EFF field (cols 18-22)',

    cancellationdate        TIMESTAMP_NTZ               COMMENT 'Date cancellation takes effect. EXP date for TSPR',
    cancellationreason      VARCHAR(100)                COMMENT 'GW internal cancellation reason',
    cancellationsource      VARCHAR(50)                 COMMENT 'Insured, Carrier, NonPayment',
    nonrenewalreason        VARCHAR(100)                COMMENT 'GW internal nonrenewal reason - maps to TSPR reason codes Sec E/F',
    declinereason           VARCHAR(100)                COMMENT 'GW internal declination reason - maps to TSPR reason codes Sec E/F',
    within60days            BOOLEAN                     COMMENT 'Cancellation within first 60 days. Maps to TSPR 60D col 18 Sec E',

    noticedate              TIMESTAMP_NTZ               COMMENT 'Date notice was sent. Maps to TSPR NDT cols 2-4 Sec E',
    noticesource            VARCHAR(50)                 COMMENT 'Whether aerial imagery or 3P data used. Maps to TSPR RSI col 17',
    aerialimageused         BOOLEAN                     COMMENT 'Aerial imagery used in decision. Component of RSI.',
    thirdpartydataused      BOOLEAN                     COMMENT 'Third-party data used in decision. Component of RSI.',

    twiadepopulation        BOOLEAN                     COMMENT 'Job is TWIA depopulation assumption reinsurance. Maps to RT 07/08 Rule31',

    retiredvalue            NUMBER(10,0),
    updatetime              TIMESTAMP_NTZ
)
COMMENT = 'Bronze: Raw CDC from Guidewire PolicyCenter pc_job. All policy transactions - endorsements, cancellations, renewals. TSPR RT EFF AT NDT RSI 60D reason codes Sec E F Rule9 Rule10 Rule34.';

-- ---------------------------------------------------------------------------
-- 7. UW Company  (GW: pc_uwcompany)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.gw_pc_uwcompany (
    gwcbi___operation          VARCHAR(10)     NOT NULL,
    gwcdac___timestampfolder          VARCHAR(64)    NOT NULL,
    gwcdac___fingerprintfolder VARCHAR(64)                COMMENT 'CDA fingerprint folder id (Guidewire diagnostic)',
    gwcbi___seqval_hex           VARCHAR(40)   ,
    _ingestion_timestamp    TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _source_file            VARCHAR(512),

    id                      NUMBER(19,0)    NOT NULL,
    publicid                VARCHAR(100),
    code                    VARCHAR(20)                 COMMENT 'GW UW company code',
    name                    VARCHAR(200)                COMMENT 'Legal company name',
    naiccode                VARCHAR(5)                  COMMENT '5-digit NAIC number. Maps to TSPR NAIC cols 146-150 Rule25',
    ticocompanynumber       VARCHAR(3)                  COMMENT 'TICO-assigned 3-char company code. Maps to TSPR CNO cols 43-45 Rule22',
    state                   VARCHAR(2)                  COMMENT 'State of domicile',
    farmmutualidicator      BOOLEAN                     COMMENT 'Farm mutual - excluded from TSPR premium/loss reporting per Rule21',
    createtime              TIMESTAMP_NTZ,
    updatetime              TIMESTAMP_NTZ,
    retiredvalue            NUMBER(10,0)
)
COMMENT = 'Bronze: Guidewire PolicyCenter pc_uwcompany. NAIC and TICO company identifiers. TSPR NAIC CNO cols 43-45 146-150 Rule22 Rule25.';

-- ---------------------------------------------------------------------------
-- 8. Address  (GW: pc_address)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.gw_pc_address (
    gwcbi___operation          VARCHAR(10)     NOT NULL,
    gwcdac___timestampfolder          VARCHAR(64)    NOT NULL,
    gwcdac___fingerprintfolder VARCHAR(64)                COMMENT 'CDA fingerprint folder id (Guidewire diagnostic)',
    gwcbi___seqval_hex           VARCHAR(40)   ,
    _ingestion_timestamp    TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _source_file            VARCHAR(512),

    id                      NUMBER(19,0)    NOT NULL,
    publicid                VARCHAR(100),
    addressline1            VARCHAR(200),
    city                    VARCHAR(100),
    county                  VARCHAR(100)                COMMENT 'Texas county name',
    state                   VARCHAR(2),
    postalcode              VARCHAR(5)                  COMMENT '5-digit ZIP',
    postalcodeplus4         VARCHAR(4)                  COMMENT '+4 extension',
    fipscodefull            VARCHAR(15)                 COMMENT 'Full 10-digit FIPS code',
    countyfipscode          VARCHAR(5)                  COMMENT '5-digit county FIPS',
    createtime              TIMESTAMP_NTZ,
    updatetime              TIMESTAMP_NTZ,
    retiredvalue            NUMBER(10,0)
)
COMMENT = 'Bronze: Guidewire PolicyCenter pc_address. ZIP code and location data. TSPR ZIP cols 91-99 Rule24.';

-- PII tags on ZIP
ALTER TABLE bronze.gw_pc_address MODIFY COLUMN postalcode    SET TAG insurance_regulatory.bronze.tspr_pii = 'true';
ALTER TABLE bronze.gw_pc_address MODIFY COLUMN postalcodeplus4 SET TAG insurance_regulatory.bronze.tspr_pii = 'true';

-- ---------------------------------------------------------------------------
-- 9. Billing Premium  (GW: bc_policyperiodpremium — BillingCenter)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.gw_bc_policyperiodpremium (
    gwcbi___operation          VARCHAR(10)     NOT NULL,
    gwcdac___timestampfolder          VARCHAR(64)    NOT NULL,
    gwcdac___fingerprintfolder VARCHAR(64)                COMMENT 'CDA fingerprint folder id (Guidewire diagnostic)',
    gwcbi___seqval_hex           VARCHAR(40)   ,
    _ingestion_timestamp    TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _source_file            VARCHAR(512),

    id                      NUMBER(19,0)    NOT NULL,
    publicid                VARCHAR(100),
    policyperiod_id         NUMBER(19,0)                COMMENT 'FK -> pc_policyperiod.id',
    policy_id               NUMBER(19,0),

    -- Premium amounts
    writtenpremium          NUMBER(15,2)                COMMENT 'Written premium amount',
    earnedpremium           NUMBER(15,2),
    unearnedpremium         NUMBER(15,2),

    -- Tenure tracking
    tenureyears             NUMBER(10,0)                COMMENT 'Years continuously insured with carrier. Maps to TSPR TENURE col 140',
    tenurediscountpct       NUMBER(5,2)                 COMMENT 'Applied tenure discount %. Maps to TSPR TENUREDISCT cols 141-142',
    tenureusedforrating     BOOLEAN                     COMMENT 'Carrier uses tenure in rating. Determines TENURE code 0 vs 1-7.',
    tenureusedfortiering    BOOLEAN                     COMMENT 'Tenure used for tiering only (report as TENUREDISCT 00)',

    transactiontype         VARCHAR(30)                 COMMENT 'Written, Earned, Unearned, Cancellation',
    transactiondate         TIMESTAMP_NTZ,

    createtime              TIMESTAMP_NTZ,
    updatetime              TIMESTAMP_NTZ,
    retiredvalue            NUMBER(10,0),
    _partition_month        VARCHAR(7)                  COMMENT 'YYYY-MM from transactiondate — set by ingestion pipeline'
)
CLUSTER BY (_partition_month, policyperiod_id)
COMMENT = 'Bronze: Raw CDC from Guidewire BillingCenter. Premium transactions and tenure data. TSPR TENURE TENUREDISCT FRPM EPRM cols 59-63 67-70 140-142 Rule7 Rule30.';
