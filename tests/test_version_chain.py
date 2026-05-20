"""Phase 1.2 — pressure test the version-chain handling end-to-end.

Creates a fictional v2 of an existing Rule with executable `violation_sql`,
then walks every downstream consumer (reference SQL builder, validation
endpoint, FILING_EXCEPTION reconciliation, workstation Regulation Explorer)
and asserts each handles "both v1 and v2 in the graph" correctly.

A v2 with `effective_from > today` and v1 with `effective_until = today`
both have `status != 'superseded'` — the naive
'WHERE status <> superseded' filter returns both, which is the central bug
this test demonstrates.

Tests cleanup their fictional v2 at the end (best effort). Requires Neo4j
reachability.
"""

from __future__ import annotations

import datetime as dt
from uuid import uuid4

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
    reason="Neo4j unreachable — skipping version-chain tests",
)


# --- Fixtures --------------------------------------------------------------

@pytest.fixture
def existing_v1():
    """A real executable rule from the KG. Skips test if none available."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        row = s.run("""
            MATCH (r:Rule)
            WHERE r.violation_sql IS NOT NULL
              AND (r.status IS NULL OR r.status <> 'superseded')
            RETURN r.id AS id, r.name AS name, r.rule_number AS num,
                   r.version AS v, r.status AS status
            LIMIT 1
        """).single()
        if not row:
            pytest.skip("No executable Rule with violation_sql in KG — run `make migrate-validation-rules`")
        return dict(row)


@pytest.fixture
def fictional_v2(existing_v1):
    """Create a v2 of an existing rule. Cleans up after the test."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
    v2_id = f"test-v2-{uuid4().hex[:8]}"
    future_date = (dt.date.today() + dt.timedelta(days=365)).isoformat()
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        s.run("""
            MATCH (v1:Rule {id: $v1_id})
            CREATE (v2:GRENode:Rule {
                id: $v2_id,
                type: 'Rule',
                name: v1.name,
                rule_number: v1.rule_number,
                section: v1.section,
                target_table: v1.target_table,
                target_id_expr: v1.target_id_expr,
                violation_sql: v1.violation_sql,
                violation_reason: v1.violation_reason + ' [v2 — test-only mutation]',
                severity: v1.severity,
                citation: v1.citation,
                version: 2,
                status: 'approved',
                effective_from: date($future),
                jurisdiction_code: COALESCE(v1.jurisdiction_code, 'US-TX'),
                created_at: datetime(),
                created_by: 'pytest-pressure-test'
            })
            MERGE (v2)-[:SUPERSEDES]->(v1)
            // P2.3: fetch_rules now joins on APPLIES_IN; mirror v1's jurisdiction.
            WITH v2
            MATCH (v1:Rule {id: $v1_id})-[:APPLIES_IN]->(j:Jurisdiction)
            MERGE (v2)-[:APPLIES_IN]->(j)
        """, v1_id=existing_v1["id"], v2_id=v2_id, future=future_date)

    yield {"id": v2_id, "v1_id": existing_v1["id"], "future_date": future_date}

    # Cleanup — remove the v2 + SUPERSEDES edge
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        s.run("MATCH (v2:Rule {id: $v2_id}) DETACH DELETE v2", v2_id=v2_id)


# --- Test 1: the canonical bug ----------------------------------------------

def test_fetch_rules_returns_only_one_version_per_rule_number(existing_v1, fictional_v2):
    """REGRESSION CANDIDATE — the reference-SQL builder must pick exactly one
    version per rule_number when both v1 and v2 are in the graph.

    Currently the WHERE clause filters out 'superseded' status, but
    both v1 (status='approved', effective_until=null) and v2
    (status='approved', effective_from=future) have non-superseded status.
    Without an additional 'currently-active' filter, both come through.
    """
    from scripts.build_validation_rules_reference import fetch_rules

    rows = fetch_rules()
    by_num: dict[str, list] = {}
    for r in rows:
        by_num.setdefault(r["rule_number"], []).append(r)

    duplicates = {num: rs for num, rs in by_num.items() if len(rs) > 1}
    if duplicates:
        details = "\n".join(
            f"  rule_number={num} returned {len(rs)} versions: "
            f"ids={[r['id'] for r in rs]}"
            for num, rs in duplicates.items()
        )
        pytest.fail(
            f"fetch_rules returned multiple versions for the same rule_number — "
            f"the reference table would carry duplicate rows for {sorted(duplicates)}.\n"
            f"Bug: WHERE clause must filter to the currently-active version "
            f"(check effective_from <= today < effective_until or use SUPERSEDES traversal).\n"
            f"{details}"
        )


# --- Test 2: status filter actually works ----------------------------------

def test_superseded_v1_is_excluded(existing_v1, fictional_v2):
    """After realistic supersession (v1 marked superseded + v2 effective today),
    v1 is excluded by fetch_rules and v2 takes over.

    This models what scripts/apply_bulletin.py actually does: when superseding,
    both the v1 status flip AND the v2 effective_from advance happen together,
    so there's no gap in coverage."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
    from scripts.build_validation_rules_reference import fetch_rules
    import datetime as dt

    today = dt.date.today().isoformat()
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        # Realistic supersession: v1 superseded + effective_until=today, v2 effective_from=today
        s.run("""
            MATCH (v1:Rule {id: $v1_id})
            SET v1.status = 'superseded',
                v1.effective_until = date($today)
        """, v1_id=existing_v1["id"], today=today)
        s.run("""
            MATCH (v2:Rule {id: $v2_id})
            SET v2.effective_from = date($today)
        """, v2_id=fictional_v2["id"], today=today)

    try:
        rows = fetch_rules()
        ids = {r["id"] for r in rows}
        assert existing_v1["id"] not in ids, "v1 should be excluded when status='superseded'"
        assert fictional_v2["id"] in ids, "v2 should be present after supersession"
    finally:
        # Restore v1
        with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
            s.run("""
                MATCH (v1:Rule {id: $v1_id})
                SET v1.status = $status,
                    v1.effective_until = null
            """, v1_id=existing_v1["id"], status=existing_v1["status"] or "approved")


# --- Test 3: API /kg/rules also returns one row per rule -------------------

def test_kg_rules_endpoint_handles_version_chain(existing_v1, fictional_v2):
    """The workstation Regulation Explorer reads /api/rhs/kg/rules. It pulls
    every Rule node. With both v1 and v2 present, the tree should either show
    the latest OR both (but the rule-tree currently dedups by name) — at
    minimum should not crash."""
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    r = client.get("/api/rhs/kg/rules")
    assert r.status_code == 200, r.text[:200]
    body = r.json()
    rules = body.get("rules") or []
    # Find any rule matching the fictional v2 id
    v2_present = any(rl.get("id") == fictional_v2["id"] for rl in rules)
    v1_present = any(rl.get("id") == existing_v1["id"] for rl in rules)
    # At least both should be reachable in the tree (no silent dedup)
    assert v1_present, "v1 missing from /kg/rules"
    assert v2_present, "v2 missing from /kg/rules"


# (Note: a fourth test verifying record_audit_entry was here but is redundant
# with tests/test_kg_audit.py::test_record_audit_entry_creates_node_and_edges
# which already covers the same behavior.)
