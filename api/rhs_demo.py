"""RHS demo endpoints — Snowflake-backed views + bulletin trigger.

Powers the `ui/demo.html` page. Reads live state from Snowflake on every
request (we want the demo to feel real). The bulletin apply/reset endpoints
shell out to the existing scripts so the audit trail (KG materialization
+ apply_bulletin's version bumps) matches what `make demo-bulletin-apply`
does.
"""

from __future__ import annotations

import datetime as dt
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
from packages.rhs.snowflake_client import query

REASON_CODE_LIST_NAME = "Reason Code List (RCL) — Notice Record Layout col36"


def _jsonify(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Coerce Snowflake row values into JSON-safe forms."""
    out: list[dict[str, Any]] = []
    for row in rows:
        clean: dict[str, Any] = {}
        for k, v in row.items():
            if isinstance(v, (dt.datetime, dt.date, dt.time)):
                clean[k] = v.isoformat()
            elif isinstance(v, Decimal):
                clean[k] = float(v)
            else:
                clean[k] = v
        out.append(clean)
    return out

router = APIRouter(prefix="/api/rhs", tags=["rhs"])

BULLETIN_OVERRIDE_NAME = "Credit Score Declination Reporting Override"
BULLETIN_PATH = Path("synthetic_regulations/synthetic/bulletins/B-2026-Q4-118.md")


@router.post("/pipeline/silver")
def pipeline_silver() -> JSONResponse:
    """Run Bronze → Silver and return per-table row counts."""
    result = _run(["uv", "run", "python", "-m", "scripts.run_silver"])
    counts = query(
        "SELECT 'TSPR_PREMIUM_STAGING' AS table_name, COUNT(*) AS row_count "
        "FROM INSURANCE_REGULATORY.SILVER.TSPR_PREMIUM_STAGING "
        "UNION ALL "
        "SELECT 'TSPR_CLAIM_STATE', COUNT(*) FROM INSURANCE_REGULATORY.SILVER.TSPR_CLAIM_STATE "
        "UNION ALL "
        "SELECT 'TSPR_LOSS_STAGING', COUNT(*) FROM INSURANCE_REGULATORY.SILVER.TSPR_LOSS_STAGING "
        "UNION ALL "
        "SELECT 'TSPR_CANCELLATION_STAGING', COUNT(*) FROM INSURANCE_REGULATORY.SILVER.TSPR_CANCELLATION_STAGING"
    )
    return JSONResponse({"ok": result["ok"], "stdout": result["stdout"], "counts": counts})


@router.post("/pipeline/gold")
def pipeline_gold() -> JSONResponse:
    """Run Silver → Gold and return per-table row counts + transmittal totals."""
    result = _run(["uv", "run", "python", "-m", "scripts.run_gold"])
    counts = query(
        "SELECT 'TSPR_PREMIUM_RECORDS' AS table_name, COUNT(*) AS row_count "
        "FROM INSURANCE_REGULATORY.GOLD.TSPR_PREMIUM_RECORDS "
        "UNION ALL "
        "SELECT 'TSPR_LOSS_RECORDS', COUNT(*) FROM INSURANCE_REGULATORY.GOLD.TSPR_LOSS_RECORDS "
        "UNION ALL "
        "SELECT 'TSPR_CANCELLATION_RECORDS', COUNT(*) FROM INSURANCE_REGULATORY.GOLD.TSPR_CANCELLATION_RECORDS "
        "UNION ALL "
        "SELECT 'TSPR_MONTHLY_AGGREGATES', COUNT(*) FROM INSURANCE_REGULATORY.GOLD.TSPR_MONTHLY_AGGREGATES"
    )
    transmittal = query(
        "SELECT premium_record_count, loss_record_count, cancellation_notice_count, "
        "       total_written_premium, total_paid_losses, total_recipient_count, "
        "       total_cancellations, total_nonrenewals, total_declinations "
        "FROM INSURANCE_REGULATORY.GOLD.TSPR_MONTHLY_AGGREGATES LIMIT 1"
    )
    return JSONResponse({
        "ok": result["ok"], "stdout": result["stdout"],
        "counts": counts,
        "transmittal": _jsonify(transmittal)[0] if transmittal else None,
    })


@router.get("/pipeline/state")
def pipeline_state() -> JSONResponse:
    """Per-layer row counts for the pipeline page."""
    counts = query(
        """
        SELECT 'BRONZE' AS layer, COUNT(*) AS table_count, SUM(row_count) AS row_total
        FROM INSURANCE_REGULATORY.INFORMATION_SCHEMA.TABLES
        WHERE table_schema = 'BRONZE' AND table_type = 'BASE TABLE' AND row_count > 0
        UNION ALL
        SELECT 'SILVER', COUNT(*), SUM(row_count)
        FROM INSURANCE_REGULATORY.INFORMATION_SCHEMA.TABLES
        WHERE table_schema = 'SILVER' AND table_type = 'BASE TABLE' AND row_count > 0
        UNION ALL
        SELECT 'GOLD', COUNT(*), SUM(row_count)
        FROM INSURANCE_REGULATORY.INFORMATION_SCHEMA.TABLES
        WHERE table_schema = 'GOLD' AND table_type = 'BASE TABLE' AND row_count > 0
        """
    )
    return JSONResponse({"layers": _jsonify(counts)})


@router.get("/catalog")
def catalog() -> JSONResponse:
    """Snowflake catalog: every schema, every table, with row counts.

    Powers the "what's in Snowflake and where" view. Calls
    INFORMATION_SCHEMA.TABLES once and falls back to per-table
    COUNT(*) where row_count is stale.
    """
    rows = query(
        """
        SELECT table_schema AS schema_name,
               table_name,
               row_count,
               bytes,
               comment,
               TO_VARCHAR(last_altered, 'YYYY-MM-DD HH24:MI:SS') AS last_altered
        FROM INSURANCE_REGULATORY.INFORMATION_SCHEMA.TABLES
        WHERE table_type = 'BASE TABLE'
          AND table_schema IN ('BRONZE','SILVER','GOLD','REFERENCE','STAGING')
        ORDER BY table_schema, table_name
        """
    )
    # Group by schema
    by_schema: dict[str, list] = {}
    for r in rows:
        by_schema.setdefault(r["schema_name"], []).append({
            "table_name": r["table_name"],
            "row_count": r["row_count"] or 0,
            "bytes": r["bytes"] or 0,
            "comment": r["comment"] or "",
            "last_altered": r["last_altered"],
        })
    descriptions = {
        "BRONZE": "Raw Guidewire CDC events — append-only, faithful replica of GDP exports.",
        "SILVER": "TSPR field-mapped staging — every Guidewire field translated to TSPR semantics.",
        "GOLD": "Submission-ready SDF records — one row per record, validated and approved.",
        "REFERENCE": "TSPR plan rules as data — generated from RegulAI's KG.",
        "STAGING": "External stage area for Snowpipe ingest.",
    }
    schemas = []
    # Show schemas in pipeline order: Bronze → Silver → Gold → Reference, then Staging
    schema_order = ["BRONZE", "SILVER", "GOLD", "REFERENCE", "STAGING"]
    for name in schema_order:
        tables = by_schema.get(name, [])
        populated = sum(1 for t in tables if t["row_count"] > 0)
        schemas.append({
            "schema": name,
            "description": descriptions.get(name, ""),
            "table_count": len(tables),
            "populated_count": populated,
            "total_rows": sum(t["row_count"] for t in tables),
            "tables": tables,
        })
    return JSONResponse({"schemas": schemas})


@router.get("/reference/table/{table_name}")
def reference_table(table_name: str) -> JSONResponse:
    """Generic SELECT for any reference table — returns rows + column metadata."""
    safe = "".join(c for c in table_name if c.isalnum() or c == "_")
    if not safe or len(safe) > 64:
        raise HTTPException(status_code=400, detail="invalid table name")
    try:
        rows = query(f"SELECT * FROM INSURANCE_REGULATORY.REFERENCE.{safe} ORDER BY tspr_code LIMIT 200")
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return JSONResponse({"table": safe, "rows": _jsonify(rows), "count": len(rows)})


@router.get("/validate/cancellations")
def validate_cancellations() -> JSONResponse:
    """Run every rule from REFERENCE.TSPR_VALIDATION_RULES against BRONZE.

    For each rule we read its `violation_sql` (TRUE → row violates the rule)
    and execute a SELECT against the rule's `target_table`, returning the
    record id and the rule's citation so the UI can show provenance.
    """
    rules = query(
        "SELECT rule_id, rule_number, rule_name, target_table, target_id_expr, "
        "       violation_sql, violation_reason, severity, citation "
        "FROM INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES "
        "ORDER BY rule_number"
    )
    # Map Bronze record's publicid → friendly policy number.
    # Single round trip; tiny synthetic dataset.
    pubid_to_policy: dict[str, str] = {}
    try:
        for r in query(
            """
            SELECT j.publicid AS pid, p.policynumber AS policy
            FROM INSURANCE_REGULATORY.BRONZE.GW_PC_JOB j
            LEFT JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY p ON p.id = j.policy_id
            UNION
            SELECT j.publicid AS pid, p.policynumber AS policy
            FROM INSURANCE_REGULATORY.BRONZE.GW_PC_POLICYPERIOD j
            LEFT JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY p ON p.id = j.policy_id
            """
        ):
            pubid_to_policy[r["pid"]] = r.get("policy") or r["pid"]
    except Exception:
        pass

    violations: list[dict] = []
    rule_results: list[dict] = []
    for rule in rules:
        target = rule["target_table"]
        sql = (
            f"SELECT {rule['target_id_expr']} AS record_id "
            f"FROM INSURANCE_REGULATORY.{target} j "
            f"WHERE ({rule['violation_sql']})"
        )
        try:
            rows = query(sql)
        except Exception as e:
            rule_results.append({
                **rule,
                "status": "error",
                "error": str(e)[:200],
                "violation_count": 0,
            })
            continue
        rule_results.append({
            **rule,
            "status": "pass" if not rows else "fail",
            "violation_count": len(rows),
        })
        for r in rows:
            pubid = r["record_id"]
            violations.append({
                "rule_id": rule["rule_id"],
                "rule_number": rule["rule_number"],
                "rule_name": rule["rule_name"],
                "record_id": pubid,
                "policy_number": pubid_to_policy.get(pubid, pubid),
                "violation_reason": rule["violation_reason"],
                "severity": rule["severity"],
                "citation": rule["citation"],
            })
    summary = {
        "rules_run": len(rule_results),
        "rules_passing": sum(1 for r in rule_results if r["status"] == "pass"),
        "rules_failing": sum(1 for r in rule_results if r["status"] == "fail"),
        "rules_errored": sum(1 for r in rule_results if r["status"] == "error"),
        "total_violations": len(violations),
    }
    return JSONResponse({
        "summary": summary,
        "rules": rule_results,
        "violations": violations,
    })


@router.get("/state")
def state() -> JSONResponse:
    """Return whether the demo bulletin is currently applied."""
    # Cheapest signal: does any reason code currently have companion_required=TRUE?
    rows = query(
        "SELECT credit_score_companion_required AS req "
        "FROM INSURANCE_REGULATORY.REFERENCE.TSPR_REASON_CODE_MAP "
        "WHERE tspr_reason_code = 'L'"
    )
    if not rows:
        return JSONResponse({"reference_loaded": False, "bulletin_applied": False})
    bulletin_applied = not bool(rows[0]["req"])  # bulletin removes the requirement
    return JSONResponse({
        "reference_loaded": True,
        "bulletin_applied": bulletin_applied,
        "bulletin_id": "B-2026-Q4-118",
        "bulletin_title": (
            "Commissioner's Bulletin B-2026-Q4-118 — Credit Score "
            "Declination During Catastrophe Periods"
        ),
    })


@router.get("/kg/reason-code/{code}")
def kg_reason_code(code: str) -> JSONResponse:
    """Read the active CodeValue for a reason code from Neo4j (the canon).

    Returns the active row plus any superseded version, so the UI can show
    "before / after" provenance from the KG side.
    """
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        result = s.run(
            """
            MATCH (cl:CodeList {name: $list_name})-[:HAS_VALUE]->(cv:CodeValue {code: $code})
            OPTIONAL MATCH (cl)-[:CITES]->(doc:RegulationDocument)
            RETURN
              cv.id AS id,
              cv.code AS code,
              cv.notes AS description,
              cv.must_appear_alone AS must_appear_alone,
              cv.companion_required AS companion_required,
              cv.status AS status,
              cv.version AS version,
              CASE
                WHEN cv.effective_from IS NOT NULL THEN toString(cv.effective_from)
                ELSE NULL
              END AS effective_from,
              CASE
                WHEN cv.effective_to IS NOT NULL THEN toString(cv.effective_to)
                ELSE NULL
              END AS effective_to,
              doc.id AS source_doc_id,
              doc.title AS source_doc_title
            ORDER BY
              CASE WHEN cv.status IS NULL OR cv.status <> 'superseded' THEN 0 ELSE 1 END,
              cv.version DESC
            """,
            list_name=REASON_CODE_LIST_NAME,
            code=code,
        )
        rows = [dict(r) for r in result]
    active = next(
        (r for r in rows if (r["status"] or "").lower() != "superseded"),
        rows[0] if rows else None,
    )
    return JSONResponse({"code": code, "active": active, "all_versions": rows})


@router.get("/kg/rules")
def kg_rules() -> JSONResponse:
    """List every Rule node in the canon (KG).

    Returns id, name, parsed section letter, citation, and an `executable`
    flag (true when the rule has been bridged to Snowflake — i.e., it has
    `target_table` + `violation_sql` properties, so it can be run).
    """
    import re
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        result = s.run(
            """
            MATCH (r:Rule)
            OPTIONAL MATCH (r)-[:CITES]->(c:Citation)
            WITH r, head(collect(c)) AS c
            RETURN
              r.id            AS id,
              r.name          AS name,
              r.target_table  AS target_table,
              r.violation_sql AS violation_sql,
              r.severity      AS severity,
              CASE
                WHEN c IS NOT NULL THEN coalesce(c.full_citation, c.text, c.name)
                ELSE NULL
              END             AS citation
            ORDER BY r.name
            """
        )
        rules = [dict(r) for r in result]
    for r in rules:
        m = re.match(r"Rule\s+([A-Z])\.", r.get("name") or "")
        r["section"] = m.group(1) if m else "Other"
        r["executable"] = bool(r.get("target_table"))
        # Don't ship the SQL/citation noise in the list view
        r.pop("target_table", None)
        r.pop("violation_sql", None)
    counts = {
        "total": len(rules),
        "executable": sum(1 for r in rules if r["executable"]),
        "descriptive": sum(1 for r in rules if not r["executable"]),
    }
    return JSONResponse({"rules": rules, "counts": counts})


@router.get("/reference/reason-codes")
def reference_reason_codes() -> JSONResponse:
    """Read REFERENCE.TSPR_REASON_CODE_MAP — what the regulation currently says."""
    rows = query(
        "SELECT tspr_reason_code, description, "
        "       must_appear_alone, credit_score_companion_required, "
        "       constraint_rationale, kg_canon_version, "
        "       TO_VARCHAR(generated_at, 'YYYY-MM-DD HH24:MI:SS') AS generated_at "
        "FROM INSURANCE_REGULATORY.REFERENCE.TSPR_REASON_CODE_MAP "
        "ORDER BY tspr_reason_code"
    )
    return JSONResponse({"rows": _jsonify(rows), "count": len(rows)})


_FIX_FIELDS: dict[str, dict] = {
    # field name → which Bronze table + column + value-handling
    "reason_code":   {"table": "BRONZE.GW_PC_JOB",          "col": None,             "kind": "reason"},
    "noticedate":    {"table": "BRONZE.GW_PC_JOB",          "col": "noticedate",     "kind": "date"},
    "naic_number":   {"table": "BRONZE.GW_PC_POLICYPERIOD", "col": "naic_number",    "kind": "text"},
    "writtenpremium":{"table": "BRONZE.GW_PC_POLICYPERIOD", "col": "writtenpremium", "kind": "number"},
    "termtype":      {"table": "BRONZE.GW_PC_POLICYPERIOD", "col": "termtype",       "kind": "text"},
}


def _g(row: dict, k: str):
    return row.get(k) if k in row else row.get(k.upper())


@router.post("/bronze/fix")
def bronze_fix(body: dict = Body(...)) -> JSONResponse:
    """Manually correct a Bronze field for a given policy.

    Simulates a carrier editing the policy in PolicyCenter and the change
    propagating into Bronze via CDC. The field name decides which Bronze
    table/column to update.

    Body: {
      "policy_number": "POL-0015",
      "field":         "termtype",   # one of: reason_code, naic_number,
                                     #         writtenpremium, termtype, noticedate
      "new_value":     "Annual"
    }

    Legacy shape `{policy_number, new_code}` is still accepted (treated as
    field=reason_code).
    """
    policy = (body.get("policy_number") or "").strip().upper()
    field  = (body.get("field") or "reason_code").strip().lower()
    raw_val = body.get("new_value")
    if raw_val is None:
        raw_val = body.get("new_code")  # backward compat

    if not policy or not policy.startswith("POL-"):
        raise HTTPException(400, "policy_number must be like POL-0015")
    if field not in _FIX_FIELDS:
        raise HTTPException(400, f"unknown field '{field}'; one of {list(_FIX_FIELDS)}")

    spec = _FIX_FIELDS[field]
    kind = spec["kind"]

    # ── Normalize the new value depending on the field's kind ───────
    if kind == "reason":
        new_str = (raw_val or "").strip().upper()
        if new_str and (not new_str.isalpha() or len(new_str) > 3):
            raise HTTPException(400, "reason_code must be 1–3 letters (or empty)")
        sql_value = "NULL" if not new_str else f"'{new_str}'"
    elif kind == "text":
        new_str = (raw_val or "").strip()
        if len(new_str) > 64 or "'" in new_str:
            raise HTTPException(400, "text value must be <=64 chars and contain no quotes")
        sql_value = "NULL" if not new_str else f"'{new_str}'"
    elif kind == "number":
        if raw_val in (None, ""):
            sql_value = "NULL"
        else:
            try:
                num = float(raw_val)
            except (TypeError, ValueError):
                raise HTTPException(400, "new_value must be a number")
            sql_value = str(num)
        new_str = sql_value if sql_value != "NULL" else None
    elif kind == "date":
        if raw_val in (None, ""):
            sql_value = "NULL"
            new_str = None
        else:
            import re as _re
            ds = str(raw_val).strip()
            if not _re.match(r"^\d{4}-\d{2}-\d{2}", ds):
                raise HTTPException(400, "date must be YYYY-MM-DD")
            sql_value = f"TO_TIMESTAMP_NTZ('{ds[:10]}')"
            new_str = ds[:10]
    else:
        raise HTTPException(500, f"unknown field kind {kind}")

    # ── Find the target row ─────────────────────────────────────────
    if spec["table"] == "BRONZE.GW_PC_JOB":
        rows = query(
            "SELECT j.publicid, j.cancellationreason, j.nonrenewalreason, "
            "       j.declinereason, j.noticedate "
            "FROM INSURANCE_REGULATORY.BRONZE.GW_PC_JOB j "
            "JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY p ON p.id = j.policy_id "
            f"WHERE p.policynumber = '{policy}'"
        )
    else:  # POLICYPERIOD
        rows = query(
            "SELECT j.publicid, j.naic_number, j.writtenpremium, j.termtype "
            "FROM INSURANCE_REGULATORY.BRONZE.GW_PC_POLICYPERIOD j "
            "JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY p ON p.id = j.policy_id "
            f"WHERE p.policynumber = '{policy}'"
        )
    if not rows:
        raise HTTPException(404, f"no {spec['table'].split('.')[-1]} record for policy {policy}")
    row = rows[0]
    pubid = _g(row, "publicid")

    # ── Decide which actual column to update ────────────────────────
    if kind == "reason":
        # Pick whichever reason column on this job is non-null
        for cand in ("cancellationreason", "nonrenewalreason", "declinereason"):
            if _g(row, cand) is not None:
                col, old = cand, _g(row, cand)
                break
        else:
            # All three null — update declinereason as the conventional fallback
            col, old = "declinereason", None
    else:
        col = spec["col"]
        old = _g(row, col)

    # ── Execute the update ──────────────────────────────────────────
    query(
        f"UPDATE INSURANCE_REGULATORY.{spec['table']} "
        f"SET {col} = {sql_value} "
        f"WHERE publicid = '{pubid}'"
    )

    # Coerce DB-returned types into JSON-safe forms (Decimal, datetime, etc.)
    def _safe(v: Any) -> Any:
        if v is None: return None
        if isinstance(v, (dt.datetime, dt.date, dt.time)): return v.isoformat()
        if isinstance(v, Decimal): return float(v)
        return v

    return JSONResponse({
        "ok": True,
        "policy_number": policy,
        "table": spec["table"],
        "field": col,
        "old_value": _safe(old),
        "new_value": new_str,
    })


@router.get("/bronze/cancellations")
def bronze_cancellations() -> JSONResponse:
    """Read BRONZE.GW_PC_JOB joined to GW_PC_POLICY — what Guidewire sent."""
    rows = query(
        "SELECT p.policynumber AS policy, "
        "       j.subtype AS action, "
        "       COALESCE(j.cancellationreason, j.nonrenewalreason, j.declinereason) AS reason_code, "
        "       TO_VARCHAR(j.noticedate, 'YYYY-MM-DD') AS noticedate, "
        "       TO_VARCHAR(j.effectivedate, 'YYYY-MM-DD') AS effectivedate "
        "FROM INSURANCE_REGULATORY.BRONZE.GW_PC_JOB j "
        "JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY p ON p.id = j.policy_id "
        "ORDER BY p.policynumber"
    )
    return JSONResponse({"rows": _jsonify(rows), "count": len(rows)})


@router.get("/validation")
def validation() -> JSONResponse:
    """Run the JOIN that produces validation outcomes — Bronze ⋈ Reference."""
    rows = query(
        """
        SELECT
            p.policynumber AS policy,
            j.subtype AS action,
            COALESCE(j.cancellationreason, j.nonrenewalreason, j.declinereason) AS reason_code,
            r.description AS regulation_describes,
            r.constraint_rationale AS rationale,
            CASE
                WHEN r.must_appear_alone
                     AND LENGTH(COALESCE(j.cancellationreason, j.nonrenewalreason, j.declinereason)) > 1
                THEN 'INVALID'
                WHEN r.credit_score_companion_required
                     AND LENGTH(COALESCE(j.cancellationreason, j.nonrenewalreason, j.declinereason)) = 1
                THEN 'INVALID'
                ELSE 'VALID'
            END AS validation_status,
            CASE
                WHEN r.must_appear_alone
                     AND LENGTH(COALESCE(j.cancellationreason, j.nonrenewalreason, j.declinereason)) > 1
                THEN 'must_appear_alone violated'
                WHEN r.credit_score_companion_required
                     AND LENGTH(COALESCE(j.cancellationreason, j.nonrenewalreason, j.declinereason)) = 1
                THEN 'credit_score needs companion'
                ELSE NULL
            END AS violation_reason
        FROM INSURANCE_REGULATORY.BRONZE.GW_PC_JOB j
        JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY p ON p.id = j.policy_id
        LEFT JOIN INSURANCE_REGULATORY.REFERENCE.TSPR_REASON_CODE_MAP r
               ON r.tspr_reason_code = SUBSTR(
                   COALESCE(j.cancellationreason, j.nonrenewalreason, j.declinereason), 1, 1
               )
        ORDER BY p.policynumber
        """
    )
    invalid = sum(1 for r in rows if r["validation_status"] == "INVALID")
    return JSONResponse({"rows": _jsonify(rows), "count": len(rows), "invalid_count": invalid})


@router.get("/bulletin")
def bulletin_text() -> PlainTextResponse:
    """Return the synthetic bulletin's markdown text."""
    if not BULLETIN_PATH.exists():
        raise HTTPException(status_code=404, detail="bulletin file not found")
    return PlainTextResponse(BULLETIN_PATH.read_text())


def _run(cmd: list[str]) -> dict:
    """Run a script, capture status."""
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout[-2000:],  # tail
        "stderr": result.stderr[-2000:],
        "returncode": result.returncode,
    }


@router.post("/bulletin/apply")
def bulletin_apply() -> JSONResponse:
    """Apply the credit-score bulletin: materialize → version-bump → reload reference."""
    steps = []
    # 1. Materialize bulletin into KG
    steps.append({"step": "materialize", **_run(
        ["uv", "run", "python", "-m", "scripts.apply_credit_score_bulletin"]
    )})
    if not steps[-1]["ok"]:
        return JSONResponse({"ok": False, "steps": steps}, status_code=500)

    # 2. Bump versions
    steps.append({"step": "version_bump", **_run([
        "uv", "run", "python", "-m", "scripts.apply_bulletin",
        "--bulletin", BULLETIN_OVERRIDE_NAME,
    ])})
    if not steps[-1]["ok"]:
        return JSONResponse({"ok": False, "steps": steps}, status_code=500)

    # 3. Regenerate reference + load to Snowflake
    steps.append({"step": "build_reference", **_run(
        ["uv", "run", "python", "-m", "scripts.build_reference_reason_codes"]
    )})
    if not steps[-1]["ok"]:
        return JSONResponse({"ok": False, "steps": steps}, status_code=500)

    steps.append({"step": "load_reference", **_run([
        "snow", "sql", "-c", "regulai", "-f",
        "materialized/reference/tspr_reason_code_map.sql",
    ])})

    return JSONResponse({"ok": all(s["ok"] for s in steps), "steps": steps})


@router.post("/bulletin/reset")
def bulletin_reset() -> JSONResponse:
    """Roll back the bulletin and reload baseline reference."""
    steps = []
    steps.append({"step": "reset", **_run(
        ["uv", "run", "python", "-m", "scripts.reset_credit_score_bulletin"]
    )})
    if not steps[-1]["ok"]:
        return JSONResponse({"ok": False, "steps": steps}, status_code=500)

    steps.append({"step": "build_reference", **_run(
        ["uv", "run", "python", "-m", "scripts.build_reference_reason_codes"]
    )})
    if not steps[-1]["ok"]:
        return JSONResponse({"ok": False, "steps": steps}, status_code=500)

    steps.append({"step": "load_reference", **_run([
        "snow", "sql", "-c", "regulai", "-f",
        "materialized/reference/tspr_reason_code_map.sql",
    ])})

    return JSONResponse({"ok": all(s["ok"] for s in steps), "steps": steps})
