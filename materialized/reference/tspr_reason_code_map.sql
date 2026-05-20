-- =============================================================
-- INSURANCE_REGULATORY.REFERENCE.TSPR_REASON_CODE_MAP
-- Generated from RegulAI KG (single source of truth for plan rules).
-- Generated at: 2026-05-20T06:50:02+00:00
-- Source CodeList node: 'Reason Code List (RCL) — Notice Record Layout col36'
-- Neo4j: bolt://localhost:7687
--
-- DO NOT EDIT MANUALLY. Re-run `make build-reference` to regenerate.
-- =============================================================

USE DATABASE INSURANCE_REGULATORY;
USE SCHEMA REFERENCE;

CREATE OR REPLACE TABLE TSPR_REASON_CODE_MAP (
    tspr_reason_code                  CHAR(1) NOT NULL,
    jurisdiction_code                 VARCHAR(8) NOT NULL DEFAULT 'US-TX',
    description                       VARCHAR(255) NOT NULL,
    must_appear_alone                 BOOLEAN NOT NULL DEFAULT FALSE,
    credit_score_companion_required   BOOLEAN NOT NULL DEFAULT FALSE,
    constraint_rationale              VARCHAR(1024),
    -- Provenance back to the regulatory canon
    kg_code_value_id                  VARCHAR(64) NOT NULL,
    kg_source_document_id             VARCHAR(64),
    kg_source_document_title          VARCHAR(512),
    kg_canon_version                  NUMBER(10,0),
    generated_at                      TIMESTAMP_NTZ NOT NULL,
    CONSTRAINT pk_tspr_reason_code_map PRIMARY KEY (tspr_reason_code, jurisdiction_code)
) COMMENT = 'Section E reason codes (Notice Record Layout col36). Sourced from RegulAI KG. P2.3: scoped by jurisdiction; default US-TX.';

DELETE FROM TSPR_REASON_CODE_MAP;

-- Code A: Failure to pay premiums when due
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'A', 'Failure to pay premiums when due', FALSE, FALSE, NULL, '9e02510b-f844-4f95-a0be-f11b1f775506', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code B: Increase in hazard
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'B', 'Increase in hazard', FALSE, FALSE, NULL, '5230b858-a5cb-41e7-8606-7eefc5f01e67', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code C: Inspection report not accepted
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'C', 'Inspection report not accepted', FALSE, FALSE, NULL, '89493613-d5d2-4ad9-8f99-d8f73ee8d803', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code D: Claims history
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'D', 'Claims history', FALSE, FALSE, NULL, '9e38d0ac-df1c-4ae7-be23-8088deb38ac1', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code E: Exposure to loss – liability
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'E', 'Exposure to loss – liability', FALSE, FALSE, NULL, '4f2ae7a5-4ba2-4a55-912a-8c8f05180cc7', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code F: Exposure to loss – wildfire
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'F', 'Exposure to loss – wildfire', FALSE, FALSE, NULL, '478488de-8409-4819-a826-5ce0680d0b8b', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code G: Exposure to loss – wind/hail/hurricane
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'G', 'Exposure to loss – wind/hail/hurricane', FALSE, FALSE, NULL, '01f1ccc9-34d7-4560-83c5-1f982587bd18', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code H: Exposure to loss – insurer's concentration of risk
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'H', 'Exposure to loss – insurer''s concentration of risk', FALSE, FALSE, NULL, 'bb6e022e-7eb7-4ada-bef4-1beaed99e61d', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code J: Insurer withdrawing from the market
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'J', 'Insurer withdrawing from the market', FALSE, FALSE, NULL, '1ab3d8ca-871f-4785-9ba1-dbb58efbd71f', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code K: Location of risk
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'K', 'Location of risk', FALSE, FALSE, NULL, '25e440a0-dc59-4c9a-a41a-0fa4a56a550f', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code L: Credit or insurance score
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'L', 'Credit or insurance score', FALSE, FALSE, NULL, 'a362a6ae-a49a-46cf-acf6-f9879ccc9787', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code M: Condition of property – roof
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'M', 'Condition of property – roof', FALSE, FALSE, NULL, 'c55e6a7b-e1c0-4e05-96b1-6a055b44dfd3', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code N: Condition of property – tree overhang
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'N', 'Condition of property – tree overhang', FALSE, FALSE, NULL, 'cee804f6-1c0f-47dc-ba1e-dbf452d74937', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code P: Condition of property – insufficient defensible space
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'P', 'Condition of property – insufficient defensible space', FALSE, FALSE, NULL, '1c7ff55b-9890-40dd-8b20-016ca8d31cf1', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code Q: Condition of property – maintenance/occupancy/vacancy
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'Q', 'Condition of property – maintenance/occupancy/vacancy', FALSE, FALSE, NULL, '0669b441-e8ed-4641-bf95-34b46eb0bcaa', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code R: Condition of property – other
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'R', 'Condition of property – other', FALSE, FALSE, NULL, '8ab88dee-885d-4093-8d3e-04c41544bbad', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code S: Value of home
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'S', 'Value of home', FALSE, FALSE, NULL, 'a5b18048-8431-4f12-b42c-e3afceafbc33', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code T: Agent no longer appointed with insurer
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'T', 'Agent no longer appointed with insurer', FALSE, FALSE, NULL, 'f5996b2a-daa5-4763-923f-ce2a33b0eb23', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code X: Assumption Reinsurance (TWIA only)
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'X', 'Assumption Reinsurance (TWIA only)', FALSE, FALSE, NULL, '4051386a-7594-40d5-9b15-3a3989a17ca0', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code Y: At insured's request
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'Y', 'At insured''s request', FALSE, FALSE, NULL, '9cdc464a-4204-48a3-9094-f9741428e70c', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code Z: Other, insurer's action
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'Z', 'Other, insurer''s action', FALSE, FALSE, NULL, 'd8850692-e4f2-41cc-ab60-513f6f77f81d', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Verification
SELECT
    COUNT(*) AS total_codes,
    SUM(IFF(must_appear_alone, 1, 0)) AS standalone_codes,
    SUM(IFF(credit_score_companion_required, 1, 0)) AS companion_required_codes
FROM TSPR_REASON_CODE_MAP;
