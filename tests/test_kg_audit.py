"""Smoke + behavioral tests for the KG audit-log mechanism (Phase 1.1).

Requires Neo4j reachability — skipped if the driver can't connect.
"""

from __future__ import annotations

import json

import pytest


def _neo4j_available() -> bool:
    try:
        from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
        with Neo4jGREAdapter() as gre:
            gre.count_nodes()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _neo4j_available(),
    reason="Neo4j unreachable — skipping KG audit tests",
)


def test_kg_audit_entry_class_carries_required_fields():
    """Schema-level: KGAuditEntry has the right fields."""
    from packages.core.nodes import KGAuditEntry
    from packages.core.enums import KGAuditAction

    e = KGAuditEntry(
        name="test",
        action=KGAuditAction.MANUAL_EDIT,
        summary="hello",
        actor="pytest",
    )
    assert e.type == "KGAuditEntry"
    assert e.action == KGAuditAction.MANUAL_EDIT
    assert e.actor == "pytest"
    assert e.affected_count == 0
    assert e.version == 1


def test_record_audit_entry_creates_node_and_edges():
    """record_audit_entry writes a KGAuditEntry + MUTATED_BY edges to every target."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
    from packages.core.enums import KGAuditAction
    from uuid import UUID

    with Neo4jGREAdapter() as gre:
        # Find a real Rule node to link. Skip cleanly if the KG was wiped
        # by an earlier destructive test in this session (test_materialization
        # / test_neo4j_adapter both call wipe_all). The conftest session hook
        # re-seeds at session-end, so the dev env stays clean.
        with gre.driver.session(database=gre.database) as s:
            # Filter to proper-UUID Rules (length 36, hyphen-formatted).
            # migrate_kg_validation_rules creates one Rule with a hand-crafted
            # id like "<uuid>-validity" that isn't a real UUID; skip it.
            row = s.run(
                "MATCH (r:Rule) WHERE size(r.id) = 36 "
                "RETURN r.id AS id LIMIT 1"
            ).single()
            if not row:
                pytest.skip("KG empty — destructive test ran earlier in session")
            target_id = UUID(row["id"])

        audit_id = gre.record_audit_entry(
            action=KGAuditAction.MANUAL_EDIT,
            summary="pytest: KG audit smoke test",
            actor="pytest-runner",
            affected_node_ids=[target_id],
            details_json=json.dumps({"test": "kg_audit"}),
        )
        assert isinstance(audit_id, UUID)

        # Verify the audit node exists with the right fields
        with gre.driver.session(database=gre.database) as s:
            r = s.run(
                """
                MATCH (a:KGAuditEntry {id: $aid})
                RETURN a.action AS action, a.actor AS actor, a.summary AS summary, a.affected_count AS n
                """,
                aid=str(audit_id),
            ).single()
            assert r is not None
            assert r["action"] == "manual_edit"
            assert r["actor"] == "pytest-runner"
            assert "pytest" in r["summary"]
            assert r["n"] == 1

            # Verify the MUTATED_BY edge
            edge = s.run(
                """
                MATCH (n:Rule {id: $rid})-[:MUTATED_BY]->(a:KGAuditEntry {id: $aid})
                RETURN 1 AS ok
                """,
                rid=str(target_id),
                aid=str(audit_id),
            ).single()
            assert edge is not None, "MUTATED_BY edge missing"

            # Cleanup: remove the test audit + its edge
            s.run("MATCH (a:KGAuditEntry {id: $aid}) DETACH DELETE a", aid=str(audit_id))


def test_record_audit_entry_with_no_targets():
    """An audit entry with zero affected nodes is still valid (system-level events)."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
    from packages.core.enums import KGAuditAction

    with Neo4jGREAdapter() as gre:
        audit_id = gre.record_audit_entry(
            action=KGAuditAction.REBUILD,
            summary="pytest: full rebuild marker",
            actor="pytest-runner",
        )
        # Verify and clean up
        with gre.driver.session(database=gre.database) as s:
            r = s.run(
                "MATCH (a:KGAuditEntry {id: $aid}) RETURN a.affected_count AS n",
                aid=str(audit_id),
            ).single()
            assert r["n"] == 0
            s.run("MATCH (a:KGAuditEntry {id: $aid}) DETACH DELETE a", aid=str(audit_id))


def test_kg_audit_action_enum_is_closed():
    """The action enum is the closed vocabulary — adding values requires deliberate code change."""
    from packages.core.enums import KGAuditAction
    expected = {
        "node_create", "node_supersede", "node_delete",
        "bulletin_apply", "bulletin_reset",
        "extraction", "backfill", "rebuild", "manual_edit",
    }
    actual = {a.value for a in KGAuditAction}
    assert actual == expected, f"unexpected audit actions: {actual ^ expected}"
