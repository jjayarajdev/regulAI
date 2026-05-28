"""Tests for the kg_hygiene migration (Phase 1.5).

Each test creates a controlled artifact (a null-type node, an orphan CodeValue
with a cited parent), runs the relevant hygiene function, asserts the fix,
and cleans up. Requires Neo4j reachability.
"""

from __future__ import annotations

import uuid as _uuid

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
    reason="Neo4j unreachable — skipping hygiene tests",
)


def test_fix_null_type_sets_type_from_native_label():
    """A node with the right native label but no type property gets fixed."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
    from scripts.kg_hygiene import fix_null_type_nodes

    test_id = f"test-null-type-{_uuid.uuid4().hex[:8]}"
    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        # Create a node with dual label but no type property
        s.run("""
            CREATE (n:GRENode:Rule {
                id: $id, name: 'pytest null-type fixture',
                version: 1, status: 'draft',
                created_at: datetime(), created_by: 'pytest'
            })
        """, id=test_id)

    try:
        # Verify type is null before
        with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
            r = s.run("MATCH (n {id: $id}) RETURN n.type AS t", id=test_id).single()
            assert r["t"] is None

        # Run the fix
        count, ids = fix_null_type_nodes()
        assert test_id in ids
        assert count >= 1

        # Verify type is now set
        with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
            r = s.run("MATCH (n {id: $id}) RETURN n.type AS t", id=test_id).single()
            assert r["t"] == "Rule"

        # Re-running is idempotent (returns 0 if no nulls remain)
        count2, _ = fix_null_type_nodes()
        # count2 might be > 0 if there are OTHER null nodes, but our test node won't appear
        count3_ids = fix_null_type_nodes()[1]
        assert test_id not in count3_ids
    finally:
        with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
            s.run("MATCH (n {id: $id}) DETACH DELETE n", id=test_id)


def test_propagate_codelist_citation_to_orphan_codevalue():
    """A CodeValue under a CITES-bearing CodeList that has no own CITES
    receives a propagated CITES with provenance marker."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
    from scripts.kg_hygiene import propagate_codelist_citations

    cl_id = f"test-cl-{_uuid.uuid4().hex[:8]}"
    cv_id = f"test-cv-{_uuid.uuid4().hex[:8]}"
    doc_id = f"test-doc-{_uuid.uuid4().hex[:8]}"

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        # Create cited document
        s.run("""
            CREATE (d:GRENode:RegulationDocument {
                id: $id, type: 'RegulationDocument', name: 'pytest doc',
                hash: $hash, kind: 'StatPlan', version: 1, status: 'approved',
                title: 'pytest', created_at: datetime(), created_by: 'pytest'
            })
        """, id=doc_id, hash=f"pytest-{_uuid.uuid4().hex[:8]}")

        # Create CodeList that cites the doc
        s.run("""
            MATCH (d:RegulationDocument {id: $doc_id})
            CREATE (cl:GRENode:CodeList {
                id: $id, type: 'CodeList', name: 'pytest cl', code_list_name: 'pytest',
                version: 1, status: 'approved',
                created_at: datetime(), created_by: 'pytest'
            })
            CREATE (cl)-[:CITES {id: randomUUID(), char_start: 0, char_end: 0, kind: 'defines'}]->(d)
        """, id=cl_id, doc_id=doc_id)

        # Create orphan CodeValue under that CodeList (no direct CITES)
        s.run("""
            MATCH (cl:CodeList {id: $cl_id})
            CREATE (cv:GRENode:CodeValue {
                id: $id, type: 'CodeValue', name: 'pytest cv', code: 'X',
                version: 1, status: 'approved',
                created_at: datetime(), created_by: 'pytest'
            })
            CREATE (cl)-[:HAS_VALUE]->(cv)
        """, cl_id=cl_id, id=cv_id)

    try:
        # Run propagation
        cvs_updated, edges_added = propagate_codelist_citations()
        assert edges_added >= 1
        assert cvs_updated >= 1

        # Verify the CodeValue now has a CITES with provenance marker
        with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
            r = s.run("""
                MATCH (cv:CodeValue {id: $id})-[r:CITES]->(d)
                RETURN r.propagated_from AS source, d.id AS doc_id
            """, id=cv_id).single()
            assert r is not None, "propagation failed — no CITES edge created"
            assert r["source"] == "parent_codelist"
            assert r["doc_id"] == doc_id
    finally:
        with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
            s.run("""
                MATCH (n) WHERE n.id IN [$cv, $cl, $doc] DETACH DELETE n
            """, cv=cv_id, cl=cl_id, doc=doc_id)


def test_codevalue_with_direct_citation_is_not_double_propagated():
    """A CodeValue that already has a CITES edge isn't given another one."""
    from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
    from scripts.kg_hygiene import propagate_codelist_citations

    cl_id = f"test-cl-{_uuid.uuid4().hex[:8]}"
    cv_id = f"test-cv-{_uuid.uuid4().hex[:8]}"
    doc_id = f"test-doc-{_uuid.uuid4().hex[:8]}"
    other_doc_id = f"test-other-{_uuid.uuid4().hex[:8]}"

    with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
        s.run("""
            CREATE (d:GRENode:RegulationDocument {
                id: $id, type: 'RegulationDocument', name: 'pytest doc 1',
                hash: $hash, kind: 'StatPlan', version: 1, status: 'approved',
                title: 'pytest', created_at: datetime(), created_by: 'pytest'
            })
        """, id=doc_id, hash=f"pytest-{_uuid.uuid4().hex[:8]}")
        s.run("""
            CREATE (d:GRENode:RegulationDocument {
                id: $id, type: 'RegulationDocument', name: 'pytest doc 2',
                hash: $hash, kind: 'StatPlan', version: 1, status: 'approved',
                title: 'pytest', created_at: datetime(), created_by: 'pytest'
            })
        """, id=other_doc_id, hash=f"pytest-{_uuid.uuid4().hex[:8]}")
        # CodeList cites doc1, CodeValue directly cites doc2
        s.run("""
            MATCH (d1:RegulationDocument {id: $doc_id}), (d2:RegulationDocument {id: $other_doc_id})
            CREATE (cl:GRENode:CodeList {
                id: $cl_id, type: 'CodeList', name: 'pytest cl', code_list_name: 'pytest',
                version: 1, status: 'approved',
                created_at: datetime(), created_by: 'pytest'
            })
            CREATE (cv:GRENode:CodeValue {
                id: $cv_id, type: 'CodeValue', name: 'pytest cv', code: 'Y',
                version: 1, status: 'approved',
                created_at: datetime(), created_by: 'pytest'
            })
            CREATE (cl)-[:CITES {id: randomUUID(), char_start: 0, char_end: 0, kind: 'defines'}]->(d1)
            CREATE (cl)-[:HAS_VALUE]->(cv)
            CREATE (cv)-[:CITES {id: randomUUID(), char_start: 0, char_end: 0, kind: 'defines'}]->(d2)
        """, doc_id=doc_id, other_doc_id=other_doc_id, cl_id=cl_id, cv_id=cv_id)

    try:
        before_count = 0
        with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
            r = s.run("MATCH (cv:CodeValue {id: $id})-[r:CITES]->() RETURN count(r) AS n", id=cv_id).single()
            before_count = r["n"]
        assert before_count == 1

        propagate_codelist_citations()

        with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
            r = s.run("MATCH (cv:CodeValue {id: $id})-[r:CITES]->() RETURN count(r) AS n", id=cv_id).single()
            assert r["n"] == before_count, "directly-cited CodeValue must not be double-propagated"
    finally:
        with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
            s.run("""
                MATCH (n) WHERE n.id IN [$cv, $cl, $doc, $other] DETACH DELETE n
            """, cv=cv_id, cl=cl_id, doc=doc_id, other=other_doc_id)
