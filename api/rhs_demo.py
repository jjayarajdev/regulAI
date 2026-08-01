"""RHS demo endpoints — Snowflake-backed views + bulletin trigger.

Powers the `ui/demo.html` page. Reads live state from Snowflake on every
request (we want the demo to feel real). The bulletin apply/reset endpoints
shell out to the existing scripts so the audit trail (KG materialization
+ apply_bulletin's version bumps) matches what `make demo-bulletin-apply`
does.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
from packages.rhs.db import backend_name, query

logger = logging.getLogger("regulai.rhs")

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


# ── Filings registry ──────────────────────────────────────────────
# Each filing scopes by the underlying GW_PC_POLICY.id range, not by
# policy-number prefix (POL-0050 would otherwise look like a TPA filing
# because it shares the "POL-00" prefix with POL-0019). The id ranges
# match the synthetic data in scripts/generate_bronze_data.py.
from packages.rhs.filings import FILINGS  # noqa: E402  — bootstrap fallback
from packages.rhs.filings import load_filings as _load_filings_from_kg  # noqa: E402


import datetime as _dt

# Days-from-today each filing is "due", so the demo dashboard always reads as
# upcoming (never overdue) regardless of when it runs. Display-only — filing
# scope uses policy-id ranges, not dates.
_DUE_OFFSETS = [75, 96, 124]


def _polish_demo_filings(filings: list[dict]) -> list[dict]:
    """Keep demo due dates in the future and fill a jurisdiction default, so the
    dashboard never shows '-90 days to file' or an empty jurisdiction pill."""
    today = _dt.date.today()
    for i, f in enumerate(filings):
        f["due_date"] = (today + _dt.timedelta(days=_DUE_OFFSETS[i % len(_DUE_OFFSETS)])).isoformat()
        f.setdefault("jurisdiction_code", "US-TX")
        if not f.get("jurisdiction_code"):
            f["jurisdiction_code"] = "US-TX"
    return filings


def _live_filings() -> list[dict]:
    """KG-preferred filings list (P2.4). Falls back to FILINGS on KG error.

    Called per-request for low-volume endpoints (`/filings`, `_filing`). The
    KG read is small (~3 nodes) and cached internally by Neo4j; refactoring
    to module-level state would defeat the purpose (KG becomes the source).
    """
    return _polish_demo_filings(_load_filings_from_kg())


def _filing(filing_id: str | None) -> dict | None:
    if not filing_id:
        return None
    for f in _live_filings():
        if f["id"] == filing_id:
            return f
    return None


def _filing_ranges(f: dict) -> list[tuple[int, int]]:
    """Return all id ranges for a filing; supports both legacy (min/max) and
    new multi-range (policy_id_ranges) shapes."""
    if "policy_id_ranges" in f:
        return list(f["policy_id_ranges"])
    return [(f["policy_id_min"], f["policy_id_max"])]


def _filing_policy_numbers(filing_id: str | None) -> set[str] | None:
    """For a filing, return the set of policy numbers in all its id ranges.
    Returns None when no filing scope is applied."""
    f = _filing(filing_id)
    if not f:
        return None
    pids: set[int] = set()
    for lo, hi in _filing_ranges(f):
        pids.update(range(lo, hi + 1))
    return {f"POL-{(pid - 2000):04d}" for pid in pids}


def _scope_clause(filing_id: str | None, policy_id_col: str = "p.id") -> str:
    """SQL fragment that constrains a policy.id column to all of the filing's id ranges."""
    f = _filing(filing_id)
    if not f:
        return ""
    parts = [f"{policy_id_col} BETWEEN {int(lo)} AND {int(hi)}" for lo, hi in _filing_ranges(f)]
    return f" AND ({' OR '.join(parts)}) "


@router.get("/filings")
def filings_list() -> JSONResponse:
    """List all known filings + which one is currently the default context.

    P2.4: source is FilingObligation nodes in KG (with fallback to the
    in-process FILINGS list if KG is unreachable). Adding a new filing now
    means creating a KG node, not editing Python.
    """
    filings = _live_filings()
    default = filings[0]["id"] if filings else None
    return JSONResponse({"filings": filings, "default": default})


# ── Audit-persistence helpers ────────────────────────────────────────
# Every validation/fix/bulletin action writes to GOLD_AUDIT or GOLD_FILING.
# Failures don't raise — audit is best-effort so it can't break the live demo.

import uuid as _uuid

def _audit_safe(fn):
    """Decorator: swallow exceptions from audit writes so the live path never fails."""
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            logger.warning("[audit] %s failed", fn.__name__, exc_info=True)
            return None
    return wrapper


@_audit_safe
def _ensure_filing_batch(filing_id: str, status: str = "draft") -> str:
    """Create a FILING_BATCH row for this filing if one doesn't exist."""
    f = _filing(filing_id) or (_live_filings()[0] if _live_filings() else FILINGS[0])
    rows = query(
        "SELECT filing_batch_id FROM INSURANCE_REGULATORY.GOLD.FILING_BATCH "
        "WHERE filing_batch_id = %s",
        (f["id"],),
    )
    if rows:
        return f["id"]
    query(
        "INSERT INTO INSURANCE_REGULATORY.GOLD.FILING_BATCH "
        "(filing_batch_id, filing_id, plan_code, plan_name, "
        " reporting_period_start, reporting_period_end, cadence, due_date, channel, status) "
        "VALUES (%s, %s, %s, %s, TO_DATE(%s), TO_DATE(%s), %s, TO_DATE(%s), %s, %s)",
        (f["id"], f["id"], f["plan_code"], f["plan_name"],
         f["period_start"], f["period_end"], f["cadence"], f["due_date"],
         f["channel"], status),
    )
    return f["id"]


# Last persisted violation signature per filing. The frontend auto-refreshes,
# re-running validation on an unchanged result set; persisting that identical
# audit run every time is pure waste — and on an analytics warehouse like
# Databricks the row-by-row audit DML (a MERGE per violation) costs seconds.
# Skip when nothing changed; only real transitions (a fix, a bulletin) persist.
_last_validation_sig: dict[str, str] = {}

# ── Validation result cache ──────────────────────────────────────────────
# Each /validate call is many Databricks round trips (rules + policy map + one
# query per rule), serialized by the connection lock — and the UI validates
# every filing on load. Cache the HTTP result per filing for a short window so
# repeated loads/navigation are instant; any write (fix / bulletin) clears it,
# and internal callers (bulletin apply) always recompute fresh.
import time as _time

_VALIDATE_CACHE: dict[str, tuple[float, dict]] = {}
_VALIDATE_TTL = 90.0


def _invalidate_validate() -> None:
    _VALIDATE_CACHE.clear()


# ── Bronze publicid/claimnumber → policy-number map (cached) ──────────────
# Used to scope violations to a filing. It only changes when Bronze rows are
# added/removed (never on a reason-code fix), so cache it — one fewer round trip
# on every /validate.
_PUBID_MAP_CACHE: tuple[float, dict[str, str]] | None = None
_PUBID_MAP_TTL = 300.0


def _pubid_map() -> dict[str, str]:
    global _PUBID_MAP_CACHE
    if _PUBID_MAP_CACHE and (_time.time() - _PUBID_MAP_CACHE[0]) < _PUBID_MAP_TTL:
        return _PUBID_MAP_CACHE[1]
    m: dict[str, str] = {}
    try:
        for r in query(
            "SELECT j.publicid AS pid, p.policynumber AS policy "
            "FROM INSURANCE_REGULATORY.BRONZE.GW_PC_JOB j "
            "LEFT JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY p ON p.id = j.policy_id "
            "UNION SELECT j.publicid, p.policynumber "
            "FROM INSURANCE_REGULATORY.BRONZE.GW_PC_POLICYPERIOD j "
            "LEFT JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY p ON p.id = j.policy_id "
            "UNION SELECT j.claimnumber, p.policynumber "
            "FROM INSURANCE_REGULATORY.BRONZE.GW_CC_CLAIM j "
            "LEFT JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY p ON p.id = j.policy_id"
        ):
            m[r["pid"]] = r.get("policy") or r["pid"]
    except Exception:
        pass
    _PUBID_MAP_CACHE = (_time.time(), m)
    return m


def _assemble_rules(rules, by_rule, errors, scope_set, pubid_to_policy):
    """Turn per-rule violating record_ids into (rule_results, violations)."""
    violations: list[dict] = []
    rule_results: list[dict] = []
    for i, rule in enumerate(rules):
        if i in errors:
            rule_results.append({**rule, "status": "error", "error": errors[i], "violation_count": 0})
            continue
        recs = by_rule.get(i, [])
        if scope_set is not None:
            recs = [rid for rid in recs if pubid_to_policy.get(rid, rid) in scope_set]
        rule_results.append({**rule, "status": "pass" if not recs else "fail", "violation_count": len(recs)})
        for pubid in recs:
            violations.append({
                "rule_id": rule["rule_id"], "rule_number": rule["rule_number"], "rule_name": rule["rule_name"],
                "record_id": pubid, "policy_number": pubid_to_policy.get(pubid, pubid),
                "violation_reason": rule["violation_reason"], "severity": rule["severity"], "citation": rule["citation"],
            })
    return rule_results, violations


def _run_rules(rules, scope_set, pubid_to_policy):
    """Evaluate every rule. Fast path: ONE `UNION ALL` query for all rules (one
    Databricks round trip instead of one per rule). Falls back to per-rule if the
    combined query errors, so a single bad rule can't break validation."""
    if not rules:
        return [], []
    try:
        subs = [
            f"SELECT {i} AS rid, CAST({r['target_id_expr']} AS STRING) AS record_id "
            f"FROM INSURANCE_REGULATORY.{r['target_table']} j WHERE ({r['violation_sql']})"
            for i, r in enumerate(rules)
        ]
        rows = query(" UNION ALL ".join(subs))
        by_rule: dict[int, list[str]] = {}
        for row in rows:
            by_rule.setdefault(int(row["rid"]), []).append(row["record_id"])
        return _assemble_rules(rules, by_rule, {}, scope_set, pubid_to_policy)
    except Exception:
        by_rule, errors = {}, {}
        for i, rule in enumerate(rules):
            try:
                rows = query(
                    f"SELECT CAST({rule['target_id_expr']} AS STRING) AS record_id "
                    f"FROM INSURANCE_REGULATORY.{rule['target_table']} j WHERE ({rule['violation_sql']})"
                )
                by_rule[i] = [r["record_id"] for r in rows]
            except Exception as e:
                errors[i] = str(e)[:200]
        return _assemble_rules(rules, by_rule, errors, scope_set, pubid_to_policy)


@_audit_safe
def _record_validation_run(filing_id: str, rule_results: list[dict], violations: list[dict],
                           resolution_action: str | None = None, force: bool = False) -> str | None:
    """Persist a complete validation run to GOLD_AUDIT.RULE_MATCH_RESULT.

    Writes one row per rule × failing-record (pass-rows are summarized by absence).
    Returns the run_id so callers can update FILING_BATCH.last_validation_run_id.
    `force` bypasses the unchanged-since-last-run dedupe (used by the bulletin
    flow, which must reconcile exceptions to compute its deltas).
    """
    sig = "|".join(sorted(f"{v.get('policy_number')}~{v.get('rule_id')}" for v in violations))
    if not force and _last_validation_sig.get(filing_id) == sig:
        return None  # unchanged since the last persisted run — skip the audit DML

    batch = _ensure_filing_batch(filing_id, status="validating") or filing_id
    run_id = "run-" + _uuid.uuid4().hex[:12]
    rows_params: list[tuple] = []
    # 1 row per violation
    for v in violations:
        match_id = "m-" + _uuid.uuid4().hex[:14]
        rows_params.append((
            match_id, run_id, batch,
            v.get("record_id"), v.get("policy_number"),
            v.get("rule_id"), v.get("rule_number"), v.get("rule_name"),
            None, "fail",
            v.get("violation_reason"), v.get("severity"), v.get("citation"),
        ))
    # 1 summary "pass" row per rule that didn't trigger
    for r in rule_results:
        if r.get("violation_count", 0) == 0:
            match_id = "m-" + _uuid.uuid4().hex[:14]
            rows_params.append((
                match_id, run_id, batch,
                None, None,
                r.get("rule_id"), r.get("rule_number"), r.get("rule_name"),
                r.get("target_table"), "pass",
                None, r.get("severity"), r.get("citation"),
            ))

    if rows_params:
        placeholder = "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL, CURRENT_TIMESTAMP())"
        query(
            "INSERT INTO INSURANCE_REGULATORY.GOLD_AUDIT.RULE_MATCH_RESULT "
            "(match_id, run_id, filing_batch_id, source_record_id, policy_number, "
            " rule_id, rule_number, rule_name, target_table, status, "
            " violation_reason, severity, citation, evidence, validation_version, run_at) "
            "VALUES " + ", ".join([placeholder] * len(rows_params)),
            tuple(p for row in rows_params for p in row),
        )

    # Reconcile FILING_EXCEPTION: open new ones for current violations,
    # mark previously-open ones that are no longer in the current run as 'fixed'.
    current_keys = {(v["policy_number"], v["rule_id"]) for v in violations}

    # Open any new exceptions
    for v in violations:
        exc_id = f"exc-{filing_id}-{v.get('policy_number','')}-{(v.get('rule_id') or '')[:8]}".replace(" ", "")[:64]
        query(
            "MERGE INTO INSURANCE_REGULATORY.GOLD.FILING_EXCEPTION t "
            "USING (SELECT %s AS exception_id) s "
            "  ON t.exception_id = s.exception_id "
            "WHEN NOT MATCHED THEN INSERT "
            "(exception_id, filing_batch_id, source_record_id, policy_number, "
            " rule_id, rule_number, rule_name, severity, violation_reason, citation, "
            " opened_at, resolution_status) VALUES "
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP(), 'open')",
            (exc_id,
             exc_id, batch, v.get("record_id"), v.get("policy_number"),
             v.get("rule_id"), v.get("rule_number"), v.get("rule_name"),
             v.get("severity"), v.get("violation_reason"), v.get("citation")),
        )

    # Close exceptions no longer present in this filing's current run
    open_rows = query(
        "SELECT exception_id, policy_number, rule_id FROM INSURANCE_REGULATORY.GOLD.FILING_EXCEPTION "
        "WHERE filing_batch_id = %s AND resolution_status = 'open'",
        (batch,),
    )
    for row in open_rows:
        key = (
            row.get("policy_number") or row.get("POLICY_NUMBER"),
            row.get("rule_id") or row.get("RULE_ID"),
        )
        if key not in current_keys:
            exc_id = row.get("exception_id") or row.get("EXCEPTION_ID")
            extra, extra_params = "", []
            if resolution_action:
                extra = ", resolution_action = %s"
                extra_params = [resolution_action]
            query(
                "UPDATE INSURANCE_REGULATORY.GOLD.FILING_EXCEPTION "
                f"SET resolution_status = 'fixed', resolved_at = CURRENT_TIMESTAMP(){extra} "
                "WHERE exception_id = %s",
                (*extra_params, exc_id),
            )

    # Update filing-batch summary.
    # State transitions:
    #   - any open ERROR-severity violation → 'resolving'
    #   - all ERRORs cleared → 'validated' (ready for analyst sign-off)
    # Note: do not regress later sign-off states (analyst_signed, actuary_approved,
    # officer_approved, submitted, acked) just because validation was re-run.
    error_blockers = sum(1 for v in violations if (v.get("severity") or "").upper() == "ERROR")
    auto_status = "resolving" if error_blockers else "validated"
    query(
        "UPDATE INSURANCE_REGULATORY.GOLD.FILING_BATCH "
        "SET last_validated_at = CURRENT_TIMESTAMP(), "
        "    last_validation_run_id = %s, "
        "    open_blockers = %s, "
        "    status = CASE WHEN status IN ('analyst_signed','actuary_approved','officer_approved','submitted','acked') "
        "              THEN status ELSE %s END "
        "WHERE filing_batch_id = %s",
        (run_id, error_blockers, auto_status, batch),
    )

    # Also log a USER_ACTION for the run itself
    _record_action(filing_id, "validation_run", actor="system",
                   summary=f"{len(rule_results)} rules · {len(violations)} violations",
                   details={"run_id": run_id, "passing": sum(1 for r in rule_results if r.get('violation_count', 0) == 0),
                            "failing": sum(1 for r in rule_results if r.get('violation_count', 0) > 0),
                            "violations": len(violations)})
    _last_validation_sig[filing_id] = sig
    return run_id


@_audit_safe
def _record_action(filing_id: str, action_type: str, *,
                   actor: str = "system",
                   target_record: str | None = None,
                   target_rule: str | None = None,
                   summary: str | None = None,
                   details: dict | None = None) -> None:
    """Log a row to GOLD_AUDIT.USER_ACTION."""
    batch = _ensure_filing_batch(filing_id) or filing_id
    action_id = "act-" + _uuid.uuid4().hex[:14]
    details_json = json.dumps(details) if details else None
    query(
        "INSERT INTO INSURANCE_REGULATORY.GOLD_AUDIT.USER_ACTION "
        "(action_id, filing_batch_id, action_type, actor, target_record, target_rule, summary, details, acted_at) "
        "SELECT %s, %s, %s, %s, %s, %s, %s, PARSE_JSON(%s), CURRENT_TIMESTAMP()",
        (action_id, batch, action_type, actor, target_record, target_rule, summary, details_json),
    )


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


# Databricks INFORMATION_SCHEMA has no row_count column (that was Snowflake),
# so layer totals need per-table COUNT(*). One list query + one UNION ALL
# round trip, cached: row totals move slowly and the free-tier warehouse has a
# daily compute budget we shouldn't spend on a dashboard poll.
_PIPELINE_STATE_CACHE: dict[str, tuple[float, dict]] = {}
_PIPELINE_STATE_TTL = 600  # seconds


def _layer_tables_and_counts() -> list[dict]:
    tables = query(
        "SELECT table_schema AS s, table_name AS t "
        "FROM INSURANCE_REGULATORY.INFORMATION_SCHEMA.TABLES "
        "WHERE table_type IN ('BASE TABLE', 'MANAGED') "
        "  AND LOWER(table_schema) IN ('bronze', 'silver', 'gold')"
    )
    if not tables:
        return []
    unions = " UNION ALL ".join(
        f"SELECT '{r['s'].upper()}' AS layer, '{r['t']}' AS table_name, COUNT(*) AS n "
        f"FROM INSURANCE_REGULATORY.{r['s']}.{r['t']}"
        for r in tables
    )
    return query(unions)


@router.get("/pipeline/state")
def pipeline_state() -> JSONResponse:
    """Per-layer table + row counts for the pipeline/dashboard pages."""
    hit = _PIPELINE_STATE_CACHE.get("state")
    if hit and (_time.time() - hit[0]) < _PIPELINE_STATE_TTL:
        return JSONResponse(hit[1])
    rows = _layer_tables_and_counts()
    layers: dict[str, dict] = {}
    for r in rows:
        d = layers.setdefault(r["layer"], {"layer": r["layer"], "table_count": 0, "row_total": 0})
        if (r["n"] or 0) > 0:
            d["table_count"] += 1
            d["row_total"] += int(r["n"])
    order = ["BRONZE", "SILVER", "GOLD"]
    payload = {"layers": [layers[k] for k in order if k in layers]}
    _PIPELINE_STATE_CACHE["state"] = (_time.time(), payload)
    return JSONResponse(payload)


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


@router.get("/validate")
@router.get("/validate/cancellations")   # legacy alias — pre-dates the rule engine running everything
def validate_cancellations(filing: str | None = None,
                           background_tasks: BackgroundTasks = None) -> JSONResponse:
    """Run every rule from REFERENCE.TSPR_VALIDATION_RULES against BRONZE.

    For each rule we read its `violation_sql` (TRUE → row violates the rule)
    and execute a SELECT against the rule's `target_table`, returning the
    record id and the rule's citation so the UI can show provenance.

    If `filing` is provided, results are scoped to that filing's policy-prefix.
    """
    # P2.3: derive the filing's jurisdiction (default US-TX for the current
    # demo). The reference table carries `jurisdiction_code` per row, so a
    # filing for a future state would automatically use only that state's
    # rules + federal defaults.
    # Serve a fresh-enough cached result for HTTP callers (background_tasks set).
    # Internal callers (bulletin apply) pass no background_tasks → always fresh.
    _cache_key = filing or "__default__"
    _use_cache = background_tasks is not None
    if _use_cache:
        _hit = _VALIDATE_CACHE.get(_cache_key)
        if _hit and (_time.time() - _hit[0]) < _VALIDATE_TTL:
            return JSONResponse(_hit[1])

    target_jur = "US-TX"
    if filing:
        f_obj = _filing(filing)
        if f_obj:
            target_jur = f_obj.get("jurisdiction_code", "US-TX")
    rules = query(
        "SELECT rule_id, rule_number, rule_name, target_table, target_id_expr, "
        "       violation_sql, violation_reason, severity, citation, "
        "       jurisdiction_code, is_federal_default "
        "FROM INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES "
        "WHERE jurisdiction_code = %s OR jurisdiction_code = 'US' "
        "ORDER BY rule_number",
        (target_jur,),
    )
    scope_set = _filing_policy_numbers(filing)  # None = no scope filter
    pubid_to_policy = _pubid_map()              # cached; publicid → policy number

    # Evaluate every rule in a single round trip (batched UNION ALL).
    rule_results, violations = _run_rules(rules, scope_set, pubid_to_policy)

    summary = {
        "rules_run": len(rule_results),
        "rules_passing": sum(1 for r in rule_results if r["status"] == "pass"),
        "rules_failing": sum(1 for r in rule_results if r["status"] == "fail"),
        "rules_errored": sum(1 for r in rule_results if r["status"] == "error"),
        "total_violations": len(violations),
    }

    # Persist this run to audit (best-effort, never fails the request). Over
    # HTTP this runs in the background so the UI gets results immediately;
    # internal callers (e.g. bulletin apply, which needs the exception table
    # reconciled before computing deltas) pass no background_tasks → synchronous.
    run_id = None
    if filing:
        if background_tasks is not None:
            background_tasks.add_task(_record_validation_run, filing, rule_results, violations)
        else:
            # Internal callers (bulletin apply) need the exception table
            # reconciled now, so force past the dedupe.
            run_id = _record_validation_run(filing, rule_results, violations, force=True)

    payload = {
        "summary": summary,
        "rules": rule_results,
        "violations": violations,
        "run_id": run_id,
    }
    if _use_cache:
        _VALIDATE_CACHE[_cache_key] = (_time.time(), payload)
    return JSONResponse(payload)


@router.get("/validate/all")
def validate_all() -> JSONResponse:
    """Validate EVERY filing in one round trip. The UI loads all filings on the
    dashboard/records screens; doing it here (rules run once, unscoped, then
    partitioned by filing in memory) collapses N per-filing calls into one —
    the big win against Databricks serverless per-query latency. Cached like
    /validate; write-invalidated the same way."""
    hit = _VALIDATE_CACHE.get("__ALL__")
    if hit and (_time.time() - hit[0]) < _VALIDATE_TTL:
        return JSONResponse(hit[1])

    rules = query(
        "SELECT rule_id, rule_number, rule_name, target_table, target_id_expr, "
        "       violation_sql, violation_reason, severity, citation, "
        "       jurisdiction_code, is_federal_default "
        "FROM INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES "
        "WHERE jurisdiction_code = 'US-TX' OR jurisdiction_code = 'US' "
        "ORDER BY rule_number"
    )
    pubid_to_policy = _pubid_map()
    _, all_violations = _run_rules(rules, None, pubid_to_policy)  # unscoped: every violation

    by_filing: dict[str, dict] = {}
    for f in _live_filings():
        scope = _filing_policy_numbers(f["id"])
        fv = all_violations if scope is None else [v for v in all_violations if v["policy_number"] in scope]
        failing = {v["rule_id"] for v in fv}
        by_filing[f["id"]] = {
            "summary": {
                "rules_run": len(rules),
                "rules_passing": len(rules) - len(failing),
                "rules_failing": len(failing),
                "rules_errored": 0,
                "total_violations": len(fv),
            },
            "violations": fv,
            "run_id": None,
        }
    payload = {"by_filing": by_filing}
    _VALIDATE_CACHE["__ALL__"] = (_time.time(), payload)
    return JSONResponse(payload)


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

    Returns id, name, parsed section letter, citation, executable flag, and
    version metadata (version, status, effective_from/until, currently_active)
    so the UI can distinguish v1 / v2 of the same rule and grey out
    superseded or not-yet-active versions.
    """
    import re
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        result = s.run(
            """
            MATCH (r:Rule)
            OPTIONAL MATCH (r)-[:CITES]->(c:Citation)
            WITH r, head(collect(c)) AS c
            RETURN
              r.id              AS id,
              r.name            AS name,
              r.target_table    AS target_table,
              r.violation_sql   AS violation_sql,
              r.severity        AS severity,
              r.version         AS version,
              r.status          AS status,
              r.effective_from  AS effective_from,
              r.effective_until AS effective_until,
              CASE
                WHEN c IS NOT NULL THEN coalesce(c.full_citation, c.text, c.name)
                ELSE NULL
              END               AS citation
            ORDER BY r.name, r.version
            """
        )
        rules = [dict(r) for r in result]

    import datetime as _dt
    today = _dt.date.today()
    for r in rules:
        m = re.match(r"Rule\s+([A-Z])\.", r.get("name") or "")
        r["section"] = m.group(1) if m else "Other"
        r["executable"] = bool(r.get("target_table"))
        # Derive currently_active: status != superseded AND effective window includes today
        status = (r.get("status") or "").lower()
        def _coerce_date(v):
            if v is None:
                return None
            if isinstance(v, str):  # Neo4j may hand dates back as ISO strings
                try: return _dt.date.fromisoformat(v[:10])
                except ValueError: return None
            try: return _dt.date(v.year, v.month, v.day)
            except Exception: return None
        ef = _coerce_date(r.get("effective_from"))
        eu = _coerce_date(r.get("effective_until"))
        r["effective_from"] = ef.isoformat() if ef else None
        r["effective_until"] = eu.isoformat() if eu else None
        r["currently_active"] = (
            status != "superseded"
            and (ef is None or ef <= today)
            and (eu is None or eu >= today)
        )
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
    # set_expr is the SQL expression for the SET clause; set_param is the
    # bound value (None → NULL via the connector).
    set_expr, set_param = "%s", None
    if kind == "reason":
        new_str = (raw_val or "").strip().upper()
        if new_str and (not new_str.isalpha() or len(new_str) > 3):
            raise HTTPException(400, "reason_code must be 1–3 letters (or empty)")
        set_param = new_str or None
    elif kind == "text":
        new_str = (raw_val or "").strip()
        if len(new_str) > 64:
            raise HTTPException(400, "text value must be <=64 chars")
        set_param = new_str or None
    elif kind == "number":
        if raw_val in (None, ""):
            new_str = None
        else:
            try:
                num = float(raw_val)
            except (TypeError, ValueError):
                raise HTTPException(400, "new_value must be a number")
            set_param = num
            new_str = str(num)
    elif kind == "date":
        if raw_val in (None, ""):
            new_str = None
        else:
            import re as _re
            ds = str(raw_val).strip()
            if not _re.match(r"^\d{4}-\d{2}-\d{2}", ds):
                raise HTTPException(400, "date must be YYYY-MM-DD")
            set_expr = "TO_TIMESTAMP_NTZ(%s)"
            set_param = ds[:10]
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
            "WHERE p.policynumber = %s",
            (policy,),
        )
    else:  # POLICYPERIOD
        rows = query(
            "SELECT j.publicid, j.naic_number, j.writtenpremium, j.termtype "
            "FROM INSURANCE_REGULATORY.BRONZE.GW_PC_POLICYPERIOD j "
            "JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY p ON p.id = j.policy_id "
            "WHERE p.policynumber = %s",
            (policy,),
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
        f"SET {col} = {set_expr} "
        "WHERE publicid = %s",
        (set_param, pubid),
    )
    _invalidate_validate()  # data changed → stale any cached validation

    # Coerce DB-returned types into JSON-safe forms (Decimal, datetime, etc.)
    def _safe(v: Any) -> Any:
        if v is None: return None
        if isinstance(v, (dt.datetime, dt.date, dt.time)): return v.isoformat()
        if isinstance(v, Decimal): return float(v)
        return v

    # Audit: log the manual fix. Filing is inferred from the policy_id range.
    pid = None
    pid_rows = query("SELECT id FROM INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY WHERE policynumber = %s LIMIT 1", (policy,))
    if pid_rows:
        pid = pid_rows[0].get("id") or pid_rows[0].get("ID")
    filing_id = None
    if pid is not None:
        pid_int = int(pid)
        for f in _live_filings():
            if any(lo <= pid_int <= hi for lo, hi in _filing_ranges(f)):
                filing_id = f["id"]
                break
    if filing_id:
        _record_action(
            filing_id, "manual_fix",
            actor=(body.get("actor") or "user"),
            target_record=policy,
            target_rule=field,
            summary=f"{col}: {_safe(old)} → {new_str or '∅'}",
            details={"table": spec["table"], "field": col, "old": _safe(old), "new": new_str},
        )

    return JSONResponse({
        "ok": True,
        "policy_number": policy,
        "table": spec["table"],
        "field": col,
        "old_value": _safe(old),
        "new_value": new_str,
    })


@router.get("/bronze/policy/{policy}")
def bronze_policy(policy: str) -> JSONResponse:
    """Return a policy's current *editable* Bronze fields (the ones `/bronze/fix`
    can change), so the record-detail Edit panel can show + edit real values."""
    policy = (policy or "").strip().upper()
    if not policy.startswith("POL-"):
        raise HTTPException(400, "policy_number must be like POL-0015")

    def _safe(v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, (dt.datetime, dt.date, dt.time)):
            return v.isoformat()[:10]
        if isinstance(v, Decimal):
            return float(v)
        return v

    job = query(
        "SELECT j.cancellationreason, j.nonrenewalreason, j.declinereason, j.noticedate "
        "FROM INSURANCE_REGULATORY.BRONZE.GW_PC_JOB j "
        "JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY p ON p.id = j.policy_id "
        "WHERE p.policynumber = %s LIMIT 1",
        (policy,),
    )
    pp = query(
        "SELECT j.naic_number, j.writtenpremium, j.termtype "
        "FROM INSURANCE_REGULATORY.BRONZE.GW_PC_POLICYPERIOD j "
        "JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY p ON p.id = j.policy_id "
        "WHERE p.policynumber = %s LIMIT 1",
        (policy,),
    )
    jr, pr = (job[0] if job else {}), (pp[0] if pp else {})
    reason = next(
        (_g(jr, c) for c in ("cancellationreason", "nonrenewalreason", "declinereason")
         if _g(jr, c) is not None), None,
    )
    return JSONResponse({
        "policy_number": policy,
        "fields": {
            "reason_code": _safe(reason),
            "naic_number": _safe(_g(pr, "naic_number")),
            "writtenpremium": _safe(_g(pr, "writtenpremium")),
            "termtype": _safe(_g(pr, "termtype")),
            "noticedate": _safe(_g(jr, "noticedate")),
        },
    })


_SUBMISSION_COLS = [
    "naic_company_no", "policy_id", "record_type", "stat_plan",
    "effective_date", "expiry_date", "amt_insurance_dw", "amt_insurance_pp",
    "line_of_business", "policy_form", "number_of_families", "coverage_occupancy",
    "construction", "ppc_simple", "deductible_1_amt", "fire_premium", "ec_premium",
    "zip9", "validation_status",
]


@router.get("/submission/{policy}")
def submission_record(policy: str) -> JSONResponse:
    """The final TSPR record that will be submitted for a policy — the encoded
    canonical row from SILVER.TSPR_PREMIUM_STAGING (MMDDY effective / MMY expiry
    dates, amounts in $1000s, coded LOB / form / construction / PPC). This is the
    output the pipeline files, as opposed to the editable Bronze source."""
    policy = (policy or "").strip().upper()
    if not policy.startswith("POL-"):
        raise HTTPException(400, "policy_number must be like POL-0015")

    def _safe(v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, (dt.datetime, dt.date, dt.time)):
            return v.isoformat()[:10]
        if isinstance(v, Decimal):
            return float(v)
        return v

    try:
        rows = query(
            f"SELECT {', '.join(_SUBMISSION_COLS)} "
            "FROM INSURANCE_REGULATORY.SILVER.TSPR_PREMIUM_STAGING "
            "WHERE policy_id = %s LIMIT 1",
            (policy,),
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"submission lookup failed: {e}") from e

    if not rows:
        return JSONResponse({
            "policy_number": policy, "found": False,
            "note": "No SILVER.TSPR_PREMIUM_STAGING row — run the Bronze→Silver pipeline.",
        })
    r = rows[0]
    return JSONResponse({
        "policy_number": policy, "found": True,
        "fields": {c: _safe(_g(r, c)) for c in _SUBMISSION_COLS},
    })


@router.get("/bronze/claims")
def bronze_claims(filing: str | None = None) -> JSONResponse:
    """List GW_CC_CLAIM rows joined to GW_PC_POLICY, scoped to a filing.

    Powers the workstation's Claims popout. Each row carries enough fields
    to render a row in the table and to power per-claim drilldowns.
    """
    where = "WHERE 1=1" + _scope_clause(filing)
    rows = query(
        "SELECT c.claimnumber AS claim_number, "
        "       p.policynumber AS policy, "
        "       c.losscause AS loss_cause, "
        "       c.losscausesubtype AS loss_subtype, "
        "       TO_VARCHAR(c.lossdate, 'YYYY-MM-DD') AS loss_date, "
        "       TO_VARCHAR(c.reporteddate, 'YYYY-MM-DD') AS reported_date, "
        "       DATEDIFF(day, c.lossdate, c.reporteddate) AS reporting_lag_days, "
        "       c.totalincurred AS total_incurred, "
        "       c.isintwiazone AS in_twia_zone, "
        "       c.state AS state "
        "FROM INSURANCE_REGULATORY.BRONZE.GW_CC_CLAIM c "
        "JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY p ON p.id = c.policy_id "
        f"{where} "
        "ORDER BY c.totalincurred DESC NULLS LAST"
    )
    return JSONResponse({"rows": _jsonify(rows), "count": len(rows), "filing": filing})


@router.get("/bronze/cancellations")
def bronze_cancellations(filing: str | None = None) -> JSONResponse:
    """Read BRONZE.GW_PC_JOB joined to GW_PC_POLICY — what Guidewire sent.

    If `filing` is provided, scope to that filing's policy prefix.
    """
    where = "WHERE 1=1" + _scope_clause(filing)
    rows = query(
        "SELECT p.policynumber AS policy, "
        "       j.subtype AS action, "
        "       COALESCE(j.cancellationreason, j.nonrenewalreason, j.declinereason) AS reason_code, "
        "       TO_VARCHAR(j.noticedate, 'YYYY-MM-DD') AS noticedate, "
        "       TO_VARCHAR(j.effectivedate, 'YYYY-MM-DD') AS effectivedate "
        "FROM INSURANCE_REGULATORY.BRONZE.GW_PC_JOB j "
        "JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY p ON p.id = j.policy_id "
        f"{where} "
        "ORDER BY p.policynumber"
    )
    return JSONResponse({"rows": _jsonify(rows), "count": len(rows), "filing": filing})


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


# ── TSPR fixed-width ASCII renderer ────────────────────────────────────────
# Reads Gold submission tables, emits 200-char records per TSPR layout, computes
# the SHA-256 seal, and (optionally) persists a row to GOLD.FILING_SUBMISSION.
# Simplified layout — captures the essential structure (record-type + key
# positional fields) without being byte-for-byte spec-compliant.

_TSPR_RECORD_WIDTH = 200


def _pad_alpha(value: Any, length: int) -> str:
    """Left-justify, pad right with spaces. NULL/None → spaces. Truncate if too long."""
    s = "" if value is None else str(value)
    return s[:length].ljust(length, " ")


def _pad_num(value: Any, length: int, *, cents: bool = False) -> str:
    """Right-justify, pad left with zeros. Numeric values rendered as integers
    (cents=True multiplies by 100 to encode money-as-cents). NULL → all zeros."""
    if value is None or value == "":
        return "0" * length
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "0" * length
    if cents:
        n = int(round(n * 100))
    else:
        n = int(round(n))
    return str(abs(n))[:length].rjust(length, "0")


def _pad_date(value: Any, length: int = 8) -> str:
    """Render a date/datetime as YYYYMMDD (or YYMMDD if length=6)."""
    if value is None:
        return "0" * length
    if isinstance(value, dt.datetime) or isinstance(value, dt.date):
        if length == 6:
            return value.strftime("%y%m%d")
        return value.strftime("%Y%m%d")
    s = str(value)
    # Already-string ISO dates: strip dashes
    s = s.replace("-", "").replace(" 00:00:00", "")[:length]
    return s.ljust(length, "0")[:length]


def _render_header(naic: str, filing: dict, premium_n: int, loss_n: int, cancel_n: int) -> str:
    """Filing header — first line of the file."""
    out = (
        "H" +
        _pad_alpha(naic, 5) +
        _pad_alpha(filing["id"], 14) +
        _pad_date(filing.get("period_start")) +
        _pad_date(filing.get("period_end")) +
        _pad_alpha(filing.get("plan_code"), 3) +
        _pad_num(premium_n, 6) +
        _pad_num(loss_n, 6) +
        _pad_num(cancel_n, 6) +
        dt.datetime.now().strftime("%Y%m%d%H%M%S")
    )
    return out.ljust(_TSPR_RECORD_WIDTH, " ")[:_TSPR_RECORD_WIDTH]


def _render_premium_record(r: dict, naic: str) -> str:
    """One P-record per row in GOLD.TSPR_PREMIUM_RECORDS."""
    g = lambda k: r.get(k) if k in r else r.get(k.upper())
    out = (
        "P" +
        _pad_alpha(naic, 5) +
        _pad_num(g("policy_id"), 10) +
        _pad_date(g("effective_date")) +
        _pad_date(g("expiry_date")) +
        _pad_num(g("amt_insurance_dw"), 10) +
        _pad_alpha(g("policy_form"), 2) +
        _pad_num(g("number_of_families"), 1) +
        _pad_alpha(g("construction"), 1) +
        _pad_alpha(g("ppc_split"), 3) +
        _pad_num(g("term"), 3) +
        _pad_alpha(g("line_of_business"), 3) +
        _pad_alpha(g("tico_company_no"), 5) +
        _pad_alpha(g("stat_plan"), 4) +
        _pad_alpha(g("place_code"), 5)
    )
    return out.ljust(_TSPR_RECORD_WIDTH, " ")[:_TSPR_RECORD_WIDTH]


def _render_loss_record(r: dict, naic: str) -> str:
    """One L-record per row in GOLD.TSPR_LOSS_RECORDS."""
    g = lambda k: r.get(k) if k in r else r.get(k.upper())
    out = (
        "L" +
        _pad_alpha(naic, 5) +
        _pad_num(g("policy_id"), 10) +
        _pad_date(g("occurrence_date")) +
        _pad_date(g("policy_effective_date")) +
        _pad_alpha(g("kind_code"), 2) +
        _pad_num(g("amt_insurance_dw"), 10) +
        _pad_alpha(g("policy_form"), 2) +
        _pad_num(g("number_of_families"), 1) +
        _pad_alpha(g("construction"), 1) +
        _pad_alpha(g("ppc_split"), 3) +
        _pad_alpha(g("line_of_business"), 3) +
        _pad_alpha(g("tico_company_no"), 5) +
        _pad_alpha(g("stat_plan"), 4) +
        _pad_alpha(g("place_code"), 5)
    )
    return out.ljust(_TSPR_RECORD_WIDTH, " ")[:_TSPR_RECORD_WIDTH]


def _render_cancellation_record(r: dict, naic: str) -> str:
    """One C-record per row in GOLD.TSPR_CANCELLATION_RECORDS."""
    g = lambda k: r.get(k) if k in r else r.get(k.upper())
    out = (
        "C" +
        _pad_alpha(naic, 5) +
        _pad_date(g("notification_date_encoded"), 6) +
        _pad_alpha(g("action_type"), 1) +
        _pad_alpha(g("type_of_policy"), 1) +
        _pad_alpha(g("reason_source_indicator"), 1) +
        _pad_alpha(g("within_60_days_indicator"), 1) +
        _pad_alpha(g("zip5"), 5) +
        _pad_alpha(g("reason_code_list"), 5) +
        _pad_num(g("recipient_count"), 6) +
        _pad_num(g("actual_action_count"), 6) +
        _pad_alpha(g("tico_company_no"), 5) +
        _pad_alpha(g("unique_combination_key"), 20)
    )
    return out.ljust(_TSPR_RECORD_WIDTH, " ")[:_TSPR_RECORD_WIDTH]


def _render_footer(naic: str, agg: dict, sha256: str) -> str:
    """Trailer record with totals + the file's own SHA-256 seal."""
    g = lambda k: agg.get(k) if k in agg else agg.get(k.upper())
    out = (
        "F" +
        _pad_alpha(naic, 5) +
        _pad_num(g("premium_record_count"), 6) +
        _pad_num(g("loss_record_count"), 6) +
        _pad_num(g("cancellation_notice_count"), 6) +
        _pad_num(g("total_written_premium"), 14, cents=True) +
        _pad_num(g("total_paid_losses"), 14, cents=True) +
        _pad_num(g("total_outstanding_losses"), 14, cents=True) +
        sha256[:64]
    )
    return out.ljust(_TSPR_RECORD_WIDTH, " ")[:_TSPR_RECORD_WIDTH]


@router.get("/filing/{filing_id}/file")
def filing_file(filing_id: str, persist: bool = False) -> JSONResponse:
    """Render the TSPR fixed-width ASCII submission file for a filing.

    Pulls every Gold record scoped to this filing, renders 200-char
    P/L/C records, prefixes a header, appends an SHA-256-sealed footer.

    Set ?persist=true to also write a FILING_SUBMISSION row + USER_ACTION
    so the audit chain captures who generated this file when.
    """
    import hashlib

    f = _filing(filing_id)
    if not f:
        raise HTTPException(404, f"unknown filing {filing_id}")

    # Resolve NAIC from the first policyperiod row in scope
    naic_rows = query(
        "SELECT pp.naic_number AS naic "
        "FROM INSURANCE_REGULATORY.BRONZE.GW_PC_POLICYPERIOD pp "
        "JOIN INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY p ON p.id = pp.policy_id "
        f"WHERE 1=1 {_scope_clause(filing_id)} "
        "AND REGEXP_LIKE(pp.naic_number, '^[0-9]{5}$') "
        "LIMIT 1"
    )
    naic = (naic_rows[0].get("naic") or naic_rows[0].get("NAIC")) if naic_rows else "00000"

    # Scope all three Gold tables to this filing via the stamped filing_batch_id
    # column. (Previously cancellation fell back to a ZIP-overlap heuristic
    # because the table was aggregated by Rule 34 unique-combination key and
    # carried no policy reference. run_gold now stamps filing_batch_id during
    # the Silver→Gold step.)
    if filing_id:
        scope = "WHERE filing_batch_id = %s"
        premium = query(f"SELECT * FROM INSURANCE_REGULATORY.GOLD.TSPR_PREMIUM_RECORDS       {scope} ORDER BY record_seq", (filing_id,))
        loss    = query(f"SELECT * FROM INSURANCE_REGULATORY.GOLD.TSPR_LOSS_RECORDS          {scope} ORDER BY record_seq", (filing_id,))
        cancel  = query(f"SELECT * FROM INSURANCE_REGULATORY.GOLD.TSPR_CANCELLATION_RECORDS  {scope} ORDER BY record_seq", (filing_id,))
    else:
        premium = query("SELECT * FROM INSURANCE_REGULATORY.GOLD.TSPR_PREMIUM_RECORDS ORDER BY record_seq")
        loss    = query("SELECT * FROM INSURANCE_REGULATORY.GOLD.TSPR_LOSS_RECORDS    ORDER BY record_seq")
        cancel  = query("SELECT * FROM INSURANCE_REGULATORY.GOLD.TSPR_CANCELLATION_RECORDS ORDER BY record_seq")

    agg_rows = query("SELECT * FROM INSURANCE_REGULATORY.GOLD.TSPR_MONTHLY_AGGREGATES LIMIT 1")
    agg = agg_rows[0] if agg_rows else {}

    # Render lines
    header_line = _render_header(naic, f, len(premium), len(loss), len(cancel))
    p_lines = [_render_premium_record(r, naic) for r in premium]
    l_lines = [_render_loss_record(r, naic) for r in loss]
    c_lines = [_render_cancellation_record(r, naic) for r in cancel]

    body = "\n".join([header_line] + p_lines + l_lines + c_lines)
    sha256 = hashlib.sha256(body.encode("ascii", errors="replace")).hexdigest()
    footer_line = _render_footer(naic, agg, sha256)

    file_text = body + "\n" + footer_line + "\n"
    file_name = f"TSPR_{naic}_{f['plan_code']}_{filing_id.replace('-', '')}.txt"

    record_total = len(p_lines) + len(l_lines) + len(c_lines)
    response = {
        "filing_id":    filing_id,
        "file_name":    file_name,
        "naic":         naic,
        "record_count": record_total,
        "byte_count":   len(file_text.encode("ascii", errors="replace")),
        "sha256":       sha256,
        "preview":      file_text[:2400],   # first ~12 lines
        "header":       header_line,
        "footer":       footer_line,
        "p_count":      len(p_lines),
        "l_count":      len(l_lines),
        "c_count":      len(c_lines),
        # Warning if Gold doesn't have records for this filing — happens when bulk
        # synthetic policies have only been promoted to Bronze, not through the
        # Silver/Gold pipeline.  Run `make run-pipeline` to populate.
        "warning":      None if record_total > 0 else (
            f"No Gold records found for filing {filing_id}. "
            f"Run `make run-pipeline` to promote Bronze → Silver → Gold."
        ),
    }

    if persist:
        # Gate sealing on the approval chain: only an officer-approved filing
        # with zero open ERROR blockers can be submitted to TICO.
        gate_rows = query(
            "SELECT status, open_blockers FROM INSURANCE_REGULATORY.GOLD.FILING_BATCH "
            "WHERE filing_batch_id = %s",
            (filing_id,),
        )
        gate_status = (gate_rows[0].get("status") or gate_rows[0].get("STATUS") or "").lower() if gate_rows else ""
        gate_blockers = int((gate_rows[0].get("open_blockers") or gate_rows[0].get("OPEN_BLOCKERS") or 0) if gate_rows else 0)
        if gate_status != "officer_approved" or gate_blockers > 0:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"cannot seal: status is '{gate_status or 'unknown'}' with "
                    f"{gate_blockers} open blocker(s); filing must be officer_approved with 0 ERROR blockers"
                ),
            )
        # Write a FILING_SUBMISSION row + USER_ACTION audit event + advance state to 'submitted'
        sub_id = "sub-" + _uuid.uuid4().hex[:14]
        try:
            query(
                "INSERT INTO INSURANCE_REGULATORY.GOLD.FILING_SUBMISSION "
                "(submission_id, filing_batch_id, channel, submitted_by, "
                " file_name, file_sha256, file_size_bytes, record_count, status, submitted_at) "
                "SELECT %s, %s, %s, %s, %s, %s, %s, %s, 'sealed', CURRENT_TIMESTAMP()",
                (sub_id, filing_id, f["channel"], "D. Reyes",
                 file_name, sha256, response["byte_count"], response["record_count"]),
            )
        except Exception:
            logger.warning("[file] FILING_SUBMISSION insert failed", exc_info=True)
        try:
            query(
                "UPDATE INSURANCE_REGULATORY.GOLD.FILING_BATCH "
                "SET status = 'submitted', submitted_at = CURRENT_TIMESTAMP() "
                "WHERE filing_batch_id = %s",
                (filing_id,),
            )
        except Exception:
            logger.warning("[file] FILING_BATCH status update failed", exc_info=True)
        _record_action(
            filing_id, "file_generated",
            actor="D. Reyes",
            target_record=file_name,
            summary=f"Sealed {response['record_count']} records · {response['byte_count']} bytes · sha256:{sha256[:12]}…",
            details={"sha256": sha256, "record_count": response["record_count"], "submission_id": sub_id},
        )
        response["persisted"] = True
        response["submission_id"] = sub_id

    return JSONResponse(response)


@router.get("/audit/{filing_id}")
def audit_history(filing_id: str, limit: int = 50) -> JSONResponse:
    """Read the persisted audit history for a filing.

    Returns the most recent N user actions (validation runs, manual fixes,
    bulletin applies, etc.) plus the filing's batch metadata and current
    exception list. Powers the Audit Log screen.
    """
    try:
        batch_rows = query(
            "SELECT filing_batch_id, status, last_validated_at, last_validation_run_id, "
            "       open_blockers, generated_at, submitted_at, acked_at "
            "FROM INSURANCE_REGULATORY.GOLD.FILING_BATCH "
            "WHERE filing_batch_id = %s",
            (filing_id,),
        )
    except Exception:
        batch_rows = []

    try:
        actions = query(
            "SELECT action_id, action_type, actor, target_record, target_rule, "
            "       summary, "
            "       TO_VARCHAR(acted_at, 'YYYY-MM-DD HH24:MI:SS') AS acted_at "
            "FROM INSURANCE_REGULATORY.GOLD_AUDIT.USER_ACTION "
            "WHERE filing_batch_id = %s "
            "ORDER BY acted_at DESC "
            "LIMIT %s",
            (filing_id, int(limit)),
        )
    except Exception:
        actions = []

    try:
        exceptions = query(
            "SELECT exception_id, source_record_id, policy_number, rule_number, rule_name, "
            "       severity, violation_reason, resolution_status, resolution_action, "
            "       TO_VARCHAR(opened_at, 'YYYY-MM-DD HH24:MI:SS') AS opened_at, "
            "       TO_VARCHAR(resolved_at, 'YYYY-MM-DD HH24:MI:SS') AS resolved_at "
            "FROM INSURANCE_REGULATORY.GOLD.FILING_EXCEPTION "
            "WHERE filing_batch_id = %s "
            "ORDER BY opened_at DESC",
            (filing_id,),
        )
    except Exception:
        exceptions = []

    return JSONResponse({
        "filing_id": filing_id,
        "batch":     _jsonify(batch_rows)[0] if batch_rows else None,
        "actions":   _jsonify(actions),
        "exceptions":_jsonify(exceptions),
    })


# Sign-off chain: analyst submits for approval, actuary signs, officer signs,
# then "Seal & submit" persists the file. Each transition writes a USER_ACTION
# row and the resulting state lives in FILING_BATCH.status.
APPROVAL_CHAIN = {
    # role:     (required_current_state,        next_state,          actor_label)
    "analyst":  (("validated",),                "analyst_signed",    "M. Okonkwo · Analyst"),
    "actuary":  (("analyst_signed",),           "actuary_approved",  "D. Reyes · Actuary"),
    "officer":  (("actuary_approved",),         "officer_approved",  "J. Park · Compliance Officer"),
}


@router.post("/filing/{filing_id}/approve")
def filing_approve(filing_id: str, body: dict = Body(...)) -> JSONResponse:
    """Advance the filing one step along the sign-off chain.

    Body: {"role": "analyst"|"actuary"|"officer"}.
    Each role is gated on the prior state AND zero open ERROR-severity blockers.
    """
    role = (body.get("role") or "").lower().strip()
    if role not in APPROVAL_CHAIN:
        raise HTTPException(status_code=400, detail=f"unknown role '{role}'; expected one of {list(APPROVAL_CHAIN)}")
    required, next_state, actor = APPROVAL_CHAIN[role]

    _ensure_filing_batch(filing_id)
    rows = query(
        "SELECT status, open_blockers FROM INSURANCE_REGULATORY.GOLD.FILING_BATCH "
        "WHERE filing_batch_id = %s",
        (filing_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"no filing batch for {filing_id}")
    current = (rows[0].get("status") or rows[0].get("STATUS") or "").lower()
    open_blockers = int(rows[0].get("open_blockers") or rows[0].get("OPEN_BLOCKERS") or 0)

    if current not in required:
        raise HTTPException(
            status_code=409,
            detail=f"cannot {role}-approve in state '{current}' — must be one of {list(required)}",
        )
    if open_blockers > 0:
        raise HTTPException(
            status_code=409,
            detail=f"cannot sign off — {open_blockers} open ERROR-severity blocker(s) remain",
        )

    query(
        "UPDATE INSURANCE_REGULATORY.GOLD.FILING_BATCH "
        "SET status = %s "
        "WHERE filing_batch_id = %s",
        (next_state, filing_id),
    )
    _record_action(
        filing_id, f"{role}_approved",
        actor=actor,
        summary=f"{actor.split(' · ')[-1]} signed off — state {current} → {next_state}",
        details={"prev_state": current, "new_state": next_state, "role": role},
    )
    return JSONResponse({"filing_id": filing_id, "role": role, "prev_state": current, "new_state": next_state, "actor": actor})


@router.post("/filing/{filing_id}/ack")
def filing_ack(filing_id: str) -> JSONResponse:
    """Record a regulator (TICO) acknowledgment for the most recent submission.

    In real life this would be an inbound webhook from TICO ShareFile carrying
    the receipt id. For the demo we synthesize one. Requires the filing to be
    in 'submitted' state.
    """
    rows = query(
        "SELECT status FROM INSURANCE_REGULATORY.GOLD.FILING_BATCH "
        "WHERE filing_batch_id = %s",
        (filing_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"no filing batch for {filing_id}")
    current = (rows[0].get("status") or rows[0].get("STATUS") or "").lower()
    if current != "submitted":
        raise HTTPException(
            status_code=409,
            detail=f"cannot ACK in state '{current}' — filing must be 'submitted'",
        )

    receipt = "TICO-ACK-" + _uuid.uuid4().hex[:8].upper()
    # Update the most recent FILING_SUBMISSION row (the seal we want to ACK)
    query(
        "UPDATE INSURANCE_REGULATORY.GOLD.FILING_SUBMISSION "
        "SET acked_at = CURRENT_TIMESTAMP(), acknowledgment = %s, status = 'acked' "
        "WHERE filing_batch_id = %s "
        "  AND submission_id = (SELECT submission_id FROM INSURANCE_REGULATORY.GOLD.FILING_SUBMISSION "
        "                       WHERE filing_batch_id = %s "
        "                       ORDER BY submitted_at DESC LIMIT 1)",
        (receipt, filing_id, filing_id),
    )
    query(
        "UPDATE INSURANCE_REGULATORY.GOLD.FILING_BATCH "
        "SET status = 'acked', acked_at = CURRENT_TIMESTAMP() "
        "WHERE filing_batch_id = %s",
        (filing_id,),
    )
    _record_action(
        filing_id, "regulator_ack",
        actor="TICO ShareFile",
        target_record=receipt,
        summary=f"Regulator acknowledged · receipt {receipt}",
        details={"receipt_id": receipt, "prev_state": "submitted", "new_state": "acked"},
    )
    return JSONResponse({"filing_id": filing_id, "receipt_id": receipt, "new_state": "acked"})


@router.get("/filing/{filing_id}/approval-state")
def filing_approval_state(filing_id: str) -> JSONResponse:
    """Compact state useful for rendering the sign-off chain widget."""
    _ensure_filing_batch(filing_id)
    rows = query(
        "SELECT status, open_blockers, last_validated_at, submitted_at, acked_at "
        "FROM INSURANCE_REGULATORY.GOLD.FILING_BATCH "
        "WHERE filing_batch_id = %s",
        (filing_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"no filing batch for {filing_id}")
    r = _jsonify(rows)[0]
    current = (r.get("status") or "").lower()
    # The next role allowed to act, given the current state
    next_role = None
    for role, (required, _, _) in APPROVAL_CHAIN.items():
        if current in required:
            next_role = role
            break
    # Can_seal: officer-approved + zero ERROR blockers
    can_seal = current == "officer_approved" and int(r.get("open_blockers") or 0) == 0
    return JSONResponse({
        "filing_id":     filing_id,
        "status":        current,
        "open_blockers": int(r.get("open_blockers") or 0),
        "next_role":     next_role,
        "can_seal":      can_seal,
        "submitted_at":  r.get("submitted_at"),
        "acked_at":      r.get("acked_at"),
    })


@router.get("/kg/diff")
def kg_diff(
    since: str | None = None,
    audit_id: str | None = None,
) -> JSONResponse:
    """Structured diff of canon changes.

    Two query modes:
      - `?since=YYYY-MM-DDTHH:MM:SS` — every node mutated since the given time
      - `?audit_id=<uuid>` — every node touched by one logical audit entry
        (e.g., a specific bulletin apply)

    Returns:
      {
        "scope":           "since" | "audit",
        "from":            ISO timestamp,
        "added_nodes":     [{id, type, name, created_at}],
        "modified_nodes":  [{id, type, name, change_summary}],
        "superseded_nodes":[{id, type, name, effective_until}],
        "added_edges":     [{src_name, dst_name, type}],   // best-effort
        "audit_entries":   [{id, action, actor, summary, occurred_at, affected_count}]
      }
    """
    if not (since or audit_id):
        raise HTTPException(status_code=400, detail="provide ?since=... or ?audit_id=...")
    if since and audit_id:
        raise HTTPException(status_code=400, detail="provide only one of ?since / ?audit_id")

    try:
        with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
            # ── Determine the affected-node set + the audit entries in scope ──
            if audit_id:
                # Single-audit scope: walk MUTATED_BY from that one entry
                audit_rows = list(s.run(
                    """
                    MATCH (a:KGAuditEntry {id: $aid})
                    RETURN a
                    """, aid=audit_id
                ))
                if not audit_rows:
                    raise HTTPException(status_code=404, detail=f"audit entry not found: {audit_id}")
                affected = list(s.run(
                    """
                    MATCH (n)-[:MUTATED_BY]->(a:KGAuditEntry {id: $aid})
                    RETURN n
                    """, aid=audit_id
                ))
                from_marker = audit_rows[0]["a"].get("occurred_at")
            else:
                # Time scope: nodes mutated AND audit entries written since the cutoff.
                # NB: occurred_at + created_at are stored as ISO 8601 strings;
                # lexicographic comparison is equivalent to chronological for ISO 8601.
                audit_rows = list(s.run(
                    """
                    MATCH (a:KGAuditEntry)
                    WHERE a.occurred_at >= $since
                    RETURN a
                    ORDER BY a.occurred_at DESC
                    """, since=since
                ))
                affected = list(s.run(
                    """
                    MATCH (n)-[:MUTATED_BY]->(a:KGAuditEntry)
                    WHERE a.occurred_at >= $since
                    RETURN DISTINCT n
                    UNION
                    MATCH (n:GRENode)
                    WHERE n.created_at >= $since
                    RETURN DISTINCT n
                    """, since=since
                ))
                from_marker = since

            # ── Classify each affected node: added / modified / superseded ──
            import neo4j.time as nt
            def _iso(v):
                if v is None: return None
                if isinstance(v, (nt.DateTime, nt.Date)): return str(v)
                return v

            # Determine the cutoff for "is this node newly added?": for since-mode
            # it's the `since` string; for audit-mode it's the audit's occurred_at
            # minus a small slack so we don't miss nodes created in the same
            # logical operation.
            cutoff_iso = since
            if audit_id and audit_rows:
                cutoff_iso = audit_rows[0]["a"].get("occurred_at")

            added, modified, superseded = [], [], []
            for row in affected:
                n = row["n"]
                if n is None:
                    continue
                props = dict(n.items())
                # Type fallback: nodes created via raw Cypher in legacy scripts may
                # not have the `type` property set even though they carry the
                # native label. Derive from labels(n) when the property is null.
                node_type = props.get("type")
                if not node_type:
                    labels = [lbl for lbl in n.labels if lbl != "GRENode"]
                    node_type = labels[0] if labels else None
                summary = {
                    "id":     props.get("id"),
                    "type":   node_type,
                    "name":   props.get("name"),
                    "status": props.get("status"),
                    "version":  props.get("version"),
                    "created_at":      _iso(props.get("created_at")),
                    "effective_from":  _iso(props.get("effective_from")),
                    "effective_until": _iso(props.get("effective_until")),
                }
                created_str = props.get("created_at")
                if isinstance(created_str, (nt.DateTime, nt.Date)):
                    created_str = str(created_str)
                # Bucketize: same-operation creation → added; superseded → superseded; else modified.
                # For audit-mode, "added" means the node's created_at is at or after the audit's occurred_at.
                # For since-mode, "added" means created_at >= since.
                is_new = bool(created_str and cutoff_iso and created_str >= cutoff_iso)
                st = (props.get("status") or "").lower()
                if is_new:
                    added.append(summary)
                elif st == "superseded":
                    superseded.append(summary)
                else:
                    modified.append(summary)

            # ── Edges: best-effort, find OVERRIDES + CITES added in the same window via MUTATED_BY chain ──
            # We can't easily diff arbitrary edges without history, but the bulletin flow's
            # main edge writes (OVERRIDES, CITES from BulletinOverride) are reachable via
            # affected nodes.
            affected_ids = [s_["id"] for s_ in added + modified + superseded]
            added_edges = []
            if affected_ids:
                edges = s.run(
                    """
                    MATCH (src)-[r:OVERRIDES|CITES]->(dst)
                    WHERE src.id IN $ids OR dst.id IN $ids
                    RETURN src.name AS src_name, src.type AS src_type,
                           dst.name AS dst_name, dst.type AS dst_type,
                           type(r) AS rel_type
                    LIMIT 200
                    """, ids=affected_ids
                )
                added_edges = [dict(r) for r in edges]

            # ── Format audit entries ──
            audits = []
            for row in audit_rows:
                a = row["a"]
                ap = dict(a.items())
                audits.append({
                    "id":             ap.get("id"),
                    "action":         ap.get("action"),
                    "actor":          ap.get("actor"),
                    "summary":        ap.get("summary"),
                    "occurred_at":    _iso(ap.get("occurred_at")),
                    "affected_count": ap.get("affected_count"),
                })

            return JSONResponse({
                "scope":             "audit" if audit_id else "since",
                "from":              _iso(from_marker),
                "added_nodes":       added,
                "modified_nodes":    modified,
                "superseded_nodes":  superseded,
                "added_edges":       added_edges,
                "audit_entries":     audits,
                "total_changes":     len(added) + len(modified) + len(superseded),
            })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"KG diff failed: {e}") from e


@router.get("/kg/audit")
def kg_audit(limit: int = 50, node_id: str | None = None) -> JSONResponse:
    """Read the KG audit history.

    Returns the most recent N KGAuditEntry rows (default 50). If `node_id` is
    provided, scopes to entries affecting that specific node via MUTATED_BY.
    Mirrors the RHS-side /audit/{filing_id} but on the canon side.
    """
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be 1..500")
    try:
        with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
            if node_id:
                cypher = """
                    MATCH (n:GRENode {id: $node_id})-[:MUTATED_BY]->(a:KGAuditEntry)
                    RETURN a
                    ORDER BY a.occurred_at DESC
                    LIMIT $limit
                """
                rows = [dict(r["a"].items()) for r in s.run(cypher, node_id=node_id, limit=limit)]
            else:
                cypher = """
                    MATCH (a:KGAuditEntry)
                    RETURN a
                    ORDER BY a.occurred_at DESC
                    LIMIT $limit
                """
                rows = [dict(r["a"].items()) for r in s.run(cypher, limit=limit)]

            # Coerce neo4j.time → iso strings for JSON
            import neo4j.time as nt
            for r in rows:
                for k, v in list(r.items()):
                    if isinstance(v, (nt.Date, nt.DateTime)):
                        r[k] = str(v)
            return JSONResponse({"entries": rows, "count": len(rows), "node_id": node_id})
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"KG unreachable: {e}") from e


@router.get("/kg/neighborhood/{rule_id}")
def kg_neighborhood(rule_id: str, depth: int = 1) -> JSONResponse:
    """Return a graph slice centered on `rule_id` for vis-network rendering.

    Pulls the rule's immediate neighbors: cited Citation, parent Section,
    companion Rules, and any KG nodes connected by named relationships.
    Output shape is {nodes: [{id,label,group,...}], edges: [{from,to,label}]}.
    """
    if depth < 1 or depth > 3:
        raise HTTPException(status_code=400, detail="depth must be 1..3")
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        # Variable-length match to grab the 1-2 hop neighborhood
        cypher = f"""
            MATCH (r:Rule)
            WHERE r.id = $rid OR elementId(r) = $rid
            OPTIONAL MATCH path = (r)-[*1..{depth}]-(n)
            WITH r, collect(DISTINCT n) AS neighbors, collect(DISTINCT path) AS paths
            RETURN r,
                   [x IN neighbors WHERE x IS NOT NULL] AS neighbors,
                   [p IN paths WHERE p IS NOT NULL | relationships(p)] AS rel_lists
        """
        res = s.run(cypher, rid=rule_id).single()
        if not res:
            return JSONResponse({"nodes": [], "edges": []})
        rule = res["r"]
        neighbors = res["neighbors"]
        rel_lists = res["rel_lists"]

        def node_dict(node, is_root=False):
            labels = list(node.labels)
            label = labels[0] if labels else "Node"
            display = node.get("name") or node.get("text") or node.get("title") or node.get("citation") or label
            return {
                "id":     str(node.element_id),
                "label":  display[:55] if isinstance(display, str) else label,
                "group":  ("root" if is_root else label),
                "title":  f"{label}\n{(display or '')[:200]}" if isinstance(display, str) else label,
                "shape":  ("box" if is_root else ("ellipse" if label == "Rule" else "dot")),
            }

        nodes_by_id: dict[str, dict] = {}
        nodes_by_id[str(rule.element_id)] = node_dict(rule, is_root=True)
        for n in neighbors:
            if n is None:
                continue
            nid = str(n.element_id)
            if nid not in nodes_by_id:
                nodes_by_id[nid] = node_dict(n)

        edges: list[dict] = []
        edge_keys = set()
        for rels in rel_lists:
            for rel in rels:
                k = (str(rel.start_node.element_id), str(rel.end_node.element_id), rel.type)
                if k in edge_keys:
                    continue
                edge_keys.add(k)
                edges.append({
                    "from":  str(rel.start_node.element_id),
                    "to":    str(rel.end_node.element_id),
                    "label": rel.type,
                })

    return JSONResponse({"nodes": list(nodes_by_id.values()), "edges": edges, "center": rule_id})


@router.get("/reg/citation")
def reg_citation(q: str) -> JSONResponse:
    """Resolve a citation string to the underlying regulator text.

    Tries an exact citation_label match first, then a regex match against
    citation_pattern (so "Rule A.34" hits "34"). Returns the top 5 matches
    with their source document for drill-down.
    """
    if not q or len(q) > 200:
        raise HTTPException(status_code=400, detail="bad query")
    like_q = f"%{q}%"
    # Exact then permissive search
    rows = query(
        "SELECT s.section_id, s.document_id, s.citation_label, s.section_heading, "
        "       s.section_text, d.title, d.document_type, d.issuing_body, d.edition "
        "FROM INSURANCE_REGULATORY.BRONZE_REGDOCS.RAW_REG_SECTION s "
        "JOIN INSURANCE_REGULATORY.BRONZE_REGDOCS.RAW_REG_DOCUMENT d ON d.document_id = s.document_id "
        "WHERE LOWER(s.citation_label) = LOWER(%s) "
        "   OR s.citation_label ILIKE %s "
        "   OR s.section_heading ILIKE %s "
        "ORDER BY (CASE WHEN LOWER(s.citation_label) = LOWER(%s) THEN 0 ELSE 1 END), "
        "         s.document_id, s.seq "
        "LIMIT 5",
        (q, like_q, like_q, q),
    )
    return JSONResponse({"q": q, "matches": _jsonify(rows), "count": len(rows)})


@router.get("/reg/documents")
def reg_documents() -> JSONResponse:
    """List all loaded regulator-source documents."""
    rows = query(
        "SELECT document_id, document_type, title, issuing_body, edition, "
        "       TO_VARCHAR(effective_date, 'YYYY-MM-DD') AS effective_date, "
        "       word_count, page_count, "
        "       TO_VARCHAR(loaded_at, 'YYYY-MM-DD HH24:MI:SS') AS loaded_at "
        "FROM INSURANCE_REGULATORY.BRONZE_REGDOCS.RAW_REG_DOCUMENT "
        "ORDER BY document_type, effective_date DESC"
    )
    return JSONResponse({"documents": _jsonify(rows), "count": len(rows)})


@router.get("/anomalies")
def anomalies_list(filing: str | None = None) -> JSONResponse:
    """List anomalies for a filing (or all). Powers the Anomalies popout."""
    where = "WHERE filing_batch_id = %s" if filing else ""
    rows = query(
        "SELECT anomaly_type, severity, territory_zip, cause_of_loss_code, "
        "       current_month_value, rolling_12m_mean, rolling_12m_stddev, "
        "       std_deviations_from_mean, anomaly_description, filing_batch_id, "
        "       source_records, "
        "       TO_VARCHAR(flagged_timestamp, 'YYYY-MM-DD HH24:MI:SS') AS flagged_at "
        f"FROM INSURANCE_REGULATORY.GOLD.TSPR_ANOMALY_FLAGS {where} "
        "ORDER BY anomaly_type, territory_zip",
        (filing,) if filing else None,
    )
    return JSONResponse({"filing": filing, "anomalies": _jsonify(rows), "count": len(rows)})


@router.post("/anomalies/detect")
def anomalies_detect() -> JSONResponse:
    """Re-run anomaly detection (TRUNCATEs + re-detects)."""
    result = _run(["uv", "run", "python", "-m", "scripts.detect_anomalies", "--month", "2026-03"])
    return JSONResponse(result)


@router.post("/bulletin/apply")
def bulletin_apply() -> JSONResponse:
    """Apply the credit-score bulletin: materialize → version-bump → reload reference."""
    _invalidate_validate()  # canon changes → drop cached validation
    steps = []
    if backend_name() == "snowflake":
        # KG-driven canon pipeline: materialize → version-bump → reference → load.
        steps.append({"step": "materialize", **_run(
            ["uv", "run", "python", "-m", "scripts.apply_credit_score_bulletin"]
        )})
        if not steps[-1]["ok"]:
            return JSONResponse({"ok": False, "steps": steps}, status_code=500)

        steps.append({"step": "version_bump", **_run([
            "uv", "run", "python", "-m", "scripts.apply_bulletin",
            "--bulletin", BULLETIN_OVERRIDE_NAME,
        ])})
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
    else:
        # Portable engines (duckdb / databricks): the A.34 rule is canon-flag
        # driven, so clearing L's companion requirement makes L-alone valid on
        # the next validation — same observable effect as the KG pipeline, one
        # UPDATE through the seam. No Snowflake/Neo4j/snow-CLI dependency.
        try:
            query(
                "UPDATE INSURANCE_REGULATORY.REFERENCE.TSPR_REASON_CODE_MAP "
                "SET credit_score_companion_required = FALSE WHERE tspr_reason_code = 'L'"
            )
            steps.append({"step": "flip_canon", "ok": True})
        except Exception as e:
            steps.append({"step": "flip_canon", "ok": False, "error": str(e)[:200]})
            return JSONResponse({"ok": False, "steps": steps}, status_code=500)

    ok = all(s["ok"] for s in steps)
    # Audit the bulletin apply against every filing (it affects the canon, which is shared).
    # Re-run validation immediately so the UI sees the flip without a manual refresh,
    # and so any exception closed by the bulletin gets resolution_action='bulletin'.
    deltas: dict[str, dict] = {}
    if ok:
        for f in _live_filings():
            _record_action(
                f["id"], "bulletin_apply",
                actor="D. Reyes",
                target_rule=BULLETIN_OVERRIDE_NAME,
                summary=f"Applied bulletin {BULLETIN_PATH.stem}",
                details={"bulletin": BULLETIN_PATH.stem, "steps": [s["step"] for s in steps]},
            )
            # Snapshot the open exceptions for this filing before re-validation
            try:
                pre_rows = query(
                    "SELECT policy_number, rule_number FROM INSURANCE_REGULATORY.GOLD.FILING_EXCEPTION "
                    "WHERE filing_batch_id = %s AND resolution_status = 'open'",
                    (f["id"],),
                )
                pre_keys = {(r.get("policy_number") or r.get("POLICY_NUMBER"),
                             r.get("rule_number") or r.get("RULE_NUMBER")) for r in pre_rows}
            except Exception:
                pre_keys = set()

            # Re-run validation, tagging any newly-closed exception as resolved-by-bulletin
            try:
                result = validate_cancellations(filing=f["id"])
                # validate_cancellations now returns JSONResponse — re-fetch the body via direct
                # call to the internal recorder so we can tag resolutions.
                # Easier path: do a second pass directly on the freshly-closed exceptions.
                post_rows = query(
                    "SELECT policy_number, rule_number FROM INSURANCE_REGULATORY.GOLD.FILING_EXCEPTION "
                    "WHERE filing_batch_id = %s AND resolution_status = 'open'",
                    (f["id"],),
                )
                post_keys = {(r.get("policy_number") or r.get("POLICY_NUMBER"),
                              r.get("rule_number") or r.get("RULE_NUMBER")) for r in post_rows}
                closed = pre_keys - post_keys
                # Mark every closed-this-turn exception as bulletin-resolved
                for policy, rule_num in closed:
                    if policy is None and rule_num is None:
                        continue
                    query(
                        "UPDATE INSURANCE_REGULATORY.GOLD.FILING_EXCEPTION "
                        "SET resolution_action = 'bulletin' "
                        "WHERE filing_batch_id = %s "
                        "  AND policy_number = %s "
                        "  AND rule_number = %s "
                        "  AND resolution_status = 'fixed'",
                        (f["id"], policy, rule_num),
                    )
                deltas[f["id"]] = {
                    "closed_count": len(closed),
                    "closed": [{"policy_number": p, "rule_number": r} for p, r in sorted(closed, key=lambda x: (x[0] or "", x[1] or ""))],
                }
            except Exception as e:
                deltas[f["id"]] = {"error": str(e)[:200], "closed_count": 0, "closed": []}

    return JSONResponse({"ok": ok, "steps": steps, "deltas": deltas})


@router.post("/bulletin/reset")
def bulletin_reset() -> JSONResponse:
    """Roll back the bulletin and reload baseline reference."""
    _invalidate_validate()  # canon changes → drop cached validation
    steps = []
    if backend_name() == "snowflake":
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
    else:
        # Portable engines: restore L's companion requirement → A.34 re-flags
        # L-alone on the next validation.
        try:
            query(
                "UPDATE INSURANCE_REGULATORY.REFERENCE.TSPR_REASON_CODE_MAP "
                "SET credit_score_companion_required = TRUE WHERE tspr_reason_code = 'L'"
            )
            steps.append({"step": "reset_canon", "ok": True})
        except Exception as e:
            steps.append({"step": "reset_canon", "ok": False, "error": str(e)[:200]})
            return JSONResponse({"ok": False, "steps": steps}, status_code=500)

    ok = all(s["ok"] for s in steps)
    if ok:
        for f in _live_filings():
            _record_action(
                f["id"], "bulletin_reset",
                actor="D. Reyes",
                target_rule=BULLETIN_OVERRIDE_NAME,
                summary=f"Reset bulletin {BULLETIN_PATH.stem} (canon back to baseline)",
            )

    return JSONResponse({"ok": ok, "steps": steps})
