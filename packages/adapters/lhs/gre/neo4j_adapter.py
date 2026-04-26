"""Neo4j-backed implementation of the GREStore port."""

from datetime import date
from typing import Any
from uuid import UUID

from neo4j import Driver, GraphDatabase

from packages.config.settings import settings
from packages.core.nodes import (
    BulletinOverride,
    CodeList,
    CodeValue,
    CoverageType,
    EndorsementRule,
    FieldRequirement,
    GRENode,
    HITLTriggerRule,
    Organization,
    ReconciliationRule,
    RecordLayout,
    RegulationDocument,
    ReportTemplate,
    Rule,
    StatPlanEdition,
)
from packages.core.relationships import GRERelationshipBase
from packages.lhs.kg import queries

# Map "type" string back to Pydantic class for read-side deserialization.
NODE_TYPE_REGISTRY: dict[str, type[GRENode]] = {
    "RegulationDocument": RegulationDocument,
    "StatPlanEdition": StatPlanEdition,
    "Rule": Rule,
    "ReportTemplate": ReportTemplate,
    "RecordLayout": RecordLayout,
    "FieldRequirement": FieldRequirement,
    "CodeList": CodeList,
    "CodeValue": CodeValue,
    "CoverageType": CoverageType,
    "EndorsementRule": EndorsementRule,
    "BulletinOverride": BulletinOverride,
    "ReconciliationRule": ReconciliationRule,
    "Organization": Organization,
    "HITLTriggerRule": HITLTriggerRule,
}


def _node_to_props(node: GRENode) -> dict[str, Any]:
    """Pydantic node → flat Neo4j-compatible property dict."""
    return node.model_dump(mode="json")


def _props_to_node(props: dict[str, Any]) -> GRENode:
    """Neo4j property dict → Pydantic node, dispatched by 'type'."""
    type_str = props.get("type")
    if type_str is None or type_str not in NODE_TYPE_REGISTRY:
        raise ValueError(f"Unknown or missing node type: {type_str!r}")
    cls = NODE_TYPE_REGISTRY[type_str]
    return cls.model_validate(props)


class Neo4jGREAdapter:
    """Neo4j-backed `GREStore`.

    Use as a context manager:
        with Neo4jGREAdapter() as gre:
            gre.create_node(...)

    Reads connection params from `settings` unless overridden.
    """

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
    ) -> None:
        self.uri = uri or settings.neo4j_uri
        self.user = user or settings.neo4j_user
        self.password = password or settings.neo4j_password
        self.database = database or settings.neo4j_database
        self._driver: Driver | None = None

    def __enter__(self) -> "Neo4jGREAdapter":
        self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        return self

    def __exit__(self, *args: object) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    @property
    def driver(self) -> Driver:
        if self._driver is None:
            raise RuntimeError("Adapter not opened — use as a context manager.")
        return self._driver

    # -- writes ---------------------------------------------------------------

    def create_node(self, node: GRENode) -> None:
        props = _node_to_props(node)
        type_label = node.type  # validated by Pydantic Literal — safe to inject as label
        cypher = f"CREATE (n:GRENode:`{type_label}`) SET n = $props"
        with self.driver.session(database=self.database) as session:
            session.run(cypher, props=props)

    def create_relationship(self, rel: GRERelationshipBase) -> None:
        """Idempotent relationship write.

        For CITES the natural key is (src, dst, char_start, char_end) — same
        cited span = same edge. For everything else, (src, dst, type) is the
        key (we assume only one relationship of each type between any pair
        of nodes; that's the closed-vocabulary assumption).

        Re-running materialize() against the same data updates non-key
        properties (e.g., rects_json, kind) but does not duplicate edges.
        """
        rel_type = rel.type.value if hasattr(rel.type, "value") else rel.type
        props = rel.model_dump(
            mode="json",
            exclude={"src_node_id", "dst_node_id"},
        )
        # 'type' lives as the relationship label, not a property. 'id' is
        # auto-generated each call — excluding it from the match keeps the
        # original edge id stable across re-runs.
        props.pop("type", None)
        props.pop("id", None)

        if rel_type == "CITES":
            cypher = f"""
                MATCH (src:GRENode {{id: $src_id}}), (dst:GRENode {{id: $dst_id}})
                MERGE (src)-[r:`{rel_type}` {{char_start: $cs, char_end: $ce}}]->(dst)
                ON CREATE SET r += $props
                ON MATCH  SET r += $props
            """
            params = dict(
                src_id=str(rel.src_node_id),
                dst_id=str(rel.dst_node_id),
                cs=props.get("char_start"),
                ce=props.get("char_end"),
                props=props,
            )
        else:
            cypher = f"""
                MATCH (src:GRENode {{id: $src_id}}), (dst:GRENode {{id: $dst_id}})
                MERGE (src)-[r:`{rel_type}`]->(dst)
                ON CREATE SET r += $props
                ON MATCH  SET r += $props
            """
            params = dict(
                src_id=str(rel.src_node_id),
                dst_id=str(rel.dst_node_id),
                props=props,
            )

        with self.driver.session(database=self.database) as session:
            session.run(cypher, **params)

    # -- reads ----------------------------------------------------------------

    def get_node(self, node_id: UUID) -> GRENode | None:
        with self.driver.session(database=self.database) as session:
            record = session.run(queries.GET_NODE_BY_ID, id=str(node_id)).single()
            if record is None:
                return None
            return _props_to_node(dict(record["n"].items()))

    def query_active_as_of(
        self,
        node_type: str,
        name: str,
        as_of: date | None = None,
    ) -> GRENode | None:
        with self.driver.session(database=self.database) as session:
            record = session.run(
                queries.QUERY_ACTIVE_AS_OF,
                type=node_type,
                name=name,
                as_of=as_of.isoformat() if as_of else None,
            ).single()
            if record is None:
                return None
            return _props_to_node(dict(record["n"].items()))

    def find_existing_by_name(self, node_type: str, name: str) -> GRENode | None:
        """Find the latest non-superseded node by (type, name). For materialization dedup."""
        with self.driver.session(database=self.database) as session:
            record = session.run(
                queries.FIND_LATEST_BY_NAME_AND_TYPE,
                type=node_type,
                name=name,
            ).single()
            if record is None:
                return None
            return _props_to_node(dict(record["n"].items()))

    def find_document_by_hash(self, hash_value: str) -> GRENode | None:
        """Find a RegulationDocument by its content hash."""
        with self.driver.session(database=self.database) as session:
            record = session.run(queries.FIND_DOCUMENT_BY_HASH, hash=hash_value).single()
            if record is None:
                return None
            return _props_to_node(dict(record["d"].items()))

    def count_nodes(self) -> int:
        with self.driver.session(database=self.database) as session:
            record = session.run(queries.COUNT_NODES).single()
            return int(record["count"]) if record else 0

    def count_by_type(self) -> dict[str, int]:
        with self.driver.session(database=self.database) as session:
            return {r["type"]: int(r["count"]) for r in session.run(queries.COUNT_BY_TYPE)}

    def count_relationships(self) -> int:
        with self.driver.session(database=self.database) as session:
            record = session.run(queries.COUNT_RELATIONSHIPS).single()
            return int(record["count"]) if record else 0

    # -- destructive ops ------------------------------------------------------

    def wipe_all(self) -> None:
        """DESTRUCTIVE: delete all nodes + relationships. Seed support only."""
        with self.driver.session(database=self.database) as session:
            session.run(queries.WIPE_ALL)
