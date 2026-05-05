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

# Validation flags from Rule A.34 + Tex. Ins. Code §559.052(a)(2).
# These are stored as Rules in the KG; for now we encode them inline with
# explicit citations. A future iteration should derive them from rule edges.
SPECIAL_FLAGS: dict[str, dict[str, bool | str]] = {
    "L": {
        "credit_score_companion_required": True,
        "rationale": (
            "Tex. Ins. Code §559.052(a)(2) — credit/insurance score may not "
            "be the sole reason for cancellation, nonrenewal, or declination."
        ),
    },
    "J": {
        "must_appear_alone": True,
        "rationale": (
            "Rule A.34 — market withdrawal (J) cannot appear alongside any "
            "other reason code; it is a complete and standalone reason."
        ),
    },
}


def _q(s: str | None) -> str:
    """SQL-quote a string, escaping single quotes."""
    if s is None:
        return "NULL"
    return "'" + s.replace("'", "''") + "'"


def fetch_reason_codes() -> list[dict]:
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        result = s.run(
            """
            MATCH (cl:CodeList {name: $list_name})-[:HAS_VALUE]->(cv:CodeValue)
            OPTIONAL MATCH (cl)-[:CITES]->(doc:RegulationDocument)
            RETURN
              cv.code AS code,
              cv.notes AS description,
              cv.id AS code_id,
              cv.version AS version,
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
    out.append("    CONSTRAINT pk_tspr_reason_code_map PRIMARY KEY (tspr_reason_code)")
    out.append(") COMMENT = 'Section E reason codes (Notice Record Layout col36). Sourced from RegulAI KG.';")
    out.append("")
    out.append("DELETE FROM TSPR_REASON_CODE_MAP;")
    out.append("")

    for r in rows:
        flags = SPECIAL_FLAGS.get(r["code"], {})
        must_alone = "TRUE" if flags.get("must_appear_alone") else "FALSE"
        cs_companion = "TRUE" if flags.get("credit_score_companion_required") else "FALSE"
        rationale = flags.get("rationale")

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
            f"    {_q(r['code'])}, {_q(r['description'])}, {must_alone}, "
            f"{cs_companion}, {_q(rationale)}, "
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
        flags = SPECIAL_FLAGS.get(r["code"], {})
        flag_str = ""
        if flags.get("must_appear_alone"):
            flag_str = "  [must_appear_alone]"
        elif flags.get("credit_score_companion_required"):
            flag_str = "  [credit_score_companion_required]"
        print(f"  {r['code']}  {r['description']}{flag_str}")
    print()
    print(f"Next: make load-reference")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
