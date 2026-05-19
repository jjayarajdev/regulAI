"""Cypher schema migrations for the GRE.

Idempotent — uses IF NOT EXISTS clauses. Safe to re-run. Run via:
    make migrate
"""

from neo4j import GraphDatabase

from packages.config.settings import settings

CONSTRAINTS: list[str] = [
    """CREATE CONSTRAINT node_id_unique IF NOT EXISTS
       FOR (n:GRENode) REQUIRE n.id IS UNIQUE""",
    """CREATE CONSTRAINT document_hash_unique IF NOT EXISTS
       FOR (d:RegulationDocument) REQUIRE d.hash IS UNIQUE""",
]

INDEXES: list[str] = [
    """CREATE INDEX node_type_version IF NOT EXISTS
       FOR (n:GRENode) ON (n.type, n.version)""",
    """CREATE INDEX node_effective_date IF NOT EXISTS
       FOR (n:GRENode) ON (n.effective_from)""",
    """CREATE INDEX rule_lookup IF NOT EXISTS
       FOR (r:Rule) ON (r.section, r.rule_number)""",
    """CREATE INDEX rule_name IF NOT EXISTS
       FOR (r:Rule) ON (r.name)""",
    """CREATE INDEX codelist_lookup IF NOT EXISTS
       FOR (c:CodeList) ON (c.code_list_name)""",
    """CREATE INDEX codevalue_code IF NOT EXISTS
       FOR (cv:CodeValue) ON (cv.code)""",
    """CREATE INDEX kg_audit_occurred_at IF NOT EXISTS
       FOR (a:KGAuditEntry) ON (a.occurred_at)""",
    """CREATE INDEX kg_audit_action IF NOT EXISTS
       FOR (a:KGAuditEntry) ON (a.action)""",
]


def run_migrations() -> None:
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    try:
        with driver.session(database=settings.neo4j_database) as session:
            print("Constraints:")
            for cypher in CONSTRAINTS:
                session.run(cypher)
                first_line = cypher.strip().split("\n")[0]
                print(f"  ✓ {first_line}")
            print("\nIndexes:")
            for cypher in INDEXES:
                session.run(cypher)
                first_line = cypher.strip().split("\n")[0]
                print(f"  ✓ {first_line}")
    finally:
        driver.close()


if __name__ == "__main__":
    print(f"Running migrations against {settings.neo4j_uri} ...\n")
    run_migrations()
    print("\nDone.")
