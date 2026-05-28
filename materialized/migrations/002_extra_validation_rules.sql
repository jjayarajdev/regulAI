-- Validation rules that the auto-generated reference SQL doesn't include
-- (because the local Docker Neo4j doesn't have target_table annotations on
-- every rule). Re-apply after every `make load-reference-all` to keep these
-- rules in TSPR_VALIDATION_RULES.
--
-- Run with: snow sql -c regulai -f materialized/reference/extra_validation_rules.sql
-- Idempotent — re-runnable; each INSERT is guarded with WHERE NOT EXISTS.

-- ── A.22 Company Number (NAIC validation) ──────────────────────────────────
INSERT INTO INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES
  (rule_id, rule_number, rule_name, target_table, target_id_expr,
   violation_sql, violation_reason, severity, citation,
   validation_version, generated_at)
SELECT
  '192283ed-3597-46fb-899f-6bc258c450e8', '22', 'Rule A.22 — Company Number',
  'BRONZE.GW_PC_POLICYPERIOD', 'j.publicid',
  'j.naic_number IS NULL OR LENGTH(TRIM(j.naic_number)) <> 5 OR NOT REGEXP_LIKE(j.naic_number, ''^[0-9]{5}$'')',
  'NAIC company number must be present and exactly 5 numeric digits',
  'ERROR', 'TICO Stat Plan Rule A.22',
  1, CURRENT_TIMESTAMP()
WHERE NOT EXISTS (SELECT 1 FROM INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES WHERE rule_id = '192283ed-3597-46fb-899f-6bc258c450e8');

-- ── A.34 Reason Codes — L requires companion (credit-score) ────────────────
INSERT INTO INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES
  (rule_id, rule_number, rule_name, target_table, target_id_expr,
   violation_sql, violation_reason, severity, citation,
   validation_version, generated_at)
SELECT
  '561478d0-fee2-4cc7-bfe8-5771dd18181c', '34', 'Rule A.34 — Reason Codes',
  'BRONZE.GW_PC_JOB', 'j.publicid',
  'LENGTH(COALESCE(j.declinereason, j.cancellationreason, j.nonrenewalreason)) = 1 AND COALESCE(j.declinereason, j.cancellationreason, j.nonrenewalreason) IN (SELECT tspr_reason_code FROM INSURANCE_REGULATORY.REFERENCE.TSPR_REASON_CODE_MAP WHERE credit_score_companion_required = TRUE)',
  'Reason Code L (credit/insurance score) requires at least one companion reason code',
  'ERROR', 'Tex. Ins. Code §559.052(a)(2); TICO Stat Plan Rule A.34',
  1, CURRENT_TIMESTAMP()
WHERE NOT EXISTS (SELECT 1 FROM INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES WHERE rule_id = '561478d0-fee2-4cc7-bfe8-5771dd18181c');

-- ── A.34 Reason Codes — J must appear alone ────────────────────────────────
INSERT INTO INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES
  (rule_id, rule_number, rule_name, target_table, target_id_expr,
   violation_sql, violation_reason, severity, citation,
   validation_version, generated_at)
SELECT
  '2d01fd58-bc62-421e-a211-c740371fce4a', '34', 'Rule A.34 — Reporting Reason Codes for Cancellation, Nonrenewal, and Declination Notices',
  'BRONZE.GW_PC_JOB', 'j.publicid',
  $$LENGTH(COALESCE(j.declinereason, j.cancellationreason, j.nonrenewalreason)) > 1 AND COALESCE(j.declinereason, j.cancellationreason, j.nonrenewalreason) LIKE ANY (SELECT '%' || tspr_reason_code || '%' FROM INSURANCE_REGULATORY.REFERENCE.TSPR_REASON_CODE_MAP WHERE must_appear_alone = TRUE)$$,
  'A reason code marked must_appear_alone (e.g. J — market withdrawal) cannot be combined with others',
  'ERROR', 'TICO Stat Plan Rule A.34',
  1, CURRENT_TIMESTAMP()
WHERE NOT EXISTS (SELECT 1 FROM INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES WHERE rule_id = '2d01fd58-bc62-421e-a211-c740371fce4a');

-- ── Section A extras (premium range / termtype / notice date) ──────────────

INSERT INTO INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES
  (rule_id, rule_number, rule_name, target_table, target_id_expr,
   violation_sql, violation_reason, severity, citation,
   validation_version, generated_at)
SELECT
  'a-30-premium-range', '30', 'Rule A.30 — Written Premium Range',
  'BRONZE.GW_PC_POLICYPERIOD', 'j.publicid',
  'j.writtenpremium IS NULL OR j.writtenpremium < 100 OR j.writtenpremium > 50000',
  'Written premium must be reported and within plausible range ($100 - $50,000)',
  'ERROR', 'TICO Stat Plan Rule A.30; 28 TAC §5.7005(b)',
  1, CURRENT_TIMESTAMP()
WHERE NOT EXISTS (SELECT 1 FROM INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES WHERE rule_id = 'a-30-premium-range');

INSERT INTO INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES
  (rule_id, rule_number, rule_name, target_table, target_id_expr,
   violation_sql, violation_reason, severity, citation,
   validation_version, generated_at)
SELECT
  'a-40-termtype', '40', 'Rule A.40 — Policy Term Type',
  'BRONZE.GW_PC_POLICYPERIOD', 'j.publicid',
  $$j.termtype IS NULL OR j.termtype NOT IN ('Annual', 'SemiAnnual', 'Monthly')$$,
  'Policy term type must be one of: Annual, SemiAnnual, Monthly',
  'WARNING', 'TICO Stat Plan Rule A.40',
  1, CURRENT_TIMESTAMP()
WHERE NOT EXISTS (SELECT 1 FROM INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES WHERE rule_id = 'a-40-termtype');

INSERT INTO INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES
  (rule_id, rule_number, rule_name, target_table, target_id_expr,
   violation_sql, violation_reason, severity, citation,
   validation_version, generated_at)
SELECT
  'a-42-notice-date', '42', 'Rule A.42 — Notice Date Required',
  'BRONZE.GW_PC_JOB', 'j.publicid',
  'j.noticedate IS NULL',
  'Notice date is required for every cancellation, nonrenewal, or declination',
  'ERROR', '28 TAC §5.7008(c)',
  1, CURRENT_TIMESTAMP()
WHERE NOT EXISTS (SELECT 1 FROM INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES WHERE rule_id = 'a-42-notice-date');

-- ── D.13 Wind/Hail attribution required ────────────────────────────────────
-- CAT-period claims with cause Wind or Hail must carry an explicit subtype
-- so Section D's CAT attribution methodology is auditable.
INSERT INTO INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES
  (rule_id, rule_number, rule_name, target_table, target_id_expr,
   violation_sql, violation_reason, severity, citation,
   validation_version, generated_at)
SELECT
  'd-13-wind-hail-attribution', 'D.13', 'Rule D.13 — Wind/Hail Attribution',
  'BRONZE.GW_CC_CLAIM', 'j.claimnumber',
  $$j.losscause IN ('Wind', 'Hail') AND (j.losscausesubtype IS NULL OR TRIM(j.losscausesubtype) = '')$$,
  'Wind or Hail loss-cause claims must carry an explicit subtype (Wind / Hail) for Section D CAT attribution',
  'ERROR', 'TICO Stat Plan Rule D.13',
  1, CURRENT_TIMESTAMP()
WHERE NOT EXISTS (SELECT 1 FROM INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES WHERE rule_id = 'd-13-wind-hail-attribution');

-- ── F.0 Reason source indicator required ──────────────────────────────────
-- Cancellation/Nonrenewal/Submission must carry a notice source so Section F
-- field 27 (insurer-initiated vs insured-requested) can be derived.
INSERT INTO INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES
  (rule_id, rule_number, rule_name, target_table, target_id_expr,
   violation_sql, violation_reason, severity, citation,
   validation_version, generated_at)
SELECT
  'f-0-reason-source-indicator', 'F.0', 'Rule F.0 — Reason Source Indicator',
  'BRONZE.GW_PC_JOB', 'j.publicid',
  $$j.subtype IN ('Cancellation','Nonrenewal','Submission')
    AND (j.noticesource IS NULL OR j.noticesource NOT IN ('Insurer','Insured'))$$,
  'Notice source must be present and one of (Insurer | Insured) — Section F field 27 cannot be derived without it',
  'ERROR', 'TICO Stat Plan Rule F.0; 28 TAC §5.7008(d)',
  1, CURRENT_TIMESTAMP()
WHERE NOT EXISTS (SELECT 1 FROM INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES WHERE rule_id = 'f-0-reason-source-indicator');

-- ── B.6 Number of families (HO 1-4) ────────────────────────────────────────
INSERT INTO INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES
  (rule_id, rule_number, rule_name, target_table, target_id_expr,
   violation_sql, violation_reason, severity, citation,
   validation_version, generated_at)
SELECT
  'b-6-number-of-families', 'B.6', 'Rule B.6 — Number of Families',
  'BRONZE.GW_PC_HODWELLING', 'j.publicid',
  'j.numberoffamilies IS NULL OR j.numberoffamilies < 1 OR j.numberoffamilies > 4',
  'Homeowners forms apply only to 1- to 4-family dwellings (B.6)',
  'ERROR', 'TICO Stat Plan Rule B.6',
  1, CURRENT_TIMESTAMP()
WHERE NOT EXISTS (SELECT 1 FROM INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES WHERE rule_id = 'b-6-number-of-families');

-- ── B.18 Texas ZIP first-digit-7 ───────────────────────────────────────────
-- Texas residential ZIP codes always start with 7. Catches mis-coded or
-- out-of-state policies that slipped into the HO line.
INSERT INTO INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES
  (rule_id, rule_number, rule_name, target_table, target_id_expr,
   violation_sql, violation_reason, severity, citation,
   validation_version, generated_at)
SELECT
  'b-18-tx-zip', 'B.18', 'Rule B.18 — Texas ZIP (first digit = 7)',
  'BRONZE.GW_PC_HODWELLING', 'j.publicid',
  $$j.zip IS NULL OR LEFT(j.zip, 1) <> '7'$$,
  'Texas residential ZIP codes must begin with 7 — non-7-prefix indicates out-of-state or mis-coded data',
  'ERROR', 'TICO Stat Plan Rule B.18',
  1, CURRENT_TIMESTAMP()
WHERE NOT EXISTS (SELECT 1 FROM INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES WHERE rule_id = 'b-18-tx-zip');
