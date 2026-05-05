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

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from packages.rhs.snowflake_client import query


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
