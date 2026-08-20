"""Materialize a SentinelExtraction into the KG (Neo4j) + JSONL snapshot.

Three phases:

1. **ID resolution**: every ProposedNode gets a UUID. If an existing node with
   the same (type, name) already lives in the KG, we reuse its UUID — no
   duplicate. This is the dedup that keeps re-running extractions or ingesting
   bulletins that reference existing rules from creating noise.

2. **Node materialization**: for each proposal not matched against existing,
   we convert the flat ProposedNode → typed GRENode and write to Neo4j.

3. **Relationship + citation materialization**: with all temp_ids → UUIDs,
   we write proposed_relationships and CITES (from the citations list) using
   real UUIDs. Already-existing identical relationships are NOT deduped in
   this POC pass — same edge twice = idempotent at write time.

The result also lands as JSONL in `materialized/approved/<doc>.json` so future
RHS work can read the approved canon without going to Neo4j.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid5

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
from packages.config.settings import settings
from packages.core.enums import RelationshipType
from packages.core.nodes import GRENode
from packages.core.relationships import CitesRelationship, GRERelationship
from packages.lhs.citations.pdf_highlight import CitationRectsBundle
from packages.lhs.materialization.node_factory import proposed_to_typed_node
from packages.lhs.materialization.parser_boundary import check_parser_boundary
from packages.lhs.sentinel.schema import (
    CitationProposal,
    ProposedNode,
    ProposedRelationship,
    SentinelExtraction,
)


@dataclass
class SkippedProposal:
    """A proposal that failed schema validation in materialize().

    Captured for audit visibility — see scripts/audit_extraction_loss.py.
    The char range (if available) lets reviewers locate the dropped content
    in the source document.
    """
    type: str          # node type (e.g., 'Rule', 'ReportTemplate')
    name: str
    reason: str        # the exception message from proposed_to_typed_node
    char_start: int | None = None  # from first CitationProposal, if any
    char_end: int | None = None


@dataclass
class MaterializationResult:
    document_label: str
    nodes_created: list[tuple[str, str]] = field(default_factory=list)  # (type, name)
    nodes_reused: list[tuple[str, str]] = field(default_factory=list)
    relationships_created: int = 0
    citations_created: int = 0
    skipped_proposals: list[SkippedProposal] = field(default_factory=list)
    materialized_path: Path | None = None

    @property
    def total_proposed(self) -> int:
        return len(self.nodes_created) + len(self.nodes_reused) + len(self.skipped_proposals)

    @property
    def skip_pct(self) -> float:
        total = self.total_proposed
        return (len(self.skipped_proposals) / total * 100.0) if total else 0.0

    def summary(self) -> str:
        return (
            f"  Created: {len(self.nodes_created)} nodes\n"
            f"  Reused:  {len(self.nodes_reused)} nodes (existing in KG)\n"
            f"  Relationships: {self.relationships_created}\n"
            f"  Citations:     {self.citations_created}\n"
            f"  Skipped:       {len(self.skipped_proposals)} ({self.skip_pct:.1f}% of proposed)"
        )


# Stable namespace for deterministic KG node UUIDs (uuid5).
#
# Re-running `make rebuild-kg` on unchanged cached extractions used to
# produce different UUIDs for every node (uuid4), which made every
# downstream artifact that embeds a UUID — REFERENCE.* SQL files,
# tspr_validation_rules.sql, snapshot JSONs — churn on every rebuild.
# Switching to uuid5 keyed on (type, name) makes the rebuild
# byte-deterministic; (type, name) is also exactly the identity
# already used by find_existing_by_name dedup, so collision semantics
# stay the same.
#
# DO NOT change this UUID. Any change would invalidate every UUID in
# every production KG snapshot or load script.
_KG_NODE_NAMESPACE = UUID("0a4d8a36-7e1a-4b8e-9c2f-67616c6c6f72")


def _deterministic_node_uuid(type_label: str, name: str, jurisdiction_code: str | None = None) -> UUID:
    """uuid5-based UUID keyed on the same identity tuple find_existing_by_name
    dedup uses. Stable across rebuilds, so reproducing the KG from disk
    produces byte-identical artifacts.

    Legacy key is (type, name); when a non-default jurisdiction is being
    materialized the key includes it — two states legitimately carry
    same-named rules, and a shared UUID would merge them. The legacy TX/None
    path is byte-identical to before (existing artifacts unaffected)."""
    if jurisdiction_code and jurisdiction_code != "US-TX":
        return uuid5(_KG_NODE_NAMESPACE, f"{type_label}|{name}|{jurisdiction_code}")
    return uuid5(_KG_NODE_NAMESPACE, f"{type_label}|{name}")


def _resolve_temp_ids(
    proposals: list[ProposedNode],
    gre: Neo4jGREAdapter,
    jurisdiction_code: str | None = None,
) -> tuple[dict[str, UUID], dict[str, GRENode], list[tuple[str, str]], set[str]]:
    """First pass: assign each temp_id a UUID, reusing existing nodes when matched.

    Returns:
      - temp_id_to_uuid: mapping for cross-reference resolution
      - existing_by_temp_id: ProposedNodes that matched existing KG nodes
        (these won't be re-created in phase 2)
      - reused: list of (type, name) for the result summary
    """
    temp_id_to_uuid: dict[str, UUID] = {}
    existing_by_temp_id: dict[str, GRENode] = {}
    reused: list[tuple[str, str]] = []
    in_extraction_dups: set[str] = set()

    # In-extraction dedup. A single extraction sometimes proposes the
    # same (type, name) under two temp_ids (parser merges page-break
    # duplicates loosely; LLM occasionally re-extracts). With uuid4 these
    # used to land as separate Neo4j nodes with same name; with uuid5
    # they collide on insert (same deterministic id). Track the first
    # temp_id we issue per (type, name) and route later proposals to it.
    name_key_to_first_temp_id: dict[tuple[str, str], str] = {}

    for p in proposals:
        type_label = p.type.value if hasattr(p.type, "value") else str(p.type)
        # Hash-based dedup for documents
        if p.hash:
            doc = gre.find_document_by_hash(p.hash)
            if doc is not None:
                temp_id_to_uuid[p.temp_id] = doc.id
                existing_by_temp_id[p.temp_id] = doc
                reused.append((type_label, p.name))
                continue
        # (type, name[, jurisdiction]) dedup against the DB
        existing = gre.find_existing_by_name(type_label, p.name, jurisdiction_code)
        if existing is not None:
            temp_id_to_uuid[p.temp_id] = existing.id
            existing_by_temp_id[p.temp_id] = existing
            reused.append((type_label, p.name))
            continue
        # (type, name) dedup *within this extraction* — later proposals
        # with the same key share the first one's UUID and skip create.
        # The first proposal still creates the node; subsequents are
        # routed to the same uuid so relationships/citations attach
        # correctly without re-attempting an insert.
        key = (type_label, p.name)
        if key in name_key_to_first_temp_id:
            first_tid = name_key_to_first_temp_id[key]
            temp_id_to_uuid[p.temp_id] = temp_id_to_uuid[first_tid]
            in_extraction_dups.add(p.temp_id)
            reused.append((type_label, p.name))
            continue
        temp_id_to_uuid[p.temp_id] = _deterministic_node_uuid(type_label, p.name, jurisdiction_code)
        name_key_to_first_temp_id[key] = p.temp_id

    return temp_id_to_uuid, existing_by_temp_id, reused, in_extraction_dups


def _write_relationship(
    gre: Neo4jGREAdapter,
    rel: ProposedRelationship,
    temp_id_to_uuid: dict[str, UUID],
) -> bool:
    src_id = temp_id_to_uuid.get(rel.src_temp_id)
    dst_id = temp_id_to_uuid.get(rel.dst_temp_id)
    if src_id is None or dst_id is None:
        return False

    if rel.type == RelationshipType.CITES and rel.char_start is not None and rel.char_end is not None:
        gre.create_relationship(
            CitesRelationship(
                src_node_id=src_id,
                dst_node_id=dst_id,
                char_start=rel.char_start,
                char_end=rel.char_end,
                kind=rel.citation_kind or "defines",
            )
        )
    else:
        gre.create_relationship(
            GRERelationship(
                type=rel.type,
                src_node_id=src_id,
                dst_node_id=dst_id,
            )
        )
    return True


def _write_citation(
    gre: Neo4jGREAdapter,
    cite: CitationProposal,
    temp_id_to_uuid: dict[str, UUID],
    document_node_id: UUID,
    rects_json: str | None = None,
) -> bool:
    """Write a CITES relationship from the cited node to the source document.

    For now we cite the document-level node. Once Sentinel emits Rule-level
    citations consistently, we can route to the specific Rule node instead.
    `rects_json` (when present) is the PyMuPDF-derived JSON list of PDF
    rectangles for this citation, persisted on the relationship so the KG
    is self-contained for highlight provenance.
    """
    src = temp_id_to_uuid.get(cite.node_temp_id)
    if src is None:
        return False
    gre.create_relationship(
        CitesRelationship(
            src_node_id=src,
            dst_node_id=document_node_id,
            char_start=cite.char_start,
            char_end=cite.char_end,
            kind=cite.kind,
            rects_json=rects_json,
        )
    )
    return True


def _identify_document_node(
    extraction: SentinelExtraction,
    temp_id_to_uuid: dict[str, UUID],
) -> UUID | None:
    """Pick the primary RegulationDocument from the extraction (the one being reviewed)."""
    for p in extraction.proposed_nodes:
        if p.type.value == "RegulationDocument" and p.hash:
            return temp_id_to_uuid.get(p.temp_id)
    # Fallback: first RegulationDocument
    for p in extraction.proposed_nodes:
        if p.type.value == "RegulationDocument":
            return temp_id_to_uuid.get(p.temp_id)
    return None


def materialize(
    extraction: SentinelExtraction,
    gre: Neo4jGREAdapter,
    document_label: str,
    snapshot_dir: Path | None = None,
    rects_bundle: CitationRectsBundle | None = None,
    source: str = "sentinel",
    jurisdiction_code: str | None = None,
) -> MaterializationResult:
    # Phase 0 (Cluster C): refuse to materialize a parser-owned doc's
    # extraction if Sentinel proposed parser-owned-type nodes. The parser
    # itself is the legitimate producer of RecordLayout / FieldRequirement
    # on parser-owned docs — when parse_record_layout.py calls materialize
    # with source='parser', we skip the gate.
    if source != "parser":
        check_parser_boundary(extraction, document_label)

    result = MaterializationResult(document_label=document_label)

    # Phase 1: resolve temp_ids → UUIDs (with dedup, jurisdiction-scoped when known)
    temp_id_to_uuid, existing, reused, dups = _resolve_temp_ids(
        extraction.proposed_nodes, gre, jurisdiction_code)
    result.nodes_reused = reused

    # Index citations by temp_id so skipped proposals can carry a char-range
    # pointer back into the source document (for audit visibility).
    citations_by_temp_id: dict[str, list[CitationProposal]] = {}
    for c in extraction.citations:
        citations_by_temp_id.setdefault(c.node_temp_id, []).append(c)

    # Phase 2: create new nodes (those not matched against existing).
    # `dups` carries temp_ids that lost an in-extraction (type, name)
    # dedup race — they share a UUID with the first proposal, which is
    # what actually creates the node. Skipping them here prevents a
    # constraint violation on the shared deterministic UUID.
    for p in extraction.proposed_nodes:
        if p.temp_id in existing or p.temp_id in dups:
            continue
        type_label = p.type.value if hasattr(p.type, "value") else str(p.type)
        try:
            typed = proposed_to_typed_node(p, temp_id_to_uuid[p.temp_id], temp_id_to_uuid)
        except ValueError as e:
            cites = citations_by_temp_id.get(p.temp_id, [])
            first = cites[0] if cites else None
            result.skipped_proposals.append(SkippedProposal(
                type=type_label,
                name=p.name,
                reason=str(e),
                char_start=first.char_start if first else None,
                char_end=first.char_end if first else None,
            ))
            continue
        gre.create_node(typed)
        result.nodes_created.append((type_label, p.name))

    # Phase 3: relationships
    for rel in extraction.proposed_relationships:
        if _write_relationship(gre, rel, temp_id_to_uuid):
            result.relationships_created += 1

    # Phase 4: citations — link every cited node to the primary document.
    # If a rects_bundle was supplied, attach the PyMuPDF-derived rects as
    # a JSON property on the CITES relationship (one per citation, by index).
    document_node_id = _identify_document_node(extraction, temp_id_to_uuid)
    if document_node_id is not None:
        for i, cite in enumerate(extraction.citations):
            rects_json: str | None = None
            if rects_bundle is not None and i < len(rects_bundle.citation_rects):
                rects = rects_bundle.citation_rects[i]
                if rects:
                    rects_json = json.dumps([r.model_dump(mode="json") for r in rects])
            if _write_citation(gre, cite, temp_id_to_uuid, document_node_id, rects_json):
                result.citations_created += 1

    # Phase 5: snapshot to disk for downstream RHS consumption
    if snapshot_dir is None:
        snapshot_dir = settings.materialized_dir / "approved"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / f"{document_label}.materialized.json"
    snapshot = {
        "document_label": document_label,
        "materialized_at": datetime.now().isoformat(),
        "extraction_summary": extraction.summary,
        "temp_id_to_uuid": {k: str(v) for k, v in temp_id_to_uuid.items()},
        "nodes_created": [{"type": t, "name": n} for t, n in result.nodes_created],
        "nodes_reused": [{"type": t, "name": n} for t, n in result.nodes_reused],
        "relationships_created": result.relationships_created,
        "citations_created": result.citations_created,
        "totals": {
            "proposed": result.total_proposed,
            "created": len(result.nodes_created),
            "reused": len(result.nodes_reused),
            "skipped": len(result.skipped_proposals),
            "skip_pct": round(result.skip_pct, 2),
        },
        "skipped_proposals": [
            {
                "type": s.type,
                "name": s.name,
                "reason": s.reason,
                "char_start": s.char_start,
                "char_end": s.char_end,
            }
            for s in result.skipped_proposals
        ],
    }
    snapshot_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    result.materialized_path = snapshot_path

    return result
