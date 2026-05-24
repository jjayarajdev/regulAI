-- =============================================================
-- INSURANCE_REGULATORY.REFERENCE.TSPR_REASON_CODE_MAP
-- Generated from RegulAI KG (single source of truth for plan rules).
-- Source CodeList node: 'Reason Code List (RCL) — Notice Record Layout col36'
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
    'A', 'Failure to pay premiums when due', FALSE, FALSE, NULL, '87695666-75d9-4db2-95a6-31ef1241f89a', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code B: Increase in hazard
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'B', 'Increase in hazard', FALSE, FALSE, NULL, '53543522-c6ac-4bfd-ab92-9fc6f6e5045e', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code C: Inspection report not accepted
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'C', 'Inspection report not accepted', FALSE, FALSE, NULL, '9a3cb9d8-2749-4d2e-875b-e941c200dfde', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code D: Claims history
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'D', 'Claims history', FALSE, FALSE, NULL, '1a345d8a-28ee-418f-a3f8-8ef3bc5b72a7', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code E: Exposure to loss – liability
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'E', 'Exposure to loss – liability', FALSE, FALSE, NULL, 'bc401069-717b-49ef-93ba-8ed5d83ca975', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code F: Exposure to loss – wildfire
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'F', 'Exposure to loss – wildfire', FALSE, FALSE, NULL, 'a01a7ab4-b21c-426e-bcfa-c379281cfd3c', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code G: Exposure to loss – wind/hail/hurricane
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'G', 'Exposure to loss – wind/hail/hurricane', FALSE, FALSE, NULL, '1222dc9e-a46f-48f9-b7b0-67b1e8de0fa6', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code H: Exposure to loss – insurer's concentration of risk
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'H', 'Exposure to loss – insurer''s concentration of risk', FALSE, FALSE, NULL, '065e8fbe-9948-4225-96dc-594965065dd0', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code J: Insurer withdrawing from the market
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'J', 'Insurer withdrawing from the market', FALSE, FALSE, NULL, 'c6fcb3aa-10ad-4030-bebf-bbe9d80e4956', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code K: Location of risk
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'K', 'Location of risk', FALSE, FALSE, NULL, '0594e5d6-8f7f-4b08-a13c-7b3c41ca6ded', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code L: Credit or insurance score
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'L', 'Credit or insurance score', FALSE, FALSE, NULL, '71f7e1fb-7bcb-4a2f-b1f7-1db089e3d070', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code M: Condition of property – roof
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'M', 'Condition of property – roof', FALSE, FALSE, NULL, 'a11a1943-ae21-43b8-abac-a50834ba26c0', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code N: Condition of property – tree overhang
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'N', 'Condition of property – tree overhang', FALSE, FALSE, NULL, '397f7a99-c1c6-4e61-b24a-9a4ed70b7fda', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code P: Condition of property – insufficient defensible space
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'P', 'Condition of property – insufficient defensible space', FALSE, FALSE, NULL, 'e83100b2-ae69-4849-a468-0af655c2b155', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code Q: Condition of property – maintenance/occupancy/vacancy
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'Q', 'Condition of property – maintenance/occupancy/vacancy', FALSE, FALSE, NULL, '3e2118d7-220a-413b-a9a0-02c148757f0f', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code R: Condition of property – other
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'R', 'Condition of property – other', FALSE, FALSE, NULL, 'df5a6cd7-c74d-4488-979c-4fa91d759336', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code S: Value of home
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'S', 'Value of home', FALSE, FALSE, NULL, '86bdbcbf-cc43-45a1-a217-3a8f6f08c6d3', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code T: Agent no longer appointed with insurer
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'T', 'Agent no longer appointed with insurer', FALSE, FALSE, NULL, '15d0ebe1-548b-4df4-ac0e-610ba6589d68', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code X: Assumption Reinsurance (TWIA only)
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'X', 'Assumption Reinsurance (TWIA only)', FALSE, FALSE, NULL, 'ffef1f93-849e-4d85-a9f0-5e70e24c5345', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code Y: At insured's request
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'Y', 'At insured''s request', FALSE, FALSE, NULL, '0bf6e1e6-c9fd-48f2-b13e-3522ae57a6b5', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code Z: Other, insurer's action
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'Z', 'Other, insurer''s action', FALSE, FALSE, NULL, '82186a48-5770-43ff-83cd-62a39d9353e5', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Verification
SELECT
    COUNT(*) AS total_codes,
    SUM(IFF(must_appear_alone, 1, 0)) AS standalone_codes,
    SUM(IFF(credit_score_companion_required, 1, 0)) AS companion_required_codes
FROM TSPR_REASON_CODE_MAP;
