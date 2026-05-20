-- =============================================================================
-- SNOWFLAKE DDL: BRONZE LAYER — Florida FHCF Annual Data Call exposure rows
-- =============================================================================
-- Multi-state proof (Cluster D). The TX Bronze tables in 01_bronze_policycenter
-- and 02_bronze_claimcenter mirror the Guidewire CDC event shape that the TX
-- statistical-plan pipeline reads. The FHCF Data Call is filed against a
-- different upstream system (insurer FHCF reporting modules / SBA portal),
-- so it lands in its own table.
--
-- Column shape follows the FHCF-D1A 320-character record layout, with column
-- names chosen to match the FHCF Data Call Form field names. The 3 validation
-- rules wired in scripts/migrate_fl_validation_rules.py reference this table:
--   Validation.2  ZIP_TX_PREFIX_INVALID  — risk_zip
--   Validation.3  COUNTY_FIPS_VALID       — county_fips
--   Validation.4  STATE_CODE_FIXED        — state_code
--
-- This table is one row per policy-in-force for the reporting period.
-- =============================================================================

USE DATABASE insurance_regulatory;
USE SCHEMA bronze;

CREATE TABLE IF NOT EXISTS fl_fhcf_policy (
    -- Identity
    insurer_naic              VARCHAR(10)    NOT NULL  COMMENT 'Cols 1-10:  10-digit NAIC company number, leading-zero padded',
    policy_number             VARCHAR(10)    NOT NULL  COMMENT 'Cols 11-20: carrier internal policy id',

    -- Location
    risk_zip                  VARCHAR(5)               COMMENT 'Cols 21-25: 5-digit ZIP of insured location; FL ZIPs start with 3',
    risk_zip4                 VARCHAR(5)               COMMENT 'Cols 26-30: ZIP+4 extension; "00000" if unknown',
    county_fips               VARCHAR(2)               COMMENT 'Cols 31-32: FL county FIPS sub-code 01..67',
    state_code                VARCHAR(2)               COMMENT 'Cols 33-34: must be ''FL'' for FHCF reporting',

    -- Policy
    policy_form               VARCHAR(2)               COMMENT 'Cols 35-36: HO3 / HO5 / HO6 / HO8 / DP1 / DP3 / MH',
    effective_date            DATE                     COMMENT 'Cols 37-46: YYYYMMDD',
    expiry_date               DATE                     COMMENT 'Cols 47-56: YYYYMMDD',

    -- Property (subset; full FHCF layout has 30+ fields)
    occupancy_type            VARCHAR(2)               COMMENT 'Cols 57-58: O1/O2/T1/V/BU',
    construction_type         VARCHAR(2)               COMMENT 'Cols 60-61: F/M/MV/S/MH/LF/HM',
    year_built                NUMBER(4)                COMMENT 'Cols 62-65',
    protection_class          NUMBER(1)                COMMENT 'Col 66: 1..9',

    -- Coverage / premium
    coverage_a                NUMBER(10)               COMMENT 'Cols 67-76: dwelling, dollars',
    hurricane_deductible      NUMBER(4)                COMMENT 'Cols 111-114: pct * 100; valid 200..1000 (2%..10%)',
    written_premium           NUMBER(10)               COMMENT 'Cols 115-124: total written premium',

    -- Wind mitigation (FBC)
    wind_mitigation           VARCHAR(1)               COMMENT 'Col 135: Y/N',

    -- Audit / provenance
    reporting_year            NUMBER(4)      NOT NULL  COMMENT 'Reporting year ending 9/30',
    submitted_at              TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP() COMMENT 'Bronze ingestion timestamp',
    source_file               VARCHAR(120)             COMMENT 'FHCF_D1A_{naic}_{year}.txt filename'
)
COMMENT = 'FHCF Annual Data Call exposure rows. Validated against FL-scoped Rules with violation_sql.';

-- Convenience: 5 synthetic exposure rows demonstrating the validation rules.
-- Two clean rows (POL-FL-0001, POL-FL-0002) and three dirty rows that each
-- trigger one of the wired Rules — exactly what the test asserts.
INSERT INTO fl_fhcf_policy
  (insurer_naic, policy_number, risk_zip, risk_zip4, county_fips, state_code,
   policy_form, effective_date, expiry_date, occupancy_type, construction_type,
   year_built, protection_class, coverage_a, hurricane_deductible, written_premium,
   wind_mitigation, reporting_year, source_file)
VALUES
  -- CLEAN — Miami-Dade homeowner, valid everything
  ('0000012345', 'POL-FL-0001', '33101', '00000', '25', 'FL',
   'HO3', '2025-01-15', '2026-01-15', 'O1', 'M', 2015, 3, 450000, 500, 4200,
   'Y', 2025, 'FHCF_D1A_0000012345_2025.txt'),

  -- CLEAN — Tallahassee homeowner, valid everything
  ('0000012345', 'POL-FL-0002', '32308', '00000', '37', 'FL',
   'HO5', '2025-03-01', '2026-03-01', 'O1', 'F', 2018, 4, 285000, 200, 2150,
   'Y', 2025, 'FHCF_D1A_0000012345_2025.txt'),

  -- DIRTY — TX ZIP slipped into an FL filing (triggers Validation.2)
  ('0000012345', 'POL-FL-0003', '77002', '00000', '25', 'FL',
   'HO3', '2025-02-01', '2026-02-01', 'O1', 'M', 2010, 3, 510000, 500, 5100,
   'Y', 2025, 'FHCF_D1A_0000012345_2025.txt'),

  -- DIRTY — county FIPS 99 (only 01..67 exist in FL) (triggers Validation.3)
  ('0000012345', 'POL-FL-0004', '33139', '00000', '99', 'FL',
   'HO3', '2025-04-15', '2026-04-15', 'O1', 'MV', 2020, 2, 625000, 500, 5800,
   'Y', 2025, 'FHCF_D1A_0000012345_2025.txt'),

  -- DIRTY — STATE_CODE='TX' on an FHCF row (triggers Validation.4)
  ('0000012345', 'POL-FL-0005', '32202', '00000', '31', 'TX',
   'HO3', '2025-05-10', '2026-05-10', 'O1', 'F', 2005, 5, 195000, 200, 1850,
   'N', 2025, 'FHCF_D1A_0000012345_2025.txt');
