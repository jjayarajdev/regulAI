"""Attach executable violation_sql to FL Rule nodes.

Phase 3 ingested FL canon as statutory text only — Rule nodes had names,
sections, and citations, but no executable predicate. Cluster D wires the
RHS pipeline through FL, so the FL Rules need the same `violation_sql` /
`target_table` / `severity` properties their TX counterparts carry.

Scope (3 of FHCF's 10 validation rules, picked for clean SQL mappings):
  - Validation.2 ZIP_TX_PREFIX_INVALID  — risk_zip first digit must be '3'
  - Validation.3 COUNTY_FIPS_VALID       — county_fips in 01..67
  - Validation.4 STATE_CODE_FIXED        — state_code must equal 'FL'

The remaining 7 (NAIC_NUMERIC, HURRICANE_DEDUCTIBLE_RANGE, COVERAGE_A_
PLAUSIBLE, WIND_MITIGATION_FBC_REQUIRED, DATE_ORDER, YEAR_BUILT_RANGE,
GEOCODE_PRESENT_OR_NULL) are wired analogously when needed; leaving them
text-only keeps this commit small.

All three target BRONZE.FL_FHCF_POLICY — a dedicated FL Bronze table for
FHCF Annual Data Call exposure rows (DDL in materialized/reference/
fl_bronze_fhcf_policy.sql). Validation flows the existing path:
  KG Rule.violation_sql
    → build_validation_rules_reference.py --jur US-FL
    → REFERENCE.TSPR_VALIDATION_RULES
    → /api/rhs/validate?jurisdiction=US-FL

Idempotent. Re-run safe. Run after `make seed-florida`.
"""

from __future__ import annotations

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

FL_VALIDATION_RULES = [
    {
        "match_id": "e888b06a-c2f3-4d78-ad22-d9ef94d4f477",
        "rule_number": "Validation.2",
        "target_table": "BRONZE.FL_FHCF_POLICY",
        "target_id_expr": "p.policy_number",
        # First digit of a FL ZIP code is always '3'. TX ZIPs start with '7'.
        # Catches the obvious mis-routed-record bug where TX data lands in
        # an FL filing because of a typo in STATE_CODE.
        "violation_sql": """
            p.risk_zip IS NULL
            OR LENGTH(TRIM(p.risk_zip)) <> 5
            OR LEFT(TRIM(p.risk_zip), 1) <> '3'
        """.strip(),
        "violation_reason": "RISK_ZIP must be 5 digits beginning with '3' (Florida prefix); non-FL prefix is a hard validation error",
        "severity": "ERROR",
        "citation": "FHCF Data Call Form / Validation Rule 2 / §215.555(5)(b), F.S.",
    },
    {
        "match_id": "1968fbc3-057f-43c5-b88c-29904efe5f29",
        "rule_number": "Validation.3",
        "target_table": "BRONZE.FL_FHCF_POLICY",
        "target_id_expr": "p.policy_number",
        # Florida has exactly 67 counties; FIPS sub-codes 01..67.
        "violation_sql": """
            p.county_fips IS NULL
            OR NOT REGEXP_LIKE(p.county_fips, '^[0-9]{1,2}$')
            OR TO_NUMBER(p.county_fips) NOT BETWEEN 1 AND 67
        """.strip(),
        "violation_reason": "COUNTY_FIPS must be a numeric Florida county FIPS sub-code in 01..67",
        "severity": "ERROR",
        "citation": "FHCF Data Call Form / Validation Rule 3",
    },
    {
        "match_id": "fdad27df-5324-4b87-b75c-07b651d55437",
        "rule_number": "Validation.4",
        "target_table": "BRONZE.FL_FHCF_POLICY",
        "target_id_expr": "p.policy_number",
        # The FHCF only accepts FL-domiciled risks. Any other STATE_CODE on
        # an FHCF row is structurally wrong (probably a misrouted record).
        "violation_sql": """
            p.state_code IS NULL
            OR UPPER(TRIM(p.state_code)) <> 'FL'
        """.strip(),
        "violation_reason": "STATE_CODE must equal 'FL' exactly — FHCF only covers Florida-domiciled risks",
        "severity": "ERROR",
        "citation": "FHCF Data Call Form / Validation Rule 4 / §215.555(2)(a), F.S.",
    },
]


def main() -> int:
    print("Attaching executable violation_sql to FL Rule nodes\n")
    attached = 0
    missing: list[str] = []
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        for rule in FL_VALIDATION_RULES:
            r = s.run(
                """
                MATCH (r:Rule {id: $id})
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
                id=rule["match_id"],
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
                print(f"  ⚠ Not found: {rule['rule_number']:<16} (id={rule['match_id'][:16]}…)")

    print()
    print(f"violation_sql attached to {attached}/{len(FL_VALIDATION_RULES)} FL Rule node(s).")
    if missing:
        print(f"Missing (run `make rebuild-kg && make seed-florida` first?): {missing}")
        return 1
    print("Next: make build-validation-rules JUR=US-FL && make load-validation-rules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
