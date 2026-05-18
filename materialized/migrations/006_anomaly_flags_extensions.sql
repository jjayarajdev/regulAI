-- Extends GOLD.TSPR_ANOMALY_FLAGS with the columns the C3 detector needs.
--   FILING_BATCH_ID  — per-filing scoping (matches the rest of Gold)
--   SOURCE_RECORDS   — VARIANT containing the contributing record IDs
--   SEVERITY         — WARN | INFO classification for the UI
--
-- Run with: snow sql -c regulai -f materialized/migrations/006_anomaly_flags_extensions.sql

ALTER TABLE INSURANCE_REGULATORY.GOLD.TSPR_ANOMALY_FLAGS
    ADD COLUMN IF NOT EXISTS FILING_BATCH_ID VARCHAR(64)
    COMMENT 'FK to GOLD.FILING_BATCH.filing_batch_id; stamped by scripts.detect_anomalies.';

ALTER TABLE INSURANCE_REGULATORY.GOLD.TSPR_ANOMALY_FLAGS
    ADD COLUMN IF NOT EXISTS SOURCE_RECORDS VARIANT
    COMMENT 'JSON array of contributing record IDs (claim numbers, policy numbers, etc.).';

ALTER TABLE INSURANCE_REGULATORY.GOLD.TSPR_ANOMALY_FLAGS
    ADD COLUMN IF NOT EXISTS SEVERITY VARCHAR(16)
    COMMENT 'WARN | INFO — controls the UI pill color in the Anomalies popout.';
