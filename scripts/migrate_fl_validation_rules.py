"""Attach executable violation_sql to FL Rule nodes.

Phase 3 ingested FL canon as statutory text only — Rule nodes had names,
sections, and citations, but no executable predicate. Cluster D + the
follow-up wire all 10 FHCF Data Call validation rules so the RHS pipeline
runs FL filings through the same /validate path TX uses.

Wired rules (all 10 from the FHCF Data Call Form's Validation Rules
section):
  Validation.1  NAIC_NUMERIC                — insurer_naic must be 10 digits
  Validation.2  ZIP_TX_PREFIX_INVALID       — risk_zip first digit must be '3'
  Validation.3  COUNTY_FIPS_VALID            — county_fips in 01..67
  Validation.4  STATE_CODE_FIXED             — state_code must equal 'FL'
  Validation.5  HURRICANE_DEDUCTIBLE_RANGE   — hurricane_deductible in [200,1000]
  Validation.6  COVERAGE_A_PLAUSIBLE         — coverage_a in [$50k, $5M]
  Validation.7  WIND_MITIGATION_FBC_REQUIRED — if wind_mitigation='Y', all
                                                5 companion fields required
  Validation.8  DATE_ORDER                   — effective_date < expiry_date
  Validation.9  YEAR_BUILT_RANGE             — year_built in [1900, reporting_year]
  Validation.10 GEOCODE_PRESENT_OR_NULL      — latitude/longitude both or neither

All target BRONZE.FL_FHCF_POLICY. Validation flows the existing path:
  KG Rule.violation_sql
    → build_validation_rules_reference.py --jur US-FL
    → REFERENCE.TSPR_VALIDATION_RULES
    → /api/rhs/validate?jurisdiction=US-FL

Every rule self-tests in CI via tests/test_fl_rules_execute.py — DuckDB
runs the same SQL the production endpoint runs against in-process
synthetic data.

Idempotent. Re-run safe. Run after `make seed-florida`.
"""

from __future__ import annotations

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

FL_VALIDATION_RULES = [
    {
        "match_name": "Rule Validation.1 — NAIC_NUMERIC",
        "rule_number": "Validation.1",
        "target_table": "BRONZE.FL_FHCF_POLICY",
        "target_id_expr": "j.policy_number",
        # NAIC must be exactly 10 digits, leading-zero padded.
        "violation_sql": """
            j.insurer_naic IS NULL
            OR LENGTH(TRIM(j.insurer_naic)) <> 10
            OR NOT REGEXP_LIKE(j.insurer_naic, '^[0-9]{10}$')
        """.strip(),
        "violation_reason": "INSURER_NAIC must be exactly 10 digits, leading-zero padded; non-numeric records are rejected",
        "severity": "ERROR",
        "citation": "FHCF Data Call Form / Validation Rule 1",
    },
    {
        "match_name": "Rule Validation.2 — ZIP_TX_PREFIX_INVALID",
        "rule_number": "Validation.2",
        "target_table": "BRONZE.FL_FHCF_POLICY",
        "target_id_expr": "j.policy_number",
        # First digit of a FL ZIP code is always '3'. TX ZIPs start with '7'.
        # Catches the obvious mis-routed-record bug where TX data lands in
        # an FL filing because of a typo in STATE_CODE.
        "violation_sql": """
            j.risk_zip IS NULL
            OR LENGTH(TRIM(j.risk_zip)) <> 5
            OR LEFT(TRIM(j.risk_zip), 1) <> '3'
        """.strip(),
        "violation_reason": "RISK_ZIP must be 5 digits beginning with '3' (Florida prefix); non-FL prefix is a hard validation error",
        "severity": "ERROR",
        "citation": "FHCF Data Call Form / Validation Rule 2 / §215.555(5)(b), F.S.",
    },
    {
        "match_name": "Rule Validation.3 — COUNTY_FIPS_VALID",
        "rule_number": "Validation.3",
        "target_table": "BRONZE.FL_FHCF_POLICY",
        "target_id_expr": "j.policy_number",
        # Florida has exactly 67 counties; FIPS sub-codes 01..67.
        "violation_sql": """
            j.county_fips IS NULL
            OR NOT REGEXP_LIKE(j.county_fips, '^[0-9]{1,2}$')
            OR TO_NUMBER(j.county_fips) NOT BETWEEN 1 AND 67
        """.strip(),
        "violation_reason": "COUNTY_FIPS must be a numeric Florida county FIPS sub-code in 01..67",
        "severity": "ERROR",
        "citation": "FHCF Data Call Form / Validation Rule 3",
    },
    {
        "match_name": "Rule Validation.4 — STATE_CODE_FIXED",
        "rule_number": "Validation.4",
        "target_table": "BRONZE.FL_FHCF_POLICY",
        "target_id_expr": "j.policy_number",
        # The FHCF only accepts FL-domiciled risks. Any other STATE_CODE on
        # an FHCF row is structurally wrong (probably a misrouted record).
        "violation_sql": """
            j.state_code IS NULL
            OR UPPER(TRIM(j.state_code)) <> 'FL'
        """.strip(),
        "violation_reason": "STATE_CODE must equal 'FL' exactly — FHCF only covers Florida-domiciled risks",
        "severity": "ERROR",
        "citation": "FHCF Data Call Form / Validation Rule 4 / §215.555(2)(a), F.S.",
    },
    {
        "match_name": "Rule Validation.5 — HURRICANE_DEDUCTIBLE_RANGE",
        "rule_number": "Validation.5",
        "target_table": "BRONZE.FL_FHCF_POLICY",
        "target_id_expr": "j.policy_number",
        # Hurricane deductible reported as pct * 100; range [200,1000] = 2%..10%.
        # Spec says "soft warning requiring justification" — modeled as WARNING.
        "violation_sql": """
            j.hurricane_deductible IS NOT NULL
            AND (j.hurricane_deductible < 200 OR j.hurricane_deductible > 1000)
        """.strip(),
        "violation_reason": "HURRICANE_DEDUCTIBLE outside [200,1000] (2%..10%) — soft warning, requires justification",
        "severity": "WARNING",
        "citation": "FHCF Data Call Form / Validation Rule 5",
    },
    {
        "match_name": "Rule Validation.6 — COVERAGE_A_PLAUSIBLE",
        "rule_number": "Validation.6",
        "target_table": "BRONZE.FL_FHCF_POLICY",
        "target_id_expr": "j.policy_number",
        # Coverage A plausibility band: $50k..$5M. Outside → warning.
        "violation_sql": """
            j.coverage_a IS NOT NULL
            AND (j.coverage_a < 50000 OR j.coverage_a > 5000000)
        """.strip(),
        "violation_reason": "COVERAGE_A outside [$50,000, $5,000,000] plausibility band",
        "severity": "WARNING",
        "citation": "FHCF Data Call Form / Validation Rule 6",
    },
    {
        "match_name": "Rule Validation.7 — WIND_MITIGATION_FBC_REQUIRED",
        "rule_number": "Validation.7",
        "target_table": "BRONZE.FL_FHCF_POLICY",
        "target_id_expr": "j.policy_number",
        # If WIND_MITIGATION='Y', all 5 companion FBC fields must be populated.
        "violation_sql": """
            UPPER(TRIM(j.wind_mitigation)) = 'Y'
            AND (
                j.opening_protection IS NULL OR TRIM(j.opening_protection) = ''
             OR j.roof_cover_type IS NULL OR TRIM(j.roof_cover_type) = ''
             OR j.roof_deck_attachment IS NULL OR TRIM(j.roof_deck_attachment) = ''
             OR j.roof_to_wall_connection IS NULL OR TRIM(j.roof_to_wall_connection) = ''
             OR j.secondary_water_resistance IS NULL OR TRIM(j.secondary_water_resistance) = ''
            )
        """.strip(),
        "violation_reason": "WIND_MITIGATION='Y' requires all 5 FBC companion fields (opening protection, roof cover, roof deck attachment, roof-to-wall connection, secondary water resistance)",
        "severity": "ERROR",
        "citation": "FHCF Data Call Form / Validation Rule 7",
    },
    {
        "match_name": "Rule Validation.8 — DATE_ORDER",
        "rule_number": "Validation.8",
        "target_table": "BRONZE.FL_FHCF_POLICY",
        "target_id_expr": "j.policy_number",
        # Effective must strictly precede expiry. NULLs on either side are
        # also a malformed policy.
        "violation_sql": """
            j.effective_date IS NULL
            OR j.expiry_date IS NULL
            OR j.effective_date >= j.expiry_date
        """.strip(),
        "violation_reason": "EFFECTIVE_DATE must precede EXPIRY_DATE; both must be populated",
        "severity": "ERROR",
        "citation": "FHCF Data Call Form / Validation Rule 8",
    },
    {
        "match_name": "Rule Validation.9 — YEAR_BUILT_RANGE",
        "rule_number": "Validation.9",
        "target_table": "BRONZE.FL_FHCF_POLICY",
        "target_id_expr": "j.policy_number",
        # Year built in [1900, reporting_year]. Reporting year is on each row,
        # so we self-reference it for the upper bound.
        "violation_sql": """
            j.year_built IS NULL
            OR j.year_built < 1900
            OR j.year_built > j.reporting_year
        """.strip(),
        "violation_reason": "YEAR_BUILT must be between 1900 and the current reporting year",
        "severity": "ERROR",
        "citation": "FHCF Data Call Form / Validation Rule 9",
    },
    {
        "match_name": "Rule Validation.10 — GEOCODE_PRESENT_OR_NULL",
        "rule_number": "Validation.10",
        "target_table": "BRONZE.FL_FHCF_POLICY",
        "target_id_expr": "j.policy_number",
        # Both populated or both null (XOR of nullness is the violation).
        "violation_sql": """
            (j.latitude IS NULL AND j.longitude IS NOT NULL)
            OR (j.latitude IS NOT NULL AND j.longitude IS NULL)
        """.strip(),
        "violation_reason": "LATITUDE and LONGITUDE must both be populated or both null; mixed null state rejected",
        "severity": "ERROR",
        "citation": "FHCF Data Call Form / Validation Rule 10",
    },
]


def main() -> int:
    print("Attaching executable violation_sql to FL Rule nodes\n")
    attached = 0
    missing: list[str] = []
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        for rule in FL_VALIDATION_RULES:
            # Match by Rule.name — survives UUID-scheme changes and is
            # more readable than chasing a hardcoded UUID. Names of FHCF
            # validation rules are unique within FL jurisdiction.
            r = s.run(
                """
                MATCH (r:Rule {name: $name})-[:APPLIES_IN]->(:Jurisdiction {jurisdiction_code: 'US-FL'})
                SET r.target_table = $target_table,
                    r.target_id_expr = $target_id_expr,
                    r.violation_sql = $violation_sql,
                    r.violation_reason = $violation_reason,
                    r.severity = $severity,
                    r.citation = $citation,
                    r.validation_version = COALESCE(r.validation_version, 0) + 1,
                    r.status = CASE WHEN r.status = 'superseded' THEN 'approved' ELSE COALESCE(r.status, 'approved') END
                REMOVE r.effective_to
                RETURN r.id AS id
                """,
                name=rule["match_name"],
                target_table=rule["target_table"],
                target_id_expr=rule["target_id_expr"],
                violation_sql=rule["violation_sql"],
                violation_reason=rule["violation_reason"],
                severity=rule["severity"],
                citation=rule["citation"],
            ).single()
            if r:
                print(f"  ✓ Attached: {rule['rule_number']:<16} → {rule['target_table']}")
                attached += 1
            else:
                missing.append(rule["rule_number"])
                print(f"  ⚠ Not found: {rule['rule_number']:<16} (name={rule['match_name'][:40]}…)")

    print()
    print(f"violation_sql attached to {attached}/{len(FL_VALIDATION_RULES)} FL Rule node(s).")
    if missing:
        print(f"Missing (run `make rebuild-kg && make seed-florida` first?): {missing}")
        return 1
    print("Next: make build-validation-rules JUR=US-FL && make load-validation-rules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
