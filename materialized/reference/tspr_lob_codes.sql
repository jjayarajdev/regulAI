-- =============================================================
-- INSURANCE_REGULATORY.REFERENCE.TSPR_LOB_CODES
-- TICO Section B.4 — Line of Business codes (LOB) — TSPR field col 41
-- Generated from RegulAI KG · 2026-05-05T10:48:50+00:00
-- Source CodeList: 'Line of Business (LOB) — Loss Record Layout col41'
-- Neo4j: neo4j+s://eaa350ec.databases.neo4j.io
--
-- DO NOT EDIT MANUALLY. Re-run `make build-reference-all`.
-- =============================================================

USE DATABASE INSURANCE_REGULATORY;
USE SCHEMA REFERENCE;

CREATE OR REPLACE TABLE TSPR_LOB_CODES (
    tspr_code                  VARCHAR(8) NOT NULL,
    description                VARCHAR(512) NOT NULL,
    -- Provenance back to the KG
    kg_code_value_id           VARCHAR(64) NOT NULL,
    kg_source_document_id      VARCHAR(64),
    kg_source_document_title   VARCHAR(512),
    kg_canon_version           NUMBER(10,0),
    kg_effective_from          DATE,
    generated_at               TIMESTAMP_NTZ NOT NULL,
    CONSTRAINT pk_tspr_lob_codes PRIMARY KEY (tspr_code)
) COMMENT = 'TICO Section B.4 · Line of Business codes (LOB) — TSPR field col 41. Sourced from RegulAI KG.';

DELETE FROM TSPR_LOB_CODES;

-- Code 02: Line of Business (LOB) — Loss Record Layout col41 = 02
INSERT INTO TSPR_LOB_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '02', 'Line of Business (LOB) — Loss Record Layout col41 = 02', 'e4a76a63-2bb7-4f19-a3e8-617eaa903941', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 03: Line of Business (LOB) — Loss Record Layout col41 = 03
INSERT INTO TSPR_LOB_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '03', 'Line of Business (LOB) — Loss Record Layout col41 = 03', 'a0c21041-4ca3-47eb-a3ef-75fe71f31589', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 10: Line of Business (LOB) — Loss Record Layout col41 = 10
INSERT INTO TSPR_LOB_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '10', 'Line of Business (LOB) — Loss Record Layout col41 = 10', 'ce8d81ea-01ae-46ec-a9ac-a904b4df1ad4', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 11: Line of Business (LOB) — Loss Record Layout col41 = 11
INSERT INTO TSPR_LOB_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '11', 'Line of Business (LOB) — Loss Record Layout col41 = 11', 'e5c810b1-1ade-4a5d-9511-f4ea83502ea7', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 12: Line of Business (LOB) — Loss Record Layout col41 = 12
INSERT INTO TSPR_LOB_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '12', 'Line of Business (LOB) — Loss Record Layout col41 = 12', '82bff4b9-9856-456d-9616-866e81801519', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 13: Line of Business (LOB) — Loss Record Layout col41 = 13
INSERT INTO TSPR_LOB_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '13', 'Line of Business (LOB) — Loss Record Layout col41 = 13', '9ba8ecff-d3b7-45ce-94a6-0e4923d91653', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 14: Line of Business (LOB) — Loss Record Layout col41 = 14
INSERT INTO TSPR_LOB_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '14', 'Line of Business (LOB) — Loss Record Layout col41 = 14', '0f5c43c7-a22f-4f7e-a536-e5795931abd3', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 15: Line of Business (LOB) — Loss Record Layout col41 = 15
INSERT INTO TSPR_LOB_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '15', 'Line of Business (LOB) — Loss Record Layout col41 = 15', 'e2c5b176-cc89-41f7-894d-2fe6283b3447', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 16: Line of Business (LOB) — Loss Record Layout col41 = 16
INSERT INTO TSPR_LOB_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '16', 'Line of Business (LOB) — Loss Record Layout col41 = 16', 'feb2f179-3c86-4c9b-a9f0-6c45734361f2', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 20: Line of Business (LOB) — Loss Record Layout col41 = 20
INSERT INTO TSPR_LOB_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '20', 'Line of Business (LOB) — Loss Record Layout col41 = 20', '04dfa8c6-65a2-47f9-b2ab-c93ef93b9b1e', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 25: Line of Business (LOB) — Loss Record Layout col41 = 25
INSERT INTO TSPR_LOB_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '25', 'Line of Business (LOB) — Loss Record Layout col41 = 25', 'b1de600d-8bba-49d0-8e95-a436840797af', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 26: Line of Business (LOB) — Loss Record Layout col41 = 26
INSERT INTO TSPR_LOB_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '26', 'Line of Business (LOB) — Loss Record Layout col41 = 26', '64e07582-f9cd-4f36-816c-337cc5544645', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 27: Line of Business (LOB) — Loss Record Layout col41 = 27
INSERT INTO TSPR_LOB_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '27', 'Line of Business (LOB) — Loss Record Layout col41 = 27', '80deba78-9d0d-42bd-a564-d6364baa0791', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 28: Line of Business (LOB) — Loss Record Layout col41 = 28
INSERT INTO TSPR_LOB_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '28', 'Line of Business (LOB) — Loss Record Layout col41 = 28', '9c82187b-59d7-4efb-9723-fec5851d89c1', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 29: Line of Business (LOB) — Loss Record Layout col41 = 29
INSERT INTO TSPR_LOB_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '29', 'Line of Business (LOB) — Loss Record Layout col41 = 29', 'dd189c99-44d1-483e-93a3-10d62eae1573', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 35: Line of Business (LOB) — Loss Record Layout col41 = 35
INSERT INTO TSPR_LOB_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '35', 'Line of Business (LOB) — Loss Record Layout col41 = 35', '3acd9e49-5ca2-4055-b8ef-ccdb554a00a1', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 50: Line of Business (LOB) — Loss Record Layout col41 = 50
INSERT INTO TSPR_LOB_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '50', 'Line of Business (LOB) — Loss Record Layout col41 = 50', 'd0049723-a548-4130-b312-c517bdcc1209', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Verification
SELECT COUNT(*) AS rows_loaded FROM TSPR_LOB_CODES;
