-- =============================================================================
-- SNOWFLAKE DDL: REFERENCE SCHEMA — TSPR Plan Rules as Queryable Data
-- =============================================================================
-- Purpose  : Every Section B code table, Section F crosswalk, and plan rule
--            stored as Snowflake managed tables with seed data.
--            Transformation pipelines read these at runtime — updating the
--            plan requires only a data change here, not a code deployment.
-- Database : insurance_regulatory
-- Schema   : reference
--
-- Snowflake translation notes:
--   STRING           -> VARCHAR
--   BOOLEAN DEFAULT FALSE -> BOOLEAN DEFAULT FALSE  (supported natively)
--   DATE DEFAULT '2026-01-01' -> DATE DEFAULT '2026-01-01'  (supported)
--   USING DELTA      -> removed
--   TBLPROPERTIES    -> COMMENT on table
--   validation_sql STRING -> kept as VARCHAR; note that REGEXP_REPLACE in
--                    Databricks uses Java regex; Snowflake uses RLIKE/REGEXP_REPLACE
--                    with similar syntax. SQL expressions stored here are
--                    documentation/reference — execution happens in the
--                    pipeline which adapts the dialect.
-- =============================================================================

CREATE DATABASE IF NOT EXISTS insurance_regulatory;

CREATE SCHEMA IF NOT EXISTS insurance_regulatory.reference
    COMMENT = 'Reference: TSPR plan rules, code mappings, and crosswalk tables encoded as queryable data. Update data here to apply plan changes without redeploying pipelines.';

USE DATABASE insurance_regulatory;
USE SCHEMA reference;

-- ---------------------------------------------------------------------------
-- 1. Cause of Loss Mapping  (Section B.12 + Rule 11 Proximate Cause)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reference.tspr_cause_of_loss_map (
    gw_loss_cause               VARCHAR(50)     NOT NULL
        COMMENT 'Guidewire cc_claim.losscause value',
    gw_loss_cause_subtype       VARCHAR(50)
        COMMENT 'Guidewire cc_claim.losscausesubtype for disambiguation',
    tspr_cause_code             VARCHAR(2)      NOT NULL
        COMMENT 'TSPR 2-digit cause of loss code (cols 90-91)',
    tspr_description            VARCHAR(200)
        COMMENT 'TSPR cause description',
    proximate_cause_override    BOOLEAN         DEFAULT FALSE
        COMMENT 'TRUE when ensuing cause maps to different TSPR code than proximate - see Rule11',
    proximate_note              VARCHAR(300)
        COMMENT 'Explanation of proximate vs ensuing distinction',
    effective_date              DATE            DEFAULT '2026-01-01'
)
COMMENT = 'Reference: GW loss cause -> TSPR COL code mapping. Implements Rule 11 proximate cause rule and Section B.12 cause of loss codes. Rule11 SectionB12 Section D.';

INSERT INTO reference.tspr_cause_of_loss_map VALUES
-- Fire
('Fire',       'InternalSource',          '05', 'Fire - Internal Source (electrical, kitchen etc.)',                    FALSE, NULL,                                                                         '2026-01-01'),
('Fire',       'ExternalSource',          '10', 'Fire - External Source (lightning, neighbor, embers)',                 FALSE, NULL,                                                                         '2026-01-01'),
('Fire',       NULL,                      '15', 'Fire - Unknown Source',                                                FALSE, NULL,                                                                         '2026-01-01'),
('Lightning',  'NoFire',                  '20', 'Lightning - No Fire',                                                  FALSE, NULL,                                                                         '2026-01-01'),
('Lightning',  'CausedFire',              '10', 'Lightning caused fire -> code 10 External Source, not 20',             TRUE,  'Lightning causing fire is coded as Fire-External (Rule11 proximate=fire)',   '2026-01-01'),
-- Wind
('Windstorm',  NULL,                      '25', 'Windstorm',                                                            FALSE, NULL,                                                                         '2026-01-01'),
('Windstorm',  'WaterIntrusionEnsuing',   '25', 'Windstorm damaged roof; water entered -> still code 25 (Rule11)',      TRUE,  'Wind is proximate cause even if water damage ensued',                        '2026-01-01'),
('Hurricane',  NULL,                      '25', 'Hurricane -> Windstorm code 25',                                       FALSE, NULL,                                                                         '2026-01-01'),
('Tornado',    NULL,                      '25', 'Tornado -> Windstorm code 25',                                         FALSE, NULL,                                                                         '2026-01-01'),
-- Hail
('Hail',       NULL,                      '30', 'Hail',                                                                 FALSE, NULL,                                                                         '2026-01-01'),
-- Flood
('Flood',      'RisingWater',             '32', 'Flood or Rising Water (private flood only - not NFIP)',                FALSE, NULL,                                                                         '2026-01-01'),
('Flood',      'StormSurge',              '32', 'Storm surge -> Flood code 32',                                         FALSE, NULL,                                                                         '2026-01-01'),
-- Explosion / Smoke
('Explosion',  NULL,                      '33', 'Explosion',                                                            FALSE, NULL,                                                                         '2026-01-01'),
('Smoke',      NULL,                      '35', 'Smoke',                                                                FALSE, NULL,                                                                         '2026-01-01'),
-- Aircraft / Vehicles
('Aircraft',   NULL,                      '40', 'Aircraft',                                                             FALSE, NULL,                                                                         '2026-01-01'),
('Vehicle',    NULL,                      '40', 'Vehicle',                                                              FALSE, NULL,                                                                         '2026-01-01'),
-- Riot / Vandalism / Collapse
('Riot',       NULL,                      '45', 'Riot and Civil Commotion',                                             FALSE, NULL,                                                                         '2026-01-01'),
('Vandalism',  NULL,                      '50', 'Vandalism and Malicious Mischief',                                     FALSE, NULL,                                                                         '2026-01-01'),
('Collapse',   NULL,                      '55', 'Collapse',                                                             FALSE, NULL,                                                                         '2026-01-01'),
-- Water discharge (Rule11: freeze-caused burst pipe -> code 70/71 not 60/61)
('WaterDamage','Discharge_Slab',          '60', 'Discharge - Damage to Slab or Foundation',                            FALSE, NULL,                                                                         '2026-01-01'),
('WaterDamage','Discharge_Other',         '61', 'Discharge - Other Damage',                                            FALSE, NULL,                                                                         '2026-01-01'),
('WaterDamage','FreezeEnsuingDischarge',  '71', 'Freeze caused pipe to burst then discharge -> code 71 (proximate=freeze Rule11)', TRUE, 'Cold weather->freeze->burst->discharge: proximate is freeze, not discharge', '2026-01-01'),
-- Freeze
('Freeze',     'Slab',                    '70', 'Freeze - Damage to Slab or Foundation',                               FALSE, NULL,                                                                         '2026-01-01'),
('Freeze',     'Other',                   '71', 'Freeze - Other Damage',                                               FALSE, NULL,                                                                         '2026-01-01'),
('Freeze',     'BurstPipe',               '71', 'Freeze caused burst pipe -> code 71 Freeze Other (not Discharge)',     TRUE,  'Freeze is proximate cause; discharge is ensuing per Rule11',                 '2026-01-01'),
-- Theft
('Theft',      NULL,                      '75', 'Burglary, Theft, Robbery',                                             FALSE, NULL,                                                                         '2026-01-01'),
('Burglary',   NULL,                      '75', 'Burglary, Theft, Robbery',                                             FALSE, NULL,                                                                         '2026-01-01'),
-- Other
('Other',      'PhysicalDamage',          '80', 'Other - Physical Damage',                                              FALSE, NULL,                                                                         '2026-01-01'),
('Liability',  NULL,                      '90', 'Other - Liability and Medical Payments',                               FALSE, NULL,                                                                         '2026-01-01'),
('MedPay',     NULL,                      '90', 'Other - Liability and Medical Payments',                               FALSE, NULL,                                                                         '2026-01-01');


-- ---------------------------------------------------------------------------
-- 2. LOB Code Mapping  (Section B.4)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reference.tspr_lob_codes (
    gw_lob_code                 VARCHAR(30)     NOT NULL
        COMMENT 'Guidewire policylinepatterncodeidentifier',
    gw_lob_description          VARCHAR(100),
    tspr_lob_code               VARCHAR(2)      NOT NULL
        COMMENT 'TSPR 2-digit LOB code (cols 41-42)',
    tspr_lob_description        VARCHAR(100),
    allied_lines_lob            BOOLEAN         DEFAULT FALSE
        COMMENT 'TRUE = allied lines reported on separate records',
    effective_date              DATE            DEFAULT '2026-01-01'
)
COMMENT = 'Reference: Guidewire LOB code -> TSPR LOB code. Section B.4. Section C cols 41-42.';

INSERT INTO reference.tspr_lob_codes VALUES
('HOPLine',       'Homeowners Policy Line',                     '03', 'Homeowners Policies Excl Tenants', FALSE, '2026-01-01'),
('HOPTenantLine', 'Homeowners Tenant/Condo Line',               '02', 'Homeowners Tenants incl Condo',   FALSE, '2026-01-01'),
('DwellingLine',  'Dwelling Fire Line',                         '10', 'Dwelling Policies - Fire PD+TE',   FALSE, '2026-01-01'),
('DwellingMisc',  'Dwelling Miscellaneous',                     '11', 'Dwelling Policies - Misc Prop',    FALSE, '2026-01-01'),
('DwellingLiab',  'Dwelling Liability',                         '12', 'Dwelling Policies - Liability',    FALSE, '2026-01-01'),
('TWIAWindLine',  'TWIA Wind-Only Policy',                      '13', 'Dwelling Policies - TWIA Wind',    FALSE, '2026-01-01'),
('VolWindAR',     'Voluntary Wind-Only Assumption Reinsurance', '14', 'Dwelling Policies - Vol Wind AR',  FALSE, '2026-01-01'),
('VolWindOther',  'Voluntary Wind-Only Other',                  '15', 'Dwelling Policies - Vol Wind Other',FALSE,'2026-01-01'),
('DwellingTheft', 'Dwelling Theft',                             '16', 'Dwelling Policies - Theft',        FALSE, '2026-01-01'),
('FloodPrivate',  'Stand-alone Private Flood Primary',          '35', 'Private Flood Stand-alone Primary', FALSE, '2026-01-01'),
('LossAssess',    'Loss Assessment',                            '25', 'Dwelling - Loss Assessment',        TRUE,  '2026-01-01'),
('AddlEC',        'Additional Extended Coverage',               '26', 'Dwelling - Additional EC',          TRUE,  '2026-01-01'),
('ResGlass',      'Residence Glass',                            '27', 'Dwelling - Residence Glass',        TRUE,  '2026-01-01'),
('AllRisk',       'All Risk Physical Loss',                     '28', 'Dwelling - All Risk',               TRUE,  '2026-01-01'),
('PrivFloodEC',   'Private Flood EC',                           '29', 'Dwelling - Private Flood',          TRUE,  '2026-01-01'),
('NatDisaster',   'Supplemental Natural Disaster',              '50', 'Supplemental Natural Disaster',     TRUE,  '2026-01-01');


-- ---------------------------------------------------------------------------
-- 3. Form Code / Policy Type Crosswalk  (Sections B.5, F)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reference.tspr_form_codes (
    gw_form_code                VARCHAR(20)     NOT NULL
        COMMENT 'Guidewire holineform value',
    tspr_form_code              VARCHAR(1)      NOT NULL
        COMMENT 'TSPR single-char form code (col 50)',
    tspr_form_description       VARCHAR(100),
    tspr_type_of_policy         VARCHAR(2)      NOT NULL
        COMMENT 'Section E typeOfPolicy code (cols 15-16): 01=Tenant,02=Condo,03=HO,04=Dwelling,05=MHO',
    is_tenant                   BOOLEAN         DEFAULT FALSE,
    is_condo                    BOOLEAN         DEFAULT FALSE,
    is_ho                       BOOLEAN         DEFAULT FALSE,
    is_dwelling                 BOOLEAN         DEFAULT FALSE,
    is_mho                      BOOLEAN         DEFAULT FALSE,
    effective_date              DATE            DEFAULT '2026-01-01'
)
COMMENT = 'Reference: Guidewire form code -> TSPR FM code and typeOfPolicy crosswalk. SectionB5 SectionF. Section C col 50 and Section E cols 15-16.';

INSERT INTO reference.tspr_form_codes VALUES
('HO_A',           '1', 'HO Policy A Form 1',                        '03', FALSE, FALSE, TRUE,  FALSE, FALSE, '2026-01-01'),
('HO_B',           '2', 'HO Policy B Form 2',                        '03', FALSE, FALSE, TRUE,  FALSE, FALSE, '2026-01-01'),
('HO_C',           '3', 'HO Policy C Form 3',                        '03', FALSE, FALSE, TRUE,  FALSE, FALSE, '2026-01-01'),
('Tenants_B',      '4', 'Tenants Form B (Form 1 w/V&MM)',             '01', TRUE,  FALSE, FALSE, FALSE, FALSE, '2026-01-01'),
('Tenants_C',      '5', 'Tenants Form C',                            '01', TRUE,  FALSE, FALSE, FALSE, FALSE, '2026-01-01'),
('HO_A_Plus',      '9', 'HO Policy A Enhanced (HO-A+)',               '03', FALSE, FALSE, TRUE,  FALSE, FALSE, '2026-01-01'),
('Ind_HO_Basic',   'A', 'Independent HO Basic Policy Form A',         '03', FALSE, FALSE, TRUE,  FALSE, FALSE, '2026-01-01'),
('Ind_Tenant_Broad','B','Independent Tenant Broad Policy Form B',     '01', TRUE,  FALSE, FALSE, FALSE, FALSE, '2026-01-01'),
('Ind_Condo_Broad','C', 'Independent Condo Broad Policy Form C',      '02', FALSE, TRUE,  FALSE, FALSE, FALSE, '2026-01-01'),
('Ind_DW_Basic',   'D', 'Independent Dwelling Basic Policy Form D',   '04', FALSE, FALSE, FALSE, TRUE,  FALSE, '2026-01-01'),
('Ind_Tenant_Spec','E', 'Independent Tenant Special Policy Form E',   '01', TRUE,  FALSE, FALSE, FALSE, FALSE, '2026-01-01'),
('ISO_HO_00_02',   'F', 'HO 00 02 ISO Homeowners 2 Broad Form',       '03', FALSE, FALSE, TRUE,  FALSE, FALSE, '2026-01-01'),
('ISO_HO_00_03',   'G', 'HO 00 03 ISO Homeowners 3 Special Form',     '03', FALSE, FALSE, TRUE,  FALSE, FALSE, '2026-01-01'),
('ISO_HO_00_04',   'H', 'HO 00 04 ISO Homeowners 4 Contents Broad',   '01', TRUE,  FALSE, FALSE, FALSE, FALSE, '2026-01-01'),
('ISO_HO_00_05',   'I', 'HO 00 05 ISO Homeowners 5 Comprehensive',    '03', FALSE, FALSE, TRUE,  FALSE, FALSE, '2026-01-01'),
('ISO_HO_00_06',   'J', 'HO 00 06 ISO Homeowners 6 Unit Owners',      '02', FALSE, TRUE,  FALSE, FALSE, FALSE, '2026-01-01'),
('ISO_HO_00_08',   'K', 'HO 00 08 ISO Homeowners 8 Modified Cov',     '03', FALSE, FALSE, TRUE,  FALSE, FALSE, '2026-01-01'),
('Ind_HO_Broad',   'L', 'Independent HO Broad Policy Form L',         '03', FALSE, FALSE, TRUE,  FALSE, FALSE, '2026-01-01'),
('Ind_HO_Spec',    'M', 'Independent HO Special Policy Form M',       '03', FALSE, FALSE, TRUE,  FALSE, FALSE, '2026-01-01'),
('Ind_Condo_Spec', 'N', 'Independent Condo Special Policy Form N',    '02', FALSE, TRUE,  FALSE, FALSE, FALSE, '2026-01-01'),
('Ind_DW_Spec',    'O', 'Independent Dwelling Special Policy Form O',  '04', FALSE, FALSE, FALSE, TRUE,  FALSE, '2026-01-01'),
('Ind_DW_Broad',   'P', 'Independent Dwelling Broad Policy Form P',   '04', FALSE, FALSE, FALSE, TRUE,  FALSE, '2026-01-01'),
('ISO_DP1',        'Q', 'ISO Dwelling Property 1 Basic Form',         '04', FALSE, FALSE, FALSE, TRUE,  FALSE, '2026-01-01'),
('ISO_DP2',        'T', 'ISO Dwelling Property 2 Broad Form',         '04', FALSE, FALSE, FALSE, TRUE,  FALSE, '2026-01-01'),
('ISO_DP3',        'U', 'ISO Dwelling Property 3 Special Form',       '04', FALSE, FALSE, FALSE, TRUE,  FALSE, '2026-01-01'),
('Ind_Liab',       'V', 'Independent Personal Liability Policy (HO)', '03', FALSE, FALSE, TRUE,  FALSE, FALSE, '2026-01-01'),
('AAIS_F1',        'W', 'AAIS Form 1 Basic Form',                     '03', FALSE, FALSE, TRUE,  FALSE, FALSE, '2026-01-01'),
('AAIS_F2',        'X', 'AAIS Form 2 Broad Form',                     '03', FALSE, FALSE, TRUE,  FALSE, FALSE, '2026-01-01'),
('AAIS_F3',        'Y', 'AAIS Form 3 Special Form',                   '03', FALSE, FALSE, TRUE,  FALSE, FALSE, '2026-01-01'),
('AAIS_F4',        'Z', 'AAIS Form 4 Contents Broad Form',            '01', TRUE,  FALSE, FALSE, FALSE, FALSE, '2026-01-01'),
('AAIS_F5',        '6', 'AAIS Form 5 Special Building and Contents',  '03', FALSE, FALSE, TRUE,  FALSE, FALSE, '2026-01-01'),
('AAIS_F6',        '7', 'AAIS Form 6 Unit-Owners Form',               '02', FALSE, TRUE,  FALSE, FALSE, FALSE, '2026-01-01'),
('AAIS_F8',        '8', 'AAIS Form 8 Limited Form',                   '03', FALSE, FALSE, TRUE,  FALSE, FALSE, '2026-01-01'),
-- Mobile home: construction code 5 overrides form code -> MHO = 05
('MobileHome',     '1', 'Mobile/Manufactured Home (construction=5)',  '05', FALSE, FALSE, FALSE, FALSE, TRUE,  '2026-01-01');


-- ---------------------------------------------------------------------------
-- 4. Cancellation / Nonrenewal Reason Code Map  (Section E, Section F)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reference.tspr_reason_code_map (
    gw_reason_code              VARCHAR(50)     NOT NULL
        COMMENT 'Guidewire cancellation/nonrenewal reason value',
    tspr_reason_code            VARCHAR(1)      NOT NULL
        COMMENT 'TSPR single-letter reason code (Section E cols 36-45)',
    applies_to_cancellation     BOOLEAN         DEFAULT FALSE,
    applies_to_nonrenewal       BOOLEAN         DEFAULT FALSE,
    applies_to_declination      BOOLEAN         DEFAULT FALSE,
    description                 VARCHAR(200),
    section_f_notes             VARCHAR(400)
        COMMENT 'Additional guidance from Section F',
    credit_score_companion_required BOOLEAN     DEFAULT FALSE
        COMMENT 'TRUE for code L: must have at least one other code',
    must_appear_alone           BOOLEAN         DEFAULT FALSE
        COMMENT 'TRUE for code J: withdrawal must appear alone',
    effective_date              DATE            DEFAULT '2026-01-01'
)
COMMENT = 'Reference: Guidewire cancellation/nonrenewal reason -> TSPR reason code. Rule34 SectionF Section E cols 36-45.';

INSERT INTO reference.tspr_reason_code_map VALUES
-- Cancellation reasons (Section E)
('NonPayment',         'A', TRUE,  FALSE, FALSE, 'Failure to pay premiums when due',
 NULL, FALSE, FALSE, '2026-01-01'),
('HazardIncrease',     'B', TRUE,  FALSE, FALSE, 'Increase in hazard',
 'Use if policy canceled due to increase in hazard within insured control that would increase premium rate', FALSE, FALSE, '2026-01-01'),
('NoInspectionReport', 'C', TRUE,  FALSE, FALSE, 'No inspection report accepted',
 'Use if before effective date insurer does not accept required inspection report dated within 90 days', FALSE, FALSE, '2026-01-01'),
('TWIAAssumptionReins','X', TRUE,  FALSE, FALSE, 'Assumption Reinsurance (TWIA only)',
 NULL, FALSE, FALSE, '2026-01-01'),
('InsuredRequest',     'Y', TRUE,  FALSE, FALSE, 'At insured request',
 'Use for insured death, loss of insurable interest, or any reason at insured request', FALSE, FALSE, '2026-01-01'),
('CarrierOther',       'Z', TRUE,  TRUE,  TRUE,  'Other - insurer action',
 'Use for fraudulent claim, TDI-directed, or any reason not otherwise listed', FALSE, FALSE, '2026-01-01'),
-- Nonrenewal and Declination reasons (Section E)
('ClaimsHistory',      'D', FALSE, TRUE,  TRUE,  'Claims history',
 NULL, FALSE, FALSE, '2026-01-01'),
('LiabilityExposure',  'E', FALSE, TRUE,  TRUE,  'Exposure to loss - liability',
 'Use if reason is due to insured personal liability risk', FALSE, FALSE, '2026-01-01'),
('WildfireExposure',   'F', FALSE, TRUE,  TRUE,  'Exposure to loss - wildfire',
 NULL, FALSE, FALSE, '2026-01-01'),
('WindHailExposure',   'G', FALSE, TRUE,  TRUE,  'Exposure to loss - wind/hail/hurricane',
 NULL, FALSE, FALSE, '2026-01-01'),
('ConcentrationRisk',  'H', FALSE, TRUE,  TRUE,  'Exposure to loss - insurer concentration of risk',
 'Use if insurer excessive exposure in area/subline. Not wildfire or wind/hail.', FALSE, FALSE, '2026-01-01'),
('MarketWithdrawal',   'J', FALSE, TRUE,  FALSE, 'Insurer withdrawing from market',
 'Use only if insurer has filed TDI-approved withdrawal plan. MUST APPEAR ALONE - no other codes.', FALSE, TRUE, '2026-01-01'),
('LocationOfRisk',     'K', FALSE, TRUE,  TRUE,  'Location of risk',
 'Use if insurer does not write in certain areas and no exposure-to-loss reason applies', FALSE, FALSE, '2026-01-01'),
('CreditScore',        'L', FALSE, TRUE,  TRUE,  'Credit or insurance score',
 'Cannot be sole nonrenewal/declination reason - must have at least one other reason (Sec559.052)', TRUE, FALSE, '2026-01-01'),
('RoofCondition',      'M', FALSE, TRUE,  TRUE,  'Condition of property - roof',
 NULL, FALSE, FALSE, '2026-01-01'),
('TreeOverhang',       'N', FALSE, TRUE,  TRUE,  'Condition of property - tree overhang',
 NULL, FALSE, FALSE, '2026-01-01'),
('DefensibleSpace',    'P', FALSE, TRUE,  TRUE,  'Condition of property - insufficient defensible space',
 NULL, FALSE, FALSE, '2026-01-01'),
('MaintenanceVacancy', 'Q', FALSE, TRUE,  TRUE,  'Condition of property - maintenance/occupancy/vacancy',
 NULL, FALSE, FALSE, '2026-01-01'),
('ConditionOther',     'R', FALSE, TRUE,  TRUE,  'Condition of property - other',
 'If nonrenewal due to not writing certain roof types (e.g. wood-shake) use Z not M', FALSE, FALSE, '2026-01-01'),
('PropertyValue',      'S', FALSE, TRUE,  TRUE,  'Value of home',
 'Use when property exceeds limit in insurer underwriting guidelines', FALSE, FALSE, '2026-01-01'),
('AgentUnappointed',   'T', FALSE, TRUE,  FALSE, 'Agent no longer appointed with insurer',
 NULL, FALSE, FALSE, '2026-01-01');


-- ---------------------------------------------------------------------------
-- 5. TSPR Validation Rules  (all Section A rules as queryable data)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reference.tspr_validation_rules (
    rule_id                     VARCHAR(30)     NOT NULL
        COMMENT 'Rule identifier (e.g. Rule6, SectionB10)',
    rule_title                  VARCHAR(100)    NOT NULL,
    applies_to_section          VARCHAR(1)
        COMMENT 'C, D, E, G, or A for general',
    affected_field              VARCHAR(20)
        COMMENT 'TSPR field abbreviation',
    affected_col_start          NUMBER(5,0),
    affected_col_end            NUMBER(5,0),
    validation_sql              VARCHAR(500)
        COMMENT 'SQL expression for validation check (references silver table columns). Note: written for Snowflake SQL dialect. REGEXP_REPLACE uses ECMAScript-compatible regex.',
    severity                    VARCHAR(10)     DEFAULT 'ERROR'
        COMMENT 'ERROR (blocks submission) or WARNING (flags for review)',
    rule_text                   VARCHAR(500)    NOT NULL
        COMMENT 'Full plan rule text excerpt',
    effective_date              DATE            DEFAULT '2026-01-01'
)
COMMENT = 'Reference: TSPR plan validation rules as executable SQL expressions. SectionA. Pipeline reads these at runtime to validate Silver/Gold records.';

INSERT INTO reference.tspr_validation_rules VALUES
('Rule1',           'Stat Plan',                    'C', 'SP',      1,   1,
 'stat_plan = ''4''',
 'ERROR', 'Statistical plan code must equal 4 for Residential risks.', '2026-01-01'),

('Rule6_ALE',       'Loss of Use conversion',        'C', 'ALE',    166, 168,
 'amt_insurance_alu IS NOT NULL OR private_flood_indicator = ''1''',
 'ERROR', 'Loss of Use amount must be in dollars not percentages. Convert % of Cov A to dollar amount first.', '2026-01-01'),

('Rule6_INS_min',   'Amount of insurance minimum',   'C', 'INS',    33,  37,
 'amt_insurance_dw >= 1',
 'ERROR', 'Amounts under $1500 must be coded as 01 (1 in $1000 units).', '2026-01-01'),

('Rule11_COL',      'Proximate cause',               'D', 'COL',    90,  91,
 'cause_of_loss IS NOT NULL AND LENGTH(cause_of_loss) = 2',
 'ERROR', 'Cause of loss code must reflect original and proximate cause, not ensuing causes. Wind+water=25 not water.', '2026-01-01'),

('Rule11_LAE',      'LAE exclusion',                 'D', 'LOSS',   61,  67,
 'is_lae = FALSE OR is_lae IS NULL',
 'ERROR', 'Loss adjustment expenses must not be reported in TSPR loss records.', '2026-01-01'),

('Rule13_NCC',      'New claim count',               'D', 'NCC',    173, 173,
 'new_claim_count IN (-1, 0, 1)',
 'ERROR', 'New claim count must be 1 (new), 0 (previously reported), or -1 (reversal).', '2026-01-01'),

('Rule14_PCC',      'Paid claim count',              'D', 'PCC',    60,  60,
 'paid_claim_count IN (-1, 0, 1)',
 'ERROR', 'Paid claim count must be 1 (first payment), 0 (nonpayment/already paid), or -1 (reversal).', '2026-01-01'),

('Rule15_RCC',      'Reopened claim count',          'D', 'RCC',    177, 177,
 'reopened_claim_count IN (-1, 0, 1)',
 'ERROR', 'Reopened claim count must be 1 (newly reopened first record), 0 (others), or -1 (reversal).', '2026-01-01'),

('Rule16_CS',       'Claim status',                  'D', 'CS',     174, 174,
 'claim_status BETWEEN 1 AND 6',
 'ERROR', 'Claim status must be 1-6: 1=open never closed, 2=CWIP never closed, 3=CWOP never closed, 4=open prev closed, 5=CWIP prev closed, 6=CWOP prev closed.', '2026-01-01'),

('Rule20_CLM',      'Prior claims history',          'C', 'CLM',    173, 173,
 'prior_claims_history IN (''0'',''1'',''2'',''3'',''4'',''5'',''6'')',
 'ERROR', 'Prior claims history must be 0-5 (count) or 6 (not used in rating/tiering). Cannot include natural-cause or prohibited claims.', '2026-01-01'),

('Rule24_ZIP',      'ZIP code',                      'C', 'ZIP',    91,  99,
 'zip9 IS NOT NULL AND LENGTH(REGEXP_REPLACE(zip9, ''[^0-9]'', '''')) >= 5',
 'ERROR', 'Five-digit ZIP code is mandatory for all records.', '2026-01-01'),

('Rule25_NAIC',     'NAIC company number',           'C', 'NAIC',   146, 150,
 'naic_company_no IS NOT NULL AND LENGTH(naic_company_no) = 5',
 'ERROR', 'NAIC company number is mandatory on ALL records. Must be 5 digits.', '2026-01-01'),

('Rule26_POLICY',   'Policy identifier',             'C', 'POLICY', 7,   16,
 'policy_id IS NOT NULL AND LENGTH(TRIM(policy_id)) > 0',
 'ERROR', 'Policy identifier must be present and cannot be reused for different policies.', '2026-01-01'),

('Rule30_TENURE',   'Tenure code required',          'C', 'TENURE', 140, 140,
 'tenure_code IN (''0'',''1'',''2'',''3'',''4'',''5'',''6'',''7'')',
 'ERROR', 'Tenure code is REQUIRED on ALL premium and loss transactions including endorsements and cancellations.', '2026-01-01'),

('Rule32_FLOOD',    'Private flood',                 'C', 'FLOOD',  154, 154,
 'private_flood_indicator IN (''0'',''1'')',
 'ERROR', 'Private flood indicator must be 0 or 1. Federal NFIP policies must NOT be reported.', '2026-01-01'),

('Rule34_CreditAlone','Credit code alone',           'E', 'RCL',    36,  45,
 'NOT (reason_code_list LIKE ''%L%'' AND TRIM(REPLACE(REPLACE(reason_code_list,''0'',''''),'' '','''')) = ''L'')',
 'ERROR', 'Credit score reason code L cannot be the sole nonrenewal/declination reason per Sec559.052(a)(2).', '2026-01-01'),

('Rule34_WithdrawalAlone','Withdrawal alone',        'E', 'RCL',    36,  45,
 'NOT (reason_code_list LIKE ''%J%'' AND LENGTH(TRIM(REPLACE(REPLACE(reason_code_list,''J'',''''),''0'',''''))) > 0)',
 'ERROR', 'Withdrawal code J must appear alone - no other reason codes permitted per Section F.', '2026-01-01'),

('SectionB10_DED7', 'Deductible code 7 territory',  'C', 'DED1',   57,  57,
 'NOT (deductible_1 = ''7'' AND territory NOT IN (''8'',''9'',''10'') AND NOT in_twia_zone)',
 'ERROR', 'Deductible code 7 (no wind coverage) only valid in territories 8,9,10 and specified TWIA portions of Territory 1.', '2026-01-01');
