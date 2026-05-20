-- =============================================================
-- INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES
-- Jurisdiction scope: US-FL ∪ US (federal defaults)
-- Generated at: 2026-05-20T15:25:46+00:00
-- Neo4j: bolt://localhost:7687
-- =============================================================

USE DATABASE INSURANCE_REGULATORY;
USE SCHEMA REFERENCE;

CREATE OR REPLACE TABLE TSPR_VALIDATION_RULES (
    rule_id              VARCHAR(64)  NOT NULL,
    rule_number          VARCHAR(32)  NOT NULL,
    rule_name            VARCHAR(512) NOT NULL,
    section              VARCHAR(8),
    jurisdiction_code    VARCHAR(8)   NOT NULL DEFAULT 'US-TX',
    is_federal_default   BOOLEAN      NOT NULL DEFAULT FALSE,
    target_table         VARCHAR(128) NOT NULL,
    target_id_expr       VARCHAR(1024),
    violation_sql        VARCHAR(8000) NOT NULL,
    violation_reason     VARCHAR(1024) NOT NULL,
    severity             VARCHAR(16)   NOT NULL,
    citation             VARCHAR(1024),
    validation_version   NUMBER(10,0)  NOT NULL,
    kg_canon_version     NUMBER(10,0),
    kg_source_document_id VARCHAR(64),
    generated_at         TIMESTAMP_NTZ NOT NULL,
    CONSTRAINT pk_tspr_validation_rules PRIMARY KEY (rule_id)
) COMMENT = 'Executable validation rules. Sourced from RegulAI KG, scoped by jurisdiction.';

-- Replace only this jurisdiction's rows so multi-jurisdiction loads accumulate safely.
DELETE FROM TSPR_VALIDATION_RULES WHERE jurisdiction_code = 'US-FL';
DELETE FROM TSPR_VALIDATION_RULES WHERE jurisdiction_code = 'US';

-- 2: Rule Validation.2 — ZIP_TX_PREFIX_INVALID  (scope=US-FL)
INSERT INTO TSPR_VALIDATION_RULES (
    rule_id, rule_number, rule_name, section, jurisdiction_code, is_federal_default, target_table, target_id_expr, violation_sql, violation_reason, severity, citation, validation_version, kg_canon_version, kg_source_document_id, generated_at
) VALUES (
    'e888b06a-c2f3-4d78-ad22-d9ef94d4f477', '2', 'Rule Validation.2 — ZIP_TX_PREFIX_INVALID', 'Validation Rules', 'US-FL', FALSE, 'BRONZE.FL_FHCF_POLICY', 'p.policy_number', 'p.risk_zip IS NULL
            OR LENGTH(TRIM(p.risk_zip)) <> 5
            OR LEFT(TRIM(p.risk_zip), 1) <> ''3''', 'RISK_ZIP must be 5 digits beginning with ''3'' (Florida prefix); non-FL prefix is a hard validation error', 'ERROR', 'FHCF Data Call Form / Validation Rule 2 / §215.555(5)(b), F.S.', 1, 1, 'ea3f3d6a-4297-4d47-a3c3-551cd8bd86b9', CURRENT_TIMESTAMP()
);

-- 3: Rule Validation.3 — COUNTY_FIPS_VALID  (scope=US-FL)
INSERT INTO TSPR_VALIDATION_RULES (
    rule_id, rule_number, rule_name, section, jurisdiction_code, is_federal_default, target_table, target_id_expr, violation_sql, violation_reason, severity, citation, validation_version, kg_canon_version, kg_source_document_id, generated_at
) VALUES (
    '1968fbc3-057f-43c5-b88c-29904efe5f29', '3', 'Rule Validation.3 — COUNTY_FIPS_VALID', 'Validation Rules', 'US-FL', FALSE, 'BRONZE.FL_FHCF_POLICY', 'p.policy_number', 'p.county_fips IS NULL
            OR NOT REGEXP_LIKE(p.county_fips, ''^[0-9]{1,2}$'')
            OR TO_NUMBER(p.county_fips) NOT BETWEEN 1 AND 67', 'COUNTY_FIPS must be a numeric Florida county FIPS sub-code in 01..67', 'ERROR', 'FHCF Data Call Form / Validation Rule 3', 1, 1, 'ea3f3d6a-4297-4d47-a3c3-551cd8bd86b9', CURRENT_TIMESTAMP()
);

-- 4: Rule Validation.4 — STATE_CODE_FIXED  (scope=US-FL)
INSERT INTO TSPR_VALIDATION_RULES (
    rule_id, rule_number, rule_name, section, jurisdiction_code, is_federal_default, target_table, target_id_expr, violation_sql, violation_reason, severity, citation, validation_version, kg_canon_version, kg_source_document_id, generated_at
) VALUES (
    'fdad27df-5324-4b87-b75c-07b651d55437', '4', 'Rule Validation.4 — STATE_CODE_FIXED', 'Validation Rules', 'US-FL', FALSE, 'BRONZE.FL_FHCF_POLICY', 'p.policy_number', 'p.state_code IS NULL
            OR UPPER(TRIM(p.state_code)) <> ''FL''', 'STATE_CODE must equal ''FL'' exactly — FHCF only covers Florida-domiciled risks', 'ERROR', 'FHCF Data Call Form / Validation Rule 4 / §215.555(2)(a), F.S.', 1, 1, 'ea3f3d6a-4297-4d47-a3c3-551cd8bd86b9', CURRENT_TIMESTAMP()
);

-- Verification
SELECT jurisdiction_code, severity, COUNT(*) AS n FROM TSPR_VALIDATION_RULES GROUP BY 1, 2 ORDER BY 1, 2;