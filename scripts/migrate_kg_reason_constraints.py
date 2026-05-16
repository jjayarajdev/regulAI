"""Add Section E reason-code constraint properties to KG CodeValues.

Backfills `must_appear_alone` and `companion_required` boolean properties
on every CodeValue in the Reason Code List. These properties are the
machine-readable form of Rule A.34 and Tex. Ins. Code §559.052(a)(2),
which up to now lived only as text in our Rule nodes.

After this migration, the reference-schema generator can read constraint
flags directly from CodeValue properties rather than from a hardcoded
Python dict — and bulletin overrides become straightforward (a new
CodeValue with the property flipped supersedes the old one).

Idempotent. Run once after deploy:
  uv run python -m scripts.migrate_kg_reason_constraints
"""

from __future__ import annotations

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

REASON_CODE_LIST_NAME = "Reason Code List (RCL) — Notice Record Layout col36"

# Today's regulatory state. Sources:
#   J — Rule A.34 (TICO Stat Plan Section A) — market withdrawal stands alone
#   L — Tex. Ins. Code §559.052(a)(2)        — credit score needs companion
CONSTRAINTS = {
    "J": {"must_appear_alone": True,  "companion_required": False},
    "L": {"must_appear_alone": False, "companion_required": True},
}


def main() -> int:
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        # 1. Default everyone to FALSE/FALSE
        result = s.run(
            """
            MATCH (cl:CodeList {name: $list_name})-[:HAS_VALUE]->(cv:CodeValue)
            SET cv.must_appear_alone = COALESCE(cv.must_appear_alone, false),
                cv.companion_required = COALESCE(cv.companion_required, false)
            RETURN count(cv) AS n
            """,
            list_name=REASON_CODE_LIST_NAME,
        ).single()
        print(f"  defaults set on {result['n']} CodeValues (must_appear_alone=false, companion_required=false)")

        # 2. Apply known constraints
        for code, flags in CONSTRAINTS.items():
            r = s.run(
                """
                MATCH (cl:CodeList {name: $list_name})-[:HAS_VALUE]->(cv:CodeValue {code: $code})
                WHERE cv.status <> 'superseded'
                SET cv.must_appear_alone = $must_appear_alone,
                    cv.companion_required = $companion_required
                RETURN cv.id AS id, cv.code AS code
                """,
                list_name=REASON_CODE_LIST_NAME,
                code=code,
                **flags,
            ).single()
            if r:
                flag_str = ", ".join(f"{k}={v}" for k, v in flags.items() if v)
                print(f"  ✓ Code {r['code']} → {flag_str}")
            else:
                print(f"  ⚠ Code {code} not found (skipped)")

    print()
    print("Verify:")
    print("  cypher-shell> MATCH (cl:CodeList {name: '" + REASON_CODE_LIST_NAME + "'})-[:HAS_VALUE]->(cv)")
    print("                WHERE cv.must_appear_alone OR cv.companion_required")
    print("                RETURN cv.code, cv.must_appear_alone, cv.companion_required;")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
