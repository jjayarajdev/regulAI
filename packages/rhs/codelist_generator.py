"""Generic CodeList → Snowflake reference-table generator.

Takes a CodeList name in the KG and produces a SQL file with:
  - DDL for the target table
  - INSERT rows with KG provenance columns (kg_code_value_id, kg_canon_version)
  - Verification SELECT

Used by `scripts/build_all_reference_tables.py` to materialize multiple
TICO sections at once. Edition-pinning (`status <> 'superseded'`) is
applied so BulletinOverride re-evaluation flows through.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
from packages.config.settings import settings


@dataclass(frozen=True)
class ReferenceSpec:
    """Definition of one Snowflake reference table to materialize from the KG."""

    section: str
    """TICO Stat Plan section, e.g. 'B.4', 'E'."""

    description: str
    """Brief human-readable purpose."""

    codelist_name: str
    """Exact name of the CodeList node in the KG."""

    target_table: str
    """Snowflake table name (qualified `REFERENCE.<...>`)."""

    extra_columns: tuple[str, ...] = ()
    """Optional extra DDL columns beyond the standard set."""

    extra_value_lookup: dict[str, dict] | None = None
    """Optional per-code values for extra columns (e.g. validation flags)."""


def _q(s: str | None) -> str:
    if s is None:
        return "NULL"
    return "'" + s.replace("'", "''") + "'"


def _b(v: bool | None) -> str:
    return "TRUE" if v else "FALSE"


def fetch_codes(spec: ReferenceSpec) -> list[dict]:
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        result = s.run(
            """
            MATCH (cl:CodeList {name: $name})-[:HAS_VALUE]->(cv:CodeValue)
            WHERE cv.status IS NULL OR cv.status <> 'superseded'
            OPTIONAL MATCH (cl)-[:CITES]->(doc:RegulationDocument)
            RETURN
              cv.code AS code,
              COALESCE(cv.description, cv.notes, cv.name) AS description,
              cv.id AS code_id,
              cv.version AS version,
              cv.must_appear_alone AS must_appear_alone,
              cv.companion_required AS companion_required,
              CASE WHEN cv.effective_from IS NOT NULL THEN toString(cv.effective_from) ELSE NULL END AS effective_from,
              doc.id AS source_doc_id,
              doc.title AS source_doc_title
            ORDER BY cv.code
            """,
            name=spec.codelist_name,
        )
        return [dict(r) for r in result]


def build_sql(spec: ReferenceSpec, rows: list[dict]) -> str:
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    out: list[str] = []
    out.append("-- =============================================================")
    out.append(f"-- INSURANCE_REGULATORY.REFERENCE.{spec.target_table}")
    out.append(f"-- TICO Section {spec.section} — {spec.description}")
    out.append(f"-- Generated from RegulAI KG · {now}")
    out.append(f"-- Source CodeList: {spec.codelist_name!r}")
    out.append(f"-- Neo4j: {settings.neo4j_uri}")
    out.append("--")
    out.append("-- DO NOT EDIT MANUALLY. Re-run `make build-reference-all`.")
    out.append("-- =============================================================")
    out.append("")
    out.append("USE DATABASE INSURANCE_REGULATORY;")
    out.append("USE SCHEMA REFERENCE;")
    out.append("")

    # DDL
    extra_cols_ddl = ""
    if spec.extra_columns:
        extra_cols_ddl = ",\n    " + ",\n    ".join(spec.extra_columns)

    out.append(f"CREATE OR REPLACE TABLE {spec.target_table} (")
    out.append("    tspr_code                  VARCHAR(8) NOT NULL,")
    out.append("    description                VARCHAR(512) NOT NULL,")
    out.append(f"    -- Provenance back to the KG{extra_cols_ddl}")
    out.append("    kg_code_value_id           VARCHAR(64) NOT NULL,")
    out.append("    kg_source_document_id      VARCHAR(64),")
    out.append("    kg_source_document_title   VARCHAR(512),")
    out.append("    kg_canon_version           NUMBER(10,0),")
    out.append("    kg_effective_from          DATE,")
    out.append("    generated_at               TIMESTAMP_NTZ NOT NULL,")
    out.append("    CONSTRAINT pk_" + spec.target_table.lower() + " PRIMARY KEY (tspr_code)")
    out.append(f") COMMENT = 'TICO Section {spec.section} · {spec.description}. Sourced from RegulAI KG.';")
    out.append("")
    out.append(f"DELETE FROM {spec.target_table};")
    out.append("")

    # INSERTs
    extra_col_names = []
    for ec in spec.extra_columns:
        # ec looks like "must_appear_alone BOOLEAN NOT NULL DEFAULT FALSE"
        extra_col_names.append(ec.split()[0])

    for r in rows:
        out.append(f"-- Code {r['code']}: {r['description']}")
        cols = ["tspr_code", "description"] + extra_col_names + [
            "kg_code_value_id", "kg_source_document_id", "kg_source_document_title",
            "kg_canon_version", "kg_effective_from", "generated_at",
        ]

        vals = [_q(r["code"]), _q(r["description"])]
        for name in extra_col_names:
            v = r.get(name)
            if isinstance(v, bool) or v is None:
                vals.append(_b(bool(v)))
            else:
                vals.append(_q(str(v)))
        vals += [
            _q(r["code_id"]),
            _q(r["source_doc_id"]),
            _q(r["source_doc_title"]),
            str(r["version"]) if r["version"] is not None else "NULL",
            f"DATE {_q(r['effective_from'])}" if r["effective_from"] else "NULL",
            "CURRENT_TIMESTAMP()",
        ]

        out.append(f"INSERT INTO {spec.target_table} (")
        out.append("    " + ", ".join(cols))
        out.append(") VALUES (")
        out.append("    " + ", ".join(vals))
        out.append(");")
        out.append("")

    out.append("-- Verification")
    out.append(f"SELECT COUNT(*) AS rows_loaded FROM {spec.target_table};")
    out.append("")
    return "\n".join(out)


def materialize(spec: ReferenceSpec, out_dir: Path) -> tuple[Path, int]:
    """Materialize a spec to a SQL file. Returns (path, row count)."""
    rows = fetch_codes(spec)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{spec.target_table.lower()}.sql"
    out_path.write_text(build_sql(spec, rows))
    return out_path, len(rows)
