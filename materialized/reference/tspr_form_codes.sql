-- =============================================================
-- INSURANCE_REGULATORY.REFERENCE.TSPR_FORM_CODES
-- TICO Section B.5 — Form (Policy) codes — TSPR field col 50
-- Generated from RegulAI KG · 2026-05-05T10:48:54+00:00
-- Source CodeList: 'Form (Policy) (FM) — Premium Record Layout col50'
-- Neo4j: neo4j+s://eaa350ec.databases.neo4j.io
--
-- DO NOT EDIT MANUALLY. Re-run `make build-reference-all`.
-- =============================================================

USE DATABASE INSURANCE_REGULATORY;
USE SCHEMA REFERENCE;

CREATE OR REPLACE TABLE TSPR_FORM_CODES (
    tspr_code                  VARCHAR(8) NOT NULL,
    description                VARCHAR(512) NOT NULL,
    -- Provenance back to the KG
    kg_code_value_id           VARCHAR(64) NOT NULL,
    kg_source_document_id      VARCHAR(64),
    kg_source_document_title   VARCHAR(512),
    kg_canon_version           NUMBER(10,0),
    kg_effective_from          DATE,
    generated_at               TIMESTAMP_NTZ NOT NULL,
    CONSTRAINT pk_tspr_form_codes PRIMARY KEY (tspr_code)
) COMMENT = 'TICO Section B.5 · Form (Policy) codes — TSPR field col 50. Sourced from RegulAI KG.';

DELETE FROM TSPR_FORM_CODES;

-- Code 1: Form (Policy) (FM) — Premium Record Layout col50 = 1
INSERT INTO TSPR_FORM_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '1', 'Form (Policy) (FM) — Premium Record Layout col50 = 1', 'cb486951-2fed-470f-8976-4b62adb31699', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 2: Form (Policy) (FM) — Premium Record Layout col50 = 2
INSERT INTO TSPR_FORM_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '2', 'Form (Policy) (FM) — Premium Record Layout col50 = 2', 'f5a9d60c-0810-4ec0-aa36-d1c926a4fe40', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 3: Form (Policy) (FM) — Premium Record Layout col50 = 3
INSERT INTO TSPR_FORM_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '3', 'Form (Policy) (FM) — Premium Record Layout col50 = 3', 'e5125b8e-7ccc-4df6-9fe1-201baae9f145', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 4: Form (Policy) (FM) — Premium Record Layout col50 = 4
INSERT INTO TSPR_FORM_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '4', 'Form (Policy) (FM) — Premium Record Layout col50 = 4', 'b70370e6-c129-43cf-aedc-9317b2377d42', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 5: Form (Policy) (FM) — Premium Record Layout col50 = 5
INSERT INTO TSPR_FORM_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '5', 'Form (Policy) (FM) — Premium Record Layout col50 = 5', 'c6206ab6-27e7-45ea-acf5-e98dea7623ef', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 9: Form (Policy) (FM) — Premium Record Layout col50 = 9
INSERT INTO TSPR_FORM_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '9', 'Form (Policy) (FM) — Premium Record Layout col50 = 9', 'c77e2e8c-72d6-488d-9ad7-51b708be7c73', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code A: Form (Policy) (FM) — Premium Record Layout col50 = A
INSERT INTO TSPR_FORM_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'A', 'Form (Policy) (FM) — Premium Record Layout col50 = A', 'a1012ad8-9aa7-4f4c-89fd-580bd0a43ad9', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code B: Form (Policy) (FM) — Premium Record Layout col50 = B
INSERT INTO TSPR_FORM_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'B', 'Form (Policy) (FM) — Premium Record Layout col50 = B', 'd313440b-b500-47ff-b24e-e8e4d7327e59', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code C: Form (Policy) (FM) — Premium Record Layout col50 = C
INSERT INTO TSPR_FORM_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'C', 'Form (Policy) (FM) — Premium Record Layout col50 = C', '4d3e8493-9161-4b2f-a0d8-c27a1174814e', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code D: Form (Policy) (FM) — Premium Record Layout col50 = D
INSERT INTO TSPR_FORM_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'D', 'Form (Policy) (FM) — Premium Record Layout col50 = D', 'f3d8f9c1-ad67-4860-9b0c-a587b26d61c9', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code E: Form (Policy) (FM) — Premium Record Layout col50 = E
INSERT INTO TSPR_FORM_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'E', 'Form (Policy) (FM) — Premium Record Layout col50 = E', '1119d9e5-031c-428a-806e-ee12ee228a38', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code F: Form (Policy) (FM) — Premium Record Layout col50 = F
INSERT INTO TSPR_FORM_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'F', 'Form (Policy) (FM) — Premium Record Layout col50 = F', 'c7fe8a85-3404-4bfd-9cbe-3e5cf8c68b07', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code G: Form (Policy) (FM) — Premium Record Layout col50 = G
INSERT INTO TSPR_FORM_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'G', 'Form (Policy) (FM) — Premium Record Layout col50 = G', '69461443-d5f9-452d-8b8d-160d674f7ad1', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code H: Form (Policy) (FM) — Premium Record Layout col50 = H
INSERT INTO TSPR_FORM_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'H', 'Form (Policy) (FM) — Premium Record Layout col50 = H', '9538561b-cba9-4613-a95d-febf54e9f990', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code I: Form (Policy) (FM) — Premium Record Layout col50 = I
INSERT INTO TSPR_FORM_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'I', 'Form (Policy) (FM) — Premium Record Layout col50 = I', '2fd173ae-ca13-4c24-b320-852c4ad0b91b', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code J: Form (Policy) (FM) — Premium Record Layout col50 = J
INSERT INTO TSPR_FORM_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'J', 'Form (Policy) (FM) — Premium Record Layout col50 = J', 'ec2ef819-11df-4563-96f7-88681327acf1', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code K: Form (Policy) (FM) — Premium Record Layout col50 = K
INSERT INTO TSPR_FORM_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'K', 'Form (Policy) (FM) — Premium Record Layout col50 = K', 'e6616571-76fc-4d6b-adab-a12e778b762b', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Verification
SELECT COUNT(*) AS rows_loaded FROM TSPR_FORM_CODES;
