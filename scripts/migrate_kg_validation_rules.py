"""Add executable validation properties to KG Rule nodes.

Today our Rule nodes carry the regulatory text (rule_number, name, section,
document_id) but no executable form. This migration attaches:
  - target_table     — which Bronze table the rule checks
  - target_id_expr   — SQL expression that produces a human-readable record id
  - violation_sql    — TRUE means this row violates the rule
  - violation_reason — short description shown to the actuary
  - severity         — ERROR or WARNING
  - citation         — exact regulatory citation
  - validation_version — incremented when the SQL is updated

The validation_sql expressions are designed to depend on REFERENCE.* tables
where appropriate, so a BulletinOverride that flips a flag in the reference
schema (e.g. companion_required on Code L) automatically changes the rule's
output without rewriting any SQL.

Idempotent. Run after deploying the KG / before generating
REFERENCE.TSPR_VALIDATION_RULES.
"""

from __future__ import annotations

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

VALIDATION_RULES = [
    {
        "match_id": "287871fa-72fc-4a42-8300-9377d69e97db",  # Rule A.34 — Reason Codes
        "rule_number": "A.34",
        "target_table": "BRONZE.GW_PC_JOB",
        "target_id_expr": "j.publicid",
        # Pure Snowflake expression — no correlated subqueries. The validator
        # JOINs to GW_PC_POLICY in Python to map publicid → policy number.
        "violation_sql": """
            LENGTH(COALESCE(j.declinereason, j.cancellationreason, j.nonrenewalreason)) = 1
            AND COALESCE(j.declinereason, j.cancellationreason, j.nonrenewalreason) IN (
              SELECT tspr_reason_code FROM INSURANCE_REGULATORY.REFERENCE.TSPR_REASON_CODE_MAP
              WHERE credit_score_companion_required = TRUE
            )
        """.strip(),
        "violation_reason": "Reason Code L (credit/insurance score) requires at least one companion reason code",
        "severity": "ERROR",
        "citation": "Tex. Ins. Code §559.052(a)(2); TICO Stat Plan Rule A.34",
    },
    {
        "match_id": "2d01fd58-bc62-421e-a211-c740371fce4a",  # Rule A.34 — J-alone variant
        "rule_number": "A.34-J-alone",
        "target_table": "BRONZE.GW_PC_JOB",
        "target_id_expr": "j.publicid",
        # Cross-join + WHERE: Snowflake handles this cleanly because the
        # reference subquery lives at the FROM level.
        "violation_sql": """
            LENGTH(COALESCE(j.declinereason, j.cancellationreason, j.nonrenewalreason)) > 1
            AND COALESCE(j.declinereason, j.cancellationreason, j.nonrenewalreason) LIKE ANY (
              SELECT '%' || tspr_reason_code || '%'
              FROM INSURANCE_REGULATORY.REFERENCE.TSPR_REASON_CODE_MAP
              WHERE must_appear_alone = TRUE
            )
        """.strip(),
        "violation_reason": "A reason code marked must_appear_alone (e.g. J — market withdrawal) cannot be combined with others",
        "severity": "ERROR",
        "citation": "TICO Stat Plan Rule A.34",
    },
    {
        "match_id": "192283ed-3597-46fb-899f-6bc258c450e8",  # Rule A.22 — Company Number
        "rule_number": "A.22",
        "target_table": "BRONZE.GW_PC_POLICYPERIOD",
        "target_id_expr": "j.publicid",
        "violation_sql": """
            j.naic_number IS NULL
            OR LENGTH(TRIM(j.naic_number)) <> 5
            OR NOT REGEXP_LIKE(j.naic_number, '^[0-9]{5}$')
        """.strip(),
        "violation_reason": "NAIC company number must be present and exactly 5 numeric digits",
        "severity": "ERROR",
        "citation": "TICO Stat Plan Rule A.22",
    },
    {
        "match_id": "287871fa-72fc-4a42-8300-9377d69e97db-validity",
        "create_if_missing": True,
        "rule_number": "A.34-valid-codes",
        "rule_label": "Reason codes must be defined in the plan",
        "rule_text": "Every reason code reported on a Section E notice must be a code published in the Reason Code List.",
        "target_table": "BRONZE.GW_PC_JOB",
        "target_id_expr": "j.publicid",
        # For each character in the reason string, check it's in the reference.
        # Uses LATERAL FLATTEN over a SPLIT array — Snowflake-native.
        # Convention: every reason letter must appear in REFERENCE — flag if
        # any letter doesn't match a known code. Pre-check via NOT LIKE ALL of
        # known codes is awkward; use a NOT-IN against a single-letter array.
        "violation_sql": """
            COALESCE(j.declinereason, j.cancellationreason, j.nonrenewalreason) IS NOT NULL
            AND NOT COALESCE(j.declinereason, j.cancellationreason, j.nonrenewalreason) RLIKE
              '^(' || (
                SELECT LISTAGG(tspr_reason_code, '|') WITHIN GROUP (ORDER BY tspr_reason_code)
                FROM INSURANCE_REGULATORY.REFERENCE.TSPR_REASON_CODE_MAP
              ) || ')+$'
        """.strip(),
        "violation_reason": "One or more reason letters are not part of the published Reason Code List",
        "severity": "ERROR",
        "citation": "TICO Stat Plan Rule A.34 / Section E",
    },
]


def main() -> int:
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        attached = 0
        for rule in VALIDATION_RULES:
            if rule.get("create_if_missing"):
                # Create a fresh Rule node with this validation embedded
                s.run(
                    """
                    MERGE (r:GRENode:Rule {id: $id})
                    ON CREATE SET
                        r.name = $name,
                        r.title = $name,
                        r.rule_number = $rule_number,
                        r.section = 'A',
                        r.status = 'approved',
                        r.version = 1
                    SET r.target_table = $target_table,
                        r.target_id_expr = $target_id_expr,
                        r.violation_sql = $violation_sql,
                        r.violation_reason = $violation_reason,
                        r.severity = $severity,
                        r.citation = $citation,
                        r.validation_version = COALESCE(r.validation_version, 0) + 1
                    """,
                    id=rule["match_id"],
                    name=rule["rule_label"],
                    rule_number=rule["rule_number"],
                    target_table=rule["target_table"],
                    target_id_expr=rule["target_id_expr"],
                    violation_sql=rule["violation_sql"],
                    violation_reason=rule["violation_reason"],
                    severity=rule["severity"],
                    citation=rule["citation"],
                )
                print(f"  ✓ Created/attached: {rule['rule_number']:<24} → {rule['target_table']}")
                attached += 1
            else:
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
                    RETURN r.id
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
                    print(f"  ✓ Attached:        {rule['rule_number']:<24} → {rule['target_table']}")
                    attached += 1
                else:
                    print(f"  ⚠ Not found:       {rule['rule_number']:<24} (id={rule['match_id'][:16]}…)")

    print()
    print(f"Validation properties attached to {attached} Rule node(s).")
    print("Next: make build-validation-rules && make load-validation-rules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
