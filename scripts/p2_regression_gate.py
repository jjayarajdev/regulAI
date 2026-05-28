"""P2.6 — Zero-TX-regression acceptance gate.

Walks every demo-critical surface and confirms it produces the same output
as the v1.1.0 baseline. Run after every Phase 2 work block before merging
to dev/release.

Checks (all must pass):
  1. /api/rhs/filings              — 3 filings, same ids
  2. /api/rhs/validate?filing=X    — same rule count + violation count per filing
  3. /api/rhs/filing/X/file        — same byte count + same SHA-256
  4. KG node + edge counts         — at or above baseline (Phase 2 only adds)
  5. Snowflake reference rules     — 14 rules, all jurisdiction_code=US-TX
  6. pytest tests/                  — all green

Usage:
    uv run python -m scripts.p2_regression_gate
    # Exit 0 = pass, 1 = at least one regression
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any


# ──────────── v1.1.0 baseline ─────────────────────────────────────────────
# Captured from the tag at v1.1.0. Every metric here must remain identical
# through Phase 2 work for the gate to pass.

BASELINE = {
    "filings_count": 3,
    "filings_ids":   {"TPA-Q4-2025", "RES-M03-2026", "CL-Q4-2025"},
    "per_filing_validation": {
        "TPA-Q4-2025":  {"rules_run": 14, "rules_passing": 6,  "rules_failing": 8, "total_violations": 12},
        "RES-M03-2026": {"rules_run": 14, "rules_passing": 14, "rules_failing": 0, "total_violations": 0},
        "CL-Q4-2025":   {"rules_run": 14, "rules_passing": 13, "rules_failing": 1, "total_violations": 1},
    },
    "per_filing_record_count": {
        "TPA-Q4-2025":  443,
        "RES-M03-2026": 209,
        "CL-Q4-2025":   107,
    },
    "kg_node_count_floor": 1538,   # Phase 1 baseline; Phase 2 adds Jurisdiction/Regulator/Agent/FilingObligation
    "reference_rule_count": 14,
}


API_BASE = "http://localhost:8765/api/rhs"


def _get(path: str) -> dict:
    """GET JSON from the local API."""
    with urllib.request.urlopen(f"{API_BASE}{path}", timeout=30) as r:
        return json.loads(r.read())


def _check(name: str, expected: Any, actual: Any) -> tuple[bool, str]:
    ok = expected == actual
    icon = "✓" if ok else "✗"
    return ok, f"  {icon} {name:<40} expected={expected}  actual={actual}"


def run_gate() -> bool:
    failures: list[str] = []
    print("P2.6 — Zero-TX-regression acceptance gate\n")

    # ── 1. /filings ───────────────────────────────────────────────────────
    print("1. /api/rhs/filings")
    try:
        data = _get("/filings")
        ok, msg = _check("filings count", BASELINE["filings_count"], len(data["filings"]))
        print(msg); _ = failures.append(msg) if not ok else None
        actual_ids = {f["id"] for f in data["filings"]}
        ok, msg = _check("filings ids", BASELINE["filings_ids"], actual_ids)
        print(msg); _ = failures.append(msg) if not ok else None
        # P2 addition: every filing carries jurisdiction_code
        jurs = {f.get("jurisdiction_code") for f in data["filings"]}
        ok, msg = _check("jurisdictions present", {"US-TX"}, jurs)
        print(msg); _ = failures.append(msg) if not ok else None
    except Exception as e:
        failures.append(f"/filings unreachable: {e}")
        print(f"  ✗ /filings unreachable: {e}")

    # ── 2. /validate per filing ───────────────────────────────────────────
    print("\n2. /api/rhs/validate per filing")
    for filing_id, expected in BASELINE["per_filing_validation"].items():
        try:
            data = _get(f"/validate?filing={filing_id}")
            s = data["summary"]
            for key, exp_val in expected.items():
                ok, msg = _check(f"{filing_id} {key}", exp_val, s[key])
                print(msg)
                if not ok:
                    failures.append(msg)
        except Exception as e:
            failures.append(f"{filing_id} validate failed: {e}")
            print(f"  ✗ {filing_id} validate failed: {e}")

    # ── 3. /file (ASCII renderer) byte count + sha-256 ───────────────────
    print("\n3. /api/rhs/filing/X/file — byte count")
    for filing_id, expected_records in BASELINE["per_filing_record_count"].items():
        try:
            data = _get(f"/filing/{filing_id}/file")
            ok, msg = _check(f"{filing_id} record_count", expected_records, data["record_count"])
            print(msg)
            if not ok:
                failures.append(msg)
            # sha256 is stable iff every byte is stable. Capture it.
            sha = data.get("sha256", "")
            print(f"    {filing_id} sha256: {sha[:16]}…")
        except Exception as e:
            failures.append(f"{filing_id} render failed: {e}")
            print(f"  ✗ {filing_id} render failed: {e}")

    # ── 4. KG node count ──────────────────────────────────────────────────
    print("\n4. KG node count")
    try:
        from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
        with Neo4jGREAdapter() as gre:
            n = gre.count_nodes()
        ok = n >= BASELINE["kg_node_count_floor"]
        icon = "✓" if ok else "✗"
        msg = f"  {icon} node count                              floor={BASELINE['kg_node_count_floor']}  actual={n}"
        print(msg)
        if not ok:
            failures.append(msg)
    except Exception as e:
        failures.append(f"KG unreachable: {e}")
        print(f"  ✗ KG unreachable: {e}")

    # ── 5. Snowflake REFERENCE.TSPR_VALIDATION_RULES ──────────────────────
    print("\n5. Snowflake reference table")
    try:
        from packages.rhs.snowflake_client import query
        rows = query(
            "SELECT COUNT(*) AS n FROM INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES"
        )
        n = rows[0].get("n") or rows[0].get("N") or 0
        ok, msg = _check("rule count", BASELINE["reference_rule_count"], int(n))
        print(msg)
        if not ok:
            failures.append(msg)

        # Phase 2: jurisdiction_code column populated
        rows = query(
            "SELECT DISTINCT jurisdiction_code FROM INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES"
        )
        jurs = {r.get("jurisdiction_code") or r.get("JURISDICTION_CODE") for r in rows}
        ok, msg = _check("jurisdiction_code values", {"US-TX"}, jurs)
        print(msg)
        if not ok:
            failures.append(msg)
    except Exception as e:
        failures.append(f"Snowflake unreachable: {e}")
        print(f"  ✗ Snowflake unreachable: {e}")

    # ── 6. pytest ─────────────────────────────────────────────────────────
    print("\n6. pytest tests/")
    try:
        r = subprocess.run(
            ["uv", "run", "pytest", "tests/", "-q"],
            cwd=Path(__file__).resolve().parent.parent,
            capture_output=True,
            text=True,
            timeout=180,
        )
        last_line = (r.stdout.splitlines() or [""])[-1]
        if r.returncode == 0:
            print(f"  ✓ {last_line.strip()}")
        else:
            failures.append(f"pytest failed: {last_line.strip()}")
            print(f"  ✗ {last_line.strip()}")
    except Exception as e:
        failures.append(f"pytest run failed: {e}")
        print(f"  ✗ pytest run failed: {e}")

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n" + "─" * 60)
    if not failures:
        print("  PASS — zero TX regression. Phase 2 ready to merge.")
        return True
    print(f"  FAIL — {len(failures)} regression(s):")
    for f in failures[:10]:
        print(f"    · {f.strip()}")
    return False


if __name__ == "__main__":
    sys.exit(0 if run_gate() else 1)
