-- =============================================================
-- INSURANCE_REGULATORY.REFERENCE.TSPR_ROOF_COVERAGE_TYPE_CODES
-- TICO Section B.8A — Roof Coverage Type codes — TSPR field col 153
-- Generated from RegulAI KG · 2026-05-05T10:48:58+00:00
-- Source CodeList: 'Roof Coverage Type (RCT) — Loss Record Layout col153'
-- Neo4j: neo4j+s://eaa350ec.databases.neo4j.io
--
-- DO NOT EDIT MANUALLY. Re-run `make build-reference-all`.
-- =============================================================

USE DATABASE INSURANCE_REGULATORY;
USE SCHEMA REFERENCE;

CREATE OR REPLACE TABLE TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code                  VARCHAR(8) NOT NULL,
    description                VARCHAR(512) NOT NULL,
    -- Provenance back to the KG
    kg_code_value_id           VARCHAR(64) NOT NULL,
    kg_source_document_id      VARCHAR(64),
    kg_source_document_title   VARCHAR(512),
    kg_canon_version           NUMBER(10,0),
    kg_effective_from          DATE,
    generated_at               TIMESTAMP_NTZ NOT NULL,
    CONSTRAINT pk_tspr_roof_coverage_type_codes PRIMARY KEY (tspr_code)
) COMMENT = 'TICO Section B.8A · Roof Coverage Type codes — TSPR field col 153. Sourced from RegulAI KG.';

DELETE FROM TSPR_ROOF_COVERAGE_TYPE_CODES;

-- Code 0: Roof Coverage Type (RCT) — Loss Record Layout col153 = 0
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '0', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = 0', 'd3bd7a14-39cf-45c3-aaeb-6776baaea92f', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 1: Roof Coverage Type (RCT) — Loss Record Layout col153 = 1
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '1', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = 1', '164e4262-f4b2-490d-94c2-a3b5d9b8c8f3', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 154: Roof Coverage Type (RCT) — Loss Record Layout col153 = 154
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '154', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = 154', 'f05dcdb4-6cde-4fd4-9751-8730a4a69c70', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 155: Roof Coverage Type (RCT) — Loss Record Layout col153 = 155
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '155', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = 155', '3624a274-050c-4cfc-b71d-96068e36255e', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 2: Roof Coverage Type (RCT) — Loss Record Layout col153 = 2
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '2', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = 2', '8f93a0a1-77e8-4360-a906-12129a648d22', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 3: Roof Coverage Type (RCT) — Loss Record Layout col153 = 3
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '3', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = 3', 'ab96da3b-f364-45f6-8e2d-ba19f7016661', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 4: Roof Coverage Type (RCT) — Loss Record Layout col153 = 4
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '4', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = 4', '905da32c-0d97-4693-b3e9-b46e26c2c67b', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 5: Roof Coverage Type (RCT) — Loss Record Layout col153 = 5
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '5', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = 5', 'e496e39e-4c35-4c43-b756-370eecaeaba6', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code 7: Roof Coverage Type (RCT) — Loss Record Layout col153 = 7
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    '7', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = 7', '15e4bcbb-371b-4fb1-87df-8bd095ddd779', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code A: Roof Coverage Type (RCT) — Loss Record Layout col153 = A
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'A', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = A', '9a8670ac-dbb3-45e0-8bea-d61dd00b72ae', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code B: Roof Coverage Type (RCT) — Loss Record Layout col153 = B
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'B', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = B', 'f64fc044-1d63-4fde-9e05-911c88af1971', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code C: Roof Coverage Type (RCT) — Loss Record Layout col153 = C
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'C', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = C', 'a569b48c-43da-427b-910e-dfc25e5ab818', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code D: Roof Coverage Type (RCT) — Loss Record Layout col153 = D
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'D', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = D', '8ab85478-472d-474d-969e-8d0cf6edf996', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code E: Roof Coverage Type (RCT) — Loss Record Layout col153 = E
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'E', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = E', '7ec578dc-6075-4438-80cd-0c39beb40231', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code F: Roof Coverage Type (RCT) — Loss Record Layout col153 = F
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'F', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = F', '4a4e274e-3dca-4383-8723-42675c2087c5', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code G: Roof Coverage Type (RCT) — Loss Record Layout col153 = G
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'G', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = G', '3df67595-e8d9-4a50-ba86-168ae1fa6469', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code H: Roof Coverage Type (RCT) — Loss Record Layout col153 = H
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'H', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = H', '9a02afec-4cfe-42d9-a22d-059c65a8bd56', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code I: Roof Coverage Type (RCT) — Loss Record Layout col153 = I
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'I', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = I', 'c6511eb7-8df7-48ce-9dc1-99065c48dd43', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code J: Roof Coverage Type (RCT) — Loss Record Layout col153 = J
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'J', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = J', 'f778f27f-23c6-4423-808d-8942a4c93164', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code K: Roof Coverage Type (RCT) — Loss Record Layout col153 = K
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'K', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = K', '007fdf9d-e7c8-4bc3-9ec7-2b30328a2e98', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code L: Roof Coverage Type (RCT) — Loss Record Layout col153 = L
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'L', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = L', '994645bb-852f-4c3e-8b31-6f1f6d303916', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code M: Roof Coverage Type (RCT) — Loss Record Layout col153 = M
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'M', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = M', '6802ae90-4677-4ce5-884b-9e60797c5c13', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code N: Roof Coverage Type (RCT) — Loss Record Layout col153 = N
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'N', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = N', 'e39ebf26-6381-4c0f-a6b8-041c21fd713f', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code O: Roof Coverage Type (RCT) — Loss Record Layout col153 = O
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'O', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = O', '612fb848-af7f-4003-9ed4-21b08a7c7ef1', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code P: Roof Coverage Type (RCT) — Loss Record Layout col153 = P
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'P', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = P', 'edbcdcbf-8d79-4fa9-b8ab-09dc0255dfcf', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code Q: Roof Coverage Type (RCT) — Loss Record Layout col153 = Q
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'Q', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = Q', '12480b42-2419-41e6-a4fc-0fdc3104c022', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code R: Roof Coverage Type (RCT) — Loss Record Layout col153 = R
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'R', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = R', 'a1ac8853-28f1-4466-849f-614fda01e95c', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code S: Roof Coverage Type (RCT) — Loss Record Layout col153 = S
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'S', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = S', '1b9dbe4b-76f2-4028-bd65-21fba21259ed', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code T: Roof Coverage Type (RCT) — Loss Record Layout col153 = T
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'T', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = T', '9ecb3178-1c45-4ac2-9f11-d0045aa064e1', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code U: Roof Coverage Type (RCT) — Loss Record Layout col153 = U
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'U', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = U', 'ff1c710f-f985-4bdc-9731-63d53a9b3a39', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code V: Roof Coverage Type (RCT) — Loss Record Layout col153 = V
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'V', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = V', 'a2ab5755-3553-467d-8f3c-0be91239e31e', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code W: Roof Coverage Type (RCT) — Loss Record Layout col153 = W
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'W', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = W', 'ef882433-b705-4c88-aa0d-f54e6fe16098', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code X: Roof Coverage Type (RCT) — Loss Record Layout col153 = X
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'X', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = X', '132027a4-98a0-4663-b1e6-05574c2fbd3b', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code Y: Roof Coverage Type (RCT) — Loss Record Layout col153 = Y
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'Y', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = Y', 'd2faacd1-b701-4d78-937b-c718023be163', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Code Z: Roof Coverage Type (RCT) — Loss Record Layout col153 = Z
INSERT INTO TSPR_ROOF_COVERAGE_TYPE_CODES (
    tspr_code, description, kg_code_value_id, kg_source_document_id, kg_source_document_title, kg_canon_version, kg_effective_from, generated_at
) VALUES (
    'Z', 'Roof Coverage Type (RCT) — Loss Record Layout col153 = Z', '4bb7edcb-722e-4087-86cb-7b8048430c68', NULL, NULL, 1, NULL, CURRENT_TIMESTAMP()
);

-- Verification
SELECT COUNT(*) AS rows_loaded FROM TSPR_ROOF_COVERAGE_TYPE_CODES;
