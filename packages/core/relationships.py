"""Pydantic models for KG relationships.

Most relationships are represented by a single GRERelationship model with a
type discriminator. CITES has additional fields (char_start, char_end, kind)
because span-level provenance is core to the design.

In Neo4j these map to typed relationships between :GRENode-labeled nodes.
"""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .enums import CitationKind, RelationshipType


class GRERelationshipBase(BaseModel):
    """Common properties shared by every KG relationship."""

    model_config = ConfigDict(use_enum_values=False)

    id: UUID = Field(default_factory=uuid4)
    type: RelationshipType
    src_node_id: UUID
    dst_node_id: UUID
    src_version: int = 1
    dst_version: int = 1
    created_at: datetime = Field(default_factory=datetime.now)


class CitesRelationship(GRERelationshipBase):
    """KG node CITES a regulation Rule, with span-level provenance.

    char_start/char_end are character offsets into the source document text;
    kind disambiguates *why* this node cites this rule (defines/modifies/references).
    rects_json is the PyMuPDF-derived list of PDF rectangles (top-left origin,
    PDF points) that locate the span on the source PDF — JSON-serialized so
    Neo4j can store it as a single string property.
    """

    type: RelationshipType = RelationshipType.CITES
    char_start: int
    char_end: int
    kind: CitationKind = CitationKind.DEFINES
    rects_json: str | None = None


class GRERelationship(GRERelationshipBase):
    """Generic relationship for non-CITES types."""

    pass
