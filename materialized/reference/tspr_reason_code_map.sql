-- =============================================================
-- INSURANCE_REGULATORY.REFERENCE.TSPR_REASON_CODE_MAP
-- Generated from RegulAI KG (single source of truth for plan rules).
-- Generated at: 2026-05-05T06:16:11+00:00
-- Source CodeList node: 'Reason Code List (RCL) — Notice Record Layout col36'
-- Neo4j: neo4j+s://eaa350ec.databases.neo4j.io
--
-- DO NOT EDIT MANUALLY. Re-run `make build-reference` to regenerate.
-- =============================================================

USE DATABASE INSURANCE_REGULATORY;
USE SCHEMA REFERENCE;

CREATE OR REPLACE TABLE TSPR_REASON_CODE_MAP (
    tspr_reason_code                  CHAR(1) NOT NULL,
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
    CONSTRAINT pk_tspr_reason_code_map PRIMARY KEY (tspr_reason_code)
) COMMENT = 'Section E reason codes (Notice Record Layout col36). Sourced from RegulAI KG.';

DELETE FROM TSPR_REASON_CODE_MAP;

-- Code A: Failure to pay premiums when due
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'A', 'Failure to pay premiums when due', FALSE, FALSE, NULL, '517d3655-306d-4ea3-b4dc-4b677277471a', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code B: Increase in hazard
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'B', 'Increase in hazard', FALSE, FALSE, NULL, 'b36e59a2-e8cc-46bb-b75a-e948fc647bb7', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code C: Inspection report not accepted
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'C', 'Inspection report not accepted', FALSE, FALSE, NULL, '90e6ea7d-c771-4906-9eb4-42a2af4dadb7', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code D: Claims history
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'D', 'Claims history', FALSE, FALSE, NULL, 'ed87d63e-3ad4-4145-9373-fbfe886d1153', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code E: Exposure to loss – liability
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'E', 'Exposure to loss – liability', FALSE, FALSE, NULL, '88258cef-8851-4517-a0b7-9fea9c3f933c', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code F: Exposure to loss – wildfire
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'F', 'Exposure to loss – wildfire', FALSE, FALSE, NULL, '6c15fb5d-2023-41fa-ae4c-421d65efda03', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code G: Exposure to loss – wind/hail/hurricane
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'G', 'Exposure to loss – wind/hail/hurricane', FALSE, FALSE, NULL, '5d0dd83b-42ea-4af3-a965-9163c50e1bea', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code H: Exposure to loss – insurer's concentration of risk
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'H', 'Exposure to loss – insurer''s concentration of risk', FALSE, FALSE, NULL, '6893042c-eb29-4e4f-b5a3-58ae9cd2d601', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code J: Insurer withdrawing from the market
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'J', 'Insurer withdrawing from the market', TRUE, FALSE, 'Rule A.34 — market withdrawal (J) cannot appear alongside any other reason code; it is a complete and standalone reason.', '911bd8d9-63b4-4ea4-916d-d97772ef1524', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code K: Location of risk
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'K', 'Location of risk', FALSE, FALSE, NULL, 'a4695fdb-8175-470c-8014-f5d839eb5d5b', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code L: Credit or insurance score
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'L', 'Credit or insurance score', FALSE, TRUE, 'Tex. Ins. Code §559.052(a)(2) — credit/insurance score may not be the sole reason for cancellation, nonrenewal, or declination.', 'a67f96c1-3c3c-480d-b7f9-f73bad118af1', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code M: Condition of property – roof
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'M', 'Condition of property – roof', FALSE, FALSE, NULL, 'dfb77386-587a-46bb-89ed-5e79941d3fca', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code N: Condition of property – tree overhang
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'N', 'Condition of property – tree overhang', FALSE, FALSE, NULL, '16fec167-419f-4538-a05e-810e225ba56c', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code P: Condition of property – insufficient defensible space
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'P', 'Condition of property – insufficient defensible space', FALSE, FALSE, NULL, 'b427482d-8684-480e-8a78-36f4a4c7aefc', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code Q: Condition of property – maintenance/occupancy/vacancy
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'Q', 'Condition of property – maintenance/occupancy/vacancy', FALSE, FALSE, NULL, 'a4791ea3-00a0-41c7-b857-649e96df2f12', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code R: Condition of property – other
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'R', 'Condition of property – other', FALSE, FALSE, NULL, '88584749-515b-4c5b-afa5-95b392968502', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code S: Value of home
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'S', 'Value of home', FALSE, FALSE, NULL, 'd5e54430-868e-41f8-8526-d5761229a6d0', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code T: Agent no longer appointed with insurer
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'T', 'Agent no longer appointed with insurer', FALSE, FALSE, NULL, 'cd9d04fa-26d5-4de8-98be-13141d7c9b16', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code X: Assumption Reinsurance (TWIA only)
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'X', 'Assumption Reinsurance (TWIA only)', FALSE, FALSE, NULL, 'c0bc7550-4ef0-426e-87c7-e6f9ddac94a9', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code Y: At insured's request
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'Y', 'At insured''s request', FALSE, FALSE, NULL, '68fbbd15-d9e3-4867-bf89-540e21570b3c', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Code Z: Other, insurer's action
INSERT INTO TSPR_REASON_CODE_MAP (
    tspr_reason_code, description, must_appear_alone, credit_score_companion_required, constraint_rationale, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, generated_at
) VALUES (
    'Z', 'Other, insurer''s action', FALSE, FALSE, NULL, '397c863a-f204-4803-8f1e-a539ff354df8', NULL, NULL, 1, CURRENT_TIMESTAMP()
);

-- Verification
SELECT
    COUNT(*) AS total_codes,
    SUM(IFF(must_appear_alone, 1, 0)) AS standalone_codes,
    SUM(IFF(credit_score_companion_required, 1, 0)) AS companion_required_codes
FROM TSPR_REASON_CODE_MAP;
