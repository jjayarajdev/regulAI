"""P2.4 — FilingObligation as data tests.

Verifies the FILINGS Python list has been mirrored into KG FilingObligation
nodes, the load_filings() helper reads from KG with Python fallback, and
the /filings endpoint serves the KG-sourced view.
"""

from __future__ import annotations

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
    reason="Stack unreachable — skipping P2.4 tests",
)


def test_filing_obligations_exist_in_kg():
    """seed_filing_obligations creates one FilingObligation per legacy entry."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
    from packages.rhs.filings import FILINGS

    expected_codes = {f["id"] for f in FILINGS}
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        rows = list(s.run(
            "MATCH (fo:FilingObligation) RETURN fo.obligation_code AS code"
        ))
        kg_codes = {r["code"] for r in rows}
        missing = expected_codes - kg_codes
        assert not missing, f"Missing FilingObligation nodes for: {missing}. Run `make seed-filing-obligations`."


def test_each_filing_obligation_has_obligates_and_receives_edges():
    """Every FilingObligation links to a carrier (OBLIGATES) + an agent (RECEIVES_SUBMISSION)."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        r = s.run("""
            MATCH (fo:FilingObligation)
            OPTIONAL MATCH (fo)-[ob:OBLIGATES]->(o:Organization)
            OPTIONAL MATCH (fo)-[rec:RECEIVES_SUBMISSION]->(a:StatisticalAgent)
            RETURN fo.obligation_code AS code,
                   count(ob) AS obligates_n,
                   count(rec) AS receives_n
        """).data()
        for row in r:
            assert row["obligates_n"] >= 1, f"{row['code']} missing OBLIGATES edge"
            assert row["receives_n"] >= 1, f"{row['code']} missing RECEIVES_SUBMISSION edge"


def test_load_filings_prefers_kg():
    """load_filings() returns the KG-sourced list, not the in-file fallback."""
    from packages.rhs.filings import load_filings, FILINGS

    live = load_filings()
    assert len(live) == len(FILINGS)
    live_codes = {f["id"] for f in live}
    py_codes = {f["id"] for f in FILINGS}
    assert live_codes == py_codes

    # The KG row has a jurisdiction_code; the legacy Python entry doesn't.
    tpa = next(f for f in live if f["id"] == "TPA-Q4-2025")
    assert tpa.get("jurisdiction_code") == "US-TX"


def test_filings_endpoint_serves_kg_view():
    """/api/rhs/filings reads from KG (via load_filings)."""
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    r = client.get("/api/rhs/filings")
    assert r.status_code == 200
    body = r.json()
    assert "filings" in body
    codes = {f["id"] for f in body["filings"]}
    assert codes == {"TPA-Q4-2025", "RES-M03-2026", "CL-Q4-2025"}
    # Each filing carries jurisdiction_code in the response
    for f in body["filings"]:
        assert f.get("jurisdiction_code") == "US-TX", (
            f"{f['id']} should be US-TX-scoped, got {f.get('jurisdiction_code')}"
        )


def test_filings_endpoint_preserves_policy_id_ranges():
    """Range tuples come back intact through the KG round-trip."""
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    r = client.get("/api/rhs/filings")
    tpa = next(f for f in r.json()["filings"] if f["id"] == "TPA-Q4-2025")
    # Expect [(2001,2019), (2100,2299)] — JSON delivers them as lists
    ranges = tpa["policy_id_ranges"]
    assert len(ranges) == 2
    assert tuple(ranges[0]) == (2001, 2019)
    assert tuple(ranges[1]) == (2100, 2299)


def test_seed_filing_obligations_idempotent():
    """Re-running seed yields zero new nodes/edges."""
    from scripts.seed_filing_obligations import seed

    summary = seed()
    assert summary["carriers_created"] == 0
    assert summary["obligations_created"] == 0
    assert summary["obligates_edges"] == 0
    assert summary["receives_edges"] == 0
