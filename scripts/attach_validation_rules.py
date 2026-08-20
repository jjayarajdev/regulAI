"""Attach a jurisdiction's executable validation rules — the generic
"compile the edit package" step for any state.

Rule definitions are CONTENT, not code: they live in
references/validation_rules/{JURISDICTION}.json as a list of

    {match_name, rule_number, target_table, target_id_expr,
     violation_sql, violation_reason, severity, citation}

This script is the MECHANISM, identical for every state:

  1. Attach — for each definition, match the KG Rule by name within
     APPLIES_IN → the jurisdiction, SET the executable properties, bump
     validation_version (the migrate_fl/ok pattern, parameterized).
  2. Load — delete-then-insert the jurisdiction's rows in
     REFERENCE.TSPR_VALIDATION_RULES straight from the KG, so /validate
     picks them up.

Onboarding state N+1 therefore needs a rulebook (upload → review →
approve), a rules JSON (authored from the approved canon), and this one
command — no new Python.

Usage:
    uv run python -m scripts.attach_validation_rules --jurisdiction US-OK
    # rules file defaults to references/validation_rules/{JUR}.json
    uv run python -m scripts.attach_validation_rules -j US-XX --rules path.json
    # attach only (skip the warehouse load — e.g. while the api holds the
    # DuckDB write lock):
    uv run python -m scripts.attach_validation_rules -j US-OK --no-load

Idempotent. Re-run safe.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

RULES_DIR = Path("references/validation_rules")

_REQUIRED_KEYS = {"match_name", "rule_number", "target_table", "target_id_expr",
                  "violation_sql", "violation_reason", "severity", "citation"}


def load_rules(jurisdiction: str, rules_path: Path | None = None) -> list[dict]:
    path = rules_path or (RULES_DIR / f"{jurisdiction}.json")
    if not path.exists():
        raise SystemExit(f"✗ No rules file at {path} — author the jurisdiction's "
                         f"executable rules there first.")
    rules = json.loads(path.read_text(encoding="utf-8"))
    for i, r in enumerate(rules):
        missing = _REQUIRED_KEYS - r.keys()
        if missing:
            raise SystemExit(f"✗ {path}: rule[{i}] missing {sorted(missing)}")
    return rules


def attach(jurisdiction: str, rules: list[dict]) -> tuple[int, list[str]]:
    """SET executable properties on the KG Rule nodes; returns (attached, missing)."""
    attached, missing = 0, []
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        for rule in rules:
            r = s.run(
                """
                MATCH (r:Rule {name: $name})-[:APPLIES_IN]->(:Jurisdiction {jurisdiction_code: $jur})
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
                jur=jurisdiction,
                name=rule["match_name"],
                target_table=rule["target_table"],
                target_id_expr=rule["target_id_expr"],
                violation_sql=rule["violation_sql"],
                violation_reason=rule["violation_reason"],
                severity=rule["severity"],
                citation=rule["citation"],
            ).single()
            if r:
                print(f"  ✓ Attached: {rule['rule_number']:<10} → {rule['target_table']}")
                attached += 1
            else:
                missing.append(rule["rule_number"])
                print(f"  ⚠ Not found: {rule['rule_number']:<10} (name={rule['match_name'][:44]}…)")
    return attached, missing


def load_reference(jurisdiction: str) -> int:
    """Refresh the jurisdiction's rows in REFERENCE.TSPR_VALIDATION_RULES from
    the KG. Requires warehouse write access (stop the api for local DuckDB)."""
    from packages.rhs.db import query

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        rows = list(s.run(
            """
            MATCH (r:Rule)-[:APPLIES_IN]->(:Jurisdiction {jurisdiction_code: $jur})
            WHERE r.violation_sql IS NOT NULL AND r.status <> 'superseded'
            RETURN r.id AS rule_id, r.rule_number AS n, r.name AS rule_name,
                   r.section AS section, r.target_table AS target_table,
                   r.target_id_expr AS target_id_expr, r.violation_sql AS violation_sql,
                   r.violation_reason AS violation_reason, r.severity AS severity,
                   r.citation AS citation, r.validation_version AS validation_version
            ORDER BY r.rule_number
            """,
            jur=jurisdiction,
        ))
    short = jurisdiction.replace("US-", "")
    query("DELETE FROM INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES "
          "WHERE jurisdiction_code = %s", (jurisdiction,))
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    for r in rows:
        query(
            "INSERT INTO INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES "
            "(rule_id, rule_number, rule_name, section, jurisdiction_code, "
            " is_federal_default, target_table, target_id_expr, violation_sql, "
            " violation_reason, severity, citation, validation_version, generated_at) "
            "VALUES (%s, %s, %s, %s, %s, FALSE, %s, %s, %s, %s, %s, %s, %s, %s)",
            (str(r["rule_id"]), f"{short}.{r['n']}", r["rule_name"], r["section"],
             jurisdiction, r["target_table"], r["target_id_expr"], r["violation_sql"],
             r["violation_reason"], r["severity"], r["citation"],
             int(r["validation_version"] or 1), now),
        )
    return len(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-j", "--jurisdiction", required=True, help="e.g. US-OK")
    ap.add_argument("--rules", type=Path, default=None, help="rules JSON (default references/validation_rules/{JUR}.json)")
    ap.add_argument("--no-load", action="store_true", help="attach to KG only; skip the warehouse reference load")
    args = ap.parse_args()
    jur = args.jurisdiction.upper()

    rules = load_rules(jur, args.rules)
    attached, missing = attach(jur, rules)
    print()
    print(f"violation_sql attached to {attached}/{len(rules)} {jur} Rule node(s).")
    if missing:
        print(f"Missing (approve the jurisdiction's extraction into the KG first?): {missing}")
        return 1
    if not args.no_load:
        n = load_reference(jur)
        print(f"  ✓ REFERENCE.TSPR_VALIDATION_RULES: {n} {jur} rules loaded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
