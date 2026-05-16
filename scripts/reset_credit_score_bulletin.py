"""Roll back the credit-score declination bulletin from the KG.

Reverses what `apply_credit_score_bulletin.py` + `apply_bulletin` did:
deletes the new CodeValue, the BulletinOverride, and the bulletin
RegulationDocument, then unsupersedes the original Code L.

Use this between demo runs so the bulletin flip can be shown again.

Run: `uv run python -m scripts.reset_credit_score_bulletin`
"""

from __future__ import annotations

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

BULLETIN_DOC_ID = "doc:bulletin:B-2026-Q4-118"
BULLETIN_OVERRIDE_ID = "bo:credit-score-declination-override"
NEW_L_ID_PREFIX = "cv:reason-code-L:v2:"
REASON_CODE_LIST_NAME = "Reason Code List (RCL) — Notice Record Layout col36"


def main() -> int:
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        # Delete the new L CodeValue (and its HAS_VALUE edge from the CodeList)
        r = s.run(
            """
            MATCH (cv:CodeValue) WHERE cv.id STARTS WITH $prefix
            DETACH DELETE cv
            RETURN count(cv) AS n
            """,
            prefix=NEW_L_ID_PREFIX,
        ).single()
        print(f"  ✓ Deleted {r['n']} new CodeValue(s)")

        # Delete the BulletinOverride and its edges
        r = s.run(
            """
            MATCH (b:BulletinOverride {id: $id})
            DETACH DELETE b
            RETURN count(b) AS n
            """,
            id=BULLETIN_OVERRIDE_ID,
        ).single()
        print(f"  ✓ Deleted {r['n']} BulletinOverride(s)")

        # Delete the bulletin RegulationDocument
        r = s.run(
            """
            MATCH (d:RegulationDocument {id: $id})
            DETACH DELETE d
            RETURN count(d) AS n
            """,
            id=BULLETIN_DOC_ID,
        ).single()
        print(f"  ✓ Deleted {r['n']} bulletin RegulationDocument(s)")

        # Unsupersede the original L
        r = s.run(
            """
            MATCH (cl:CodeList {name: $list_name})-[:HAS_VALUE]->(cv:CodeValue {code: 'L'})
            WHERE cv.status = 'superseded'
            REMOVE cv.effective_to
            SET cv.status = 'approved'
            RETURN count(cv) AS n
            """,
            list_name=REASON_CODE_LIST_NAME,
        ).single()
        print(f"  ✓ Restored {r['n']} CodeValue(s) to active state")

    print()
    print("Run `make load-reference` and `make demo-join` to confirm baseline restored.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
