"""In-process DuckDB harness for verifying violation_sql against synthetic data.

Production runs violation_sql via api/rhs_demo.py's /validate endpoint:

    SELECT {target_id_expr} AS record_id
    FROM INSURANCE_REGULATORY.{target_table} j
    WHERE ({violation_sql})

We replicate the same query shape against DuckDB so CI can prove the
rules actually catch violators, not just that the SQL artifact is
well-formed. DuckDB's SQL dialect overlaps Snowflake's for the
functions our rules use (LEFT, TRIM, LENGTH, REGEXP_LIKE, BETWEEN,
COALESCE, IS NULL, UPPER, TO_NUMBER → CAST).

The rules target GOLD.FHCF_EXPOSURE_RECORDS — the filing-ready table
built by scripts/run_fhcf.py from the FL rows in the Guidewire Bronze.
This harness builds that table directly from the 12 fixture rows below:
the fixtures test RULE SEMANTICS (each dirty row trips exactly one
rule), not the Bronze→Silver→Gold transform — that end-to-end path is
covered by tests/test_fhcf_pipeline.py against the seeded warehouse.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb


# Historical fixture set (originally mirrored the retired
# BRONZE.FL_FHCF_POLICY DDL in references/files -Snowflake/03_bronze_fl_fhcf.sql;
# now loaded straight into the GOLD.FHCF_EXPOSURE_RECORDS shape).
#
# Schema invariant: each dirty row is designed to trigger EXACTLY ONE
# wired rule. Anything else triggering means false positive (rule
# overreach) or fixture drift. Held by test_fl_rules_execute.py.
FL_FHCF_FIXTURE_ROWS = [
    # (naic, policy_number, risk_zip, zip4, county_fips, state_code,
    #  policy_form, eff_date, exp_date, occupancy, construction,
    #  year_built, protection_class, coverage_a, hurricane_deductible,
    #  written_premium, wind_mitigation,
    #  opening_protection, roof_cover_type, roof_deck_attachment,
    #  roof_to_wall_connection, secondary_water_resistance,
    #  latitude, longitude,
    #  reporting_year, source_file)

    # CLEAN — Miami-Dade
    ("0000012345", "POL-FL-0001", "33101", "00000", "25", "FL",
     "HO3", "2025-01-15", "2026-01-15", "O1", "M", 2015, 3,
     450000, 500, 4200, "N",
     None, None, None, None, None,
     None, None,
     2025, "FHCF_D1A_0000012345_2025.txt"),

    # CLEAN — Tallahassee
    ("0000012345", "POL-FL-0002", "32308", "00000", "37", "FL",
     "HO5", "2025-03-01", "2026-03-01", "O1", "F", 2018, 4,
     285000, 200, 2150, "N",
     None, None, None, None, None,
     None, None,
     2025, "FHCF_D1A_0000012345_2025.txt"),

    # DIRTY — risk_zip='77002' (TX prefix) → Validation.2
    ("0000012345", "POL-FL-0003", "77002", "00000", "25", "FL",
     "HO3", "2025-02-01", "2026-02-01", "O1", "M", 2010, 3,
     510000, 500, 5100, "N",
     None, None, None, None, None,
     None, None,
     2025, "FHCF_D1A_0000012345_2025.txt"),

    # DIRTY — county_fips='99' → Validation.3
    ("0000012345", "POL-FL-0004", "33139", "00000", "99", "FL",
     "HO3", "2025-04-15", "2026-04-15", "O1", "MV", 2020, 2,
     625000, 500, 5800, "N",
     None, None, None, None, None,
     None, None,
     2025, "FHCF_D1A_0000012345_2025.txt"),

    # DIRTY — state_code='TX' → Validation.4
    ("0000012345", "POL-FL-0005", "32202", "00000", "31", "TX",
     "HO3", "2025-05-10", "2026-05-10", "O1", "F", 2005, 5,
     195000, 200, 1850, "N",
     None, None, None, None, None,
     None, None,
     2025, "FHCF_D1A_0000012345_2025.txt"),

    # DIRTY — insurer_naic='123' (not 10 digits) → Validation.1
    ("123", "POL-FL-0006", "33122", "00000", "25", "FL",
     "HO3", "2025-06-01", "2026-06-01", "O1", "M", 2012, 3,
     380000, 500, 3200, "N",
     None, None, None, None, None,
     None, None,
     2025, "FHCF_D1A_0000012345_2025.txt"),

    # DIRTY — hurricane_deductible=1500 (out of [200,1000]) → Validation.5
    ("0000012345", "POL-FL-0007", "33480", "00000", "50", "FL",
     "HO3", "2025-07-15", "2026-07-15", "O1", "M", 2017, 3,
     720000, 1500, 7800, "N",
     None, None, None, None, None,
     None, None,
     2025, "FHCF_D1A_0000012345_2025.txt"),

    # DIRTY — coverage_a=10000000 (out of [50000,5000000]) → Validation.6
    ("0000012345", "POL-FL-0008", "33020", "00000", "11", "FL",
     "HO5", "2025-08-01", "2026-08-01", "O1", "S", 2019, 2,
     10000000, 500, 95000, "N",
     None, None, None, None, None,
     None, None,
     2025, "FHCF_D1A_0000012345_2025.txt"),

    # DIRTY — effective_date AFTER expiry_date → Validation.8
    ("0000012345", "POL-FL-0009", "34102", "00000", "21", "FL",
     "HO3", "2026-01-01", "2025-09-01", "O1", "F", 2008, 4,
     425000, 500, 4100, "N",
     None, None, None, None, None,
     None, None,
     2025, "FHCF_D1A_0000012345_2025.txt"),

    # DIRTY — year_built=1850 (<1900) → Validation.9
    ("0000012345", "POL-FL-0010", "32601", "00000", "01", "FL",
     "HO3", "2025-09-15", "2026-09-15", "O1", "F", 1850, 5,
     165000, 200, 1500, "N",
     None, None, None, None, None,
     None, None,
     2025, "FHCF_D1A_0000012345_2025.txt"),

    # DIRTY — wind_mitigation='Y' but companion fields all null → Validation.7
    ("0000012345", "POL-FL-0011", "33445", "00000", "50", "FL",
     "HO3", "2025-10-01", "2026-10-01", "O1", "M", 2016, 3,
     395000, 500, 3800, "Y",
     None, None, None, None, None,
     None, None,
     2025, "FHCF_D1A_0000012345_2025.txt"),

    # DIRTY — latitude populated, longitude null → Validation.10
    ("0000012345", "POL-FL-0012", "32034", "00000", "19", "FL",
     "HO3", "2025-11-01", "2026-11-01", "O1", "F", 2013, 4,
     245000, 500, 2300, "N",
     None, None, None, None, None,
     30670000, None,
     2025, "FHCF_D1A_0000012345_2025.txt"),
]


# DuckDB-compatible DDL for the FHCF gold exposure table. Mirrors
# scripts/run_fhcf.py's FHCF_GOLD_DDL column shape but uses DuckDB types
# directly so we don't have to translate. Schema-qualified to match the
# production target_table value 'GOLD.FHCF_EXPOSURE_RECORDS' — production
# /validate prepends 'INSURANCE_REGULATORY.', here we point it at our
# test schema.
_DDL = """
    CREATE SCHEMA IF NOT EXISTS gold;
    CREATE TABLE gold.fhcf_exposure_records (
        insurer_naic              VARCHAR,
        policy_number             VARCHAR,
        risk_zip                  VARCHAR,
        risk_zip4                 VARCHAR,
        county_fips               VARCHAR,
        state_code                VARCHAR,
        policy_form               VARCHAR,
        effective_date            DATE,
        expiry_date               DATE,
        occupancy_type            VARCHAR,
        construction_type         VARCHAR,
        year_built                INTEGER,
        protection_class          INTEGER,
        coverage_a                INTEGER,
        hurricane_deductible      INTEGER,
        written_premium           INTEGER,
        wind_mitigation           VARCHAR,
        opening_protection        VARCHAR,
        roof_cover_type           VARCHAR,
        roof_deck_attachment      VARCHAR,
        roof_to_wall_connection   VARCHAR,
        secondary_water_resistance VARCHAR,
        latitude                  BIGINT,
        longitude                 BIGINT,
        reporting_year            INTEGER,
        source_file               VARCHAR,
        filing_batch_id           VARCHAR
    );
"""

# Column order of FL_FHCF_FIXTURE_ROWS (filing_batch_id is stamped by the
# loader, not carried in the fixture tuples).
_FIXTURE_COLUMNS = [
    "insurer_naic", "policy_number", "risk_zip", "risk_zip4", "county_fips",
    "state_code", "policy_form", "effective_date", "expiry_date",
    "occupancy_type", "construction_type", "year_built", "protection_class",
    "coverage_a", "hurricane_deductible", "written_premium", "wind_mitigation",
    "opening_protection", "roof_cover_type", "roof_deck_attachment",
    "roof_to_wall_connection", "secondary_water_resistance",
    "latitude", "longitude", "reporting_year", "source_file",
]


@dataclass(frozen=True)
class RuleSpec:
    """Just the fields needed to execute a rule. Mirrors the columns
    api/rhs_demo.py:validate selects from REFERENCE.TSPR_VALIDATION_RULES."""
    rule_number: str
    rule_name: str
    target_table: str
    target_id_expr: str
    violation_sql: str


def _install_snowflake_aliases(conn: duckdb.DuckDBPyConnection) -> None:
    """Bridge the Snowflake → DuckDB dialect gap via MACROs. Lets rule
    SQL stay Snowflake-native (production source of truth) while still
    running in DuckDB for CI verification. Add more aliases here as
    new rules introduce Snowflake-specific functions."""
    # REGEXP_LIKE(s, pat) → regexp_matches(s, pat)
    conn.execute("CREATE OR REPLACE MACRO regexp_like(s, pat) AS regexp_matches(s, pat)")
    # TO_NUMBER(s) → CAST(s AS DOUBLE). Snowflake's TO_NUMBER also accepts
    # precision/scale args, but our FL rules use the 1-arg form.
    conn.execute("CREATE OR REPLACE MACRO to_number(s) AS CAST(s AS DOUBLE)")


def load_fl_bronze() -> duckdb.DuckDBPyConnection:
    """Open an in-memory DuckDB with gold.fhcf_exposure_records + the 12
    fixture rows (name kept for the existing test imports)."""
    conn = duckdb.connect()
    conn.execute(_DDL)
    _install_snowflake_aliases(conn)
    placeholders = ", ".join(["?"] * len(_FIXTURE_COLUMNS))
    conn.executemany(
        f"INSERT INTO gold.fhcf_exposure_records ({', '.join(_FIXTURE_COLUMNS)}, filing_batch_id) "
        f"VALUES ({placeholders}, 'FHCF-A-2026')",
        FL_FHCF_FIXTURE_ROWS,
    )
    return conn


def execute_rule(conn: duckdb.DuckDBPyConnection, rule: RuleSpec) -> list[str]:
    """Execute one rule the same way production does. Returns the list
    of record_ids that violated the rule (policy_numbers, since
    target_id_expr is 'j.policy_number')."""
    # production form (api/rhs_demo.py::_run_rules):
    #   SELECT {target_id_expr} AS record_id
    #   FROM INSURANCE_REGULATORY.{target_table} j
    #   WHERE ({violation_sql})
    # target_table is 'GOLD.FHCF_EXPOSURE_RECORDS' — warehouses are case-
    # insensitive, DuckDB is case-sensitive on quoted but tolerant on
    # unquoted. We just lowercase the schema-qualified name; the bare
    # 'gold.fhcf_exposure_records' matches our CREATE.
    target_clause = rule.target_table.lower()
    sql = (
        f"SELECT {rule.target_id_expr} AS record_id "
        f"FROM {target_clause} j "
        f"WHERE ({rule.violation_sql})"
    )
    return [row[0] for row in conn.execute(sql).fetchall()]


def fetch_fl_rules_from_kg() -> list[RuleSpec]:
    """Read every FL Rule with violation_sql from the KG."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        rows = s.run(
            """
            MATCH (r:Rule)-[:APPLIES_IN]->(:Jurisdiction {jurisdiction_code: 'US-FL'})
            WHERE r.violation_sql IS NOT NULL
            RETURN
                r.rule_number   AS rule_number,
                r.name          AS rule_name,
                r.target_table  AS target_table,
                r.target_id_expr AS target_id_expr,
                r.violation_sql AS violation_sql
            ORDER BY r.rule_number
            """
        ).data()
    return [
        RuleSpec(
            rule_number=str(r["rule_number"]),
            rule_name=r["rule_name"],
            target_table=r["target_table"],
            target_id_expr=r["target_id_expr"],
            violation_sql=r["violation_sql"],
        )
        for r in rows
    ]
