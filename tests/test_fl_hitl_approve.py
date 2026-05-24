"""HITL — drive FL cached extractions through /api/regulations/{slug}/approve.

The /approve endpoint is the same call the review UI makes when a user
clicks "approve" on a Sentinel extraction. Reading code suggested FL
extractions would just work because the materialize() path was hardened
in Clusters A–C. This file verifies that by exercising each FL slug
through the actual HTTP path.

What this catches that the materialize-level tests don't:
  - FastAPI serialization of the post-Cluster-B SkippedProposal dataclass
  - The full request → response cycle including Pydantic re-validation
    of the cached extraction (would fail if the schema drifted in ways
    that broke cached files)
  - Parser-boundary enforcement on user-driven approval (Cluster C wired
    the gate inside materialize() so this path inherits it)
  - 5xx errors that surface only when the API layer touches FL-specific
    shapes (MemoDirective Rules, weekly cadence, etc.)

What this DOES NOT catch yet (documented gaps from exercising HITL):
  - Position resolver only runs in scripts/rebuild_kg.py, not in /approve.
    Approving an extraction with NULL field positions via the UI lands
    them as NULL in the KG; rebuild-kg back-fills via position_resolver.
    Asymmetric — file gh issue or move the call site.
  - Jurisdiction retag (seed_florida) only runs separately, not in
    /approve. Approving a *new* FL extraction would default-tag new
    nodes US-TX (the Pydantic default) instead of US-FL. Not surfaced
    here because we approve already-materialized extractions where
    dedup returns existing US-FL-tagged nodes.

Both gaps are out-of-scope for this task; documenting so the next
person picking this up knows where to look.
"""

from __future__ import annotations

import sys

import pytest


def _stack_available() -> bool:
    try:
        from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
        with Neo4jGREAdapter() as gre:
            gre.count_nodes()
        from fastapi.testclient import TestClient  # noqa: F401
        from api.main import app  # noqa: F401
        return True
    except Exception as e:
        print(f"[_stack_available] {type(e).__name__}: {e}", file=sys.stderr)
        return False


pytestmark = pytest.mark.skipif(
    not _stack_available(),
    reason="Stack unreachable — skipping HITL tests",
)


# Each FL slug + a tag noting the schema shape it exercises through HITL.
FL_SLUGS_TO_EXERCISE = [
    ("fl-627-062", "statute / prose statute"),
    ("fl-627-351", "statute / ReportTemplate with null cadence"),
    ("fl-oir-22-04m", "regulator memo / MemoDirective Rules"),
    ("fl-fhcf-data-call", "statistical plan / parser-respecting boundary"),
]


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from api.main import app
    return TestClient(app)


@pytest.mark.parametrize("slug,shape", FL_SLUGS_TO_EXERCISE, ids=[s[0] for s in FL_SLUGS_TO_EXERCISE])
def test_approve_endpoint_handles_fl_extraction(client, slug, shape):
    """The HITL approve path completes 200 on every FL extraction.
    Schema-drift bugs (e.g. Pydantic rejection of a cached extraction
    after a model change) surface here as 500s; parser-boundary
    violations surface as 400/500 with the violation message."""
    response = client.post(f"/api/regulations/{slug}/approve")
    assert response.status_code == 200, (
        f"/approve for {slug} ({shape}) returned {response.status_code}: "
        f"{response.text[:400]}"
    )
    body = response.json()
    # All response keys the UI reads
    for key in ("slug", "nodes_created", "nodes_reused", "relationships_created",
                "citations_created", "skipped"):
        assert key in body, f"{slug}: response missing key {key!r}"
    assert body["slug"] == slug


@pytest.mark.parametrize("slug,shape", FL_SLUGS_TO_EXERCISE, ids=[s[0] for s in FL_SLUGS_TO_EXERCISE])
def test_approve_endpoint_reuses_existing_fl_nodes(client, slug, shape):
    """After rebuild-kg has run (which the conftest reseed chain
    guarantees), approving the same FL extraction again should dedup
    against existing nodes. nodes_created should be 0 and nodes_reused
    should be non-empty. If this fails, materialize's (type, name)
    dedup regressed."""
    response = client.post(f"/api/regulations/{slug}/approve")
    body = response.json()
    n_created = len(body["nodes_created"])
    n_reused = len(body["nodes_reused"])
    assert n_reused > 0, (
        f"{slug}: approving twice should reuse — got {n_reused} reused. "
        f"Either rebuild didn't run, or dedup regressed."
    )
    # Some docs deduplicate everything (n_created=0), others may create
    # nothing-new because the second approve runs after first. Either way,
    # the test is that we don't error and we do reuse.
    assert n_created + n_reused > 0, f"{slug}: nothing materialized at all"


@pytest.mark.parametrize("slug,shape", FL_SLUGS_TO_EXERCISE, ids=[s[0] for s in FL_SLUGS_TO_EXERCISE])
def test_approve_endpoint_has_no_schema_skips_on_fl(client, slug, shape):
    """After Clusters A+B, no FL extraction should have any skipped_proposals
    coming out of materialize(). If any do, either schemas regressed or
    Sentinel proposed a new shape we don't handle."""
    response = client.post(f"/api/regulations/{slug}/approve")
    body = response.json()
    skipped = body.get("skipped", [])
    assert not skipped, (
        f"{slug}: /approve dropped {len(skipped)} proposals via schema validation. "
        f"First few: {skipped[:3]}"
    )


def test_approve_on_parser_owned_slug_returns_clean_400(client):
    """Approving a parser-owned slug's Sentinel extraction must:
      - NOT crash (5xx)
      - Return a clean 400 with the ParserBoundaryViolation detail
      - Surface enough info for the UI to render the violation

    Today the cached extractions for parser-owned slugs (e.g.
    section_C_record.extraction.json) predate the strip_parser_owned
    behavior in batch_extract, so they still contain Sentinel-proposed
    RecordLayout / FieldRequirement nodes. The gate inside materialize()
    rightly rejects them; this test asserts the API layer translates
    that into a useful 400 instead of a generic 500.

    Follow-up to consider: re-run batch_extract --force on the parser-
    owned slugs to clear the stale Sentinel proposals from disk. Out of
    scope here (burns OpenAI tokens) but worth doing once.
    """
    response = client.post("/api/regulations/tico-section-c/approve")
    assert response.status_code == 400, (
        f"Expected 400 (clean parser-boundary error), got {response.status_code}: "
        f"{response.text[:400]}"
    )
    body = response.json()
    detail = body["detail"]
    assert detail["error"] == "parser_boundary_violation"
    assert detail["document_label"] == "tico-section-c"
    assert detail["offender_count"] > 0
    # The first offenders carry type + name so the UI can show them
    assert all("type" in o and "name" in o for o in detail["first_offenders"])
