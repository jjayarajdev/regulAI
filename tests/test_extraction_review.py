"""Per-proposal extraction review — apply_review() + the review endpoints.

Pure-function tests plus FastAPI route tests with the registry path helpers
monkeypatched into tmp_path, so nothing touches materialized/ or Neo4j.
"""

import json
from pathlib import Path

import pytest

from packages.core.enums import CitationKind, NodeType, RelationshipType
from packages.lhs.materialization.review import (
    ExtractionReview,
    ProposalVerdict,
    ReviewOverrideError,
    apply_review,
    validate_overrides,
)
from packages.lhs.sentinel.schema import (
    CitationProposal,
    ProposedNode,
    ProposedRelationship,
    SentinelExtraction,
)


def _extraction() -> SentinelExtraction:
    """One document + two rules, cross-referenced, cited, related."""
    return SentinelExtraction(
        summary="Two rules from one stat plan section.",
        proposed_nodes=[
            ProposedNode(temp_id="doc1", type=NodeType.REGULATION_DOCUMENT,
                         name="TICO Stat Plan — Section A", confidence=0.99),
            ProposedNode(temp_id="rule_a", type=NodeType.RULE, name="Rule A-1",
                         confidence=0.95, section="A", rule_number=1,
                         document_temp_id="doc1"),
            ProposedNode(temp_id="rule_b", type=NodeType.RULE, name="Rule A-2",
                         confidence=0.62, section="A", rule_number=2,
                         document_temp_id="doc1"),
        ],
        proposed_relationships=[
            ProposedRelationship(type=RelationshipType.CITES,
                                 src_temp_id="rule_a", dst_temp_id="doc1"),
            ProposedRelationship(type=RelationshipType.CITES,
                                 src_temp_id="rule_b", dst_temp_id="doc1"),
        ],
        citations=[
            CitationProposal(node_temp_id="rule_a", char_start=0, char_end=40,
                             kind=CitationKind.DEFINES),
            CitationProposal(node_temp_id="rule_b", char_start=50, char_end=90,
                             kind=CitationKind.DEFINES),
            CitationProposal(node_temp_id="rule_a", char_start=100, char_end=140,
                             kind=CitationKind.REFERENCES),
        ],
        uncited_spans=[],
        document_total_chars=200,
    )


# ── apply_review ───────────────────────────────────────────────────────────


def test_no_review_is_identity():
    ext = _extraction()
    app = apply_review(ext, None)
    assert app.extraction is ext
    assert app.kept_citation_indices == [0, 1, 2]
    assert app.nodes_rejected == app.nodes_overridden == 0

    # An empty review file behaves the same.
    app = apply_review(ext, ExtractionReview(slug="x"))
    assert app.extraction is ext


def test_reject_drops_node_relationships_and_citations():
    review = ExtractionReview(slug="x", verdicts={
        "rule_b": ProposalVerdict(verdict="rejected", reason="not a reporting rule"),
    })
    app = apply_review(_extraction(), review)

    assert [p.temp_id for p in app.extraction.proposed_nodes] == ["doc1", "rule_a"]
    assert app.nodes_rejected == 1
    # rule_b's relationship and citation are pruned with it.
    assert all("rule_b" not in (r.src_temp_id, r.dst_temp_id)
               for r in app.extraction.proposed_relationships)
    assert app.relationships_dropped == 1
    assert all(c.node_temp_id != "rule_b" for c in app.extraction.citations)
    assert app.citations_dropped == 1
    # Kept indices map back into the ORIGINAL citations list (rects alignment).
    assert app.kept_citation_indices == [0, 2]


def test_reject_document_clears_dangling_refs():
    """Kept rules pointing at a rejected doc get their ref nulled, not skipped."""
    review = ExtractionReview(slug="x", verdicts={
        "doc1": ProposalVerdict(verdict="rejected"),
    })
    app = apply_review(_extraction(), review)
    assert all(p.document_temp_id is None for p in app.extraction.proposed_nodes)
    assert app.refs_cleared == 2


def test_override_applies_and_counts():
    review = ExtractionReview(slug="x", verdicts={
        "rule_b": ProposalVerdict(verdict="overridden",
                                  overrides={"name": "Rule A-2 (corrected)", "rule_number": 20},
                                  reason="agent misread the rule number"),
    })
    app = apply_review(_extraction(), review)
    rb = next(p for p in app.extraction.proposed_nodes if p.temp_id == "rule_b")
    assert rb.name == "Rule A-2 (corrected)"
    assert rb.rule_number == 20
    assert rb.section == "A"  # untouched fields survive
    assert app.nodes_overridden == 1


def test_overridden_without_overrides_is_accepted():
    review = ExtractionReview(slug="x", verdicts={
        "rule_b": ProposalVerdict(verdict="overridden"),
    })
    app = apply_review(_extraction(), review)
    assert app.nodes_overridden == 0
    assert len(app.extraction.proposed_nodes) == 3


def test_override_locked_field_raises():
    node = _extraction().proposed_nodes[1]
    with pytest.raises(ReviewOverrideError, match="identity field"):
        validate_overrides(node, {"type": "CodeList"})


def test_override_unknown_field_raises():
    node = _extraction().proposed_nodes[1]
    with pytest.raises(ReviewOverrideError):
        validate_overrides(node, {"not_a_field": 1})


def test_override_bad_value_raises():
    node = _extraction().proposed_nodes[1]
    with pytest.raises(ReviewOverrideError):
        validate_overrides(node, {"confidence": 3.5})  # ge=0, le=1


def test_review_file_round_trip():
    review = ExtractionReview(slug="doc", verdicts={
        "r1": ProposalVerdict(verdict="rejected", reason="dup", actor="j.doe",
                              at="2026-08-19T10:00:00"),
    }, updated_at="2026-08-19T10:00:00")
    back = ExtractionReview.model_validate(json.loads(review.model_dump_json()))
    assert back == review


# ── the review endpoints (registry paths → tmp_path, no Neo4j) ─────────────


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import api.main as main
    from api.registry import DocEntry

    doc_text = tmp_path / "reviewdoc.md"
    doc_text.write_text("A" * 45 + " rule one text. " + "B" * 45 + " rule two.",
                        encoding="utf-8")
    entry = DocEntry(slug="review-test-doc", label="Review test doc",
                     category="test", path=doc_text, blurb="")

    (tmp_path / "reviewdoc.extraction.json").write_text(
        _extraction().model_dump_json(), encoding="utf-8")

    monkeypatch.setattr(main, "get_doc",
                        lambda slug: entry if slug == "review-test-doc" else None)
    monkeypatch.setattr(main, "extraction_path_for",
                        lambda d: tmp_path / f"{d.path.stem}.extraction.json")
    monkeypatch.setattr(main, "review_path_for",
                        lambda d: tmp_path / f"{d.path.stem}.review.json")
    return TestClient(main.app)


def test_get_review_defaults_to_accepted(client):
    r = client.get("/api/regulations/review-test-doc/review")
    assert r.status_code == 200
    body = r.json()
    assert body["totals"] == {
        "proposals": 3, "accepted": 3, "rejected": 0, "overridden": 0,
        "queued": 0, "escalated": 1, "avg_confidence": 0.853,
    }
    by_id = {p["temp_id"]: p for p in body["proposals"]}
    assert by_id["rule_a"]["verdict"] == "accepted"
    assert by_id["rule_b"]["band"] == "escalated"
    # Citation excerpts are sliced from the document text.
    assert by_id["rule_a"]["citations"][0]["excerpt"].startswith("A")


def test_put_verdict_persists_and_merges(client, tmp_path):
    r = client.put("/api/regulations/review-test-doc/review/rule_b",
                   json={"verdict": "rejected", "reason": "duplicate", "actor": "j.doe"})
    assert r.status_code == 200
    body = r.json()
    assert body["totals"]["rejected"] == 1
    assert body["totals"]["accepted"] == 2
    rb = next(p for p in body["proposals"] if p["temp_id"] == "rule_b")
    assert rb["verdict"] == "rejected" and rb["reason"] == "duplicate"

    saved = json.loads((tmp_path / "reviewdoc.review.json").read_text(encoding="utf-8"))
    assert saved["verdicts"]["rule_b"]["verdict"] == "rejected"

    # Re-accepting with no reason clears the entry entirely.
    r = client.put("/api/regulations/review-test-doc/review/rule_b",
                   json={"verdict": "accepted"})
    assert r.status_code == 200
    saved = json.loads((tmp_path / "reviewdoc.review.json").read_text(encoding="utf-8"))
    assert saved["verdicts"] == {}


def test_put_override_is_validated(client):
    r = client.put("/api/regulations/review-test-doc/review/rule_a",
                   json={"verdict": "overridden", "overrides": {"type": "CodeList"}})
    assert r.status_code == 422
    r = client.put("/api/regulations/review-test-doc/review/rule_a",
                   json={"verdict": "overridden"})
    assert r.status_code == 422
    r = client.put("/api/regulations/review-test-doc/review/rule_a",
                   json={"verdict": "overridden",
                         "overrides": {"name": "Rule A-1 fixed"}, "reason": "typo"})
    assert r.status_code == 200
    ra = next(p for p in r.json()["proposals"] if p["temp_id"] == "rule_a")
    assert ra["verdict"] == "overridden"
    assert ra["overrides"] == {"name": "Rule A-1 fixed"}


def test_put_unknown_proposal_404(client):
    r = client.put("/api/regulations/review-test-doc/review/nope",
                   json={"verdict": "rejected"})
    assert r.status_code == 404


# ── processing locks — no conflicting action while a doc is processing ─────


def test_actions_blocked_while_extracting(client):
    import api.main as main

    main._EXTRACT_JOBS["review-test-doc"] = {"status": "running", "result": None, "error": None}
    try:
        r = client.put("/api/regulations/review-test-doc/review/rule_a",
                       json={"verdict": "rejected", "reason": "x"})
        assert r.status_code == 409
        r = client.post("/api/regulations/review-test-doc/approve")
        assert r.status_code == 409
        # Reads stay available — the user can still look at things.
        assert client.get("/api/regulations/review-test-doc/review").status_code == 200
    finally:
        main._EXTRACT_JOBS.pop("review-test-doc", None)


def test_actions_blocked_while_approving(client):
    import api.main as main

    main._APPROVE_LOCKS.add("review-test-doc")
    try:
        r = client.put("/api/regulations/review-test-doc/review/rule_a",
                       json={"verdict": "rejected", "reason": "x"})
        assert r.status_code == 409
        r = client.post("/api/regulations/review-test-doc/approve")
        assert r.status_code == 409
        r = client.post("/api/regulations/review-test-doc/extract/start")
        assert r.status_code == 409
    finally:
        main._APPROVE_LOCKS.discard("review-test-doc")


# ── jurisdiction resolution (upload → approve tagging) ─────────────────────


def test_resolve_jurisdiction_variants():
    from packages.lhs.materialization.jurisdiction import resolve_jurisdiction

    assert resolve_jurisdiction("Oklahoma") == ("US-OK", "Oklahoma")
    assert resolve_jurisdiction("oklahoma") == ("US-OK", "Oklahoma")
    assert resolve_jurisdiction("OK") == ("US-OK", "Oklahoma")
    assert resolve_jurisdiction("us-ok") == ("US-OK", "Oklahoma")
    assert resolve_jurisdiction("California — Department of Insurance") == ("US-CA", "California")
    assert resolve_jurisdiction("New York") == ("US-NY", "New York")
    assert resolve_jurisdiction("Texas") == ("US-TX", "Texas")
    assert resolve_jurisdiction(None) is None
    assert resolve_jurisdiction("") is None
    assert resolve_jurisdiction("Atlantis") is None
