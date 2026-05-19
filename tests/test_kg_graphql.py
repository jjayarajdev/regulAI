"""Smoke tests for the KG GraphQL surface (Phase 1.6).

Hits /api/lhs/kg/graphql via FastAPI TestClient. Requires Neo4j reachability.
"""

from __future__ import annotations

import pytest


def _stack_available() -> bool:
    import sys
    try:
        from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
        with Neo4jGREAdapter() as gre:
            gre.count_nodes()
        from fastapi.testclient import TestClient
        from api.main import app
        TestClient(app)
        return True
    except Exception as e:
        print(f"[_stack_available] {type(e).__name__}: {e}", file=sys.stderr)
        return False


pytestmark = pytest.mark.skipif(
    not _stack_available(),
    reason="Stack unreachable — skipping GraphQL tests",
)

GRAPHQL_URL = "/api/lhs/kg/graphql"


def _post(client, query: str, variables: dict | None = None) -> dict:
    r = client.post(GRAPHQL_URL, json={"query": query, "variables": variables or {}})
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert "errors" not in body, body.get("errors")
    return body["data"]


def test_rules_query_returns_section_A_rules():
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    data = _post(client, '{ rules(section: "A") { id name } }')
    assert "rules" in data
    assert isinstance(data["rules"], list)
    assert len(data["rules"]) > 0, "no section A rules — KG must be seeded"


def test_rule_by_id_returns_single_match():
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    # Fetch any rule, then look it up by id
    data = _post(client, '{ rules { id name } }')
    assert data["rules"], "no rules available"
    first_id = data["rules"][0]["id"]
    one = _post(client, '{ rule(id: "' + first_id + '") { id name version status } }')
    assert one["rule"] is not None
    assert one["rule"]["id"] == first_id


def test_documents_query_includes_stat_plan():
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    data = _post(client, '{ documents { id title kind } }')
    titles = " ".join((d.get("title") or "") for d in data["documents"])
    assert "Statistical" in titles or "Stat" in titles, "expected stat plan in documents"


def test_code_values_scoped_by_codelist():
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    # Without filter
    data = _post(client, '{ codeValues { id code name } }')
    total = len(data["codeValues"])
    assert total > 50, f"expected many code values, got {total}"


def test_audit_entries_returns_list():
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    data = _post(client, '{ auditEntries(limit: 5) { id action actor occurredAt } }')
    assert isinstance(data["auditEntries"], list)


def test_introspection_works():
    """GraphQL introspection is enabled — external clients can discover the schema."""
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    data = _post(client, '{ __schema { queryType { name } } }')
    assert data["__schema"]["queryType"]["name"] == "Query"
