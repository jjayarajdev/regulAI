"""FL FHCF medallion transforms: Guidewire Bronze → Silver → Gold.

Mirrors the run_silver / run_gold conventions for the Florida Hurricane
Catastrophe Fund Annual Data Call (filing FHCF-A-2026):

  BRONZE.GW_PC_POLICY + GW_PC_HOPOLICYLINE + GW_PC_HOCOVERAGE +
  GW_PC_HODWELLING  (state = 'FL' rows, seeded by scripts.seed_fl_fhcf)
      │  FHCF_SILVER_SQL  ← the ONE swappable mapping unit (see below)
      ▼
  SILVER.FHCF_EXPOSURE_STAGING          one row per FL property policy
      │  gold_fhcf() — stamps filing_batch_id (jurisdiction scope: all FL
      ▼               rows belong to the single FHCF annual filing)
  GOLD.FHCF_EXPOSURE_RECORDS            the table the 10 US-FL rules validate

Invocation parity with the TX pipeline: scripts.run_silver calls
silver_fhcf() and scripts.run_gold calls gold_fhcf(), so `make run-pipeline`,
the Dagster job, and the /api/rhs/pipeline/{silver,gold} endpoints all
rebuild FHCF alongside TSPR with no extra wiring.

⚠ SWAP SEAM (agent-generated mappings — wired):
  The Bronze→Silver field mapping is a compiled artifact of the agentic
  schema mapper (packages/rhs/mapper): the reviewed spec
  materialized/mappings/guidewire_fl_fhcf.reviewed.json compiles to
  …/guidewire_fl_fhcf.compiled.json, which silver_fhcf() resolves by target
  name FHCF_EXPOSURE and executes. When no artifact is present the
  hand-written FHCF_SILVER_SQL constant below remains the documented
  fallback/reference (a warning is logged). tests/test_fhcf_mapping_compile.py
  proves the two produce identical Silver contents.

All SQL is portable (duckdb / databricks / snowflake) through
packages.rhs.db.query(): no MERGE / RLIKE / LISTAGG; bare VARCHAR is
translated to STRING by the databricks client.

Run:  REGULAI_DB=duckdb uv run python -m scripts.run_fhcf
Idempotent — TRUNCATE-and-reload on every run.
"""

from __future__ import annotations

import logging
import time

from packages.rhs.db import query
from packages.rhs.filings import FILINGS

logger = logging.getLogger(__name__)

RUN_ID = f"fhcf-{int(time.time())}"

# Registered mapping-target name the compiled Silver artifact is resolved by
# (see packages.rhs.mapper.target_schema and the SWAP SEAM note above).
MAPPING_TARGET = "FHCF_EXPOSURE"

# How the last silver_fhcf() run sourced its mapping — "compiled:<path>" or
# "handwritten-fallback". Introspectable by callers/tests.
LAST_SILVER_MAPPING: str | None = None

# The single FHCF annual filing. All FL exposure rows are stamped with it —
# jurisdiction-scoped stamping (unlike TX, which maps policy-id ranges to
# several filings via the CASE generators in packages.rhs.filings).
FILING_ID = next(f["id"] for f in FILINGS if f["plan_code"] == "FHCF")
# Data-call reporting year = year of the filing period start (2025-07-01).
REPORTING_YEAR = int(
    next(f["period_start"] for f in FILINGS if f["plan_code"] == "FHCF")[:4]
)

# Filing-ready column list — the exact fields the 10 US-FL validation rules
# reference (same names the retired BRONZE.FL_FHCF_POLICY table carried).
# Consumed by api/rhs_demo._build_fhcf_csv for the submission package.
FHCF_COLUMNS = [
    "insurer_naic", "policy_number", "risk_zip", "risk_zip4", "county_fips",
    "state_code", "policy_form", "effective_date", "expiry_date",
    "occupancy_type", "construction_type", "year_built", "protection_class",
    "coverage_a", "hurricane_deductible", "written_premium", "wind_mitigation",
    "opening_protection", "roof_cover_type", "roof_deck_attachment",
    "roof_to_wall_connection", "secondary_water_resistance",
    "latitude", "longitude", "reporting_year", "source_file",
]

# Shared column DDL for the exposure shape (portable types; the databricks
# client maps length-less VARCHAR → STRING).
_EXPOSURE_COLS_DDL = """
    insurer_naic               VARCHAR,
    policy_number              VARCHAR,
    risk_zip                   VARCHAR,
    risk_zip4                  VARCHAR,
    county_fips                VARCHAR,
    state_code                 VARCHAR,
    policy_form                VARCHAR,
    effective_date             DATE,
    expiry_date                DATE,
    occupancy_type             VARCHAR,
    construction_type          VARCHAR,
    year_built                 INT,
    protection_class           INT,
    coverage_a                 BIGINT,
    hurricane_deductible       INT,
    written_premium            BIGINT,
    wind_mitigation            VARCHAR,
    opening_protection         VARCHAR,
    roof_cover_type            VARCHAR,
    roof_deck_attachment       VARCHAR,
    roof_to_wall_connection    VARCHAR,
    secondary_water_resistance VARCHAR,
    latitude                   BIGINT,
    longitude                  BIGINT,
    reporting_year             INT,
    source_file                VARCHAR"""

FHCF_SILVER_DDL = f"""
CREATE TABLE IF NOT EXISTS INSURANCE_REGULATORY.SILVER.FHCF_EXPOSURE_STAGING (
{_EXPOSURE_COLS_DDL},
    _created_timestamp         TIMESTAMP,
    _pipeline_run_id           VARCHAR,
    _source_system             VARCHAR
)"""

FHCF_GOLD_DDL = f"""
CREATE TABLE IF NOT EXISTS INSURANCE_REGULATORY.GOLD.FHCF_EXPOSURE_RECORDS (
{_EXPOSURE_COLS_DDL},
    filing_batch_id            VARCHAR,
    _created_timestamp         TIMESTAMP
)"""


# ═══════════════════════════════════════════════════════════════════════════
# FHCF_SILVER_SQL — the hand-written Bronze→Silver mapping REFERENCE.
#
# The live path executes the agent-compiled mapping artifact instead (see
# _compiled_silver_sql below); this constant stays as the documented fallback
# and the golden reference the compiled artifact is tested against.
# Contract: INSERT INTO SILVER.FHCF_EXPOSURE_STAGING (FHCF_COLUMNS + audit
# cols), one row per in-scope FL property policy, sourced only from
# INSURANCE_REGULATORY.BRONZE.* Guidewire tables.
#
# Mapping notes:
#   insurer_naic          carrier-level NAIC from GW_PC_UWCOMPANY, left-padded
#                         to the FHCF's 10-digit format
#   risk_zip/county/state GW_PC_HODWELLING (FL rows carry the 2-digit FL
#                         county FIPS sub-code in countyfips)
#   hurricane_deductible  GW_PC_HOCOVERAGE.tropicalcyclonedeductible — the
#                         natural Guidewire home for a hurricane deductible
#   wind-mitigation set   GW_PC_HODWELLING.windmitigation + 4 companions
#                         (FL OIR-B1-1802 inspection attributes; nullable
#                         extension columns added by scripts.seed_fl_fhcf —
#                         stock Guidewire HO has no such fields), plus
#                         roof_cover_type from GW_PC_HOPOLICYLINE
#   reporting_year        constant per data-call cycle ({REPORTING_YEAR})
# ═══════════════════════════════════════════════════════════════════════════
FHCF_SILVER_SQL = f"""
    INSERT INTO INSURANCE_REGULATORY.SILVER.FHCF_EXPOSURE_STAGING (
        insurer_naic, policy_number, risk_zip, risk_zip4, county_fips,
        state_code, policy_form, effective_date, expiry_date,
        occupancy_type, construction_type, year_built, protection_class,
        coverage_a, hurricane_deductible, written_premium, wind_mitigation,
        opening_protection, roof_cover_type, roof_deck_attachment,
        roof_to_wall_connection, secondary_water_resistance,
        latitude, longitude, reporting_year, source_file,
        _created_timestamp, _pipeline_run_id, _source_system
    )
    SELECT
        -- FHCF wants the carrier NAIC as exactly 10 digits, zero-padded
        (SELECT LPAD(CAST(MAX(uw.naiccode) AS VARCHAR), 10, '0')
           FROM INSURANCE_REGULATORY.BRONZE.GW_PC_UWCOMPANY uw),
        p.policynumber,
        TRIM(dw.zip),
        dw.ziplus4,
        TRIM(dw.countyfips),
        UPPER(TRIM(dw.state)),
        line.holineform,
        CAST(line.effectivedate AS DATE),
        CAST(line.expirationdate AS DATE),
        -- FHCF occupancy code: O1 = owner-occupied single family
        CASE WHEN line.occupancytype = 'OwnerOccupied' THEN 'O1' ELSE 'O2' END,
        dw.constructiontype,
        CAST(dw.yearbuilt AS INT),
        CAST(dw.ppccode AS INT),
        CAST(cov.coverageamount AS BIGINT),
        CAST(cov.tropicalcyclonedeductible AS INT),
        CAST(cov.writtenpremium AS BIGINT),
        -- Normalize the wind-mitigation flag: any non-'Y' value reports 'N'
        CASE WHEN UPPER(COALESCE(dw.windmitigation, 'N')) = 'Y'
             THEN 'Y' ELSE 'N' END,
        dw.openingprotection,
        -- Roof cover companion comes from the HO line's roof covering type
        CASE WHEN UPPER(COALESCE(dw.windmitigation, 'N')) = 'Y'
             THEN line.roofcoveringtype ELSE NULL END,
        dw.roofdeckattachment,
        dw.rooftowallconnection,
        dw.secondarywaterresistance,
        dw.latitude,
        dw.longitude,
        {REPORTING_YEAR},
        'FHCF_D1A_GUIDEWIRE_{REPORTING_YEAR}.txt',
        CURRENT_TIMESTAMP(), '{RUN_ID}', 'GUIDEWIRE'
    FROM INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY p
    JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_HOPOLICYLINE line ON line.policy_id = p.id
    JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_HOCOVERAGE cov ON cov.policyline_id = line.id
    JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_HODWELLING dw ON dw.policyline_id = line.id
    WHERE UPPER(TRIM(dw.state)) = 'FL'
"""


def ensure_tables() -> None:
    """Create the FHCF Silver/Gold tables if a seed hasn't already."""
    query(FHCF_SILVER_DDL)
    query(FHCF_GOLD_DDL)


def _compiled_silver_sql() -> tuple[str, str] | None:
    """(insert_sql, artifact_path) from the compiled mapping artifact for the
    FHCF_EXPOSURE target, or None when no artifact is available."""
    try:
        from packages.rhs.mapper.compiler import load_compiled_artifact
        artifact = load_compiled_artifact(MAPPING_TARGET)
    except Exception as e:  # noqa: BLE001 — a broken artifact must not down the pipeline
        logger.warning("FHCF mapping artifact lookup failed (%s) — "
                       "falling back to hand-written FHCF_SILVER_SQL", e)
        return None
    if not artifact or not artifact.get("insert_sql"):
        return None
    return artifact["insert_sql"], artifact.get("_path", "")


def silver_fhcf() -> int:
    """Bronze → SILVER.FHCF_EXPOSURE_STAGING (truncate-and-reload).

    Executes the agent-compiled mapping artifact when present (resolved from
    materialized/mappings/ by target name FHCF_EXPOSURE), then stamps the
    system-populated audit columns — those are the pipeline's job, never the
    mapping's. Falls back to the hand-written FHCF_SILVER_SQL with a warning.
    """
    global LAST_SILVER_MAPPING
    ensure_tables()
    query("TRUNCATE TABLE INSURANCE_REGULATORY.SILVER.FHCF_EXPOSURE_STAGING")
    compiled = _compiled_silver_sql()
    if compiled:
        insert_sql, path = compiled
        query(insert_sql)
        query(f"""
            UPDATE INSURANCE_REGULATORY.SILVER.FHCF_EXPOSURE_STAGING
            SET _created_timestamp = CURRENT_TIMESTAMP(),
                _pipeline_run_id = '{RUN_ID}',
                _source_system = 'GUIDEWIRE'
        """)
        LAST_SILVER_MAPPING = f"compiled:{path}"
        logger.info("FHCF silver loaded via compiled mapping artifact %s", path)
    else:
        LAST_SILVER_MAPPING = "handwritten-fallback"
        logger.warning("No compiled mapping artifact for target %s — "
                       "using hand-written FHCF_SILVER_SQL fallback", MAPPING_TARGET)
        query(FHCF_SILVER_SQL)
    r = query("SELECT COUNT(*) AS n FROM INSURANCE_REGULATORY.SILVER.FHCF_EXPOSURE_STAGING")
    return r[0]["n"]


def gold_fhcf() -> int:
    """SILVER → GOLD.FHCF_EXPOSURE_RECORDS, stamped with the FHCF filing.

    Stamping is jurisdiction-scoped: the FHCF Data Call has no Guidewire
    policy-id ranges (packages.rhs.filings CASE generators skip it), so
    every FL exposure row belongs to the single annual filing batch.
    """
    ensure_tables()
    query("TRUNCATE TABLE INSURANCE_REGULATORY.GOLD.FHCF_EXPOSURE_RECORDS")
    cols = ", ".join(FHCF_COLUMNS)
    query(f"""
        INSERT INTO INSURANCE_REGULATORY.GOLD.FHCF_EXPOSURE_RECORDS (
            {cols}, filing_batch_id, _created_timestamp
        )
        SELECT {cols}, '{FILING_ID}', CURRENT_TIMESTAMP()
        FROM INSURANCE_REGULATORY.SILVER.FHCF_EXPOSURE_STAGING
    """)
    r = query("SELECT COUNT(*) AS n FROM INSURANCE_REGULATORY.GOLD.FHCF_EXPOSURE_RECORDS")
    return r[0]["n"]


def main() -> int:
    print(f"FHCF Bronze → Silver → Gold  ·  filing = {FILING_ID}")
    print()
    n_s = silver_fhcf()
    print(f"  ✓ FHCF_EXPOSURE_STAGING   {n_s} rows  (mapping: {LAST_SILVER_MAPPING})")
    n_g = gold_fhcf()
    print(f"  ✓ FHCF_EXPOSURE_RECORDS   {n_g} rows  (stamped {FILING_ID})")
    print()
    print(f"FHCF gold assembled · run_id = {RUN_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
