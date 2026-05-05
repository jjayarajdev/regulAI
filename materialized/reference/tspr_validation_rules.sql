-- =============================================================
-- INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES
-- TICO Section A — executable plan rules generated from RegulAI KG
-- Generated at: 2026-05-05T12:13:51+00:00
-- Neo4j: neo4j+s://eaa350ec.databases.neo4j.io
-- =============================================================

USE DATABASE INSURANCE_REGULATORY;
USE SCHEMA REFERENCE;

CREATE OR REPLACE TABLE TSPR_VALIDATION_RULES (
    rule_id              VARCHAR(64)  NOT NULL,
    rule_number          VARCHAR(32)  NOT NULL,
    rule_name            VARCHAR(512) NOT NULL,
    section              VARCHAR(8),
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
) COMMENT = 'TICO Section A — executable validation rules. Sourced from RegulAI KG.';

DELETE FROM TSPR_VALIDATION_RULES;

-- A.34-valid-codes: Reason codes must be defined in the plan
INSERT INTO TSPR_VALIDATION_RULES (
    rule_id, rule_number, rule_name, section, target_table, target_id_expr, violation_sql, violation_reason, severity, citation, validation_version, kg_canon_version, kg_source_document_id, generated_at
) VALUES (
    '287871fa-72fc-4a42-8300-9377d69e97db-validity', 'A.34-valid-codes', 'Reason codes must be defined in the plan', 'A', 'BRONZE.GW_PC_JOB', 'j.publicid', 'COALESCE(j.declinereason, j.cancellationreason, j.nonrenewalreason) IS NOT NULL
            AND NOT COALESCE(j.declinereason, j.cancellationreason, j.nonrenewalreason) RLIKE
              ''^('' || (
                SELECT LISTAGG(tspr_reason_code, ''|'') WITHIN GROUP (ORDER BY tspr_reason_code)
                FROM INSURANCE_REGULATORY.REFERENCE.TSPR_REASON_CODE_MAP
              ) || '')+$''', 'One or more reason letters are not part of the published Reason Code List', 'ERROR', 'TICO Stat Plan Rule A.34 / Section E', 8, 1, NULL, CURRENT_TIMESTAMP()
);

-- 22: Rule A.22 — Company Number
INSERT INTO TSPR_VALIDATION_RULES (
    rule_id, rule_number, rule_name, section, target_table, target_id_expr, violation_sql, violation_reason, severity, citation, validation_version, kg_canon_version, kg_source_document_id, generated_at
) VALUES (
    '192283ed-3597-46fb-899f-6bc258c450e8', '22', 'Rule A.22 — Company Number', 'A', 'BRONZE.GW_PC_POLICYPERIOD', 'j.publicid', 'j.naic_number IS NULL
            OR LENGTH(TRIM(j.naic_number)) <> 5
            OR NOT REGEXP_LIKE(j.naic_number, ''^[0-9]{5}$'')', 'NAIC company number must be present and exactly 5 numeric digits', 'ERROR', 'TICO Stat Plan Rule A.22', 8, 1, '0a98f58e-bf63-4fd8-8ca9-069a4f3b4c70', CURRENT_TIMESTAMP()
);

-- 34: Rule A.34 — Reason Codes
INSERT INTO TSPR_VALIDATION_RULES (
    rule_id, rule_number, rule_name, section, target_table, target_id_expr, violation_sql, violation_reason, severity, citation, validation_version, kg_canon_version, kg_source_document_id, generated_at
) VALUES (
    '287871fa-72fc-4a42-8300-9377d69e97db', '34', 'Rule A.34 — Reason Codes', 'A', 'BRONZE.GW_PC_JOB', 'j.publicid', 'LENGTH(COALESCE(j.declinereason, j.cancellationreason, j.nonrenewalreason)) = 1
            AND COALESCE(j.declinereason, j.cancellationreason, j.nonrenewalreason) IN (
              SELECT tspr_reason_code FROM INSURANCE_REGULATORY.REFERENCE.TSPR_REASON_CODE_MAP
              WHERE credit_score_companion_required = TRUE
            )', 'Reason Code L (credit/insurance score) requires at least one companion reason code', 'ERROR', 'Tex. Ins. Code §559.052(a)(2); TICO Stat Plan Rule A.34', 8, 1, '9d7085b4-0471-449f-af85-01b57bce09a9', CURRENT_TIMESTAMP()
);

-- 34: Rule A.34 — Reporting Reason Codes for Cancellation, Nonrenewal, and Declination Notices
INSERT INTO TSPR_VALIDATION_RULES (
    rule_id, rule_number, rule_name, section, target_table, target_id_expr, violation_sql, violation_reason, severity, citation, validation_version, kg_canon_version, kg_source_document_id, generated_at
) VALUES (
    '2d01fd58-bc62-421e-a211-c740371fce4a', '34', 'Rule A.34 — Reporting Reason Codes for Cancellation, Nonrenewal, and Declination Notices', 'A', 'BRONZE.GW_PC_JOB', 'j.publicid', 'LENGTH(COALESCE(j.declinereason, j.cancellationreason, j.nonrenewalreason)) > 1
            AND COALESCE(j.declinereason, j.cancellationreason, j.nonrenewalreason) LIKE ANY (
              SELECT ''%'' || tspr_reason_code || ''%''
              FROM INSURANCE_REGULATORY.REFERENCE.TSPR_REASON_CODE_MAP
              WHERE must_appear_alone = TRUE
            )', 'A reason code marked must_appear_alone (e.g. J — market withdrawal) cannot be combined with others', 'ERROR', 'TICO Stat Plan Rule A.34', 8, 1, '0a98f58e-bf63-4fd8-8ca9-069a4f3b4c70', CURRENT_TIMESTAMP()
);

-- Verification
SELECT severity, COUNT(*) AS n FROM TSPR_VALIDATION_RULES GROUP BY severity;