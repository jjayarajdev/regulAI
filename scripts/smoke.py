"""LHS-1 smoke test — write a node, read it back, clean up.

Validates: Pydantic models construct cleanly, Neo4j connection works,
Cypher writes/reads round-trip correctly.

Run via: make smoke
"""

from uuid import uuid4

from neo4j import GraphDatabase

from packages.config.settings import settings
from packages.core.enums import DocumentKind, NodeStatus
from packages.core.nodes import RegulationDocument


def main() -> None:
    print(f"Connecting to {settings.neo4j_uri} ...")

    doc = RegulationDocument(
        name="TICO TX Statistical Plan for Residential Risks (smoke test)",
        kind=DocumentKind.STAT_PLAN,
        title="Texas Statistical Plan for Residential Risks",
        hash=f"smoke-{uuid4().hex[:8]}",
        source_url="https://www.tdi.texas.gov/rules/2025/documents/statplanres.pdf",
        status=NodeStatus.APPROVED,
    )
    print(f"  Constructed RegulationDocument: id={doc.id}")

    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    try:
        with driver.session(database=settings.neo4j_database) as session:
            session.run(
                """
                CREATE (n:GRENode:RegulationDocument {
                    id: $id,
                    type: $type,
                    name: $name,
                    version: $version,
                    status: $status,
                    kind: $kind,
                    title: $title,
                    hash: $hash,
                    source_url: $source_url,
                    created_at: $created_at
                })
                """,
                id=str(doc.id),
                type=doc.type,
                name=doc.name,
                version=doc.version,
                status=doc.status.value,
                kind=doc.kind.value,
                title=doc.title,
                hash=doc.hash,
                source_url=doc.source_url,
                created_at=doc.created_at.isoformat(),
            )
            print(f"  ✓ Wrote node to Neo4j")

            result = session.run(
                "MATCH (n:GRENode:RegulationDocument {id: $id}) RETURN n",
                id=str(doc.id),
            )
            record = result.single()
            assert record is not None, "Node not found after write"
            n = record["n"]
            assert n["title"] == doc.title, f"Title mismatch: {n['title']} != {doc.title}"
            assert n["kind"] == DocumentKind.STAT_PLAN.value
            assert n["hash"] == doc.hash
            print(f"  ✓ Read back: {n['title']}")
            print(f"    kind={n['kind']}, status={n['status']}, version={n['version']}")

            session.run(
                "MATCH (n:GRENode:RegulationDocument {id: $id}) DETACH DELETE n",
                id=str(doc.id),
            )
            print(f"  ✓ Cleaned up smoke node")

    finally:
        driver.close()

    print("\nLHS-1 smoke test PASSED.")


if __name__ == "__main__":
    main()
