-- Three additional executable rules — broadens the demo beyond just A.34
-- so violations span multiple rule types instead of one.
--
-- Run with: snow sql -c regulai -f materialized/reference/extra_validation_rules.sql
-- Idempotent — re-runnable; each INSERT is guarded with WHERE NOT EXISTS.

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
