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
    'A', 'Failure to pay premiums when due', FALSE, FALSE, NULL, '111d598d-8769-5999-858f-3ee91f127be2', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code B: Increase in hazard
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'B', 'Increase in hazard', FALSE, FALSE, NULL, '6d06ed55-d799-5f80-b743-a2f8f9bf2253', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code C: Inspection report not accepted
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'C', 'Inspection report not accepted', FALSE, FALSE, NULL, '436d9ac4-5c33-53f7-b838-60a9a923892c', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code D: Claims history
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'D', 'Claims history', FALSE, FALSE, NULL, 'c1dacece-c48d-5e32-9940-e8852ecd1d44', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code E: Exposure to loss – liability
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'E', 'Exposure to loss – liability', FALSE, FALSE, NULL, '25941701-2eef-5900-8622-84e86d50a153', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code F: Exposure to loss – wildfire
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'F', 'Exposure to loss – wildfire', FALSE, FALSE, NULL, '2079a84a-db1b-595a-b5f5-e7ac31e3570a', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code G: Exposure to loss – wind/hail/hurricane
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'G', 'Exposure to loss – wind/hail/hurricane', FALSE, FALSE, NULL, 'd79d3ea3-9f8a-5003-a595-a11e1b0de72f', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code H: Exposure to loss – insurer's concentration of risk
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'H', 'Exposure to loss – insurer''s concentration of risk', FALSE, FALSE, NULL, 'd2388f2e-4ba0-5d42-94b4-57b8d382f152', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code J: Insurer withdrawing from the market
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'J', 'Insurer withdrawing from the market', FALSE, FALSE, NULL, '7d2d7e57-2ad6-5342-a688-af973618a102', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code K: Location of risk
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'K', 'Location of risk', FALSE, FALSE, NULL, '74258dde-46e6-56cd-ad7c-b9deddc1e0cd', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code L: Credit or insurance score
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'L', 'Credit or insurance score', FALSE, FALSE, NULL, '4493d4dc-6845-581d-862f-7e7286924532', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code M: Condition of property – roof
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'M', 'Condition of property – roof', FALSE, FALSE, NULL, 'd61e97ad-900a-59ca-9b60-76491bce5e9c', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code N: Condition of property – tree overhang
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'N', 'Condition of property – tree overhang', FALSE, FALSE, NULL, '5ed740d0-4fdd-599d-8378-dda7b6cb285f', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code P: Condition of property – insufficient defensible space
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'P', 'Condition of property – insufficient defensible space', FALSE, FALSE, NULL, '1bcbf492-72ce-5a19-956b-fb4cce15cff9', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code Q: Condition of property – maintenance/occupancy/vacancy
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'Q', 'Condition of property – maintenance/occupancy/vacancy', FALSE, FALSE, NULL, '475bcf18-291f-521d-bf04-58eb53120acd', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code R: Condition of property – other
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'R', 'Condition of property – other', FALSE, FALSE, NULL, '91ca4711-ecc5-513e-aef2-3461093363b9', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code S: Value of home
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'S', 'Value of home', FALSE, FALSE, NULL, 'e4dce0fa-0aef-5897-8aaf-e51c3649f5b8', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code T: Agent no longer appointed with insurer
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'T', 'Agent no longer appointed with insurer', FALSE, FALSE, NULL, '93f74fe3-2eef-5425-8d2d-20a0509aeeab', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code X: Assumption Reinsurance (TWIA only)
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'X', 'Assumption Reinsurance (TWIA only)', FALSE, FALSE, NULL, '6db5289b-c966-5852-af4d-ac40bb7b7eaa', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code Y: At insured's request
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'Y', 'At insured''s request', FALSE, FALSE, NULL, '06056d5c-2a0e-5f47-8971-ba9a22adbdb5', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code Z: Other, insurer's action
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'Z', 'Other, insurer''s action', FALSE, FALSE, NULL, '72ba319e-c5a9-5fe0-9d52-07cea2980af7', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Verification
SELECT
    COUNT(*) AS total_codes,
    SUM(IFF(must_appear_alone, 1, 0)) AS standalone_codes,
    SUM(IFF(credit_score_companion_required, 1, 0)) AS companion_required_codes
FROM TSPR_REASON_CODE_MAP;
