-- BRONZE_REGDOCS schema — raw regulator-source documents.
-- These tables back the "click a citation → see the regulator text" drill-down
-- and the change-log for edition diffs.
--
-- Run with: snow sql -c regulai -f materialized/migrations/004_bronze_regdocs.sql

CREATE SCHEMA IF NOT EXISTS INSURANCE_REGULATORY.BRONZE_REGDOCS
    COMMENT = 'Raw regulator-source documents (TX stat plan, HB 2067, TDI bulletins). Full text + page-keyed sections. Reads only — sourced from references/regulations/.';

-- 1. raw_reg_document — one row per source document (plan, statute, bulletin).
CREATE TABLE IF NOT EXISTS INSURANCE_REGULATORY.BRONZE_REGDOCS.RAW_REG_DOCUMENT (
    document_id         VARCHAR(64)  NOT NULL,
    document_type       VARCHAR(32)  NOT NULL    COMMENT 'stat_plan | statute | bulletin | record_layout',
    title               VARCHAR(512) NOT NULL,
    issuing_body        VARCHAR(128)             COMMENT 'TICO | TDI | Texas Legislature',
    effective_date      DATE,
    edition             VARCHAR(64),
    source_path         VARCHAR(512),
    full_text           VARCHAR(16777216)        COMMENT 'Raw extracted text. Use VARIANT field on next migration for richer.',
    page_count          NUMBER(6),
    word_count          NUMBER(10),
    loaded_at           TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_raw_reg_document PRIMARY KEY (document_id)
)
COMMENT = 'BRONZE: one row per regulator-source document. full_text is the canonical extracted text used for citation drill-downs.';

-- 2. raw_reg_section — per-section slice, keyed by document + citation hint.
CREATE TABLE IF NOT EXISTS INSURANCE_REGULATORY.BRONZE_REGDOCS.RAW_REG_SECTION (
    section_id          VARCHAR(64)  NOT NULL,
    document_id         VARCHAR(64)  NOT NULL,
    citation_label      VARCHAR(128)             COMMENT 'e.g. "Rule A.34" or "Sec. 559.052(a)(2)" — the human reference.',
    citation_pattern    VARCHAR(256)             COMMENT 'Regex for fuzzy citation matching (e.g. "A\\.34" or "559\\.052").',
    section_heading     VARCHAR(512),
    section_text        VARCHAR(16777216),
    page_start          NUMBER(6),
    page_end            NUMBER(6),
    seq                 NUMBER(6),
    CONSTRAINT pk_raw_reg_section PRIMARY KEY (section_id),
    CONSTRAINT fk_section_doc FOREIGN KEY (document_id)
        REFERENCES INSURANCE_REGULATORY.BRONZE_REGDOCS.RAW_REG_DOCUMENT (document_id)
)
COMMENT = 'BRONZE: per-section slices of regulator documents. citation_pattern is what the rule-citation UI matches against.';

-- 3. raw_reg_change_log — diffs between document editions.
CREATE TABLE IF NOT EXISTS INSURANCE_REGULATORY.BRONZE_REGDOCS.RAW_REG_CHANGE_LOG (
    change_id           VARCHAR(64)  NOT NULL,
    document_id         VARCHAR(64)  NOT NULL,
    prior_edition       VARCHAR(64),
    new_edition         VARCHAR(64),
    change_type         VARCHAR(32)              COMMENT 'added | modified | superseded | clarified',
    affected_citation   VARCHAR(128),
    summary             VARCHAR(2048),
    detected_at         TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT pk_raw_reg_change_log PRIMARY KEY (change_id)
)
COMMENT = 'BRONZE: detected diffs between document editions. Powers the bulletin-impact panel.';
