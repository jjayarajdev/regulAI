"""Generate REFERENCE.TSPR_REASON_CODE_MAP DDL + seed INSERTs from the KG.

The Snowflake reference schema is the data-plane projection of our regulatory
canon. This script reads Reason Code List nodes from Neo4j and emits a
Snowflake SQL file: one DDL + 21 INSERTs, each carrying a comment line that
cites the source plan section.

Output: materialized/reference/tspr_reason_code_map.sql

Run: `uv run python -m scripts.build_reference_reason_codes`
Then: `make load-reference`
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
from packages.config.settings import settings

REASON_CODE_LIST_NAME = "Reason Code List (RCL) — Notice Record Layout col36"

# Citations for the constraint flags now sourced from CodeValue properties
# in the KG. Rationale text remains here because the citation is editorial
# context for the SQL row, not regulatory canon. The flags themselves come
# from the KG and are subject to BulletinOverride versioning.
RATIONALE_BY_FLAG: dict[str, str] = {
    "must_appear_alone": (
        "Rule A.34 — market withdrawal cannot appear alongside any other "
        "reason code; it is a complete and standalone reason."
    ),
    "companion_required": (
        "Tex. Ins. Code §559.052(a)(2) — credit/insurance score may not "
        "be the sole reason for cancellation, nonrenewal, or declination."
    ),
}


def _q(s: str | None) -> str:
    """SQL-quote a string, escaping single quotes."""
    if s is None:
        return "NULL"
    return "'" + s.replace("'", "''") + "'"


def fetch_reason_codes() -> list[dict]:
    """Read active CodeValues for the Reason Code List with constraint flags.

    Edition pinning: only emit codes whose status is not 'superseded'. This
    ensures BulletinOverride re-evaluation (which marks old versions
    superseded and introduces new ones) is reflected in the next reference
    schema regeneration without any code change.
    """
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        result = s.run(
            """
            MATCH (cl:CodeList {name: $list_name})-[:HAS_VALUE]->(cv:CodeValue)
            WHERE cv.status IS NULL OR cv.status <> 'superseded'
            OPTIONAL MATCH (cl)-[:CITES]->(doc:RegulationDocument)
            RETURN
              cv.code AS code,
              cv.notes AS description,
              cv.id AS code_id,
              cv.version AS version,
              cv.must_appear_alone AS must_appear_alone,
              cv.companion_required AS companion_required,
              cv.effective_from AS effective_from,
              doc.id AS source_doc_id,
              doc.title AS source_doc_title
            ORDER BY cv.code
            """,
            list_name=REASON_CODE_LIST_NAME,
        )
        return [dict(r) for r in result]


def build_sql(rows: list[dict]) -> str:
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    out: list[str] = []
    out.append("-- =============================================================")
    out.append("-- INSURANCE_REGULATORY.REFERENCE.TSPR_REASON_CODE_MAP")
    out.append("-- Generated from RegulAI KG (single source of truth for plan rules).")
    out.append(f"-- Generated at: {now}")
    out.append(f"-- Source CodeList node: {REASON_CODE_LIST_NAME!r}")
    out.append(f"-- Neo4j: {settings.neo4j_uri}")
    out.append("--")
    out.append("-- DO NOT EDIT MANUALLY. Re-run `make build-reference` to regenerate.")
    out.append("-- =============================================================")
    out.append("")
    out.append("USE DATABASE INSURANCE_REGULATORY;")
    out.append("USE SCHEMA REFERENCE;")
    out.append("")
    out.append("CREATE OR REPLACE TABLE TSPR_REASON_CODE_MAP (")
    out.append("    tspr_reason_code                  CHAR(1) NOT NULL,")
    out.append("    jurisdiction_code                 VARCHAR(8) NOT NULL DEFAULT 'US-TX',")
    out.append("    description                       VARCHAR(255) NOT NULL,")
    out.append("    must_appear_alone                 BOOLEAN NOT NULL DEFAULT FALSE,")
    out.append("    credit_score_companion_required   BOOLEAN NOT NULL DEFAULT FALSE,")
    out.append("    constraint_rationale              VARCHAR(1024),")
    out.append("    -- Provenance back to the regulatory canon")
    out.append("    kg_code_value_id                  VARCHAR(64) NOT NULL,")
    out.append("    kg_source_document_id             VARCHAR(64),")
    out.append("    kg_source_document_title          VARCHAR(512),")
    out.append("    kg_canon_version                  NUMBER(10,0),")
    out.append("    generated_at                      TIMESTAMP_NTZ NOT NULL,")
    out.append("    CONSTRAINT pk_tspr_reason_code_map PRIMARY KEY (tspr_reason_code, jurisdiction_code)")
    out.append(") COMMENT = 'Section E reason codes (Notice Record Layout col36). Sourced from RegulAI KG. P2.3: scoped by jurisdiction; default US-TX.';")
    out.append("")
    out.append("DELETE FROM TSPR_REASON_CODE_MAP;")
    out.append("")

    for r in rows:
        must_alone = bool(r["must_appear_alone"])
        comp_req = bool(r["companion_required"])
        # Pick the rationale that matches whichever flag is set.
        rationale = None
        if must_alone:
            rationale = RATIONALE_BY_FLAG["must_appear_alone"]
        elif comp_req:
            rationale = RATIONALE_BY_FLAG["companion_required"]

        out.append(f"-- Code {r['code']}: {r['description']}")
        out.append("INSERT INTO TSPR_REASON_CODE_MAP (")
        out.append(
            "    tspr_reason_code, description, must_appear_alone, "
            "credit_score_companion_required, constraint_rationale, "
            "kg_code_value_id, kg_source_document_id, kg_source_document_title, "
            "kg_canon_version, generated_at"
        )
        out.append(") VALUES (")
        out.append(
            f"    {_q(r['code'])}, {_q(r['description'])}, "
            f"{'TRUE' if must_alone else 'FALSE'}, "
            f"{'TRUE' if comp_req else 'FALSE'}, {_q(rationale)}, "
            f"{_q(r['code_id'])}, {_q(r['source_doc_id'])}, "
            f"{_q(r['source_doc_title'])}, "
            f"{r['version'] if r['version'] is not None else 'NULL'}, "
            "CURRENT_TIMESTAMP()"
        )
        out.append(");")
        out.append("")

    out.append("-- Verification")
    out.append("SELECT")
    out.append("    COUNT(*) AS total_codes,")
    out.append("    SUM(IFF(must_appear_alone, 1, 0)) AS standalone_codes,")
    out.append("    SUM(IFF(credit_score_companion_required, 1, 0)) AS companion_required_codes")
    out.append("FROM TSPR_REASON_CODE_MAP;")
    out.append("")

    return "\n".join(out)


def main() -> int:
    rows = fetch_reason_codes()
    if not rows:
        print(f"ERROR: no codes found for CodeList '{REASON_CODE_LIST_NAME}'")
        return 1

    out_path = Path("materialized/reference/tspr_reason_code_map.sql")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_sql(rows))

    print(f"Wrote {out_path}  ({len(rows)} reason codes)")
    print()
    print("Codes:")
    for r in rows:
        flag_str = ""
        if r["must_appear_alone"]:
            flag_str = "  [must_appear_alone]"
        elif r["companion_required"]:
            flag_str = "  [companion_required]"
        eff_str = f"  (effective {r['effective_from']})" if r.get("effective_from") else ""
        print(f"  {r['code']}  {r['description']}{flag_str}{eff_str}")
    print()
    print(f"Next: make load-reference")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
