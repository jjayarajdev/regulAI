-- =============================================================================
-- SNOWFLAKE: SILVER LAYER STORED PROCEDURES
-- TSPR Field Transformation — Snowflake equivalent of Databricks Silver DLT Pipeline
-- =============================================================================
-- File    : 02_silver_procedures.sql
-- Schema  : insurance_regulatory.silver
-- Calls   : bronze.gw_pc_*, bronze.gw_cc_*, reference.*
-- Writes  : silver.tspr_premium_staging, silver.tspr_claim_state,
--           silver.tspr_loss_staging, silver.tspr_cancellation_staging
--
-- Execution: Called by Snowflake Tasks (see 00_setup.sql, Step 14).
--   Manually: CALL silver.sp_transform_premium('2026-01', NULL, FALSE);
--             CALL silver.sp_transform_claim_state('2026-01', NULL);
--             CALL silver.sp_transform_loss('2026-01', NULL, FALSE);
--             CALL silver.sp_transform_cancellation('2026-01', NULL, FALSE);
--
-- Design notes:
--   - Each procedure is idempotent: DELETE+INSERT for the target month/NAIC.
--   - All TSPR rule logic ported from silver_dlt_pipeline.py using SQL CASE/WHEN.
--   - Bronze CDC de-duplication: latest row per id resolved by MAX(_cdc_timestamp).
--   - Rule 6  : ALE % → dollar conversion, $1000 rounding, <$1500 → 1
--   - Rule 11 : Proximate cause lookup via reference.tspr_cause_of_loss_map
--   - Rules 13-15-16 : Full SCD-2 claim state machine using status history
--   - Rule 30 : Tenure NOT NULL enforced on premium AND loss records
--   - Rule 32 : Private flood NFIP excluded
--   - Rule 34 : Reason code concatenation + L-alone and J-alone validation
-- =============================================================================

USE DATABASE insurance_regulatory;
USE SCHEMA silver;

-- ---------------------------------------------------------------------------
-- Helper: Bronze CDC de-duplication view — latest record per GW primary key
-- Create these as secure views so procedures can reference them cleanly.
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW silver.v_latest_policyperiod AS
    SELECT pp.*
    FROM bronze.gw_pc_policyperiod pp
    INNER JOIN (
        SELECT id, MAX(_cdc_timestamp) AS latest_ts
        FROM   bronze.gw_pc_policyperiod
        WHERE  _cdc_operation != 'DELETE'
        GROUP  BY id
    ) latest ON pp.id = latest.id AND pp._cdc_timestamp = latest.latest_ts
    WHERE pp.status IN ('Bound', 'Canceled', 'Expired', 'NonRenewed')
      AND pp.basestate = 'TX';

CREATE OR REPLACE VIEW silver.v_latest_hopolicyline AS
    SELECT pl.*
    FROM bronze.gw_pc_hopolicyline pl
    INNER JOIN (
        SELECT id, MAX(_cdc_timestamp) AS latest_ts
        FROM   bronze.gw_pc_hopolicyline
        WHERE  _cdc_operation != 'DELETE'
        GROUP  BY id
    ) latest ON pl.id = latest.id AND pl._cdc_timestamp = latest.latest_ts;

CREATE OR REPLACE VIEW silver.v_latest_hocoverage AS
    SELECT cov.*
    FROM bronze.gw_pc_hocoverage cov
    INNER JOIN (
        SELECT id, MAX(_cdc_timestamp) AS latest_ts
        FROM   bronze.gw_pc_hocoverage
        WHERE  _cdc_operation != 'DELETE'
        GROUP  BY id
    ) latest ON cov.id = latest.id AND cov._cdc_timestamp = latest.latest_ts;

CREATE OR REPLACE VIEW silver.v_latest_hodwelling AS
    SELECT dw.*
    FROM bronze.gw_pc_hodwelling dw
    INNER JOIN (
        SELECT id, MAX(_cdc_timestamp) AS latest_ts
        FROM   bronze.gw_pc_hodwelling
        WHERE  _cdc_operation != 'DELETE'
        GROUP  BY id
    ) latest ON dw.id = latest.id AND dw._cdc_timestamp = latest.latest_ts;

CREATE OR REPLACE VIEW silver.v_latest_claim AS
    SELECT c.*
    FROM bronze.gw_cc_claim c
    INNER JOIN (
        SELECT id, MAX(_cdc_timestamp) AS latest_ts
        FROM   bronze.gw_cc_claim
        WHERE  _cdc_operation != 'DELETE'
        GROUP  BY id
    ) latest ON c.id = latest.id AND c._cdc_timestamp = latest.latest_ts;

CREATE OR REPLACE VIEW silver.v_latest_exposure AS
    SELECT e.*
    FROM bronze.gw_cc_exposure e
    INNER JOIN (
        SELECT id, MAX(_cdc_timestamp) AS latest_ts
        FROM   bronze.gw_cc_exposure
        WHERE  _cdc_operation != 'DELETE'
        GROUP  BY id
    ) latest ON e.id = latest.id AND e._cdc_timestamp = latest.latest_ts;


-- ===========================================================================
-- PROCEDURE 1: sp_transform_premium
-- Transforms Bronze PolicyCenter → Silver tspr_premium_staging (Section C)
-- Equivalent to Databricks: tspr_premium_staging() DLT function
-- ===========================================================================
CREATE OR REPLACE PROCEDURE silver.sp_transform_premium(
    p_accounting_month  VARCHAR   DEFAULT NULL,   -- 'YYYY-MM'; NULL = prior month
    p_naic_codes        VARIANT   DEFAULT NULL,   -- JSON array ['12345','67890']; NULL = all
    p_dry_run           BOOLEAN   DEFAULT FALSE
)
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
DECLARE
    v_month     VARCHAR;
    v_inserted  INTEGER DEFAULT 0;
    v_deleted   INTEGER DEFAULT 0;
    v_result    VARIANT;
BEGIN
    -- Resolve target month
    v_month := COALESCE(
        p_accounting_month,
        TO_VARCHAR(DATEADD(MONTH, -1, DATE_TRUNC('MONTH', CURRENT_DATE())), 'YYYY-MM')
    );

    -- Delete existing staging rows for this month/NAIC (idempotent)
    IF (NOT p_dry_run) THEN
        DELETE FROM silver.tspr_premium_staging
        WHERE accounting_month = v_month
          AND (p_naic_codes IS NULL
               OR ARRAY_CONTAINS(naic_company_no::VARIANT, p_naic_codes));
        v_deleted := SQLROWCOUNT;
    END IF;

    -- Insert transformed Section C premium records
    IF (NOT p_dry_run) THEN
        INSERT INTO silver.tspr_premium_staging (
            accounting_month, naic_company_no, tico_company_no, stat_plan,
            record_type, policy_id, term, effective_date, expiry_date,
            place_code, amt_insurance_dw, line_of_business,
            policy_form, number_of_families, coverage_occupancy, construction,
            ppc_split, ppc_simple, deductible_1, deductible_2,
            fire_premium, ec_premium,
            roof_covering, roof_credit, roof_install_year, cosmetic_excl,
            zip9, record_indicator,
            optional_cov_code, optional_cov_amount,
            deductible_1_amt, deductible_2_amt,
            wind_coverage_included, building_code_credit, law_ordinance_pct,
            optional_credit_ppid, tenure_code, tenure_discount_pct,
            replacement_cost_building, replacement_cost_pp,
            roof_coverage_type, private_flood_indicator,
            trop_cyclone_deductible, trop_cyclone_deductible_amt,
            year_of_construction, amt_insurance_alu, amt_insurance_pp,
            prior_claims_history,
            rv_alarm, rv_age_of_home, rv_sprinkler, rv_claims_exp,
            rv_companion, rv_credit_score, rv_senior, rv_smart_home,
            rv_new_home, rv_surcharges,
            validation_status, _source_system
        )
        WITH

        -- ----------------------------------------------------------------
        -- Latest Bronze source rows (CDC de-duplicated)
        -- ----------------------------------------------------------------
        pp  AS (SELECT * FROM silver.v_latest_policyperiod),
        pl  AS (SELECT * FROM silver.v_latest_hopolicyline),
        cov AS (SELECT * FROM silver.v_latest_hocoverage),
        dw  AS (SELECT * FROM silver.v_latest_hodwelling),

        -- ----------------------------------------------------------------
        -- Rating variable mapper  (Section B.20 codes 1-5)
        -- Inline CASE used repeatedly; factored here for readability.
        -- ----------------------------------------------------------------
        joined AS (
            SELECT
                -- Partition
                TO_VARCHAR(DATE_TRUNC('MONTH', pp.periodstart), 'YYYY-MM')  AS accounting_month,
                pp.naic_number          AS naic_company_no,
                pp.tico_company_number  AS tico_company_no,

                -- SDF col 1
                '4'                     AS stat_plan,

                -- SDF cols 5-6: Record type from GW job type
                CASE pp.jobtype
                    WHEN 'Submission'    THEN '01'
                    WHEN 'Renewal'       THEN '01'
                    WHEN 'PolicyChange'  THEN '02'
                    WHEN 'Reinstatement' THEN '03'
                    WHEN 'Cancellation'  THEN
                        CASE WHEN pp.cancellationsource = 'Flat' THEN '05' ELSE '06' END
                    ELSE '01'
                END                     AS record_type,

                -- SDF cols 7-16: Policy ID (Rule 26)
                LEFT(pp.publicid, 10)   AS policy_id,

                -- SDF col 17: Term
                CASE WHEN DATEDIFF(DAY, pp.periodstart, pp.periodend) <= 366
                     THEN '1' ELSE '9' END  AS term,

                -- SDF cols 18-22: EFF in MMDDY format
                TO_VARCHAR(pp.periodstart, 'MMDD') ||
                    RIGHT(TO_VARCHAR(YEAR(pp.periodstart)), 1)  AS effective_date,

                -- SDF cols 23-25: EXP in MMY format
                TO_VARCHAR(pp.periodend, 'MM') ||
                    RIGHT(TO_VARCHAR(YEAR(pp.periodend)), 1)    AS expiry_date,

                -- SDF cols 26-30: Place code (TDI county-community)
                dw.placecodetdi         AS place_code,

                -- SDF cols 33-37: Dwelling insurance in $1000s (Rule 6)
                CASE WHEN cov.coverageamount IS NULL  THEN NULL
                     WHEN cov.coverageamount < 1500   THEN 1
                     ELSE ROUND(cov.coverageamount / 1000)::INTEGER
                END                     AS amt_insurance_dw,

                -- SDF cols 41-42: LOB from reference table
                COALESCE(lob.tspr_lob_code, '03')  AS line_of_business,

                -- SDF col 50: Policy form
                COALESCE(
                    -- Mobile home: CT=5 overrides form code -> form '1' but typeOfPolicy=05
                    CASE WHEN dw.constructiontype = 'MobileManufactured'
                         THEN frm.tspr_form_code ELSE NULL END,
                    frm.tspr_form_code,
                    '1'
                )                       AS policy_form,

                -- SDF col 51: Number of families
                CASE WHEN pl.numberofunits <= 2 THEN '1' ELSE '9' END  AS number_of_families,

                -- SDF col 52: Coverage-occupancy
                CASE pl.occupancytype
                    WHEN 'OwnerOccupied'    THEN '1'
                    WHEN 'NonOwnerOccupied' THEN '2'
                    WHEN 'TenantDwelling'   THEN '3'
                    WHEN 'Apartment'        THEN '4'
                    WHEN 'TenantOther'      THEN '5'
                    WHEN 'Condo'            THEN '6'
                    WHEN 'Vacant'           THEN '7'
                    ELSE '1'
                END                     AS coverage_occupancy,

                -- SDF col 53: Construction type
                CASE dw.constructiontype
                    WHEN 'Frame'             THEN '1'
                    WHEN 'BrickVeneer'       THEN '2'
                    WHEN 'BrickStoneMasonry' THEN '3'
                    WHEN 'FireResistive'     THEN '4'
                    WHEN 'MobileManufactured'THEN '5'
                    WHEN 'StuccoAsbestos'    THEN '8'
                    ELSE '9'
                END                     AS construction,

                dw.ppccodesplit         AS ppc_split,
                dw.ppccode              AS ppc_simple,

                -- SDF col 57: DED1 Wind/Hail (territory-aware — code 7 restricted)
                CASE
                    WHEN cov.windexcluded = TRUE
                         AND (dw.territory IN ('8','9','10') OR dw.intwiazone = TRUE)
                         THEN '7'
                    WHEN cov.windhailddeductiblepct IS NOT NULL THEN
                        CASE cov.windhailddeductiblepct
                            WHEN 0.5  THEN '4'  WHEN 1.0  THEN '5'  WHEN 1.5  THEN 'A'
                            WHEN 2.0  THEN 'B'  WHEN 2.5  THEN 'C'  WHEN 3.0  THEN 'D'
                            WHEN 4.0  THEN 'E'  WHEN 5.0  THEN 'F'  WHEN 6.0  THEN 'R'
                            WHEN 7.0  THEN 'S'  WHEN 8.0  THEN 'T'  WHEN 9.0  THEN 'U'
                            WHEN 10.0 THEN 'N'  ELSE '9'
                        END
                    WHEN cov.windhailddeductible IS NOT NULL THEN
                        CASE cov.windhailddeductible::INTEGER
                            WHEN 0      THEN '1'  WHEN 100    THEN '2'  WHEN 200    THEN 'Y'
                            WHEN 250    THEN '3'  WHEN 500    THEN '6'  WHEN 750    THEN 'M'
                            WHEN 1000   THEN '8'  WHEN 1500   THEN 'G'  WHEN 2000   THEN 'H'
                            WHEN 2500   THEN 'I'  WHEN 3000   THEN 'J'  WHEN 3500   THEN 'O'
                            WHEN 4000   THEN 'K'  WHEN 5000   THEN 'L'  WHEN 7500   THEN 'P'
                            WHEN 10000  THEN 'Q'  WHEN 15000  THEN 'Z'  WHEN 25000  THEN 'V'
                            WHEN 50000  THEN 'W'
                            ELSE CASE WHEN cov.windhailddeductible >= 100000 THEN 'X' ELSE '1' END
                        END
                    ELSE '1'
                END                     AS deductible_1,

                -- SDF col 58: DED2 Other-than-W/H
                CASE cov.allperilsdeductible::INTEGER
                    WHEN 0    THEN '1'  WHEN 100  THEN '2'  WHEN 250  THEN '3'
                    WHEN 500  THEN '6'  WHEN 1000 THEN '8'  WHEN 1500 THEN 'G'
                    WHEN 2000 THEN 'H'  WHEN 2500 THEN 'I'  WHEN 3000 THEN 'J'
                    WHEN 5000 THEN 'L'
                    ELSE '6'
                END                     AS deductible_2,

                -- SDF cols 59-63: Fire/HO written premium
                pp.writtenpremium       AS fire_premium,
                cov.ecpremium           AS ec_premium,

                -- SDF col 83: Roof covering type code
                CASE pl.roofcoveringtype
                    WHEN 'CompShingle'  THEN 'A'  WHEN 'Wood'         THEN 'B'
                    WHEN 'Aluminum'     THEN 'C'  WHEN 'Steel'        THEN 'D'
                    WHEN 'Copper'       THEN 'E'  WHEN 'Roll'         THEN 'F'
                    WHEN 'TarGravel'    THEN 'G'  WHEN 'Tile'         THEN 'H'
                    WHEN 'Slate'        THEN 'I'  WHEN 'FiberCement'  THEN 'J'
                    WHEN 'Plastic'      THEN 'K'  WHEN 'Recycled'     THEN 'L'
                    WHEN 'SinglePly'    THEN 'M'  WHEN 'Metal'        THEN 'O'
                    WHEN 'Other'        THEN 'N'
                    ELSE 'P'
                END                     AS roof_covering,

                -- SDF col 84: Roof credit class (UL2218)
                TO_VARCHAR(COALESCE(pl.roofcoveringcreditclass, 0))  AS roof_credit,

                -- SDF cols 85-88: Roof installation year
                pl.roofinstallationyear AS roof_install_year,

                -- SDF col 89: Cosmetic damage exclusion
                CASE WHEN pl.cosmeticdamageexclusion = TRUE THEN '1' ELSE '0' END  AS cosmetic_excl,

                -- SDF cols 91-99: ZIP (PII)
                dw.zip || COALESCE(dw.ziplus4, '')  AS zip9,

                'P'                     AS record_indicator,

                -- Optional coverage endorsement
                cov.optionalcovcode     AS optional_cov_code,
                cov.optionalcovamount   AS optional_cov_amount,

                -- Actual deductible dollar amounts
                cov.allperilsdeductible AS deductible_2_amt,
                cov.windhailddeductible AS deductible_1_amt,

                -- Wind excluded
                CASE WHEN cov.windexcluded = TRUE THEN '1' ELSE '0' END  AS wind_coverage_included,

                -- Building code credit (TWIA only)
                COALESCE(dw.buildingcodecredit, '09')  AS building_code_credit,

                -- Law & ordinance
                CASE pl.lawordcompct
                    WHEN '10'    THEN '1'  WHEN '15'    THEN '2'
                    WHEN '25'    THEN '3'  WHEN '0'     THEN '0'
                    WHEN 'Other' THEN '4'
                    ELSE '0'
                END                     AS law_ordinance_pct,

                '0'                     AS optional_credit_ppid,  -- default

                -- SDF col 140: Tenure code (Rule 30 — REQUIRED on ALL transactions)
                CASE
                    WHEN bc.tenureusedforrating  = FALSE
                         AND bc.tenureusedfortiering = FALSE  THEN '0'
                    WHEN bc.tenureyears <= 2   THEN '1'
                    WHEN bc.tenureyears <= 5   THEN '2'
                    WHEN bc.tenureyears <= 8   THEN '3'
                    WHEN bc.tenureyears <= 10  THEN '4'
                    WHEN bc.tenureyears <= 15  THEN '5'
                    WHEN bc.tenureyears <= 19  THEN '6'
                    ELSE '7'
                END                     AS tenure_code,

                -- SDF cols 141-142: Tenure discount percentage
                CASE WHEN bc.tenureusedfortiering = TRUE
                          AND bc.tenureusedforrating = FALSE
                     THEN '00'
                     ELSE TO_VARCHAR(ROUND(COALESCE(bc.tenurediscountpct, 0))::INTEGER, 'FM00')
                END                     AS tenure_discount_pct,

                -- SDF col 151: Replacement cost building
                CASE pl.dwellingcoveragetype
                    WHEN 'ReplacementCost' THEN '1'
                    WHEN 'ActualCashValue' THEN '0'
                    ELSE CASE WHEN cov.coverageamount = 0 THEN '2' ELSE '0' END
                END                     AS replacement_cost_building,

                -- SDF col 152: Replacement cost personal property
                CASE pl.personalpropertycovtype
                    WHEN 'ReplacementCost' THEN '1'
                    WHEN 'ActualCashValue' THEN '0'
                    ELSE '0'
                END                     AS replacement_cost_pp,

                -- SDF col 153: Roof coverage type
                CASE pl.roofcoveragetype
                    WHEN 'ReplacementCost'      THEN '2'
                    WHEN 'ActualCashValue'      THEN '0'
                    WHEN 'ACV_WH_Only'          THEN '1'
                    ELSE '0'
                END                     AS roof_coverage_type,

                -- SDF col 154: Private flood indicator (Rule 32)
                -- Federal NFIP policies excluded (privatefloodcoverage=FALSE for NFIP)
                CASE WHEN pl.privatefloodcoverage = TRUE THEN '1' ELSE '0' END
                                        AS private_flood_indicator,

                -- SDF col 155: Tropical cyclone deductible code
                CASE cov.tropicalcyclonedeductibletype
                    WHEN 'FixedDollar'          THEN '2'
                    WHEN 'PercentageOfDwelling' THEN '5'
                    ELSE ' '
                END                     AS trop_cyclone_deductible,
                cov.tropicalcyclonedeductible  AS trop_cyclone_deductible_amt,

                -- SDF cols 162-165: Year of construction
                dw.yearbuilt            AS year_of_construction,

                -- SDF cols 166-168: ALE in $1000s (Rule 6: convert % of Cov A if needed)
                CASE
                    WHEN cov.lossofuselimit IS NOT NULL THEN
                        CASE WHEN cov.lossofuselimit >= 998499  THEN 999
                             WHEN cov.lossofuselimit  <   1500  THEN 1
                             ELSE ROUND(cov.lossofuselimit / 1000)::INTEGER
                        END
                    WHEN cov.lossofusepct IS NOT NULL THEN
                        -- Convert % of Cov A to dollars, then to $1000s
                        CASE WHEN (cov.coverageamount * cov.lossofusepct / 100) >= 998499
                             THEN 999
                             ELSE ROUND(cov.coverageamount * cov.lossofusepct / 100 / 1000)::INTEGER
                        END
                    ELSE 0
                END                     AS amt_insurance_alu,

                -- SDF cols 169-172: HO PP in $1000s (Rule 6)
                CASE
                    WHEN cov.personalpropertylimit IS NULL   THEN NULL
                    WHEN cov.personalpropertylimit >= 9998499 THEN 9999
                    WHEN cov.personalpropertylimit < 1500     THEN 1
                    ELSE ROUND(cov.personalpropertylimit / 1000)::INTEGER
                END                     AS amt_insurance_pp,

                -- SDF col 173: Prior claims history (Rule 20)
                CASE
                    WHEN pl.priorclaimsused = FALSE THEN '6'
                    WHEN pl.priorclaimscount = 0    THEN '0'
                    WHEN pl.priorclaimscount = 1    THEN '1'
                    WHEN pl.priorclaimscount = 2    THEN '2'
                    WHEN pl.priorclaimscount = 3    THEN '3'
                    WHEN pl.priorclaimscount = 4    THEN '4'
                    ELSE '5'
                END                     AS prior_claims_history,

                -- SDF cols 174-183: Rating variables (Section B.20) — 1-5 codes
                CASE pl.rv_alarm             WHEN 'Used' THEN '1' WHEN 'Discount' THEN '2'
                    WHEN 'Surcharge' THEN '3' WHEN 'TieringOnly' THEN '4' ELSE '5' END  AS rv_alarm,
                CASE pl.rv_age_of_home       WHEN 'Used' THEN '1' WHEN 'Discount' THEN '2'
                    WHEN 'Surcharge' THEN '3' WHEN 'TieringOnly' THEN '4' ELSE '5' END  AS rv_age_of_home,
                CASE pl.rv_sprinkler         WHEN 'Used' THEN '1' WHEN 'Discount' THEN '2'
                    WHEN 'Surcharge' THEN '3' WHEN 'TieringOnly' THEN '4' ELSE '5' END  AS rv_sprinkler,
                CASE pl.rv_claims_experience WHEN 'Used' THEN '1' WHEN 'Discount' THEN '2'
                    WHEN 'Surcharge' THEN '3' WHEN 'TieringOnly' THEN '4' ELSE '5' END  AS rv_claims_exp,
                CASE pl.rv_companion_policy  WHEN 'Used' THEN '1' WHEN 'Discount' THEN '2'
                    WHEN 'Surcharge' THEN '3' WHEN 'TieringOnly' THEN '4' ELSE '5' END  AS rv_companion,
                CASE pl.rv_credit_score      WHEN 'Used' THEN '1' WHEN 'Discount' THEN '2'
                    WHEN 'Surcharge' THEN '3' WHEN 'TieringOnly' THEN '4' ELSE '5' END  AS rv_credit_score,
                CASE pl.rv_senior_citizen    WHEN 'Used' THEN '1' WHEN 'Discount' THEN '2'
                    WHEN 'Surcharge' THEN '3' WHEN 'TieringOnly' THEN '4' ELSE '5' END  AS rv_senior,
                CASE pl.rv_smart_home        WHEN 'Used' THEN '1' WHEN 'Discount' THEN '2'
                    WHEN 'Surcharge' THEN '3' WHEN 'TieringOnly' THEN '4' ELSE '5' END  AS rv_smart_home,
                CASE pl.rv_new_home          WHEN 'Used' THEN '1' WHEN 'Discount' THEN '2'
                    WHEN 'Surcharge' THEN '3' WHEN 'TieringOnly' THEN '4' ELSE '5' END  AS rv_new_home,
                CASE pl.rv_additional_surcharges WHEN 'Used' THEN '1' WHEN 'Discount' THEN '2'
                    WHEN 'Surcharge' THEN '3' WHEN 'TieringOnly' THEN '4' ELSE '5' END  AS rv_surcharges

            FROM pp
            JOIN pl  ON pp.id = pl.branchid
            JOIN cov ON pp.id = cov.branchid
            JOIN dw  ON pp.id = dw.branchid
            -- Reference lookups
            LEFT JOIN reference.tspr_lob_codes  lob
                ON pl.policylinepatterncodeidentifier = lob.gw_lob_code
            LEFT JOIN reference.tspr_form_codes frm
                ON pl.holineform = frm.gw_form_code
            -- BillingCenter tenure data (latest record per period)
            LEFT JOIN (
                SELECT policyperiod_id,
                       tenureyears, tenurediscountpct,
                       tenureusedforrating, tenureusedfortiering,
                       ROW_NUMBER() OVER (PARTITION BY policyperiod_id
                                         ORDER BY _cdc_timestamp DESC) AS rn
                FROM bronze.gw_bc_policyperiodpremium
                WHERE _cdc_operation != 'DELETE'
            ) bc ON pp.id = bc.policyperiod_id AND bc.rn = 1
            WHERE TO_VARCHAR(DATE_TRUNC('MONTH', pp.periodstart), 'YYYY-MM') = :v_month
              AND (p_naic_codes IS NULL
                   OR ARRAY_CONTAINS(pp.naic_number::VARIANT, p_naic_codes))
        )

        SELECT
            accounting_month, naic_company_no, tico_company_no, stat_plan,
            record_type, policy_id, term, effective_date, expiry_date,
            place_code, amt_insurance_dw, line_of_business,
            policy_form, number_of_families, coverage_occupancy, construction,
            ppc_split, ppc_simple, deductible_1, deductible_2,
            fire_premium, ec_premium,
            roof_covering, roof_credit, roof_install_year, cosmetic_excl,
            zip9, record_indicator,
            optional_cov_code, optional_cov_amount,
            deductible_1_amt, deductible_2_amt,
            wind_coverage_included, building_code_credit, law_ordinance_pct,
            optional_credit_ppid, tenure_code, tenure_discount_pct,
            replacement_cost_building, replacement_cost_pp,
            roof_coverage_type, private_flood_indicator,
            trop_cyclone_deductible, trop_cyclone_deductible_amt,
            year_of_construction, amt_insurance_alu, amt_insurance_pp,
            prior_claims_history,
            rv_alarm, rv_age_of_home, rv_sprinkler, rv_claims_exp,
            rv_companion, rv_credit_score, rv_senior, rv_smart_home,
            rv_new_home, rv_surcharges,
            'PENDING'::VARCHAR,
            'Guidewire PolicyCenter'::VARCHAR
        FROM joined;

        v_inserted := SQLROWCOUNT;
    END IF;

    v_result := OBJECT_CONSTRUCT(
        'procedure',         'sp_transform_premium',
        'accounting_month',  v_month,
        'dry_run',           p_dry_run,
        'rows_deleted',      v_deleted,
        'rows_inserted',     v_inserted
    );
    RETURN v_result;
END;
$$;


-- ===========================================================================
-- PROCEDURE 2: sp_transform_claim_state
-- Rules 13-15-16 SCD-2 claim state machine
-- Equivalent to Databricks: tspr_claim_state() DLT function
-- ===========================================================================
CREATE OR REPLACE PROCEDURE silver.sp_transform_claim_state(
    p_accounting_month  VARCHAR  DEFAULT NULL,
    p_naic_codes        VARIANT  DEFAULT NULL
)
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
DECLARE
    v_month    VARCHAR;
    v_inserted INTEGER DEFAULT 0;
    v_deleted  INTEGER DEFAULT 0;
    v_result   VARIANT;
BEGIN
    v_month := COALESCE(
        p_accounting_month,
        TO_VARCHAR(DATEADD(MONTH, -1, DATE_TRUNC('MONTH', CURRENT_DATE())), 'YYYY-MM')
    );

    DELETE FROM silver.tspr_claim_state
    WHERE accounting_month = v_month
      AND (p_naic_codes IS NULL
           OR ARRAY_CONTAINS(naic_company_no::VARIANT, p_naic_codes));
    v_deleted := SQLROWCOUNT;

    INSERT INTO silver.tspr_claim_state (
        claim_id, exposure_id, claimnumber, accounting_month, naic_company_no,
        new_claim_count, paid_claim_count, reopened_claim_count,
        claim_status, kind_code,
        is_first_report_this_period, was_previously_closed,
        has_any_payment, has_payment_this_period,
        is_newly_reopened_this_period, is_first_rcc_record_this_month,
        scd_effective_month, scd_version
    )
    WITH

    -- -----------------------------------------------------------------------
    -- Step 1: Monthly payment summary per claim/exposure (exclude LAE + reins)
    -- Rule 11: losses exclusive of loss adjustment expense
    -- Rule 11: not net of reinsurance recoveries
    -- -----------------------------------------------------------------------
    monthly_payments AS (
        SELECT
            TO_VARCHAR(DATE_TRUNC('MONTH', accountingdate), 'YYYY-MM') AS accounting_month,
            claim_id,
            exposure_id,
            SUM(CASE WHEN isindemnity = TRUE  THEN amount ELSE 0 END)  AS indemnity_paid,
            SUM(CASE WHEN issubrogation = TRUE OR issalvage = TRUE
                     THEN amount ELSE 0 END)                            AS recoveries,
            COUNT(CASE WHEN isindemnity = TRUE AND isreversal = FALSE THEN 1 END)
                                                                        AS payment_records,
            BOOLOR_AGG(isreversal)                                      AS has_reversal
        FROM bronze.gw_cc_transaction
        WHERE (isindemnity = TRUE OR issalvage = TRUE OR issubrogation = TRUE)
          AND islae                = FALSE
          AND isreinsurancerecovery = FALSE
          AND isreserve            = FALSE
          AND TO_VARCHAR(DATE_TRUNC('MONTH', accountingdate), 'YYYY-MM') = :v_month
        GROUP BY 1, 2, 3
    ),

    -- -----------------------------------------------------------------------
    -- Step 2: All-time payment summary per claim/exposure
    -- Used to determine CWIP vs CWOP status codes
    -- -----------------------------------------------------------------------
    alltime_payments AS (
        SELECT
            claim_id,
            exposure_id,
            SUM(amount)  AS cumulative_indemnity,
            COUNT(*)     AS total_payment_records
        FROM bronze.gw_cc_transaction
        WHERE isindemnity          = TRUE
          AND islae                = FALSE
          AND isreinsurancerecovery = FALSE
          AND isreserve            = FALSE
        GROUP BY 1, 2
    ),

    -- -----------------------------------------------------------------------
    -- Step 3: First reported month per claim (Rule 13 — NCC)
    -- Report new claim in month carrier FIRST received it (not payment month)
    -- -----------------------------------------------------------------------
    first_report AS (
        SELECT
            claim_id,
            TO_VARCHAR(DATE_TRUNC('MONTH', MIN(reporteddate)), 'YYYY-MM') AS first_reported_month
        FROM bronze.gw_cc_claim
        WHERE _cdc_operation != 'DELETE'
        GROUP BY 1
    ),

    -- -----------------------------------------------------------------------
    -- Step 4: Prior close events (SCD lookback for Rules 15, 16)
    -- Was this claim/exposure reported as closed in ANY prior month?
    -- -----------------------------------------------------------------------
    prior_close AS (
        SELECT DISTINCT claim_id, exposure_id
        FROM bronze.gw_cc_claim_status_history
        WHERE is_close_event = TRUE
          AND accounting_month < :v_month
    ),

    -- -----------------------------------------------------------------------
    -- Step 5: Reopen events this month (Rule 15 — RCC)
    -- Claim was closed in prior month and has a new open event this month
    -- RCC=1 only on the FIRST record of the reporting month
    -- -----------------------------------------------------------------------
    reopen_this_month AS (
        SELECT DISTINCT h.claim_id, h.exposure_id
        FROM bronze.gw_cc_claim_status_history h
        WHERE h.is_reopen_event  = TRUE
          AND h.accounting_month = :v_month
          AND EXISTS (
              SELECT 1 FROM prior_close pc
              WHERE pc.claim_id   = h.claim_id
                AND pc.exposure_id = h.exposure_id
          )
    ),

    -- -----------------------------------------------------------------------
    -- Step 6: Assemble the state record per claim/exposure for this month
    -- -----------------------------------------------------------------------
    base AS (
        SELECT
            c.id                AS claim_id,
            e.id                AS exposure_id,
            c.claimnumber,
            :v_month            AS accounting_month,
            c.naic_number       AS naic_company_no,

            -- Rule 13: NCC = 1 only in the month the carrier first received the claim
            CASE WHEN fr.first_reported_month = :v_month THEN 1 ELSE 0 END
                                AS new_claim_count,

            -- Rule 14: PCC = 1 only on first payment record for this claim/exposure
            -- Reversal: PCC = -1 when payment reversed after full recovery
            CASE
                WHEN mp.has_reversal = TRUE
                     AND COALESCE(ap.cumulative_indemnity, 0) <= 0  THEN -1
                WHEN mp.payment_records >= 1                         THEN  1
                ELSE                                                       0
            END                 AS paid_claim_count,

            -- Rule 15: RCC = 1 only on first record of the month for a newly reopened claim
            CASE WHEN rt.claim_id IS NOT NULL THEN 1 ELSE 0 END
                                AS reopened_claim_count,

            -- Rule 16: Claim status 1-6
            -- 1=open/never closed  2=CWIP/never closed  3=CWOP/never closed
            -- 4=open/prev closed   5=CWIP/prev closed   6=CWOP/prev closed
            CASE
                WHEN pc.claim_id IS NULL THEN                   -- never previously closed
                    CASE c.state
                        WHEN 'Open'   THEN 1
                        WHEN 'Closed' THEN
                            CASE WHEN COALESCE(ap.cumulative_indemnity, 0) > 0
                                 THEN 2 ELSE 3 END
                        ELSE 1
                    END
                ELSE                                            -- previously closed
                    CASE c.state
                        WHEN 'Open'   THEN 4
                        WHEN 'Closed' THEN
                            CASE WHEN COALESCE(ap.cumulative_indemnity, 0) > 0
                                 THEN 5 ELSE 6 END
                        ELSE 4
                    END
            END                 AS claim_status,

            -- Section B.3: Kind code 1-9
            -- 1-3=no payment (outstanding/open/closed)
            -- 4-5=paid on reopened claim this period
            -- 6=paid first time (not reopened)
            -- 7-9=outstanding (open with reserve, no payment this period)
            CASE
                -- Paid this period + was previously closed (reopened) -> 4 or 5
                WHEN mp.payment_records >= 1 AND pc.claim_id IS NOT NULL THEN
                    CASE WHEN COALESCE(ap.cumulative_indemnity, 0) > 0 THEN 5 ELSE 4 END
                -- Paid this period + not previously closed -> 6
                WHEN mp.payment_records >= 1                          THEN  6
                -- Open with outstanding reserve, no payment this period -> 7
                WHEN c.state = 'Open'  AND mp.payment_records = 0    THEN  7
                -- Closed with outstanding (rare) -> 8
                WHEN c.state = 'Closed' AND mp.payment_records = 0
                     AND COALESCE(ap.cumulative_indemnity, 0) > 0    THEN  8
                -- No payment, closed, CWOP -> 3
                ELSE                                                        3
            END                 AS kind_code,

            fr.first_reported_month = :v_month     AS is_first_report_this_period,
            pc.claim_id IS NOT NULL                AS was_previously_closed,
            COALESCE(ap.cumulative_indemnity, 0) > 0 AS has_any_payment,
            COALESCE(mp.payment_records, 0) > 0    AS has_payment_this_period,
            rt.claim_id IS NOT NULL                AS is_newly_reopened_this_period,
            -- RCC first record flag: only the first RCC record of the month gets RCC=1
            CASE WHEN rt.claim_id IS NOT NULL THEN TRUE ELSE FALSE END
                                AS is_first_rcc_record_this_month,
            :v_month            AS scd_effective_month,
            1                   AS scd_version

        FROM silver.v_latest_claim         c
        JOIN silver.v_latest_exposure      e  ON c.id = e.claim_id
        JOIN first_report                  fr ON c.id = fr.claim_id
        LEFT JOIN monthly_payments         mp ON c.id = mp.claim_id
                                              AND e.id = mp.exposure_id
        LEFT JOIN alltime_payments         ap ON c.id = ap.claim_id
                                              AND e.id = ap.exposure_id
        LEFT JOIN prior_close              pc ON c.id = pc.claim_id
                                              AND e.id = pc.exposure_id
        LEFT JOIN reopen_this_month        rt ON c.id = rt.claim_id
                                              AND e.id = rt.exposure_id
        WHERE (fr.first_reported_month = :v_month    -- newly reported this month
               OR mp.claim_id IS NOT NULL             -- had activity this month
               OR c.state = 'Open')                  -- still open = always report
          AND (p_naic_codes IS NULL
               OR ARRAY_CONTAINS(c.naic_number::VARIANT, p_naic_codes))
    )

    SELECT * FROM base;

    v_inserted := SQLROWCOUNT;

    v_result := OBJECT_CONSTRUCT(
        'procedure',         'sp_transform_claim_state',
        'accounting_month',  v_month,
        'rows_deleted',      v_deleted,
        'rows_inserted',     v_inserted
    );
    RETURN v_result;
END;
$$;


-- ===========================================================================
-- PROCEDURE 3: sp_transform_loss
-- Bronze ClaimCenter → Silver tspr_loss_staging (Section D)
-- Equivalent to Databricks: tspr_loss_staging() DLT function
-- Depends on: tspr_claim_state being populated first for the same month
-- ===========================================================================
CREATE OR REPLACE PROCEDURE silver.sp_transform_loss(
    p_accounting_month  VARCHAR  DEFAULT NULL,
    p_naic_codes        VARIANT  DEFAULT NULL,
    p_dry_run           BOOLEAN  DEFAULT FALSE
)
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
DECLARE
    v_month    VARCHAR;
    v_inserted INTEGER DEFAULT 0;
    v_deleted  INTEGER DEFAULT 0;
    v_result   VARIANT;
BEGIN
    v_month := COALESCE(
        p_accounting_month,
        TO_VARCHAR(DATEADD(MONTH, -1, DATE_TRUNC('MONTH', CURRENT_DATE())), 'YYYY-MM')
    );

    IF (NOT p_dry_run) THEN
        DELETE FROM silver.tspr_loss_staging
        WHERE accounting_month = v_month
          AND (p_naic_codes IS NULL
               OR ARRAY_CONTAINS(naic_company_no::VARIANT, p_naic_codes));
        v_deleted := SQLROWCOUNT;

        INSERT INTO silver.tspr_loss_staging (
            accounting_month, naic_company_no, tico_company_no, stat_plan,
            policy_id, occurrence_date, policy_effective_date, place_code,
            kind_code, amt_insurance_dw, line_of_business,
            policy_form, number_of_families, coverage_occupancy, construction,
            ppc_split, ppc_simple, deductible_1, deductible_2,
            type_of_loss, paid_claim_count, loss_amount, zip9,
            record_indicator, wind_coverage_included, law_ordinance_pct,
            tenure_code, tenure_discount_pct,
            replacement_cost_building, replacement_cost_pp,
            roof_coverage_type, private_flood_indicator,
            trop_cyclone_deductible, trop_cyclone_deductible_amt,
            year_of_construction, amt_insurance_alu, amt_insurance_pp,
            new_claim_count, claim_status, claim_id_tspr, reopened_claim_count,
            roof_covering, roof_credit, roof_install_year, cosmetic_excl,
            cause_of_loss, roof_depreciation,
            rv_alarm, rv_credit_score,
            deductible_1_amt, deductible_2_amt,
            validation_status, _source_system
        )
        WITH

        -- Net paid loss per exposure per month (Rule 11)
        net_paid AS (
            SELECT
                TO_VARCHAR(DATE_TRUNC('MONTH', accountingdate), 'YYYY-MM') AS accounting_month,
                claim_id,
                exposure_id,
                SUM(CASE WHEN isindemnity  = TRUE THEN amount ELSE 0 END)        AS indemnity_paid,
                SUM(CASE WHEN issubrogation = TRUE OR issalvage = TRUE
                         THEN amount ELSE 0 END)                                  AS recoveries,
                SUM(CASE WHEN isindemnity = TRUE  THEN amount ELSE 0 END)
                    - SUM(CASE WHEN issubrogation = TRUE OR issalvage = TRUE
                               THEN amount ELSE 0 END)                            AS loss_amount_net,
                MAX(CASE WHEN replacementcostestimate IS NOT NULL
                         THEN replacementcostestimate - actualcashvaluepaid END)  AS roof_depreciation_amt
            FROM bronze.gw_cc_transaction
            WHERE (isindemnity = TRUE OR issalvage = TRUE OR issubrogation = TRUE)
              AND islae                 = FALSE
              AND isreinsurancerecovery = FALSE
              AND isreserve             = FALSE
              AND TO_VARCHAR(DATE_TRUNC('MONTH', accountingdate), 'YYYY-MM') = :v_month
            GROUP BY 1, 2, 3
        ),

        -- Outstanding reserves per exposure (Kind Codes 7-9)
        outstanding AS (
            SELECT
                accountingmonth AS accounting_month,
                claim_id,
                exposure_id,
                SUM(indemnityreserve) AS outstanding_loss
                -- laereserve excluded per Rule 11
            FROM bronze.gw_cc_reserveline
            WHERE accountingmonth = :v_month
            GROUP BY 1, 2, 3
        )

        SELECT
            st.accounting_month,
            c.naic_number       AS naic_company_no,
            c.naic_number       AS tico_company_no,  -- populated from uwcompany lookup in production
            '4'                 AS stat_plan,
            LEFT(c.policynumber, 10)  AS policy_id,
            TO_VARCHAR(c.lossdate, 'MMDDYY')  AS occurrence_date,
            pr.effective_date   AS policy_effective_date,
            pr.place_code,
            st.kind_code,
            pr.amt_insurance_dw,
            pr.line_of_business,
            pr.policy_form,
            pr.number_of_families,
            pr.coverage_occupancy,
            pr.construction,
            pr.ppc_split,
            pr.ppc_simple,
            pr.deductible_1,
            pr.deductible_2,
            -- Type of loss (Section B.11)
            CASE WHEN e.isenhancementendorsement = TRUE    THEN '3'
                 WHEN e.losstype = 'AdditionalEndorsement' THEN '2'
                 ELSE '1'
            END                 AS type_of_loss,
            st.paid_claim_count,
            -- Net loss (Rule 11: indemnity net of salvage/subro, NOT net of reinsurance)
            COALESCE(np.loss_amount_net, out.outstanding_loss, 0)  AS loss_amount,
            pr.zip9,
            'L'                 AS record_indicator,
            pr.wind_coverage_included,
            pr.law_ordinance_pct,
            pr.tenure_code,     -- Rule 30: required on loss records too
            pr.tenure_discount_pct,
            pr.replacement_cost_building,
            pr.replacement_cost_pp,
            pr.roof_coverage_type,
            pr.private_flood_indicator,
            pr.trop_cyclone_deductible,
            pr.trop_cyclone_deductible_amt,
            pr.year_of_construction,
            pr.amt_insurance_alu,
            pr.amt_insurance_pp,
            st.new_claim_count,
            st.claim_status,
            e.claimidentifier   AS claim_id_tspr,
            st.reopened_claim_count,
            pr.roof_covering,
            pr.roof_credit,
            pr.roof_install_year,
            pr.cosmetic_excl,
            -- Cause of loss: PROXIMATE cause (Rule 11, Section B.12)
            COALESCE(
                col_map.tspr_cause_code,
                CASE c.losscause
                    WHEN 'Windstorm'  THEN '25'  WHEN 'Hail'      THEN '30'
                    WHEN 'Fire'       THEN '10'  WHEN 'Flood'     THEN '32'
                    WHEN 'Freeze'     THEN '71'  WHEN 'Theft'     THEN '75'
                    WHEN 'Vandalism'  THEN '50'  WHEN 'Collapse'  THEN '55'
                    WHEN 'Explosion'  THEN '33'  WHEN 'Lightning' THEN '20'
                    ELSE '80'
                END
            )                   AS cause_of_loss,
            -- Roof depreciation (roof losses only — TSPR cols 93-97)
            CASE WHEN e.isroofloss = TRUE THEN np.roof_depreciation_amt ELSE NULL END
                                AS roof_depreciation,
            pr.rv_alarm,
            pr.rv_credit_score,
            pr.deductible_1_amt,
            pr.deductible_2_amt,
            'PENDING'           AS validation_status,
            'Guidewire ClaimCenter'  AS _source_system

        FROM silver.tspr_claim_state     st
        JOIN silver.v_latest_claim        c  ON st.claim_id    = c.id
        JOIN silver.v_latest_exposure     e  ON st.exposure_id = e.id
                                            AND c.id           = e.claim_id
        -- Join to premium staging for shared risk characteristic fields
        LEFT JOIN silver.tspr_premium_staging pr
            ON c.policynumber = pr.policy_id
            AND st.accounting_month = pr.accounting_month
        -- Proximate cause lookup (Rule 11)
        LEFT JOIN reference.tspr_cause_of_loss_map col_map
            ON c.losscause        = col_map.gw_loss_cause
            AND (c.losscausesubtype = col_map.gw_loss_cause_subtype
                 OR (c.losscausesubtype IS NULL AND col_map.gw_loss_cause_subtype IS NULL))
        LEFT JOIN net_paid np
            ON st.claim_id    = np.claim_id
            AND st.exposure_id = np.exposure_id
            AND st.accounting_month = np.accounting_month
        LEFT JOIN outstanding out
            ON st.claim_id    = out.claim_id
            AND st.exposure_id = out.exposure_id
            AND st.accounting_month = out.accounting_month
        WHERE st.accounting_month = :v_month
          AND (p_naic_codes IS NULL
               OR ARRAY_CONTAINS(c.naic_number::VARIANT, p_naic_codes));

        v_inserted := SQLROWCOUNT;
    END IF;

    v_result := OBJECT_CONSTRUCT(
        'procedure',         'sp_transform_loss',
        'accounting_month',  v_month,
        'dry_run',           p_dry_run,
        'rows_deleted',      v_deleted,
        'rows_inserted',     v_inserted
    );
    RETURN v_result;
END;
$$;


-- ===========================================================================
-- PROCEDURE 4: sp_transform_cancellation
-- Bronze pc_job → Silver tspr_cancellation_staging (Sections E + G)
-- Applies Rule 34 aggregation and Section F crosswalk
-- ===========================================================================
CREATE OR REPLACE PROCEDURE silver.sp_transform_cancellation(
    p_accounting_month  VARCHAR  DEFAULT NULL,
    p_naic_codes        VARIANT  DEFAULT NULL,
    p_dry_run           BOOLEAN  DEFAULT FALSE
)
RETURNS VARIANT
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
DECLARE
    v_month    VARCHAR;
    v_inserted INTEGER DEFAULT 0;
    v_deleted  INTEGER DEFAULT 0;
    v_result   VARIANT;
BEGIN
    v_month := COALESCE(
        p_accounting_month,
        TO_VARCHAR(DATEADD(MONTH, -1, DATE_TRUNC('MONTH', CURRENT_DATE())), 'YYYY-MM')
    );

    IF (NOT p_dry_run) THEN
        DELETE FROM silver.tspr_cancellation_staging
        WHERE accounting_month = v_month
          AND (p_naic_codes IS NULL
               OR ARRAY_CONTAINS(naic_company_no::VARIANT, p_naic_codes));
        v_deleted := SQLROWCOUNT;

        INSERT INTO silver.tspr_cancellation_staging (
            accounting_month, naic_company_no, tico_company_no,
            notification_date, action_type, type_of_policy,
            reason_source_indicator, within_60_days_indicator,
            zip5, action_effective_date,
            recipient_count, reason_code_list,
            unique_combination_key, actual_action_count,
            credit_score_violation, withdrawal_violation,
            validation_status, _source_system, _effective_jan2026
        )
        WITH

        -- Latest policyperiod records for joining
        pp  AS (SELECT * FROM silver.v_latest_policyperiod),

        -- All jobs that have a notice date in this reporting month
        jobs_this_month AS (
            SELECT
                j.id            AS job_id,
                j.policy_id,
                pp.naic_number,
                pp.tico_company_number,
                -- Action type: 80=Cancel 81=NonReneW 82=Decline
                CASE j.subtype
                    WHEN 'Cancellation' THEN '80'
                    WHEN 'NonRenewal'   THEN '81'
                    ELSE '82'
                END             AS action_type,
                -- Notification date in MMY encoding
                TO_VARCHAR(j.noticedate, 'MM') ||
                    RIGHT(TO_VARCHAR(YEAR(j.noticedate)), 1)  AS notification_date,
                -- Type of policy from Section F crosswalk
                -- Mobile home (CT=5) overrides form code
                CASE
                    WHEN dw.constructiontype = 'MobileManufactured' THEN '05'
                    ELSE COALESCE(frm.tspr_type_of_policy, '03')
                END             AS type_of_policy,
                -- Reason source indicator (RSI): aerial/3P data usage
                CASE
                    WHEN j.aerialimageused = TRUE AND j.thirdpartydataused = TRUE THEN '3'
                    WHEN j.aerialimageused = TRUE                                  THEN '1'
                    WHEN j.thirdpartydataused = TRUE                               THEN '2'
                    ELSE '0'
                END             AS reason_source_indicator,
                -- 60-day indicator
                CASE
                    WHEN j.subtype != 'Cancellation'  THEN '0'
                    WHEN j.within60days = TRUE         THEN 'Y'
                    ELSE                                    'N'
                END             AS within_60_days_indicator,
                -- ZIP (5-digit only for Section E)
                dw.zip          AS zip5,
                -- Action effective date YYYYMM
                TO_VARCHAR(
                    CASE j.subtype
                        WHEN 'Cancellation' THEN
                            CASE WHEN j.cancellationdate IS NOT NULL
                                 THEN j.cancellationdate
                                 ELSE j.noticedate
                            END
                        ELSE j.effectivedate
                    END,
                    'YYYYMM'
                )               AS action_effective_date,
                -- Reason code from reference table (single code per job)
                COALESCE(rcm.tspr_reason_code, 'Z')  AS tspr_reason_code

            FROM bronze.gw_pc_job j
            JOIN pp  ON j.policy_id = pp.policy_id
            JOIN silver.v_latest_hopolicyline pl ON pp.id = pl.branchid
            JOIN silver.v_latest_hodwelling   dw ON pp.id = dw.branchid
            LEFT JOIN reference.tspr_form_codes frm
                ON pl.holineform = frm.gw_form_code
            LEFT JOIN reference.tspr_reason_code_map rcm
                ON COALESCE(j.cancellationreason, j.nonrenewalreason, j.declinereason)
                   = rcm.gw_reason_code
            WHERE j._cdc_operation != 'DELETE'
              AND j.status = 'Bound'
              AND j.noticedate IS NOT NULL
              AND TO_VARCHAR(DATE_TRUNC('MONTH', j.noticedate), 'YYYY-MM') = :v_month
              AND (p_naic_codes IS NULL
                   OR ARRAY_CONTAINS(pp.naic_number::VARIANT, p_naic_codes))
        ),

        -- Build reason code list per unique combination (alphabetically sorted, padded to 10)
        -- Rule 34: aggregate all reason codes for identical 8-field combination
        aggregated AS (
            SELECT
                :v_month        AS accounting_month,
                naic_number     AS naic_company_no,
                tico_company_number  AS tico_company_no,
                notification_date,
                action_type,
                type_of_policy,
                reason_source_indicator,
                within_60_days_indicator,
                zip5,
                action_effective_date,
                -- Recipient count = count of policies sharing this unique combination
                COUNT(DISTINCT job_id)                  AS recipient_count,
                -- Section G actual action count (same grouping, count of actual events)
                COUNT(DISTINCT job_id)                  AS actual_action_count,
                -- Rule 34: reason code list — sorted, concatenated, padded to 10
                RPAD(
                    LISTAGG(DISTINCT tspr_reason_code, '')
                        WITHIN GROUP (ORDER BY tspr_reason_code),
                    10, '0'
                )               AS reason_code_list
            FROM jobs_this_month
            GROUP BY 2,3,4,5,6,7,8,9,10,11
        ),

        -- Compute unique combination key and validation flags
        with_key AS (
            SELECT
                *,
                -- Unique combination key (Rule 34 — 8 fields)
                notification_date     || '|' ||
                action_type           || '|' ||
                type_of_policy        || '|' ||
                reason_source_indicator || '|' ||
                within_60_days_indicator || '|' ||
                zip5                  || '|' ||
                action_effective_date || '|' ||
                reason_code_list      AS unique_combination_key,
                -- Credit code L not alone (Sec559.052) validation
                (CONTAINS(reason_code_list, 'L')
                 AND LENGTH(TRIM(REPLACE(REPLACE(reason_code_list, '0', ''), ' ', ''))) = 1
                )                     AS credit_score_violation,
                -- Withdrawal code J must appear alone validation
                (CONTAINS(reason_code_list, 'J')
                 AND LENGTH(TRIM(
                     TRANSLATE(REPLACE(reason_code_list, '0', ''), 'J', ' ')
                 )) > 0
                )                     AS withdrawal_violation
            FROM aggregated
        )

        SELECT
            accounting_month, naic_company_no, tico_company_no,
            notification_date, action_type, type_of_policy,
            reason_source_indicator, within_60_days_indicator,
            zip5, action_effective_date,
            recipient_count, reason_code_list,
            unique_combination_key, actual_action_count,
            credit_score_violation, withdrawal_violation,
            'PENDING'           AS validation_status,
            'Guidewire PolicyCenter'  AS _source_system,
            TRUE                AS _effective_jan2026
        FROM with_key;

        v_inserted := SQLROWCOUNT;
    END IF;

    v_result := OBJECT_CONSTRUCT(
        'procedure',         'sp_transform_cancellation',
        'accounting_month',  v_month,
        'dry_run',           p_dry_run,
        'rows_deleted',      v_deleted,
        'rows_inserted',     v_inserted
    );
    RETURN v_result;
END;
$$;


-- ---------------------------------------------------------------------------
-- Grant execute on all Silver procedures to pipeline role
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA insurance_regulatory.silver TO ROLE tspr_pipeline;
GRANT EXECUTE ON PROCEDURE silver.sp_transform_premium(VARCHAR, VARIANT, BOOLEAN)
    TO ROLE tspr_pipeline;
GRANT EXECUTE ON PROCEDURE silver.sp_transform_claim_state(VARCHAR, VARIANT)
    TO ROLE tspr_pipeline;
GRANT EXECUTE ON PROCEDURE silver.sp_transform_loss(VARCHAR, VARIANT, BOOLEAN)
    TO ROLE tspr_pipeline;
GRANT EXECUTE ON PROCEDURE silver.sp_transform_cancellation(VARCHAR, VARIANT, BOOLEAN)
    TO ROLE tspr_pipeline;
