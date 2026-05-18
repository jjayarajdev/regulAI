-- Audit-persistence tables
--
-- Promotes the previously-ephemeral validation/fix/bulletin events into queryable
-- Snowflake history. Each table is keyed and timestamped; the application writes
-- to them on every action so "what did we file and why?" can be answered for any
-- past moment.
--
-- Run with: snow sql -c regulai -f materialized/audit/audit_tables.sql

USE DATABASE INSURANCE_REGULATORY;

-- ── GOLD_FILING · canonical filing metadata + lifecycle ─────────────
USE SCHEMA GOLD;

CREATE TABLE IF NOT EXISTS FILING_BATCH (
  filing_batch_id          VARCHAR(64)  NOT NULL,   -- 'TPA-Q4-2025' (one per filing per edition)
  filing_id                VARCHAR(64)  NOT NULL,
  plan_code                VARCHAR(8)   NOT NULL,   -- TPA | RES | CL
  plan_name                VARCHAR(128),
  reporting_period_start   DATE,
  reporting_period_end     DATE,
  cadence                  VARCHAR(32),             -- Quarterly | Monthly | Annual
  due_date                 DATE,
  channel                  VARCHAR(64),             -- TICO ShareFile | NAIC | …
  status                   VARCHAR(32) NOT NULL,    -- draft|validating|resolving|approved|submitted|acked
  canon_edition            VARCHAR(64),             -- which KG version produced this batch
  generated_at             TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  last_validated_at        TIMESTAMP_NTZ,
  last_validation_run_id   VARCHAR(64),
  open_blockers            NUMBER(8, 0) DEFAULT 0,
  submitted_at             TIMESTAMP_NTZ,
  acked_at                 TIMESTAMP_NTZ,
  CONSTRAINT pk_filing_batch PRIMARY KEY (filing_batch_id)
);

CREATE TABLE IF NOT EXISTS FILING_SUBMISSION (
  submission_id            VARCHAR(64)  NOT NULL,
  filing_batch_id          VARCHAR(64)  NOT NULL,
  channel                  VARCHAR(64),
  submitted_at             TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  submitted_by             VARCHAR(128),
  file_name                VARCHAR(256),
  file_sha256              VARCHAR(64),
  file_size_bytes          NUMBER(18, 0),
  record_count             NUMBER(10, 0),
  acknowledgment           VARCHAR(64),             -- TICO ack hash
  acked_at                 TIMESTAMP_NTZ,
  status                   VARCHAR(32),             -- pending|sent|acked|rejected
  CONSTRAINT pk_filing_submission PRIMARY KEY (submission_id)
);

CREATE TABLE IF NOT EXISTS FILING_EXCEPTION (
  exception_id             VARCHAR(64)  NOT NULL,
  filing_batch_id          VARCHAR(64)  NOT NULL,
  source_record_id         VARCHAR(64)  NOT NULL,   -- e.g. job:7011 or pp:5017
  policy_number            VARCHAR(32),
  rule_id                  VARCHAR(64)  NOT NULL,
  rule_number              VARCHAR(32),
  rule_name                VARCHAR(256),
  severity                 VARCHAR(16),
  violation_reason         VARCHAR(512),
  citation                 VARCHAR(256),
  opened_at                TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  resolved_at              TIMESTAMP_NTZ,
  resolution_status        VARCHAR(32) NOT NULL DEFAULT 'open',  -- open|fixed|overridden|dismissed
  resolution_action        VARCHAR(256),                          -- 'manual_fix:JD→J', 'bulletin:B-…'
  assigned_to              VARCHAR(128),
  notes                    VARCHAR(1024),
  CONSTRAINT pk_filing_exception PRIMARY KEY (exception_id)
);


-- ── GOLD_AUDIT · per-rule-run + per-user-action history ─────────────
CREATE SCHEMA IF NOT EXISTS INSURANCE_REGULATORY.GOLD_AUDIT;
USE SCHEMA GOLD_AUDIT;

CREATE TABLE IF NOT EXISTS RULE_MATCH_RESULT (
  match_id                 VARCHAR(64)  NOT NULL,
  run_id                   VARCHAR(64)  NOT NULL,   -- groups matches from same validation pass
  filing_batch_id          VARCHAR(64),
  source_record_id         VARCHAR(64),
  policy_number            VARCHAR(32),
  rule_id                  VARCHAR(64)  NOT NULL,
  rule_number              VARCHAR(32),
  rule_name                VARCHAR(256),
  target_table             VARCHAR(128),
  status                   VARCHAR(16)  NOT NULL,   -- pass | fail | error
  violation_reason         VARCHAR(512),
  severity                 VARCHAR(16),
  citation                 VARCHAR(256),
  evidence                 VARIANT,                  -- JSON · actual values that triggered
  validation_version       VARCHAR(64),
  run_at                   TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  CONSTRAINT pk_rule_match PRIMARY KEY (match_id)
);

CREATE TABLE IF NOT EXISTS USER_ACTION (
  action_id                VARCHAR(64)  NOT NULL,
  filing_batch_id          VARCHAR(64),
  action_type              VARCHAR(32)  NOT NULL,   -- manual_fix|bulletin_apply|bulletin_reset|validation_run|approve|submit|comment
  actor                    VARCHAR(128),            -- 'system' | 'D.Reyes' | user email
  target_record            VARCHAR(64),             -- policy_number or record id
  target_rule              VARCHAR(64),             -- rule_id if applicable
  summary                  VARCHAR(512),            -- human-readable one-liner
  details                  VARIANT,                  -- JSON · structured payload
  acted_at                 TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  CONSTRAINT pk_user_action PRIMARY KEY (action_id)
);
