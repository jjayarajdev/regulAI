"""Attach executable violation_sql to the Oklahoma Rule nodes.

The OK intake (uploaded-ok-homeowners-stat-plan-2026) landed 10 approved
descriptive rules. This wires the mechanically-checkable predicate for each
onto its Rule node, following the FL pattern (migrate_fl_validation_rules):
match by Rule.name within APPLIES_IN → US-OK, SET the executable properties,
bump validation_version.

All rules target GOLD.OK_STAT_RECORDS — the filing-ready statistical record
table seeded by scripts/seed_ok_stat.py (a data-call style direct feed, like
FL's FHCF records; premium and loss records share the table, discriminated
by record_type 'P'/'L').

Validation then flows the existing path:
  KG Rule.violation_sql
    → REFERENCE.TSPR_VALIDATION_RULES (jurisdiction_code='US-OK',
      loaded by seed_ok_stat.py)
    → /api/rhs/validate?filing=OK-HO-2026A

Every rule self-tests in CI via tests/test_ok_rules_execute.py — DuckDB runs
the same SQL against in-process fixture rows (one designated violator per
rule, two clean policies).

Idempotent. Re-run safe. Requires the OK canon approved into the KG.
"""

from __future__ import annotations

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

_TABLE = "GOLD.OK_STAT_RECORDS"
_ID = "j.policy_number"

OK_VALIDATION_RULES = [
    {
        "match_name": "Rule 1 — Quarterly Reporting Obligation",
        "rule_number": "OK.1",
        "target_table": _TABLE,
        "target_id_expr": _ID,
        # §1 Rule 1: report within 45 days of the close of the quarter.
        "violation_sql": """
            j.reported_lag_days IS NULL OR j.reported_lag_days > 45
        """.strip(),
        "violation_reason": "Transaction reported more than 45 days after the close of the calendar quarter",
        "severity": "WARNING",
        "citation": "OK Statistical Plan §1, Rule 1",
    },
    {
        "match_name": "Rule 2 — Fixed-Width Record Format and NAIC Company Code",
        "rule_number": "OK.2",
        "target_table": _TABLE,
        "target_id_expr": _ID,
        "violation_sql": """
            j.naic_code IS NULL
            OR NOT REGEXP_LIKE(TRIM(j.naic_code), '^[0-9]{5}$')
        """.strip(),
        "violation_reason": "NAIC company code must be exactly 5 digits",
        "severity": "ERROR",
        "citation": "OK Statistical Plan §1, Rule 2",
    },
    {
        "match_name": "Rule 3 — County FIPS Code",
        "rule_number": "OK.3",
        "target_table": _TABLE,
        "target_id_expr": _ID,
        "violation_sql": """
            j.county_fips IS NULL
            OR NOT REGEXP_LIKE(TRIM(j.county_fips), '^[0-9]{3}$')
        """.strip(),
        "violation_reason": "County code must be the 3-digit FIPS code of the insured dwelling's county",
        "severity": "ERROR",
        "citation": "OK Statistical Plan §1, Rule 3",
    },
    {
        "match_name": "Rule 4 — Written Premium and Return Premium Reporting",
        "rule_number": "OK.4",
        "target_table": _TABLE,
        "target_id_expr": _ID,
        # Whole dollars; returns are negative amounts on the same code —
        # the mechanical check is whole-dollar-ness on premium records.
        "violation_sql": """
            j.record_type = 'P'
            AND (j.written_premium IS NULL
                 OR j.written_premium <> ROUND(j.written_premium))
        """.strip(),
        "violation_reason": "Written premium must be reported in whole dollars",
        "severity": "ERROR",
        "citation": "OK Statistical Plan §2, Rule 4",
    },
    {
        "match_name": "Rule 5 — Amount of Insurance for Coverage A",
        "rule_number": "OK.5",
        "target_table": _TABLE,
        "target_id_expr": _ID,
        "violation_sql": """
            j.record_type = 'P'
            AND (j.aoi_thousands IS NULL OR j.aoi_thousands <= 0)
        """.strip(),
        "violation_reason": "Amount of insurance (Coverage A, whole thousands) missing or non-positive on a premium record",
        "severity": "ERROR",
        "citation": "OK Statistical Plan §2, Rule 5",
    },
    {
        "match_name": "Rule 6 — Windstorm or Hail Deductible Type Codes",
        "rule_number": "OK.6",
        "target_table": _TABLE,
        "target_id_expr": _ID,
        # Percentage wind deductible → type 3; flat-dollar → type 2.
        "violation_sql": """
            j.wind_deductible_pct IS NOT NULL AND j.deductible_type <> '3'
        """.strip(),
        "violation_reason": "Percentage windstorm/hail deductible must carry deductible type code 3",
        "severity": "ERROR",
        "citation": "OK Statistical Plan §2, Rule 6",
    },
    {
        "match_name": "Rule 7 — Roof Impact-Resistance Mitigation Code",
        "rule_number": "OK.7",
        "target_table": _TABLE,
        "target_id_expr": _ID,
        "violation_sql": """
            j.mitigation_credit > 0
            AND (j.mitigation_code IS NULL OR TRIM(j.mitigation_code) = '')
        """.strip(),
        "violation_reason": "Mitigation premium credit reported without the mitigation code from the Section 4 code table",
        "severity": "WARNING",
        "citation": "OK Statistical Plan §2, Rule 7",
    },
    {
        "match_name": "Rule 8 — Paid Loss Reporting",
        "rule_number": "OK.8",
        "target_table": _TABLE,
        "target_id_expr": _ID,
        "violation_sql": """
            j.record_type = 'L' AND j.paid_amount > 0
            AND (j.cause_of_loss IS NULL OR j.accident_date IS NULL)
        """.strip(),
        "violation_reason": "Paid loss must carry the cause of loss code and the accident date",
        "severity": "ERROR",
        "citation": "OK Statistical Plan §3, Rule 8",
    },
    {
        "match_name": "Rule 9 — Claims Closed Without Payment",
        "rule_number": "OK.9",
        "target_table": _TABLE,
        "target_id_expr": _ID,
        "violation_sql": """
            j.record_type = 'L' AND j.disposition_code = 'C'
            AND j.paid_amount <> 0
        """.strip(),
        "violation_reason": "Closed-without-payment claims must report a paid amount of zero with disposition code C",
        "severity": "ERROR",
        "citation": "OK Statistical Plan §3, Rule 9",
    },
    {
        "match_name": "Rule 10 — Catastrophe Serial Number Reporting",
        "rule_number": "OK.10",
        "target_table": _TABLE,
        "target_id_expr": _ID,
        # Non-catastrophe losses report serial 0 — NULL means unreported.
        "violation_sql": """
            j.record_type = 'L' AND j.cat_serial IS NULL
        """.strip(),
        "violation_reason": "Loss record missing the catastrophe serial number (0 for non-catastrophe losses)",
        "severity": "WARNING",
        "citation": "OK Statistical Plan §3, Rule 10",
    },
]


def main() -> int:
    attached = 0
    missing: list[str] = []
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        for rule in OK_VALIDATION_RULES:
            r = s.run(
                """
                MATCH (r:Rule {name: $name})-[:APPLIES_IN]->(:Jurisdiction {jurisdiction_code: 'US-OK'})
                SET r.target_table = $target_table,
                    r.target_id_expr = $target_id_expr,
                    r.violation_sql = $violation_sql,
                    r.violation_reason = $violation_reason,
                    r.severity = $severity,
                    r.citation = $citation,
                    r.validation_version = COALESCE(r.validation_version, 0) + 1,
                    r.status = CASE WHEN r.status = 'superseded' THEN 'approved' ELSE COALESCE(r.status, 'approved') END
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
                print(f"  ✓ Attached: {rule['rule_number']:<8} → {rule['target_table']}")
                attached += 1
            else:
                missing.append(rule["rule_number"])
                print(f"  ⚠ Not found: {rule['rule_number']:<8} (name={rule['match_name'][:44]}…)")

    print()
    print(f"violation_sql attached to {attached}/{len(OK_VALIDATION_RULES)} OK Rule node(s).")
    if missing:
        print(f"Missing (approve the OK extraction into the KG first?): {missing}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
