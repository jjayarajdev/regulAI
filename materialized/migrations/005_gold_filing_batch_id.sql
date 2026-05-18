-- Adds FILING_BATCH_ID to the three Gold record tables.
-- Lets run_gold stamp every row with its source filing, replacing the
-- ZIP-overlap heuristic the renderer used to fall back on for cancellations.
--
-- Run with: snow sql -c regulai -f materialized/migrations/005_gold_filing_batch_id.sql

ALTER TABLE INSURANCE_REGULATORY.GOLD.TSPR_PREMIUM_RECORDS
    ADD COLUMN IF NOT EXISTS FILING_BATCH_ID VARCHAR(64)
    COMMENT 'FK to GOLD.FILING_BATCH.filing_batch_id; stamped by run_gold via policy_id range map.';

ALTER TABLE INSURANCE_REGULATORY.GOLD.TSPR_LOSS_RECORDS
    ADD COLUMN IF NOT EXISTS FILING_BATCH_ID VARCHAR(64)
    COMMENT 'FK to GOLD.FILING_BATCH.filing_batch_id; stamped by run_gold via policy_id range map.';

ALTER TABLE INSURANCE_REGULATORY.GOLD.TSPR_CANCELLATION_RECORDS
    ADD COLUMN IF NOT EXISTS FILING_BATCH_ID VARCHAR(64)
    COMMENT 'FK to GOLD.FILING_BATCH.filing_batch_id; stamped by run_gold via JOIN back to BRONZE.GW_PC_JOB.';
