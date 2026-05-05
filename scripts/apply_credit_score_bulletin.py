"""Materialize the synthetic credit-score declination bulletin into the KG.

Simulates what Sentinel would produce when extracting B-2026-Q4-118.md:
a new CodeValue for Reason Code L with `companion_required=false` and
`effective_from=2027-01-01`, plus a BulletinOverride node that links the
bulletin document to the old CodeValue it supersedes.

After this script runs, calling `apply_bulletin` (the existing version
bumper) will mark the old L superseded so the reference-schema regenerator
picks up the new L on its next run.

Idempotent — safe to re-run.

Run: `uv run python -m scripts.apply_credit_score_bulletin`
Then: `make apply-bulletin BULLETIN="Credit Score Declination Reporting Override"`
Then: `make load-reference`
Then: `make demo-join`  ← POL-0011 should flip from INVALID to VALID
"""

from __future__ import annotations

import datetime as dt
import uuid

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

BULLETIN_ID = "B-2026-Q4-118"
BULLETIN_TITLE = "Commissioner's Bulletin B-2026-Q4-118 — Credit Score Declination During Catastrophe Periods"
BULLETIN_DOC_ID = "doc:bulletin:B-2026-Q4-118"
BULLETIN_OVERRIDE_NAME = "Credit Score Declination Reporting Override"
BULLETIN_OVERRIDE_ID = "bo:credit-score-declination-override"
EFFECTIVE_DATE = "2027-01-01"

REASON_CODE_LIST_NAME = "Reason Code List (RCL) — Notice Record Layout col36"
TARGET_CODE = "L"

# Property delta the bulletin imposes on the new code version:
NEW_PROPERTIES = {
    "companion_required": False,
    # must_appear_alone unchanged; description unchanged.
}


def main() -> int:
    now_iso = dt.datetime.now(dt.UTC).isoformat()

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        # 1. Bulletin RegulationDocument
        s.run(
            """
            MERGE (d:GRENode:RegulationDocument {id: $doc_id})
            ON CREATE SET
                d.name        = $name,
                d.title       = $name,
                d.kind        = 'Bulletin',
                d.status      = 'approved',
                d.version     = 1,
                d.created_at  = $now,
                d.created_by  = 'apply_credit_score_bulletin',
                d.bulletin_ref = $bulletin_ref
            """,
            doc_id=BULLETIN_DOC_ID,
            name=BULLETIN_TITLE,
            bulletin_ref=BULLETIN_ID,
            now=now_iso,
        )
        print(f"  ✓ RegulationDocument: {BULLETIN_TITLE}")

        # 2. Find the existing CodeList + old L CodeValue
        rec = s.run(
            """
            MATCH (cl:CodeList {name: $list_name})-[:HAS_VALUE]->(cv:CodeValue {code: $code})
            WHERE cv.status IS NULL OR cv.status <> 'superseded'
            RETURN cl.id AS list_id, cv.id AS old_id, cv.notes AS notes,
                   cv.code_list_id AS code_list_id
            """,
            list_name=REASON_CODE_LIST_NAME,
            code=TARGET_CODE,
        ).single()
        if not rec:
            print(f"ERROR: no active Code {TARGET_CODE} found in {REASON_CODE_LIST_NAME!r}")
            return 1
        old_l_id = rec["old_id"]
        list_id = rec["list_id"]
        notes = rec["notes"]
        code_list_id = rec["code_list_id"]
        print(f"  ✓ Found old Code {TARGET_CODE}: id={old_l_id}")

        # 3. Create the NEW CodeValue (post-bulletin version)
        new_l_id = f"cv:reason-code-L:v2:{BULLETIN_ID}"
        s.run(
            """
            MERGE (cv:GRENode:CodeValue {id: $new_id})
            ON CREATE SET
                cv.name              = $name,
                cv.code              = $code,
                cv.code_list_id      = $code_list_id,
                cv.notes             = $notes,
                cv.description       = $notes,
                cv.must_appear_alone = false,
                cv.companion_required = $companion_required,
                cv.status            = 'draft',
                cv.version           = 2,
                cv.effective_from    = date($effective_from),
                cv.created_at        = $now,
                cv.created_by        = 'apply_credit_score_bulletin'
            WITH cv
            MATCH (cl:CodeList {id: $list_id})
            MERGE (cl)-[:HAS_VALUE]->(cv)
            """,
            new_id=new_l_id,
            name=f"Cause of Loss Code {TARGET_CODE} — post-{BULLETIN_ID}",
            code=TARGET_CODE,
            code_list_id=code_list_id,
            notes=notes,
            companion_required=NEW_PROPERTIES["companion_required"],
            effective_from=EFFECTIVE_DATE,
            list_id=list_id,
            now=now_iso,
        )
        print(f"  ✓ New CodeValue {TARGET_CODE} (v2): id={new_l_id}")
        print(f"    → companion_required = {NEW_PROPERTIES['companion_required']}")
        print(f"    → effective_from = {EFFECTIVE_DATE}")

        # 4. Create the BulletinOverride
        s.run(
            """
            MERGE (b:GRENode:BulletinOverride {id: $bo_id})
            ON CREATE SET
                b.name           = $name,
                b.title          = $name,
                b.bulletin_ref   = $bulletin_ref,
                b.effective_date = date($effective_from),
                b.effective_from = date($effective_from),
                b.status         = 'draft',
                b.version        = 1,
                b.created_at     = $now,
                b.created_by     = 'apply_credit_score_bulletin'
            WITH b
            MATCH (old:CodeValue {id: $old_id})
            MERGE (b)-[:OVERRIDES]->(old)
            WITH b
            MATCH (doc:RegulationDocument {id: $doc_id})
            MERGE (b)-[:CITES]->(doc)
            """,
            bo_id=BULLETIN_OVERRIDE_ID,
            name=BULLETIN_OVERRIDE_NAME,
            bulletin_ref=BULLETIN_ID,
            effective_from=EFFECTIVE_DATE,
            old_id=old_l_id,
            doc_id=BULLETIN_DOC_ID,
            now=now_iso,
        )
        print(f"  ✓ BulletinOverride: {BULLETIN_OVERRIDE_NAME!r}")

    print()
    print("Next steps:")
    print("  1. make apply-bulletin BULLETIN=\"Credit Score Declination Reporting Override\"")
    print("     (marks the old Code L superseded, sets effective_to)")
    print("  2. make load-reference")
    print("     (KG → SQL regenerates with new Code L)")
    print("  3. make demo-join")
    print("     (POL-0011 should flip from INVALID to VALID)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
