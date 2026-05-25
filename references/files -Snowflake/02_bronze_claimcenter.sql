-- =============================================================================
-- SNOWFLAKE DDL: BRONZE LAYER — Guidewire ClaimCenter Raw Ingestion Tables
-- =============================================================================
-- Every status change on cc_claim creates a separate CDC event row.
-- The append-only gw_cc_claim_status_history table is the direct input
-- for the Rules 13-15-16 claim count state machine in Silver.
-- =============================================================================

USE DATABASE insurance_regulatory;
USE SCHEMA bronze;

-- ---------------------------------------------------------------------------
-- 1. Claim  (GW: cc_claim)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.gw_cc_claim (
    -- CDC envelope
    gwcbi___operation          VARCHAR(10)     NOT NULL    COMMENT 'INSERT, UPDATE, DELETE',
    gwcdac___timestampfolder          VARCHAR(64)    NOT NULL    COMMENT 'GDP CDC event timestamp',
    gwcdac___fingerprintfolder VARCHAR(64)                COMMENT 'CDA fingerprint folder id (Guidewire diagnostic)',
    gwcbi___seqval_hex           VARCHAR(40)                   COMMENT 'Ordering sequence within microsecond',
    _ingestion_timestamp    TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _source_file            VARCHAR(512),
    _partition_month        VARCHAR(7)                  COMMENT 'YYYY-MM from lossdate — set by ingestion pipeline',

    -- GW internal keys
    id                      NUMBER(19,0)    NOT NULL    COMMENT 'GW claim ID (primary key)',
    publicid                VARCHAR(100)                COMMENT 'GW public GUID e.g. cc:Claim:9876',
    claimnumber             VARCHAR(30)                 COMMENT 'Human-readable claim number',

    -- Policy linkage
    policy_id               NUMBER(19,0)                COMMENT 'FK -> pc_policy.id',
    policynumber            VARCHAR(30)                 COMMENT 'Denormalized policy number for join efficiency',
    policyperiod_id         NUMBER(19,0)                COMMENT 'FK -> pc_policyperiod.id - the period the loss occurred under',
    uwcompany_id            NUMBER(19,0)                COMMENT 'FK -> pc_uwcompany.id',
    naic_number             VARCHAR(5)                  COMMENT 'Denormalized NAIC number for reporting partitioning',

    -- Claim occurrence
    lossdate                TIMESTAMP_NTZ   NOT NULL    COMMENT 'Date and time of loss. Maps to TSPR OCC cols 17-22 MMDDYY',
    losslocation_id         NUMBER(19,0)                COMMENT 'FK -> cc_address.id - location of loss',
    reporteddate            TIMESTAMP_NTZ               COMMENT 'Date claim was reported to carrier. Drives TSPR NCC Rule13: report in month carrier FIRST received claim',

    -- Loss classification
    losscause               VARCHAR(50)                 COMMENT 'GW loss cause code. Maps to TSPR COL cols 90-91 via silver mapping table. Must apply proximate cause rule (Rule11).',
    losscausesubtype        VARCHAR(50)                 COMMENT 'GW loss cause subcategory (e.g. WindstormHurricane, FreezeBurstPipe) for proximate cause resolution',
    lobtypecode             VARCHAR(30)                 COMMENT 'GW LOB type: HOPLine, DwellingLine etc.',
    coveragecategory        VARCHAR(30)                 COMMENT 'Property, Liability, MedPay - maps to TSPR TYPE col 59',

    -- Claim status
    state                   VARCHAR(20)                 COMMENT 'GW claim status: Open, Closed, Denied. Critical for TSPR claim status 1-6.',
    closedate               TIMESTAMP_NTZ               COMMENT 'Date claim was closed. NULL if open.',
    reopendate              TIMESTAMP_NTZ               COMMENT 'Date claim was most recently reopened.',

    -- Payment indicators
    hasindemnity            BOOLEAN                     COMMENT 'Claim has at least one indemnity payment. Determines CWIP vs CWOP.',
    totalincurred           NUMBER(15,2)                COMMENT 'Total incurred (paid + outstanding). NOT used for TSPR - use cc_transaction.',

    -- Subrogation / salvage
    subrogationamount       NUMBER(15,2)                COMMENT 'Subrogation recovered. Netted from TSPR LOSS per Rule11.',
    salvageamount           NUMBER(15,2)                COMMENT 'Salvage recovered. Netted from TSPR LOSS per Rule11.',

    -- TWIA
    isintwiazone            BOOLEAN                     COMMENT 'Risk is in TWIA coastal zone',

    createtime              TIMESTAMP_NTZ,
    updatetime              TIMESTAMP_NTZ,
    retiredvalue            NUMBER(10,0)
)
CLUSTER BY (_partition_month, naic_number)
COMMENT = 'Bronze: Raw CDC from Guidewire ClaimCenter cc_claim. Every status change preserved for Rules 13-16 state machine. TSPR OCC CS NCC COL TYPE cols 17-22 59 90-91 173 174 Rules 11 13 15 16.';

-- ---------------------------------------------------------------------------
-- 2. Exposure  (GW: cc_exposure)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.gw_cc_exposure (
    gwcbi___operation          VARCHAR(10)     NOT NULL,
    gwcdac___timestampfolder          VARCHAR(64)    NOT NULL,
    gwcdac___fingerprintfolder VARCHAR(64)                COMMENT 'CDA fingerprint folder id (Guidewire diagnostic)',
    gwcbi___seqval_hex           VARCHAR(40)   ,
    _ingestion_timestamp    TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _source_file            VARCHAR(512),
    _partition_month        VARCHAR(7)                  COMMENT 'YYYY-MM from createtime — set by ingestion pipeline',

    id                      NUMBER(19,0)    NOT NULL    COMMENT 'GW exposure ID',
    publicid                VARCHAR(100),
    claim_id                NUMBER(19,0)    NOT NULL    COMMENT 'FK -> cc_claim.id',
    claimnumber             VARCHAR(30)                 COMMENT 'Denormalized for join efficiency',

    -- Coverage identification
    coveragetype            VARCHAR(50)                 COMMENT 'GW coverage type: DwellingCoverage, PersonalProperty, LossOfUse, Liability, MedPay',
    coveragesegment         VARCHAR(50)                 COMMENT 'SectionI_Dwelling, SectionI_PP, SectionII_Liability, SectionII_MedPay',
    coveragesubtype         VARCHAR(50)                 COMMENT 'Specific coverage pattern code',

    losstype                VARCHAR(30)                 COMMENT 'Basic, AdditionalEndorsement, EnhancementEndorsement. Maps to TSPR TYPE col 59',
    isenhancementendorsement BOOLEAN                    COMMENT 'Loss covered by enhancement endorsement - TSPR TYPE code 3',

    state                   VARCHAR(20)                 COMMENT 'GW exposure state: Open, Closed',
    closedate               TIMESTAMP_NTZ,
    reopendate              TIMESTAMP_NTZ,
    previouslyclosed        BOOLEAN                     COMMENT 'Was this exposure previously reported as closed (for kind code 4-5 vs 6)',

    claimidentifier         VARCHAR(2)                  COMMENT '2-char alphanumeric claim ID unique per policy per occurrence date. Maps to TSPR CLAIMID cols 175-176.',

    isroofloss              BOOLEAN                     COMMENT 'Loss is to roof - enables roof depreciation field (TSPR cols 93-97)',
    rooflosscauseoftype     VARCHAR(20)                 COMMENT 'Wind, Hail, Other - for roof depreciation qualification',

    totalincurred           NUMBER(15,2),
    totalpaid               NUMBER(15,2),
    totaloutstanding        NUMBER(15,2),

    createtime              TIMESTAMP_NTZ,
    updatetime              TIMESTAMP_NTZ,
    retiredvalue            NUMBER(10,0)
)
CLUSTER BY (_partition_month, claim_id)
COMMENT = 'Bronze: Raw CDC from Guidewire ClaimCenter cc_exposure. Coverage-level claim data. One TSPR loss record per exposure. TSPR KIND CLAIMID TYPE cols 31 59 175-176 Rule11 multi-coverage Rule13.';

-- ---------------------------------------------------------------------------
-- 3. Transaction  (GW: cc_transaction)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.gw_cc_transaction (
    gwcbi___operation          VARCHAR(10)     NOT NULL,
    gwcdac___timestampfolder          VARCHAR(64)    NOT NULL,
    gwcdac___fingerprintfolder VARCHAR(64)                COMMENT 'CDA fingerprint folder id (Guidewire diagnostic)',
    gwcbi___seqval_hex           VARCHAR(40)   ,
    _ingestion_timestamp    TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _source_file            VARCHAR(512),
    _partition_month        VARCHAR(7)                  COMMENT 'YYYY-MM from accountingdate — set by ingestion pipeline',

    id                      NUMBER(19,0)    NOT NULL    COMMENT 'GW transaction ID',
    publicid                VARCHAR(100),
    claim_id                NUMBER(19,0)    NOT NULL    COMMENT 'FK -> cc_claim.id',
    exposure_id             NUMBER(19,0)                COMMENT 'FK -> cc_exposure.id',
    claimnumber             VARCHAR(30),

    -- Transaction classification
    subtype                 VARCHAR(30)                 COMMENT 'ClaimPayment, Recovery, ReserveChange, RecoveryReserve',
    transactiontype         VARCHAR(30)                 COMMENT 'Indemnity, Expense, Salvage, Subrogation, OtherRecovery',
    costtype                VARCHAR(30)                 COMMENT 'ClaimCost, LAECost - LAE excluded from TSPR per Rule11',
    costcategory            VARCHAR(20)                 COMMENT 'Indemnity, ALAE, ULAE',

    -- TSPR relevance flags
    isindemnity             BOOLEAN                     COMMENT 'TRUE if indemnity payment - counts toward PCC (Rule14) and CWIP status (Rule16)',
    islae                   BOOLEAN                     COMMENT 'TRUE if LAE - EXCLUDED from TSPR per Rule11 (losses exclusive of LAE)',
    isreinsurancerecovery   BOOLEAN                     COMMENT 'TRUE if reinsurance recovery - EXCLUDED from TSPR LOSS per Rule11',
    issalvage               BOOLEAN                     COMMENT 'TRUE if salvage - included in net of Rule11',
    issubrogation           BOOLEAN                     COMMENT 'TRUE if subrogation - included in net of Rule11',

    amount                  NUMBER(15,2)    NOT NULL    COMMENT 'Transaction amount. Positive=payment, Negative=recovery/reversal',
    currency                VARCHAR(3)      DEFAULT 'USD',

    transactiondate         TIMESTAMP_NTZ   NOT NULL    COMMENT 'Date transaction was posted to GW',
    paymentdate             TIMESTAMP_NTZ               COMMENT 'Date check was issued / EFT sent',
    accountingdate          TIMESTAMP_NTZ               COMMENT 'Accounting date for TSPR period assignment (maps to ACDT)',

    linkedtransaction_id    NUMBER(19,0)                COMMENT 'FK to original transaction if this is a reversal',
    isreversal              BOOLEAN                     COMMENT 'This transaction reverses a prior payment - drives PCC -1 (Rule14)',

    isreserve               BOOLEAN                     COMMENT 'TRUE if reserve change (not payment)',
    reserveamount           NUMBER(15,2)                COMMENT 'Reserve amount - drives TSPR outstanding loss Kind Codes 7-9',
    reserveline             VARCHAR(30)                 COMMENT 'Reserve line type: Indemnity, Expense',

    -- Roof depreciation (ACV vs RC)
    replacementcostestimate NUMBER(15,2)                COMMENT 'RC estimate for roof. Used to compute TSPR DEPREC.',
    actualcashvaluepaid     NUMBER(15,2)                COMMENT 'ACV paid for roof. DEPREC = RC estimate minus ACV paid.',

    createtime              TIMESTAMP_NTZ,
    updatetime              TIMESTAMP_NTZ
)
CLUSTER BY (_partition_month, claim_id, exposure_id)
COMMENT = 'Bronze: Raw CDC from Guidewire ClaimCenter cc_transaction. Every payment and reserve movement. First payment drives PCC=1 (Rule14). TSPR LOSS PCC KIND DEPREC cols 60-67 93-97 Rule11 Rule14 LAE exclusion reinsurance exclusion.';

-- ---------------------------------------------------------------------------
-- 4. Reserve Line  (GW: cc_reserveline)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.gw_cc_reserveline (
    gwcbi___operation          VARCHAR(10)     NOT NULL,
    gwcdac___timestampfolder          VARCHAR(64)    NOT NULL,
    gwcdac___fingerprintfolder VARCHAR(64)                COMMENT 'CDA fingerprint folder id (Guidewire diagnostic)',
    gwcbi___seqval_hex           VARCHAR(40)   ,
    _ingestion_timestamp    TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _source_file            VARCHAR(512),
    _partition_month        VARCHAR(7)                  COMMENT 'YYYY-MM from accountingmonth — set by ingestion pipeline',

    id                      NUMBER(19,0)    NOT NULL,
    publicid                VARCHAR(100),
    claim_id                NUMBER(19,0)    NOT NULL,
    exposure_id             NUMBER(19,0)    NOT NULL,
    claimnumber             VARCHAR(30),

    totalreserve            NUMBER(15,2)                COMMENT 'Current total reserve (incurred minus paid). Maps to TSPR outstanding loss amount',
    indemnitypaid           NUMBER(15,2),
    indemnityreserve        NUMBER(15,2)                COMMENT 'Outstanding indemnity reserve. Used for TSPR LOSS on Kind Codes 7-9',
    laepaid                 NUMBER(15,2),
    laereserve              NUMBER(15,2)                COMMENT 'LAE reserve - EXCLUDED from TSPR per Rule11',

    asofdate                TIMESTAMP_NTZ               COMMENT 'Date reserve snapshot is valid as of',
    accountingmonth         VARCHAR(7)                  COMMENT 'YYYY-MM accounting month for this snapshot',

    createtime              TIMESTAMP_NTZ,
    updatetime              TIMESTAMP_NTZ
)
CLUSTER BY (_partition_month, claim_id)
COMMENT = 'Bronze: Raw CDC from Guidewire ClaimCenter cc_reserveline. Point-in-time reserve snapshots. Drives outstanding loss in TSPR. TSPR LOSS cols 61-67 KIND 7-9 outstanding loss Rule11 LAE exclusion.';

-- ---------------------------------------------------------------------------
-- 5. Claim Address  (GW: cc_address)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.gw_cc_address (
    gwcbi___operation          VARCHAR(10)     NOT NULL,
    gwcdac___timestampfolder          VARCHAR(64)    NOT NULL,
    gwcdac___fingerprintfolder VARCHAR(64)                COMMENT 'CDA fingerprint folder id (Guidewire diagnostic)',
    gwcbi___seqval_hex           VARCHAR(40)   ,
    _ingestion_timestamp    TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _source_file            VARCHAR(512),

    id                      NUMBER(19,0)    NOT NULL,
    publicid                VARCHAR(100),
    claim_id                NUMBER(19,0),
    addresstype             VARCHAR(30)                 COMMENT 'LossLocation, Mailing, etc.',
    addressline1            VARCHAR(200),
    city                    VARCHAR(100),
    county                  VARCHAR(100),
    state                   VARCHAR(2),
    postalcode              VARCHAR(5)                  COMMENT '5-digit ZIP. Maps to TSPR loss record ZIP cols 68-76',
    postalcodeplus4         VARCHAR(4),
    fipscodefull            VARCHAR(15),

    createtime              TIMESTAMP_NTZ,
    updatetime              TIMESTAMP_NTZ,
    retiredvalue            NUMBER(10,0)
)
COMMENT = 'Bronze: Raw CDC from Guidewire ClaimCenter cc_address. Loss location ZIP for TSPR loss records. TSPR loss record ZIP cols 68-76 Rule24.';

ALTER TABLE bronze.gw_cc_address MODIFY COLUMN postalcode SET TAG insurance_regulatory.bronze.tspr_pii = 'true';

-- ---------------------------------------------------------------------------
-- 6. Claim Status History  (derived from cc_claim CDC — append-only)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bronze.gw_cc_claim_status_history (
    _ingestion_timestamp        TIMESTAMP_NTZ   NOT NULL    DEFAULT CURRENT_TIMESTAMP(),
    _source_file                VARCHAR(512),
    _partition_month            VARCHAR(7)                  COMMENT 'YYYY-MM from accounting_month — set by ingestion pipeline',

    -- Identity
    claim_id                    NUMBER(19,0)    NOT NULL    COMMENT 'FK -> cc_claim.id',
    claimnumber                 VARCHAR(30),
    exposure_id                 NUMBER(19,0)                COMMENT 'NULL for claim-level status, FK for exposure-level',

    -- Status event
    status_from                 VARCHAR(20)                 COMMENT 'Previous GW status',
    status_to                   VARCHAR(20)     NOT NULL    COMMENT 'New GW status after this event',
    status_change_timestamp     TIMESTAMP_NTZ   NOT NULL    COMMENT 'Exact timestamp of status change (from CDC)',
    accounting_month            VARCHAR(7)      NOT NULL    COMMENT 'YYYY-MM derived from status_change_timestamp',

    -- Payment context at time of status change
    has_indemnity_payment       BOOLEAN                     COMMENT 'Had indemnity payment at time of status change',
    cumulative_paid             NUMBER(15,2)                COMMENT 'Cumulative indemnity paid at time of this event',

    -- TSPR state machine inputs
    -- Note: Databricks GENERATED ALWAYS AS boolean expressions are implemented
    -- as Snowflake virtual columns using a view, or computed in the ingestion pipeline.
    -- These are stored as regular columns and populated by the ingestion stream.
    is_close_event              BOOLEAN                     COMMENT 'TRUE when status_to IN (Closed, Denied). Populated by ingestion pipeline.',
    is_reopen_event             BOOLEAN                     COMMENT 'TRUE when status_to=Open AND status_from IN (Closed, Denied). Populated by ingestion pipeline.',
    is_new_event                BOOLEAN                     COMMENT 'TRUE when status_from IS NULL or empty (first ever report). Populated by ingestion pipeline.'
)
CLUSTER BY (_partition_month, claim_id)
COMMENT = 'Bronze: Append-only claim status history derived from cc_claim CDC events. Foundation for TSPR Rules 13-16 state machine in Silver. TSPR Rules 13 14 15 16 NCC PCC RCC CS claim state machine foundation.';
