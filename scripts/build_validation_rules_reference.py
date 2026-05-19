"""Generate REFERENCE.TSPR_VALIDATION_RULES from KG Rule nodes.

Reads every Rule that has been annotated with `validation_sql` (see
migrate_kg_validation_rules.py) and emits a Snowflake table whose rows
are executable: each carries the SQL expression the validation engine
evaluates, plus full provenance back to the regulatory citation.

Run: `make build-validation-rules`
Then: `make load-validation-rules`
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
from packages.config.settings import settings

OUT_PATH = Path("materialized/reference/tspr_validation_rules.sql")


def _q(s) -> str:
    if s is None:
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"


def fetch_rules() -> list[dict]:
    """Return every Rule node that is currently in force.

    Currently-in-force means:
      - has executable `violation_sql`
      - status is not 'superseded'
      - effective_from is null OR has already passed (not a future-dated v2)
      - effective_until is null OR has not yet arrived (not an expired v1)

    The temporal filter is critical: without it, when a v2 of a Rule exists
    with effective_from=future-date, both v1 (status='approved',
    effective_until=null) and v2 (status='approved', effective_from=future)
    pass the status filter and the reference table ends up with two rows
    for the same rule_number — validation runs the predicate twice.
    """
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        result = s.run(
            """
            MATCH (r:Rule)
            WHERE r.violation_sql IS NOT NULL
              AND (r.status IS NULL OR r.status <> 'superseded')
              AND (r.effective_from IS NULL OR r.effective_from <= date())
              AND (r.effective_until IS NULL OR r.effective_until >= date())
            OPTIONAL MATCH (r)-[:CONTAINED_IN|CITES]->(d:RegulationDocument)
            WITH r, head(collect(d)) AS d
            RETURN
              r.id AS id,
              r.rule_number AS rule_number,
              r.name AS name,
              r.section AS section,
              r.target_table AS target_table,
              r.target_id_expr AS target_id_expr,
              r.violation_sql AS violation_sql,
              r.violation_reason AS violation_reason,
              r.severity AS severity,
              r.citation AS citation,
              COALESCE(r.validation_version, 1) AS validation_version,
              r.version AS canon_version,
              d.id AS source_doc_id,
              d.title AS source_doc_title
            ORDER BY r.rule_number
            """
        )
        return [dict(r) for r in result]


def build_sql(rows: list[dict]) -> str:
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    out: list[str] = []
    out.append("-- =============================================================")
    out.append("-- INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES")
    out.append(f"-- TICO Section A — executable plan rules generated from RegulAI KG")
    out.append(f"-- Generated at: {now}")
    out.append(f"-- Neo4j: {settings.neo4j_uri}")
    out.append("-- =============================================================")
    out.append("")
    out.append("USE DATABASE INSURANCE_REGULATORY;")
    out.append("USE SCHEMA REFERENCE;")
    out.append("")
    out.append("CREATE OR REPLACE TABLE TSPR_VALIDATION_RULES (")
    out.append("    rule_id              VARCHAR(64)  NOT NULL,")
    out.append("    rule_number          VARCHAR(32)  NOT NULL,")
    out.append("    rule_name            VARCHAR(512) NOT NULL,")
    out.append("    section              VARCHAR(8),")
    out.append("    target_table         VARCHAR(128) NOT NULL,")
    out.append("    target_id_expr       VARCHAR(1024),")
    out.append("    violation_sql        VARCHAR(8000) NOT NULL,")
    out.append("    violation_reason     VARCHAR(1024) NOT NULL,")
    out.append("    severity             VARCHAR(16)   NOT NULL,")
    out.append("    citation             VARCHAR(1024),")
    out.append("    validation_version   NUMBER(10,0)  NOT NULL,")
    out.append("    kg_canon_version     NUMBER(10,0),")
    out.append("    kg_source_document_id VARCHAR(64),")
    out.append("    generated_at         TIMESTAMP_NTZ NOT NULL,")
    out.append("    CONSTRAINT pk_tspr_validation_rules PRIMARY KEY (rule_id)")
    out.append(") COMMENT = 'TICO Section A — executable validation rules. Sourced from RegulAI KG.';")
    out.append("")
    out.append("DELETE FROM TSPR_VALIDATION_RULES;")
    out.append("")

    for r in rows:
        out.append(f"-- {r['rule_number']}: {r['name']}")
        out.append("INSERT INTO TSPR_VALIDATION_RULES (")
        out.append(
            "    rule_id, rule_number, rule_name, section, "
            "target_table, target_id_expr, violation_sql, violation_reason, "
            "severity, citation, validation_version, kg_canon_version, "
            "kg_source_document_id, generated_at"
        )
        out.append(") VALUES (")
        out.append(
            f"    {_q(r['id'])}, {_q(r['rule_number'])}, {_q(r['name'])}, "
            f"{_q(r['section'])}, {_q(r['target_table'])}, "
            f"{_q(r['target_id_expr'])}, {_q(r['violation_sql'])}, "
            f"{_q(r['violation_reason'])}, {_q(r['severity'])}, "
            f"{_q(r['citation'])}, {r['validation_version']}, "
            f"{r['canon_version'] if r['canon_version'] is not None else 'NULL'}, "
            f"{_q(r['source_doc_id'])}, CURRENT_TIMESTAMP()"
        )
        out.append(");")
        out.append("")

    out.append("-- Verification")
    out.append("SELECT severity, COUNT(*) AS n FROM TSPR_VALIDATION_RULES GROUP BY severity;")
    return "\n".join(out)


def main() -> int:
    rows = fetch_rules()
    if not rows:
        print("ERROR: no Rule nodes with violation_sql found. Run migrate_kg_validation_rules.py first.")
        return 1
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(build_sql(rows))
    print(f"Wrote {OUT_PATH}  ({len(rows)} rules)")
    print()
    for r in rows:
        print(f"  [{r['severity']:<7}] {r['rule_number']:<20} → {r['target_table']}")
        print(f"            {r['violation_reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
