-- Section B/D claim-validation rules · executable against BRONZE.GW_CC_CLAIM
--
-- Run with: snow sql -c regulai -f materialized/reference/claim_validation_rules.sql
-- Idempotent — WHERE NOT EXISTS guards each INSERT.

INSERT INTO INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES
  (rule_id, rule_number, rule_name, target_table, target_id_expr,
   violation_sql, violation_reason, severity, citation,
   validation_version, generated_at)
SELECT
  'b-11-loss-cause', 'B.11', 'Rule B.11 — Loss Cause in TSPR codeset',
  'BRONZE.GW_CC_CLAIM', 'j.claimnumber',
  $$j.losscause IS NULL OR j.losscause NOT IN ('Wind', 'Hail', 'WaterDamage', 'Fire', 'Theft', 'Liability', 'Vandalism', 'Lightning', 'Freeze', 'Other')$$,
  'Loss cause must be one of the published TSPR cause categories',
  'ERROR', 'TICO Stat Plan §B.11',
  1, CURRENT_TIMESTAMP()
WHERE NOT EXISTS (SELECT 1 FROM INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES WHERE rule_id = 'b-11-loss-cause');

INSERT INTO INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES
  (rule_id, rule_number, rule_name, target_table, target_id_expr,
   violation_sql, violation_reason, severity, citation,
   validation_version, generated_at)
SELECT
  'b-14-reporting-lag', 'B.14', 'Rule B.14 — Late Loss Reporting (>90 days)',
  'BRONZE.GW_CC_CLAIM', 'j.claimnumber',
  'j.lossdate IS NULL OR j.reporteddate IS NULL OR DATEDIFF(day, j.lossdate, j.reporteddate) > 90',
  'Reported date must be within 90 days of loss date — late-reporting weakens reserve adequacy',
  'WARNING', 'TICO Stat Plan §B.14',
  1, CURRENT_TIMESTAMP()
WHERE NOT EXISTS (SELECT 1 FROM INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES WHERE rule_id = 'b-14-reporting-lag');

INSERT INTO INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES
  (rule_id, rule_number, rule_name, target_table, target_id_expr,
   violation_sql, violation_reason, severity, citation,
   validation_version, generated_at)
SELECT
  'd-12-cat-loss-attribution', 'D.12', 'Rule D.12 — Catastrophe-attributable loss reporting',
  'BRONZE.GW_CC_CLAIM', 'j.claimnumber',
  -- A claim where loss_cause is in the CAT-likely set (Hail / Freeze)
  -- AND total incurred > $25K must have isintwiazone or losscausesubtype set
  $$j.losscause IN ('Hail','Freeze') AND j.totalincurred > 25000 AND (j.losscausesubtype IS NULL OR j.isintwiazone IS NULL)$$,
  'High-severity hail/freeze claims must populate the catastrophe-attribution fields (subtype + TWIA-zone flag)',
  'ERROR', 'TICO Stat Plan §D.12 / 28 TAC §5.7009',
  1, CURRENT_TIMESTAMP()
WHERE NOT EXISTS (SELECT 1 FROM INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES WHERE rule_id = 'd-12-cat-loss-attribution');
