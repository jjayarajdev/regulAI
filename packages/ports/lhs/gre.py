"""GREStore port — abstract interface for the LHS knowledge graph."""

from datetime import date
from typing import Protocol
from uuid import UUID

from packages.core.nodes import GRENode
from packages.core.relationships import GRERelationshipBase


class GREStore(Protocol):
    """Abstract interface for the regulatory knowledge graph store.

    POC impl: Neo4j (`Neo4jGREAdapter`). Future: swap behind same interface.
    """

    def create_node(self, node: GRENode) -> None:
        """Persist a single node."""
        ...

    def create_relationship(self, rel: GRERelationshipBase) -> None:
        """Persist a single relationship between two existing nodes."""
        ...

    def get_node(self, node_id: UUID) -> GRENode | None:
        """Fetch a node by id, or None if not found."""
        ...

    def query_active_as_of(
        self,
        node_type: str,
        name: str,
        as_of: date | None = None,
    ) -> GRENode | None:
        """Active version of a node by type+name as of a given date.

        as_of=None means 'right now' (effectivity windows ignored).
        Only returns nodes with status='approved'.
        """
        ...

    def count_nodes(self) -> int:
        """Total node count — useful for seed verification and tests."""
        ...

    def count_by_type(self) -> dict[str, int]:
        """Counts grouped by node type."""
        ...

    def wipe_all(self) -> None:
        """DESTRUCTIVE: delete every node and relationship.

        POC seed support. Never call from production paths.
        """
        ...
