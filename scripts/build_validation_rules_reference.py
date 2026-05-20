"""Generate REFERENCE.TSPR_VALIDATION_RULES from KG Rule nodes.

Reads every Rule that has been annotated with `validation_sql` (see
migrate_kg_validation_rules.py) and emits a Snowflake table whose rows
are executable: each carries the SQL expression the validation engine
evaluates, plus full provenance back to the regulatory citation.

P2.3 — jurisdiction-aware: filters rules to (US federal-default) ∪
(target jurisdiction-specific). Default jurisdiction is US-TX so the
existing demo flow is unchanged.

Run: `make build-validation-rules`           # → US-TX scope (default)
     `make build-validation-rules JUR=US-FL`  # → for a future state
Then: `make load-validation-rules`
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
from packages.config.settings import settings

OUT_DIR = Path("materialized/reference")
DEFAULT_JURISDICTION = "US-TX"


def _out_path_for(jurisdiction: str) -> Path:
    """Default jurisdiction (US-TX) keeps the legacy file path so existing
    Makefile + Snowflake-load wiring is unchanged. Other jurisdictions get
    a suffixed file so multi-state generation doesn't clobber TX."""
    if jurisdiction == DEFAULT_JURISDICTION:
        return OUT_DIR / "tspr_validation_rules.sql"
    suffix = jurisdiction.lower().replace("-", "_")
    return OUT_DIR / f"tspr_validation_rules_{suffix}.sql"


def _q(s) -> str:
    if s is None:
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"


def fetch_rules(jurisdiction: str = DEFAULT_JURISDICTION) -> list[dict]:
    """Return every Rule that's currently in force for `jurisdiction`.

    The result is the **union** of:
      - Rules with APPLIES_IN → US (federal defaults inherited by every state)
      - Rules with APPLIES_IN → :jurisdiction (state-specific rules)

    A state-specific rule that overrides a federal default (via
    `supersedes_federal_rule_id`) takes precedence — the federal default is
    excluded from the result for that jurisdiction.

    Other in-force filters (carried over from P1.2 fix):
      - has executable `violation_sql`
      - status is not 'superseded'
      - effective_from is null OR has already passed (not a future-dated v2)
      - effective_until is null OR has not yet arrived (not an expired v1)
    """
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        result = s.run(
            """
            // Union: federal defaults (US) + jurisdiction-specific (e.g. US-TX)
            MATCH (r:Rule)-[:APPLIES_IN]->(j:Jurisdiction)
            WHERE j.jurisdiction_code IN ['US', $jur]
              AND r.violation_sql IS NOT NULL
              AND (r.status IS NULL OR r.status <> 'superseded')
              AND (r.effective_from IS NULL OR r.effective_from <= date())
              AND (r.effective_until IS NULL OR r.effective_until >= date())
              // Exclude federal defaults that are overridden by a state-specific rule
              AND NOT EXISTS {
                MATCH (override:Rule)-[:APPLIES_IN]->(:Jurisdiction {jurisdiction_code: $jur})
                WHERE override.supersedes_federal_rule_id = r.id
                  AND (override.status IS NULL OR override.status <> 'superseded')
              }
            OPTIONAL MATCH (r)-[:CONTAINED_IN|CITES]->(d:RegulationDocument)
            WITH r, j, head(collect(d)) AS d
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
              j.jurisdiction_code AS jurisdiction_code,
              COALESCE(r.is_federal_default, false) AS is_federal_default,
              d.id AS source_doc_id,
              d.title AS source_doc_title
            ORDER BY r.rule_number
            """,
            jur=jurisdiction,
        )
        return [dict(r) for r in result]


def build_sql(rows: list[dict], jurisdiction: str) -> str:
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    out: list[str] = []
    out.append("-- =============================================================")
    out.append("-- INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES")
    out.append(f"-- Jurisdiction scope: {jurisdiction} ∪ US (federal defaults)")
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
    # Default 'US-TX' so hand-curated migrations (002, 003) that don't set
    # this column still load. Federal defaults are explicitly set to 'US'.
    out.append("    jurisdiction_code    VARCHAR(8)   NOT NULL DEFAULT 'US-TX',")
    out.append("    is_federal_default   BOOLEAN      NOT NULL DEFAULT FALSE,")
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
    out.append(") COMMENT = 'Executable validation rules. Sourced from RegulAI KG, scoped by jurisdiction.';")
    out.append("")
    out.append(f"-- Replace only this jurisdiction's rows so multi-jurisdiction loads accumulate safely.")
    out.append(f"DELETE FROM TSPR_VALIDATION_RULES WHERE jurisdiction_code = '{jurisdiction}';")
    out.append(f"DELETE FROM TSPR_VALIDATION_RULES WHERE jurisdiction_code = 'US';")
    out.append("")

    for r in rows:
        fed = "TRUE" if r.get("is_federal_default") else "FALSE"
        out.append(f"-- {r['rule_number']}: {r['name']}  (scope={r.get('jurisdiction_code')})")
        out.append("INSERT INTO TSPR_VALIDATION_RULES (")
        out.append(
            "    rule_id, rule_number, rule_name, section, jurisdiction_code, is_federal_default, "
            "target_table, target_id_expr, violation_sql, violation_reason, "
            "severity, citation, validation_version, kg_canon_version, "
            "kg_source_document_id, generated_at"
        )
        out.append(") VALUES (")
        out.append(
            f"    {_q(r['id'])}, {_q(r['rule_number'])}, {_q(r['name'])}, "
            f"{_q(r['section'])}, {_q(r.get('jurisdiction_code'))}, {fed}, "
            f"{_q(r['target_table'])}, "
            f"{_q(r['target_id_expr'])}, {_q(r['violation_sql'])}, "
            f"{_q(r['violation_reason'])}, {_q(r['severity'])}, "
            f"{_q(r['citation'])}, {r['validation_version']}, "
            f"{r['canon_version'] if r['canon_version'] is not None else 'NULL'}, "
            f"{_q(r['source_doc_id'])}, CURRENT_TIMESTAMP()"
        )
        out.append(");")
        out.append("")

    out.append("-- Verification")
    out.append("SELECT jurisdiction_code, severity, COUNT(*) AS n FROM TSPR_VALIDATION_RULES GROUP BY 1, 2 ORDER BY 1, 2;")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--jurisdiction", "-j", default=DEFAULT_JURISDICTION,
        help=f"Target jurisdiction code (e.g. US-TX, US-FL). Federal defaults always inherit. Default: {DEFAULT_JURISDICTION}",
    )
    args = ap.parse_args()

    rows = fetch_rules(jurisdiction=args.jurisdiction)
    if not rows:
        print(f"ERROR: no in-force Rule nodes with violation_sql found for {args.jurisdiction}.")
        print("       Run `make migrate-validation-rules` and (for Phase 2) `make seed-jurisdictions`.")
        return 1
    out_path = _out_path_for(args.jurisdiction)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_sql(rows, args.jurisdiction))
    print(f"Wrote {out_path}  ({len(rows)} rules for {args.jurisdiction} ∪ federal)")
    print()
    fed_count = sum(1 for r in rows if r.get("is_federal_default"))
    state_count = len(rows) - fed_count
    print(f"  Federal defaults  : {fed_count}")
    print(f"  State-specific    : {state_count}")
    print()
    for r in rows:
        marker = "🇺🇸" if r.get("is_federal_default") else f"  "
        print(f"  {marker} [{r['severity']:<7}] {r['rule_number']:<20} → {r['target_table']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
