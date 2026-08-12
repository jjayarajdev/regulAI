"""Seal → send → ack journey over HTTP, on the DuckDB backend.

Uses the FL FHCF filing (FHCF-A-2026); its submission file renders from
GOLD.FHCF_EXPOSURE_RECORDS, which the fixture rebuilds from the FL Guidewire
Bronze rows via the scripts.run_fhcf Silver/Gold transforms.
The KG filings registry is monkeypatched to the in-code FILINGS fallback so
the test doesn't depend on Neo4j being up or seeded.

Covers:
  - GET  /filing/{id}/file returns the FHCF CSV package (feature 2e)
  - GET  /validate?filing=FHCF-A-2026 runs the 10 US-FL rules (feature 2d)
  - POST /filing/{id}/send RBAC (cco only) + sealed-first gate (409)
  - the full journey: approve×3 → seal → send → ack → /submission
    with outbox .eml + sftp drop + read-only archive + FILING_DISPATCH row
    + FILING_BATCH status transitions (submitted → sent → acked)

Run:  REGULAI_DB=duckdb uv run pytest tests/test_filing_send.py -q
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

os.environ.setdefault("REGULAI_DB", "duckdb")

import pytest

FILING = "FHCF-A-2026"
API = "/api/rhs"

# X-Actor personas (dev-fallback identity in api.rhs_demo.current_user)
ANALYST = {"X-Actor": "u-okonkwo"}
ACTUARY = {"X-Actor": "u-reyes"}
CCO = {"X-Actor": "u-park"}


def _duckdb_ready() -> bool:
    try:
        from packages.rhs.db import backend_name, query
        if backend_name() != "duckdb":
            return False
        query("SELECT 1 AS one")
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _duckdb_ready(),
    reason="DuckDB backend unavailable (set REGULAI_DB=duckdb and run scripts.seed_duckdb)",
)


@pytest.fixture(scope="module")
def client():
    """TestClient with the filings registry pinned to the Python fallback."""
    from fastapi.testclient import TestClient

    from api import rhs_demo
    from api.main import app
    from packages.rhs.filings import FILINGS

    original = rhs_demo._load_filings_from_kg
    rhs_demo._load_filings_from_kg = lambda: copy.deepcopy(FILINGS)
    try:
        yield TestClient(app)
    finally:
        rhs_demo._load_filings_from_kg = original


@pytest.fixture()
def fresh_filing_state():
    """Reseed FL data + reset the FHCF filing to a clean 'validated' batch."""
    from packages.rhs.db import query
    from scripts.run_fhcf import gold_fhcf, silver_fhcf
    from scripts.seed_fl_fhcf import _load_fl_rules, _seed_bronze, _seed_filing_batch

    _seed_bronze()
    silver_fhcf()
    gold_fhcf()
    _load_fl_rules()
    for table in ("FILING_BATCH", "FILING_SUBMISSION", "FILING_EXCEPTION"):
        query(f"DELETE FROM INSURANCE_REGULATORY.GOLD.{table} WHERE filing_batch_id = %s",
              (FILING,))
    try:
        query("DELETE FROM INSURANCE_REGULATORY.GOLD.FILING_DISPATCH "
              "WHERE filing_batch_id = %s", (FILING,))
    except Exception:
        pass  # table only exists after the first send
    _seed_filing_batch()


def test_fhcf_filing_file_is_csv(client, fresh_filing_state):
    r = client.get(f"{API}/filing/{FILING}/file")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["file_name"].endswith(".csv")
    assert body["record_count"] == 15  # the 15 FL Guidewire policies, via Gold
    assert body["warning"] is None
    assert body["header"].startswith("insurer_naic,")
    assert body["footer"].startswith("# sha256=")
    assert len(body["sha256"]) == 64


def test_validate_runs_fl_rules(client, fresh_filing_state):
    from api import rhs_demo
    rhs_demo._invalidate_validate()
    r = client.get(f"{API}/validate", params={"filing": FILING})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summary"]["rules_run"] == 10
    flagged = {v["policy_number"] for v in body["violations"]}
    # The 5 dirty FL policies (see scripts/seed_fl_fhcf.py data design) —
    # violations now come from GOLD.FHCF_EXPOSURE_RECORDS, post-transform.
    assert flagged == {f"POL-FL-{i:04d}" for i in range(1011, 1016)}
    assert all(v["jurisdiction_code"] == "US-FL" for v in body["violations"])


def test_send_requires_cco_and_sealed_state(client, fresh_filing_state):
    # analyst lacks the 'send' grant
    r = client.post(f"{API}/filing/{FILING}/send", headers=ANALYST, json={})
    assert r.status_code == 403
    # cco, but the filing is only 'validated' — must seal first
    r = client.post(f"{API}/filing/{FILING}/send", headers=CCO, json={})
    assert r.status_code == 409
    assert "seal" in r.json()["detail"].lower()


def test_full_seal_send_ack_journey(client, fresh_filing_state):
    from packages.rhs.db import query

    def batch_status() -> str:
        rows = query(
            "SELECT status FROM INSURANCE_REGULATORY.GOLD.FILING_BATCH "
            "WHERE filing_batch_id = %s", (FILING,))
        return rows[0]["status"]

    # ── sign-off chain ──────────────────────────────────────────────
    for headers, role in ((ANALYST, "analyst"), (ACTUARY, "actuary"), (CCO, "officer")):
        r = client.post(f"{API}/filing/{FILING}/approve", headers=headers,
                        json={"role": role})
        assert r.status_code == 200, f"{role}: {r.text}"
    assert batch_status() == "officer_approved"

    # ── seal ────────────────────────────────────────────────────────
    r = client.get(f"{API}/filing/{FILING}/file", params={"persist": "true"},
                   headers=CCO)
    assert r.status_code == 200, r.text
    sealed = r.json()
    assert sealed["persisted"] is True
    submission_id = sealed["submission_id"]
    assert batch_status() == "submitted"

    # cannot ACK before sending
    r = client.post(f"{API}/filing/{FILING}/ack", headers=CCO)
    assert r.status_code == 409

    # ── send ────────────────────────────────────────────────────────
    r = client.post(f"{API}/filing/{FILING}/send", headers=CCO, json={})
    assert r.status_code == 200, r.text
    sent = r.json()
    assert sent["status"] == "sent"
    assert sent["email"]["to"] == ["datacall@fhcf.example"]
    assert sent["email"]["transport"] in ("outbox", "smtp")
    assert sent["email"]["message_id"].endswith("@regulai.demo>")
    assert sent["archive"]["sha256"] == sealed["sha256"]
    assert batch_status() == "sent"

    # outbox .eml exists and is a real RFC-5322 message with the attachment
    eml = Path(sent["email"]["eml_path"])
    assert eml.exists()
    raw = eml.read_text(encoding="utf-8", errors="replace")
    assert sealed["file_name"] in raw
    assert "From: J. Park <j.park@regulai.demo>" in raw

    # SFTP dropbox stub + read-only archive with manifest
    assert Path(sent["sftp_path"]).exists()
    archive_dir = Path(sent["archive"]["path"])
    assert (archive_dir / sealed["file_name"]).exists()
    manifest = json.loads((archive_dir / "manifest.json").read_text())
    assert manifest["sha256"] == sealed["sha256"]
    assert manifest["record_counts"]["total"] == sealed["record_count"]
    assert (archive_dir / "manifest.json").stat().st_mode & 0o777 == 0o444

    # FILING_DISPATCH row landed
    rows = query(
        "SELECT * FROM INSURANCE_REGULATORY.GOLD.FILING_DISPATCH "
        "WHERE filing_batch_id = %s ORDER BY sent_at DESC", (FILING,))
    assert rows and rows[0]["submission_id"] == submission_id
    assert rows[0]["message_id"] == sent["email"]["message_id"]

    # ── ack ─────────────────────────────────────────────────────────
    r = client.post(f"{API}/filing/{FILING}/ack", headers=CCO)
    assert r.status_code == 200, r.text
    acked = r.json()
    assert acked["receipt_id"].startswith("FHCF-ACK-")
    assert acked["new_state"] == "acked"
    assert acked["ack_eml_path"] and Path(acked["ack_eml_path"]).exists()
    ack_raw = Path(acked["ack_eml_path"]).read_text(encoding="utf-8", errors="replace")
    assert "In-Reply-To" in ack_raw and acked["receipt_id"] in ack_raw
    assert batch_status() == "acked"

    # ── journey endpoint ────────────────────────────────────────────
    r = client.get(f"{API}/filing/{FILING}/submission", headers=CCO)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "acked"
    assert j["submission"]["submission_id"] == submission_id
    assert j["email"]["message_id"] == sent["email"]["message_id"]
    assert j["email"]["attachment"]["name"] == sealed["file_name"]
    assert j["ack"]["receipt"] == acked["receipt_id"]
    assert j["archive"]["sha256"] == sealed["sha256"]


def test_submission_journey_never_500s_on_fresh_filing(client, fresh_filing_state):
    """Before any seal/send activity every section is null but the endpoint works."""
    r = client.get(f"{API}/filing/{FILING}/submission")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "validated"
    assert j["submission"] is None
    assert j["email"] is None
    assert j["ack"] is None
    assert j["archive"] is None
