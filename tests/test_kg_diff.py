"""Tests for the KG diff endpoint (Phase 1.4).

Requires Neo4j + the API. Each test creates a controlled mutation, calls
the diff endpoint, asserts the response shape and content, and cleans up.
"""

from __future__ import annotations

import datetime as dt
import json
from uuid import UUID, uuid4

import pytest


def _stack_available() -> bool:
    try:
        from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
        with Neo4jGREAdapter() as gre:
            gre.count_nodes()
        from fastapi.testclient import TestClient
        from api.main import app
        TestClient(app)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _stack_available(),
    reason="Neo4j or FastAPI app unreachable — skipping KG diff tests",
)


def test_diff_requires_either_since_or_audit_id():
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    r = client.get("/api/rhs/kg/diff")
    assert r.status_code == 400, r.text


def test_diff_rejects_both_params():
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    r = client.get("/api/rhs/kg/diff?since=2026-01-01T00:00:00&audit_id=abc")
    assert r.status_code == 400, r.text


def test_diff_by_audit_id_returns_affected_nodes_as_added():
    """Create an audit entry that touches one node; verify the diff returns
    it in the added_nodes bucket (created_at = the audit timestamp = cutoff)."""
    from fastapi.testclient import TestClient
    from api.main import app
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
    from packages.core.enums import KGAuditAction

    with Neo4jGREAdapter() as gre:
        # Find or create a target node
        with gre.driver.session(database=gre.database) as s:
            # Filter to proper-UUID Rules (skip hand-crafted ids from
            # migrate_kg_validation_rules — see test_kg_audit for the same fix).
            row = s.run(
                "MATCH (r:Rule) WHERE size(r.id) = 36 "
                "RETURN r.id AS id LIMIT 1"
            ).single()
            if not row:
                pytest.skip("KG empty — skipping")
            target_id = UUID(row["id"])

        audit_id = gre.record_audit_entry(
            action=KGAuditAction.MANUAL_EDIT,
            summary="pytest: diff endpoint test mutation",
            actor="pytest",
            affected_node_ids=[target_id],
            details_json=json.dumps({"test": "diff"}),
        )

    try:
        client = TestClient(app)
        r = client.get(f"/api/rhs/kg/diff?audit_id={audit_id}")
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["scope"] == "audit"
        # 1 audit entry, 1 affected node
        assert len(body["audit_entries"]) == 1
        ids = {n["id"] for n in body["added_nodes"] + body["modified_nodes"] + body["superseded_nodes"]}
        assert str(target_id) in ids, f"target node missing from diff; got buckets ids={ids}"
    finally:
        # Cleanup
        with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
            s.run("MATCH (a:KGAuditEntry {id: $aid}) DETACH DELETE a", aid=str(audit_id))


def test_diff_by_since_returns_recent_audit_entries():
    """Audit entries written after `since` are returned in audit_entries."""
    from fastapi.testclient import TestClient
    from api.main import app
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
    from packages.core.enums import KGAuditAction

    cutoff = dt.datetime.now(dt.UTC).isoformat()

    with Neo4jGREAdapter() as gre:
        audit_id = gre.record_audit_entry(
            action=KGAuditAction.MANUAL_EDIT,
            summary="pytest: diff since-mode test",
            actor="pytest",
            affected_node_ids=[],
        )

    try:
        client = TestClient(app)
        r = client.get(f"/api/rhs/kg/diff?since={cutoff}")
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["scope"] == "since"
        audit_ids = {a["id"] for a in body["audit_entries"]}
        assert str(audit_id) in audit_ids, "our test audit entry missing from since-mode response"
    finally:
        with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
            s.run("MATCH (a:KGAuditEntry {id: $aid}) DETACH DELETE a", aid=str(audit_id))


def test_diff_unknown_audit_id_returns_404():
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    r = client.get(f"/api/rhs/kg/diff?audit_id={uuid4()}")
    assert r.status_code == 404
