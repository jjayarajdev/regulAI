-- =============================================================
-- INSURANCE_REGULATORY.REFERENCE.TSPR_CAUSE_OF_LOSS_CODES
-- TICO Section B.12 — Cause of Loss codes — TSPR field cols 90-91
-- Generated from RegulAI KG · 2026-05-05T10:48:56+00:00
-- Source CodeList: 'Cause of Loss Code List'
-- Neo4j: neo4j+s://eaa350ec.databases.neo4j.io
--
-- DO NOT EDIT MANUALLY. Re-run `make build-reference-all`.
-- =============================================================

USE DATABASE INSURANCE_REGULATORY;
USE SCHEMA REFERENCE;

CREATE OR REPLACE TABLE TSPR_CAUSE_OF_LOSS_CODES (
    tspr_code                  VARCHAR(8) NOT NULL,
    description                VARCHAR(512) NOT NULL,
    -- Provenance back to the KG
    kg_code_value_id           VARCHAR(64) NOT NULL,
    kg_source_document_id      VARCHAR(64),
    kg_source_document_title   VARCHAR(512),
    kg_canon_version           NUMBER(10,0),
    kg_effective_from          DATE,
    generated_at               TIMESTAMP_NTZ NOT NULL,
    CONSTRAINT pk_tspr_cause_of_loss_codes PRIMARY KEY (tspr_code)
) COMMENT = 'TICO Section B.12 · Cause of Loss codes — TSPR field cols 90-91. Sourced from RegulAI KG.';

DELETE FROM TSPR_CAUSE_OF_LOSS_CODES;

-- Code 05: Fire — Internal Source
INSERT INTO TSPR_CAUSE_OF_LOSS_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '05', 'Fire — Internal Source', 'b4d345ff-61c1-4bc8-8c13-5852e07b8035', '6a57faff-c1ae-43ad-8638-7350113f7c57', 'Commissioner''s Bulletin # B-2026-Q3-104 — Revisions to the Texas Statistical Plan for Residential Risks: Cause of Loss reporting for named storm events', 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 10: Fire — External Source (Including fire caused by lightning)
INSERT INTO TSPR_CAUSE_OF_LOSS_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '10', 'Fire — External Source (Including fire caused by lightning)', '3c661f0c-911d-4853-ae34-4f63db8ee3f6', '6a57faff-c1ae-43ad-8638-7350113f7c57', 'Commissioner''s Bulletin # B-2026-Q3-104 — Revisions to the Texas Statistical Plan for Residential Risks: Cause of Loss reporting for named storm events', 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 26: Named Storm Wind — wind losses associated with a named storm event, including hurricanes and named tropical storms designated by the National Weather Service or its successor agency.
INSERT INTO TSPR_CAUSE_OF_LOSS_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '26', 'Named Storm Wind — wind losses associated with a named storm event, including hurricanes and named tropical storms designated by the National Weather Service or its successor agency.', '7cfd4d68-e050-4b34-9832-ae1f343d37b2', '6a57faff-c1ae-43ad-8638-7350113f7c57', 'Commissioner''s Bulletin # B-2026-Q3-104 — Revisions to the Texas Statistical Plan for Residential Risks: Cause of Loss reporting for named storm events', 1, DATE '2026-10-01', CURRENT_TIMESTAMP()
);

-- Code 30: Hail
INSERT INTO TSPR_CAUSE_OF_LOSS_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '30', 'Hail', 'd08e78a5-29d6-4e59-980e-b1422f292ded', '6a57faff-c1ae-43ad-8638-7350113f7c57', 'Commissioner''s Bulletin # B-2026-Q3-104 — Revisions to the Texas Statistical Plan for Residential Risks: Cause of Loss reporting for named storm events', 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 32: Flood or Rising Water
INSERT INTO TSPR_CAUSE_OF_LOSS_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '32', 'Flood or Rising Water', 'add70e2f-e213-4d53-b480-48862e5b8e68', '6a57faff-c1ae-43ad-8638-7350113f7c57', 'Commissioner''s Bulletin # B-2026-Q3-104 — Revisions to the Texas Statistical Plan for Residential Risks: Cause of Loss reporting for named storm events', 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 75: Burglary, Theft, Robbery
INSERT INTO TSPR_CAUSE_OF_LOSS_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '75', 'Burglary, Theft, Robbery', 'b82022c7-448a-49f2-a94d-1622836b8fd8', '6a57faff-c1ae-43ad-8638-7350113f7c57', 'Commissioner''s Bulletin # B-2026-Q3-104 — Revisions to the Texas Statistical Plan for Residential Risks: Cause of Loss reporting for named storm events', 1, NULL, CURRENT_TIMESTAMP()
);

-- Verification
SELECT COUNT(*) AS rows_loaded FROM TSPR_CAUSE_OF_LOSS_CODES;
