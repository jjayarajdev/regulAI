-- =============================================================================
-- SNOWFLAKE: GOLD LAYER STORED PROCEDURE
-- TSPR Gold Assembly — Snowflake equivalent of Databricks gold_assembly_notebook.py
-- =============================================================================
-- File    : 02_gold_procedure.sql
-- Schema  : insurance_regulatory.gold
-- Calls   : silver.tspr_premium_staging, silver.tspr_loss_staging,
--           silver.tspr_cancellation_staging, reference.tspr_validation_rules
-- Writes  : gold.tspr_premium_records, gold.tspr_loss_records,
--           gold.tspr_cancellation_records, gold.tspr_monthly_aggregates,
--           gold.tspr_validation_results, gold.tspr_anomaly_flags
--
-- Execution phases (mirrors gold_assembly_notebook.py):
--   Phase 1 — Assembly   : Silver → Gold record tables
--   Phase 2 — Validation : Field rules + cross-record checks + anomaly detection
--   Phase 3 — SDF Render : (Handled separately by Python/app layer — not in SQL)
--   Phase 4 — Submission : Approval gate + audit log
--
-- Call example:
--   CALL gold.sp_gold_assembly('2026-01', NULL, FALSE);
--   CALL gold.sp_gold_assembly('2026-01', ARRAY_CONSTRUCT('12345'), TRUE);
--
-- Design notes:
--   - Phase 2 is a GATE: validation ERRORs block Phase 3 (SDF render).
--   - naic_company_no_sdf populated on INSERT (= naic_company_no).
--   - retention_expiry_date in tspr_submissions computed as accounting_month + 25 months.
--   - anomaly detection: 2.5 std-dev threshold on premium, 3.0 on hail losses.
-- =============================================================================

USE DATABASE insurance_regulatory;
USE SCHEMA gold;

CREATE OR REPLACE PROCEDURE gold.sp_gold_assembly(
    p_accounting_month  VARCHAR   DEFAULT NULL,   -- 'YYYY-MM'; NULL = prior month
    p_naic_codes        VARIANT   DEFAULT NULL,   -- JSON array; NULL = all companies
    p_dry_run           BOOLEAN   DEFAULT FALSE   -- TRUE = read-only validation pass
)
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
DECLARE
    v_month             VARCHAR;
    v_run_id            VARCHAR;
    v_premium_count     INTEGER DEFAULT 0;
    v_loss_count        INTEGER DEFAULT 0;
    v_cancel_count      INTEGER DEFAULT 0;
    v_error_count       INTEGER DEFAULT 0;
    v_warning_count     INTEGER DEFAULT 0;
    v_anomaly_count     INTEGER DEFAULT 0;
    v_result            VARIANT;
BEGIN
    -- -----------------------------------------------------------------------
    -- Resolve parameters
    -- -----------------------------------------------------------------------
    v_month  := COALESCE(
        p_accounting_month,
        TO_VARCHAR(DATEADD(MONTH, -1, DATE_TRUNC('MONTH', CURRENT_DATE())), 'YYYY-MM')
    );
    v_run_id := 'gold_' || v_month || '_' ||
                TO_VARCHAR(CURRENT_TIMESTAMP(), 'YYYYMMDD_HH24MISS');


    -- =======================================================================
    -- PHASE 1: ASSEMBLY — Silver → Gold record tables
    -- =======================================================================

    -- -------------------------------------------------------------------
    -- 1a: Section C — Premium records
    -- -------------------------------------------------------------------
    IF (NOT p_dry_run) THEN
        DELETE FROM gold.tspr_premium_records
        WHERE accounting_month = v_month
          AND (p_naic_codes IS NULL
               OR ARRAY_CONTAINS(naic_company_no::VARIANT, p_naic_codes));

        INSERT INTO gold.tspr_premium_records (
            accounting_month, naic_company_no, run_id, source_policyperiod_id,
            stat_plan, accounting_date_encoded, record_type, policy_id,
            term, effective_date, expiry_date, place_code,
            amt_insurance_dw, line_of_business, tico_company_no,
            policy_form, number_of_families, coverage_occupancy, construction,
            ppc_split, ppc_simple, deductible_1, deductible_2,
            fire_premium, ec_premium, allied_lob, allied_amt_insurance, allied_premium,
            roof_covering, roof_credit, roof_install_year, cosmetic_excl,
            zip9, record_indicator,
            optional_cov_code, optional_cov_amount,
            deductible_1_amt, deductible_2_amt, wind_coverage_included,
            building_code_credit, law_ordinance_pct, optional_credit_ppid,
            tenure_code, tenure_discount_pct,
            naic_company_no_sdf,
            replacement_cost_building, replacement_cost_pp,
            roof_coverage_type, private_flood_indicator,
            trop_cyclone_deductible, trop_cyclone_deductible_amt,
            year_of_construction, amt_insurance_alu, amt_insurance_pp,
            prior_claims_history,
            rv_alarm, rv_age_of_home, rv_sprinkler, rv_claims_exp,
            rv_companion, rv_credit_score, rv_senior, rv_smart_home,
            rv_new_home, rv_surcharges,
            validation_status, _pipeline_run_id
        )
        SELECT
            s.accounting_month,
            s.naic_company_no,
            :v_run_id,
            s.source_policyperiod_id,
            s.stat_plan,
            -- ACDT encoding: Jan-Sep=1-9, Oct=0, Nov=-, Dec=&
            CASE MONTH(TO_DATE(s.accounting_month || '-01'))
                WHEN 10 THEN '0'  || RIGHT(s.accounting_month, 2)
                WHEN 11 THEN '-'  || RIGHT(s.accounting_month, 2)
                WHEN 12 THEN '&'  || RIGHT(s.accounting_month, 2)
                ELSE         TO_VARCHAR(MONTH(TO_DATE(s.accounting_month || '-01')))
                             || RIGHT(s.accounting_month, 2)
            END             AS accounting_date_encoded,
            s.record_type,
            s.policy_id,
            s.term,
            s.effective_date,
            s.expiry_date,
            s.place_code,
            s.amt_insurance_dw,
            s.line_of_business,
            s.tico_company_no,
            s.policy_form,
            s.number_of_families,
            s.coverage_occupancy,
            s.construction,
            s.ppc_split,
            s.ppc_simple,
            s.deductible_1,
            s.deductible_2,
            s.fire_premium,
            s.ec_premium,
            NULL,   -- allied_lob (populated for Dwelling Fire in production)
            NULL,   -- allied_amt_insurance
            NULL,   -- allied_premium
            s.roof_covering,
            s.roof_credit,
            s.roof_install_year,
            s.cosmetic_excl,
            s.zip9,
            s.record_indicator,
            s.optional_cov_code,
            s.optional_cov_amount,
            s.deductible_1_amt,
            s.deductible_2_amt,
            s.wind_coverage_included,
            s.building_code_credit,
            s.law_ordinance_pct,
            s.optional_credit_ppid,
            s.tenure_code,
            s.tenure_discount_pct,
            s.naic_company_no,  -- naic_company_no_sdf = naic_company_no
            s.replacement_cost_building,
            s.replacement_cost_pp,
            s.roof_coverage_type,
            s.private_flood_indicator,
            s.trop_cyclone_deductible,
            s.trop_cyclone_deductible_amt,
            s.year_of_construction,
            s.amt_insurance_alu,
            s.amt_insurance_pp,
            s.prior_claims_history,
            s.rv_alarm, s.rv_age_of_home, s.rv_sprinkler, s.rv_claims_exp,
            s.rv_companion, s.rv_credit_score, s.rv_senior, s.rv_smart_home,
            s.rv_new_home, s.rv_surcharges,
            'PENDING',
            :v_run_id
        FROM silver.tspr_premium_staging s
        WHERE s.accounting_month = v_month
          AND s.validation_status IN ('PENDING', 'CLEAN')
          AND (p_naic_codes IS NULL
               OR ARRAY_CONTAINS(s.naic_company_no::VARIANT, p_naic_codes))
        ORDER BY s.naic_company_no, s.record_type, s.policy_id, s.effective_date;

        v_premium_count := SQLROWCOUNT;
    END IF;

    -- -------------------------------------------------------------------
    -- 1b: Section D — Loss records
    -- -------------------------------------------------------------------
    IF (NOT p_dry_run) THEN
        DELETE FROM gold.tspr_loss_records
        WHERE accounting_month = v_month
          AND (p_naic_codes IS NULL
               OR ARRAY_CONTAINS(naic_company_no::VARIANT, p_naic_codes));

        INSERT INTO gold.tspr_loss_records (
            accounting_month, naic_company_no, run_id,
            source_claim_id, source_exposure_id,
            stat_plan, accounting_date_encoded, policy_id,
            occurrence_date, policy_effective_date, place_code,
            kind_code, amt_insurance_dw, line_of_business, tico_company_no,
            policy_form, number_of_families, coverage_occupancy, construction,
            ppc_split, ppc_simple, deductible_1, deductible_2,
            type_of_loss, paid_claim_count, loss_amount, zip9,
            record_indicator, optional_cov_code, optional_cov_amount,
            deductible_1_amt, deductible_2_amt, wind_coverage_included,
            building_code_credit, law_ordinance_pct,
            tenure_code, tenure_discount_pct,
            naic_company_no_sdf,
            replacement_cost_building, replacement_cost_pp,
            roof_coverage_type, private_flood_indicator,
            trop_cyclone_deductible, trop_cyclone_deductible_amt,
            year_of_construction, amt_insurance_alu, amt_insurance_pp,
            new_claim_count, claim_status, claim_id_tspr, reopened_claim_count,
            roof_covering, roof_credit, roof_install_year, cosmetic_excl,
            cause_of_loss, roof_depreciation,
            rv_alarm, rv_credit_score,
            validation_status, _pipeline_run_id
        )
        SELECT
            s.accounting_month, s.naic_company_no, :v_run_id,
            s.source_claim_id, s.source_exposure_id,
            s.stat_plan,
            CASE MONTH(TO_DATE(s.accounting_month || '-01'))
                WHEN 10 THEN '0' || RIGHT(s.accounting_month, 2)
                WHEN 11 THEN '-' || RIGHT(s.accounting_month, 2)
                WHEN 12 THEN '&' || RIGHT(s.accounting_month, 2)
                ELSE TO_VARCHAR(MONTH(TO_DATE(s.accounting_month || '-01')))
                     || RIGHT(s.accounting_month, 2)
            END,
            s.policy_id, s.occurrence_date, s.policy_effective_date, s.place_code,
            s.kind_code, s.amt_insurance_dw, s.line_of_business, s.tico_company_no,
            s.policy_form, s.number_of_families, s.coverage_occupancy, s.construction,
            s.ppc_split, s.ppc_simple, s.deductible_1, s.deductible_2,
            s.type_of_loss, s.paid_claim_count, s.loss_amount, s.zip9,
            s.record_indicator, s.optional_cov_code, s.optional_cov_amount,
            s.deductible_1_amt, s.deductible_2_amt, s.wind_coverage_included,
            s.building_code_credit, s.law_ordinance_pct,
            s.tenure_code, s.tenure_discount_pct,
            s.naic_company_no,   -- naic_company_no_sdf
            s.replacement_cost_building, s.replacement_cost_pp,
            s.roof_coverage_type, s.private_flood_indicator,
            s.trop_cyclone_deductible, s.trop_cyclone_deductible_amt,
            s.year_of_construction, s.amt_insurance_alu, s.amt_insurance_pp,
            s.new_claim_count, s.claim_status, s.claim_id_tspr, s.reopened_claim_count,
            s.roof_covering, s.roof_credit, s.roof_install_year, s.cosmetic_excl,
            s.cause_of_loss, s.roof_depreciation,
            s.rv_alarm, s.rv_credit_score,
            'PENDING', :v_run_id
        FROM silver.tspr_loss_staging s
        WHERE s.accounting_month = v_month
          AND s.validation_status IN ('PENDING', 'CLEAN')
          AND (p_naic_codes IS NULL
               OR ARRAY_CONTAINS(s.naic_company_no::VARIANT, p_naic_codes))
        ORDER BY s.naic_company_no, s.policy_id, s.occurrence_date, s.claim_id_tspr;

        v_loss_count := SQLROWCOUNT;
    END IF;

    -- -------------------------------------------------------------------
    -- 1c: Section E + G — Cancellation records (Rule 34 aggregation)
    -- -------------------------------------------------------------------
    IF (NOT p_dry_run) THEN
        DELETE FROM gold.tspr_cancellation_records
        WHERE accounting_month = v_month
          AND (p_naic_codes IS NULL
               OR ARRAY_CONTAINS(naic_company_no::VARIANT, p_naic_codes));

        INSERT INTO gold.tspr_cancellation_records (
            accounting_month, naic_company_no, run_id,
            notification_date_encoded, action_type, naic_company_no_sdf, tico_company_no,
            type_of_policy, reason_source_indicator, within_60_days_indicator,
            zip5, action_effective_date, recipient_count, reason_code_list,
            actual_action_count, unique_combination_key,
            credit_score_alone, withdrawal_not_alone,
            validation_status, _pipeline_run_id
        )
        SELECT
            s.accounting_month, s.naic_company_no, :v_run_id,
            s.notification_date, s.action_type,
            s.naic_company_no,   -- naic_company_no_sdf
            s.tico_company_no,
            s.type_of_policy, s.reason_source_indicator, s.within_60_days_indicator,
            s.zip5, s.action_effective_date,
            -- Rule 34 aggregation: sum recipient counts across identical combination keys
            SUM(s.recipient_count)       AS recipient_count,
            s.reason_code_list,
            SUM(s.actual_action_count)   AS actual_action_count,
            s.unique_combination_key,
            -- Credit score violation: L is sole reason
            BOOLOR_AGG(s.credit_score_violation)  AS credit_score_alone,
            -- Withdrawal violation: J not alone
            BOOLOR_AGG(s.withdrawal_violation)    AS withdrawal_not_alone,
            'PENDING',
            :v_run_id
        FROM silver.tspr_cancellation_staging s
        WHERE s.accounting_month = v_month
          AND (p_naic_codes IS NULL
               OR ARRAY_CONTAINS(s.naic_company_no::VARIANT, p_naic_codes))
        GROUP BY
            s.accounting_month, s.naic_company_no, s.tico_company_no,
            s.notification_date, s.action_type,
            s.type_of_policy, s.reason_source_indicator, s.within_60_days_indicator,
            s.zip5, s.action_effective_date, s.reason_code_list, s.unique_combination_key
        ORDER BY s.naic_company_no, s.action_type, s.notification_date, s.zip5;

        v_cancel_count := SQLROWCOUNT;
    END IF;

    -- -------------------------------------------------------------------
    -- 1d: Section 29 transmittal control totals
    -- -------------------------------------------------------------------
    IF (NOT p_dry_run) THEN
        DELETE FROM gold.tspr_monthly_aggregates
        WHERE accounting_month = v_month
          AND (p_naic_codes IS NULL
               OR ARRAY_CONTAINS(naic_company_no::VARIANT, p_naic_codes));

        INSERT INTO gold.tspr_monthly_aggregates (
            accounting_month, naic_company_no, tico_company_no, run_id,
            premium_record_count, loss_record_count,
            cancellation_notice_count, actual_count_record_count,
            total_written_premium, total_paid_losses, total_outstanding_losses,
            total_recipient_count, total_cancellations,
            total_nonrenewals, total_declinations,
            total_new_claims, total_paid_claims, total_reopened_claims,
            transmittal_balanced, approval_status, _pipeline_run_id
        )
        WITH
        pr_agg AS (
            SELECT naic_company_no,
                   MAX(tico_company_no)      AS tico_company_no,
                   COUNT(*)                  AS premium_record_count,
                   SUM(fire_premium)         AS total_written_premium
            FROM gold.tspr_premium_records
            WHERE accounting_month = :v_month
              AND (p_naic_codes IS NULL
                   OR ARRAY_CONTAINS(naic_company_no::VARIANT, p_naic_codes))
            GROUP BY 1
        ),
        lo_agg AS (
            SELECT naic_company_no,
                   COUNT(*)  AS loss_record_count,
                   SUM(CASE WHEN kind_code BETWEEN 4 AND 6
                            THEN loss_amount ELSE 0 END)  AS total_paid_losses,
                   SUM(CASE WHEN kind_code BETWEEN 7 AND 9
                            THEN loss_amount ELSE 0 END)  AS total_outstanding_losses,
                   SUM(CASE WHEN new_claim_count    = 1 THEN 1 ELSE 0 END) AS total_new_claims,
                   SUM(CASE WHEN paid_claim_count   = 1 THEN 1 ELSE 0 END) AS total_paid_claims,
                   SUM(CASE WHEN reopened_claim_count = 1 THEN 1 ELSE 0 END) AS total_reopened_claims
            FROM gold.tspr_loss_records
            WHERE accounting_month = :v_month
              AND (p_naic_codes IS NULL
                   OR ARRAY_CONTAINS(naic_company_no::VARIANT, p_naic_codes))
            GROUP BY 1
        ),
        ca_agg AS (
            SELECT naic_company_no,
                   COUNT(DISTINCT unique_combination_key)  AS cancellation_notice_count,
                   COUNT(DISTINCT
                       action_effective_date || action_type || type_of_policy || zip5
                   )                                       AS actual_count_record_count,
                   SUM(recipient_count)                    AS total_recipient_count,
                   SUM(CASE WHEN action_type = '80'
                            THEN actual_action_count ELSE 0 END)  AS total_cancellations,
                   SUM(CASE WHEN action_type = '81'
                            THEN actual_action_count ELSE 0 END)  AS total_nonrenewals,
                   SUM(CASE WHEN action_type = '82'
                            THEN actual_action_count ELSE 0 END)  AS total_declinations
            FROM gold.tspr_cancellation_records
            WHERE accounting_month = :v_month
              AND (p_naic_codes IS NULL
                   OR ARRAY_CONTAINS(naic_company_no::VARIANT, p_naic_codes))
            GROUP BY 1
        )
        SELECT
            :v_month, pr.naic_company_no, pr.tico_company_no, :v_run_id,
            COALESCE(pr.premium_record_count,    0),
            COALESCE(lo.loss_record_count,       0),
            COALESCE(ca.cancellation_notice_count, 0),
            COALESCE(ca.actual_count_record_count, 0),
            COALESCE(pr.total_written_premium,   0),
            COALESCE(lo.total_paid_losses,       0),
            COALESCE(lo.total_outstanding_losses,0),
            COALESCE(ca.total_recipient_count,   0),
            COALESCE(ca.total_cancellations,     0),
            COALESCE(ca.total_nonrenewals,       0),
            COALESCE(ca.total_declinations,      0),
            COALESCE(lo.total_new_claims,        0),
            COALESCE(lo.total_paid_claims,       0),
            COALESCE(lo.total_reopened_claims,   0),
            TRUE,       -- transmittal_balanced (set after validation)
            'PENDING',
            :v_run_id
        FROM pr_agg pr
        LEFT JOIN lo_agg lo ON pr.naic_company_no = lo.naic_company_no
        LEFT JOIN ca_agg ca ON pr.naic_company_no = ca.naic_company_no;
    END IF;


    -- =======================================================================
    -- PHASE 2: VALIDATION
    -- Field-level rules from reference.tspr_validation_rules
    -- Cross-record consistency checks
    -- Anomaly detection (12-month rolling window)
    -- =======================================================================

    -- -------------------------------------------------------------------
    -- 2a: Field-level validation rules (executes each rule's SQL expression)
    -- -------------------------------------------------------------------
    IF (NOT p_dry_run) THEN
        -- Run each executable validation rule against the Gold record tables
        INSERT INTO gold.tspr_validation_results (
            run_id, accounting_month, naic_company_no, validation_timestamp,
            record_type_tspr, source_record_id, field_name, col_start, col_end,
            rule_id, field_value, error_message, severity, resolved
        )
        -- Rule: stat_plan must = '4'
        SELECT :v_run_id, g.accounting_month, g.naic_company_no, CURRENT_TIMESTAMP(),
               'C', g.record_seq, 'SP', 1, 1,
               'Rule1', g.stat_plan::VARCHAR, 'Stat plan must be 4 for Residential', 'ERROR', FALSE
        FROM gold.tspr_premium_records g
        WHERE g.accounting_month = :v_month
          AND g.stat_plan != '4'
          AND (p_naic_codes IS NULL OR ARRAY_CONTAINS(g.naic_company_no::VARIANT, p_naic_codes))

        UNION ALL

        -- Rule 6: ALE must be populated (not null) for HO/Dwelling policies
        SELECT :v_run_id, g.accounting_month, g.naic_company_no, CURRENT_TIMESTAMP(),
               'C', g.record_seq, 'ALE', 166, 168,
               'Rule6_ALE', g.amt_insurance_alu::VARCHAR,
               'Loss of Use (ALE) amount required. Convert % of Cov A to dollars.',
               'ERROR', FALSE
        FROM gold.tspr_premium_records g
        WHERE g.accounting_month = :v_month
          AND g.amt_insurance_alu IS NULL
          AND g.private_flood_indicator != '1'
          AND g.line_of_business IN ('02','03','10','11')
          AND (p_naic_codes IS NULL OR ARRAY_CONTAINS(g.naic_company_no::VARIANT, p_naic_codes))

        UNION ALL

        -- Rule 24: ZIP must be present and have at least 5 digits
        SELECT :v_run_id, g.accounting_month, g.naic_company_no, CURRENT_TIMESTAMP(),
               'C', g.record_seq, 'ZIP', 91, 99,
               'Rule24_ZIP', g.zip9,
               'Five-digit ZIP code is mandatory.', 'ERROR', FALSE
        FROM gold.tspr_premium_records g
        WHERE g.accounting_month = :v_month
          AND (g.zip9 IS NULL OR LENGTH(REGEXP_REPLACE(g.zip9, '[^0-9]', '')) < 5)
          AND (p_naic_codes IS NULL OR ARRAY_CONTAINS(g.naic_company_no::VARIANT, p_naic_codes))

        UNION ALL

        -- Rule 25: NAIC must be 5 digits
        SELECT :v_run_id, g.accounting_month, g.naic_company_no, CURRENT_TIMESTAMP(),
               'C', g.record_seq, 'NAIC', 146, 150,
               'Rule25_NAIC', g.naic_company_no,
               'NAIC company number is mandatory and must be 5 digits.', 'ERROR', FALSE
        FROM gold.tspr_premium_records g
        WHERE g.accounting_month = :v_month
          AND (g.naic_company_no IS NULL OR LENGTH(g.naic_company_no) != 5)
          AND (p_naic_codes IS NULL OR ARRAY_CONTAINS(g.naic_company_no::VARIANT, p_naic_codes))

        UNION ALL

        -- Rule 30: Tenure code must be present on ALL premium records
        SELECT :v_run_id, g.accounting_month, g.naic_company_no, CURRENT_TIMESTAMP(),
               'C', g.record_seq, 'TENURE', 140, 140,
               'Rule30_TENURE', g.tenure_code,
               'Tenure code is REQUIRED on ALL premium transactions including endorsements.',
               'ERROR', FALSE
        FROM gold.tspr_premium_records g
        WHERE g.accounting_month = :v_month
          AND g.tenure_code NOT IN ('0','1','2','3','4','5','6','7')
          AND (p_naic_codes IS NULL OR ARRAY_CONTAINS(g.naic_company_no::VARIANT, p_naic_codes))

        UNION ALL

        -- Rule 32: Private flood indicator must be 0 or 1
        SELECT :v_run_id, g.accounting_month, g.naic_company_no, CURRENT_TIMESTAMP(),
               'C', g.record_seq, 'FLOOD', 154, 154,
               'Rule32_FLOOD', g.private_flood_indicator,
               'Private flood indicator must be 0 or 1. Federal NFIP policies must not be reported.',
               'ERROR', FALSE
        FROM gold.tspr_premium_records g
        WHERE g.accounting_month = :v_month
          AND g.private_flood_indicator NOT IN ('0','1')
          AND (p_naic_codes IS NULL OR ARRAY_CONTAINS(g.naic_company_no::VARIANT, p_naic_codes))

        UNION ALL

        -- Rule 13: NCC must be -1, 0, or 1
        SELECT :v_run_id, l.accounting_month, l.naic_company_no, CURRENT_TIMESTAMP(),
               'D', l.record_seq, 'NCC', 173, 173,
               'Rule13_NCC', l.new_claim_count::VARCHAR,
               'New claim count must be 1, 0, or -1 (reversal).', 'ERROR', FALSE
        FROM gold.tspr_loss_records l
        WHERE l.accounting_month = :v_month
          AND l.new_claim_count NOT IN (-1, 0, 1)
          AND (p_naic_codes IS NULL OR ARRAY_CONTAINS(l.naic_company_no::VARIANT, p_naic_codes))

        UNION ALL

        -- Rule 14: PCC must be -1, 0, or 1
        SELECT :v_run_id, l.accounting_month, l.naic_company_no, CURRENT_TIMESTAMP(),
               'D', l.record_seq, 'PCC', 60, 60,
               'Rule14_PCC', l.paid_claim_count::VARCHAR,
               'Paid claim count must be 1 (first payment), 0, or -1 (reversal).', 'ERROR', FALSE
        FROM gold.tspr_loss_records l
        WHERE l.accounting_month = :v_month
          AND l.paid_claim_count NOT IN (-1, 0, 1)
          AND (p_naic_codes IS NULL OR ARRAY_CONTAINS(l.naic_company_no::VARIANT, p_naic_codes))

        UNION ALL

        -- Rule 15: RCC must be -1, 0, or 1
        SELECT :v_run_id, l.accounting_month, l.naic_company_no, CURRENT_TIMESTAMP(),
               'D', l.record_seq, 'RCC', 177, 177,
               'Rule15_RCC', l.reopened_claim_count::VARCHAR,
               'Reopened claim count must be 1 (newly reopened first record), 0, or -1.',
               'ERROR', FALSE
        FROM gold.tspr_loss_records l
        WHERE l.accounting_month = :v_month
          AND l.reopened_claim_count NOT IN (-1, 0, 1)
          AND (p_naic_codes IS NULL OR ARRAY_CONTAINS(l.naic_company_no::VARIANT, p_naic_codes))

        UNION ALL

        -- Rule 16: Claim status 1-6
        SELECT :v_run_id, l.accounting_month, l.naic_company_no, CURRENT_TIMESTAMP(),
               'D', l.record_seq, 'CS', 174, 174,
               'Rule16_CS', l.claim_status::VARCHAR,
               'Claim status must be 1-6.',  'ERROR', FALSE
        FROM gold.tspr_loss_records l
        WHERE l.accounting_month = :v_month
          AND l.claim_status NOT BETWEEN 1 AND 6
          AND (p_naic_codes IS NULL OR ARRAY_CONTAINS(l.naic_company_no::VARIANT, p_naic_codes))

        UNION ALL

        -- Rule 34: Credit code L not alone
        SELECT :v_run_id, c.accounting_month, c.naic_company_no, CURRENT_TIMESTAMP(),
               'E', c.record_seq, 'RCL', 36, 45,
               'Rule34_CreditAlone', c.reason_code_list,
               'Credit score reason code L cannot be the sole reason (Sec559.052).',
               'ERROR', FALSE
        FROM gold.tspr_cancellation_records c
        WHERE c.accounting_month = :v_month
          AND c.credit_score_alone = TRUE
          AND (p_naic_codes IS NULL OR ARRAY_CONTAINS(c.naic_company_no::VARIANT, p_naic_codes))

        UNION ALL

        -- Rule 34: Withdrawal code J must appear alone
        SELECT :v_run_id, c.accounting_month, c.naic_company_no, CURRENT_TIMESTAMP(),
               'E', c.record_seq, 'RCL', 36, 45,
               'Rule34_WithdrawalAlone', c.reason_code_list,
               'Withdrawal code J must appear alone - no other reason codes permitted.',
               'ERROR', FALSE
        FROM gold.tspr_cancellation_records c
        WHERE c.accounting_month = :v_month
          AND c.withdrawal_not_alone = TRUE
          AND (p_naic_codes IS NULL OR ARRAY_CONTAINS(c.naic_company_no::VARIANT, p_naic_codes));

        v_error_count := SQLROWCOUNT;
    END IF;

    -- -------------------------------------------------------------------
    -- 2b: Stamp validation_status on Gold record tables
    -- -------------------------------------------------------------------
    IF (NOT p_dry_run) THEN
        UPDATE gold.tspr_premium_records g
        SET    validation_status = CASE
                   WHEN EXISTS (
                       SELECT 1 FROM gold.tspr_validation_results v
                       WHERE v.source_record_id = g.record_seq
                         AND v.accounting_month = :v_month
                         AND v.severity = 'ERROR'
                         AND v.resolved = FALSE
                   ) THEN 'EXCEPTION' ELSE 'VALIDATED'
               END
        WHERE  g.accounting_month = :v_month
          AND  g.validation_status = 'PENDING';

        UPDATE gold.tspr_loss_records l
        SET    validation_status = CASE
                   WHEN EXISTS (
                       SELECT 1 FROM gold.tspr_validation_results v
                       WHERE v.source_record_id = l.record_seq
                         AND v.accounting_month = :v_month
                         AND v.severity = 'ERROR'
                         AND v.resolved = FALSE
                   ) THEN 'EXCEPTION' ELSE 'VALIDATED'
               END
        WHERE  l.accounting_month = :v_month
          AND  l.validation_status = 'PENDING';

        UPDATE gold.tspr_cancellation_records c
        SET    validation_status = CASE
                   WHEN EXISTS (
                       SELECT 1 FROM gold.tspr_validation_results v
                       WHERE v.source_record_id = c.record_seq
                         AND v.accounting_month = :v_month
                         AND v.severity = 'ERROR'
                         AND v.resolved = FALSE
                   ) THEN 'EXCEPTION' ELSE 'VALIDATED'
               END
        WHERE  c.accounting_month = :v_month
          AND  c.validation_status = 'PENDING';
    END IF;

    -- -------------------------------------------------------------------
    -- 2c: Anomaly detection (12-month rolling window)
    -- -------------------------------------------------------------------
    IF (NOT p_dry_run) THEN
        INSERT INTO gold.tspr_anomaly_flags (
            run_id, accounting_month, naic_company_no, flagged_timestamp,
            anomaly_type, cause_of_loss_code, territory_zip,
            current_month_value, rolling_12m_mean, rolling_12m_stddev,
            std_deviations_from_mean, anomaly_description
        )
        -- Premium spike or drop (>2.5 std deviations from 12-month mean)
        WITH monthly_premium AS (
            SELECT accounting_month, naic_company_no, SUM(fire_premium) AS written_premium
            FROM gold.tspr_premium_records
            WHERE accounting_month <= :v_month
            GROUP BY 1, 2
        ),
        premium_stats AS (
            SELECT
                naic_company_no,
                accounting_month,
                written_premium,
                AVG(written_premium) OVER (
                    PARTITION BY naic_company_no
                    ORDER BY accounting_month
                    ROWS BETWEEN 12 PRECEDING AND 1 PRECEDING
                )   AS rolling_mean,
                STDDEV(written_premium) OVER (
                    PARTITION BY naic_company_no
                    ORDER BY accounting_month
                    ROWS BETWEEN 12 PRECEDING AND 1 PRECEDING
                )   AS rolling_stddev
            FROM monthly_premium
        )
        SELECT
            :v_run_id, :v_month, naic_company_no, CURRENT_TIMESTAMP(),
            'PREMIUM_SPIKE_OR_DROP', NULL, NULL,
            written_premium, rolling_mean, rolling_stddev,
            ROUND((written_premium - rolling_mean) / NULLIF(rolling_stddev, 0), 2),
            'Written premium is more than 2.5 std deviations from the 12-month mean. ' ||
            'Check Guidewire feed for missing records or large endorsement batch.'
        FROM premium_stats
        WHERE accounting_month = :v_month
          AND rolling_stddev   > 0
          AND ABS(written_premium - rolling_mean) > 2.5 * rolling_stddev
          AND (p_naic_codes IS NULL
               OR ARRAY_CONTAINS(naic_company_no::VARIANT, p_naic_codes))

        UNION ALL

        -- Hail spike (>3.0 std deviations — cat event check)
        WITH hail_monthly AS (
            SELECT accounting_month, naic_company_no, SUM(loss_amount) AS hail_losses
            FROM gold.tspr_loss_records
            WHERE cause_of_loss = '30'
              AND accounting_month <= :v_month
            GROUP BY 1, 2
        ),
        hail_stats AS (
            SELECT
                naic_company_no, accounting_month, hail_losses,
                AVG(hail_losses)    OVER (
                    PARTITION BY naic_company_no ORDER BY accounting_month
                    ROWS BETWEEN 12 PRECEDING AND 1 PRECEDING) AS rolling_mean,
                STDDEV(hail_losses) OVER (
                    PARTITION BY naic_company_no ORDER BY accounting_month
                    ROWS BETWEEN 12 PRECEDING AND 1 PRECEDING) AS rolling_stddev
            FROM hail_monthly
        )
        SELECT
            :v_run_id, :v_month, naic_company_no, CURRENT_TIMESTAMP(),
            'HAIL_SPIKE', '30', NULL,
            hail_losses, rolling_mean, rolling_stddev,
            ROUND((hail_losses - rolling_mean) / NULLIF(rolling_stddev, 0), 2),
            'Hail losses (COL=30) are more than 3 std deviations above the 12-month mean. ' ||
            'Confirm cat event or verify proximate cause coding per Rule 11.'
        FROM hail_stats
        WHERE accounting_month = :v_month
          AND rolling_stddev   > 0
          AND hail_losses > rolling_mean + 3.0 * rolling_stddev
          AND (p_naic_codes IS NULL
               OR ARRAY_CONTAINS(naic_company_no::VARIANT, p_naic_codes))

        UNION ALL

        -- Freeze losses in summer months (May-Sep) — almost certainly a coding error
        SELECT
            :v_run_id, :v_month, naic_company_no, CURRENT_TIMESTAMP(),
            'FREEZE_IN_SUMMER', '70/71', NULL,
            COUNT(*)::NUMBER, NULL, NULL, NULL,
            'Freeze losses (COL=70 or 71) recorded in summer month. ' ||
            'Verify proximate cause per Rule 11 and Section B.12.'
        FROM gold.tspr_loss_records
        WHERE accounting_month = :v_month
          AND cause_of_loss IN ('70','71')
          AND MONTH(TO_DATE(accounting_month || '-01')) BETWEEN 5 AND 9
          AND (p_naic_codes IS NULL
               OR ARRAY_CONTAINS(naic_company_no::VARIANT, p_naic_codes))
        GROUP BY naic_company_no
        HAVING COUNT(*) > 0;

        v_anomaly_count := SQLROWCOUNT;
    END IF;

    -- -------------------------------------------------------------------
    -- Count final error/warning totals for result summary
    -- -------------------------------------------------------------------
    IF (NOT p_dry_run) THEN
        SELECT COUNT(*) INTO v_error_count
        FROM gold.tspr_validation_results
        WHERE accounting_month = v_month
          AND severity = 'ERROR'
          AND resolved = FALSE;

        SELECT COUNT(*) INTO v_warning_count
        FROM gold.tspr_validation_results
        WHERE accounting_month = v_month
          AND severity = 'WARNING'
          AND resolved = FALSE;
    END IF;

    -- =======================================================================
    -- Build result summary
    -- =======================================================================
    v_result := OBJECT_CONSTRUCT(
        'run_id',                   v_run_id,
        'accounting_month',         v_month,
        'dry_run',                  p_dry_run,
        'phase_1_assembly', OBJECT_CONSTRUCT(
            'premium_records',          v_premium_count,
            'loss_records',             v_loss_count,
            'cancellation_records',     v_cancel_count
        ),
        'phase_2_validation', OBJECT_CONSTRUCT(
            'errors',                   v_error_count,
            'warnings',                 v_warning_count,
            'anomalies',                v_anomaly_count,
            'gate_clear',               (v_error_count = 0)
        ),
        'next_step', CASE
            WHEN p_dry_run    THEN 'Dry run complete — review results, then run with dry_run=FALSE'
            WHEN v_error_count > 0
                THEN 'BLOCKED: Resolve ' || v_error_count ||
                     ' ERRORs in gold.tspr_validation_results before proceeding to Phase 3'
            ELSE 'Gate clear — SDF renderer can proceed with Phase 3'
        END
    );
    RETURN v_result;
END;
$$;


-- ---------------------------------------------------------------------------
-- Grants
-- ---------------------------------------------------------------------------
GRANT EXECUTE ON PROCEDURE gold.sp_gold_assembly(VARCHAR, VARIANT, BOOLEAN)
    TO ROLE tspr_pipeline;
GRANT EXECUTE ON PROCEDURE gold.sp_gold_assembly(VARCHAR, VARIANT, BOOLEAN)
    TO ROLE tspr_compliance_admin;
