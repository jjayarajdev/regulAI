"""Per-proposal review verdicts for a SentinelExtraction — the HITL gate.

Mirrors the schema-mapper's review model (agent proposes, human governs):
every ProposedNode can carry a verdict — accepted (default), rejected, or
overridden (accepted with field corrections). Verdicts live in a sidecar
file next to the extraction JSON (`{doc}.review.json`), so the extraction
itself stays the agent's untouched proposal and the review is a separate,
auditable artifact.

`apply_review` folds the verdicts into a new SentinelExtraction right before
materialization: rejected nodes disappear along with every relationship and
citation that touches them, and overrides are re-validated through
ProposedNode so a bad edit fails loudly instead of landing in the KG.
"""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict

from packages.lhs.sentinel.schema import ProposedNode, SentinelExtraction

# Identity fields a reviewer may not edit — changing them would silently
# re-key the node past the (type, name)+temp_id machinery. Renames are a
# legitimate override; `name` is deliberately editable.
_LOCKED_FIELDS = frozenset({"temp_id", "type"})

# Cross-reference fields that may point at a rejected proposal. Cleared
# rather than left dangling: node_factory raises on an unresolvable ref,
# which would skip an otherwise-accepted node.
_REF_FIELDS = ("document_temp_id", "bulletin_temp_id",
               "from_report_temp_id", "code_list_temp_id")

Verdict = Literal["accepted", "rejected", "overridden"]


class ProposalVerdict(BaseModel):
    """One reviewer decision on one proposed node."""

    model_config = ConfigDict(extra="forbid")

    verdict: Verdict
    # Field → new value, applied over the agent's proposal. Only meaningful
    # for verdict='overridden'; validated against ProposedNode on apply.
    overrides: dict[str, object] | None = None
    reason: str | None = None
    actor: str | None = None
    at: str | None = None  # ISO timestamp


class ExtractionReview(BaseModel):
    """The sidecar review file — verdicts keyed by the proposal's temp_id.

    Absence of a temp_id means accepted-as-proposed; an empty review is a
    valid no-op, so approve without any review behaves exactly as before.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str
    verdicts: dict[str, ProposalVerdict] = {}
    updated_at: str | None = None

    def rejected_temp_ids(self) -> set[str]:
        return {t for t, v in self.verdicts.items() if v.verdict == "rejected"}


@dataclass
class ReviewApplication:
    """apply_review output: the reviewed extraction + audit counts.

    `kept_citation_indices` maps positions in the reviewed extraction's
    citations list back to the original list — the rects bundle is aligned
    to the original by index, so callers must subset it with these.
    """

    extraction: SentinelExtraction
    kept_citation_indices: list[int] = field(default_factory=list)
    nodes_rejected: int = 0
    nodes_overridden: int = 0
    relationships_dropped: int = 0
    citations_dropped: int = 0
    refs_cleared: int = 0


class ReviewOverrideError(ValueError):
    """An override edits a locked field or produces an invalid ProposedNode."""


def validate_overrides(node: ProposedNode, overrides: dict[str, object]) -> ProposedNode:
    """Apply `overrides` to `node`, re-validating the result.

    Raises ReviewOverrideError on a locked/unknown field or a value the
    ProposedNode schema rejects — used both at apply time and by the PUT
    endpoint so a bad edit is refused when it's made, not at approval.
    """
    locked = _LOCKED_FIELDS & overrides.keys()
    if locked:
        raise ReviewOverrideError(
            f"Cannot override identity field(s) {sorted(locked)} on {node.temp_id!r}"
        )
    try:
        return ProposedNode.model_validate({**node.model_dump(mode="json"), **overrides})
    except Exception as e:  # pydantic.ValidationError — unknown field, bad type/enum
        raise ReviewOverrideError(
            f"Invalid override for {node.temp_id!r} ({node.name!r}): {e}"
        ) from e


def apply_review(
    extraction: SentinelExtraction,
    review: ExtractionReview | None,
) -> ReviewApplication:
    """Fold review verdicts into a new SentinelExtraction.

    Rejected proposals are removed together with every relationship and
    citation that references them; overrides are applied and re-validated.
    A None/empty review returns the extraction unchanged (identity).
    """
    if review is None or not review.verdicts:
        return ReviewApplication(
            extraction=extraction,
            kept_citation_indices=list(range(len(extraction.citations))),
        )

    rejected = review.rejected_temp_ids()
    app = ReviewApplication(extraction=extraction, nodes_rejected=0)

    nodes: list[ProposedNode] = []
    for p in extraction.proposed_nodes:
        if p.temp_id in rejected:
            app.nodes_rejected += 1
            continue
        v = review.verdicts.get(p.temp_id)
        if v is not None and v.verdict == "overridden" and v.overrides:
            p = validate_overrides(p, v.overrides)
            app.nodes_overridden += 1
        # Clear cross-references into rejected proposals so node_factory
        # doesn't skip this (accepted) node over a dangling temp_id.
        cleared = {f: None for f in _REF_FIELDS if getattr(p, f) in rejected}
        if cleared:
            p = p.model_copy(update=cleared)
            app.refs_cleared += len(cleared)
        nodes.append(p)

    relationships = []
    for r in extraction.proposed_relationships:
        if r.src_temp_id in rejected or r.dst_temp_id in rejected:
            app.relationships_dropped += 1
            continue
        relationships.append(r)

    citations, kept_indices = [], []
    for i, c in enumerate(extraction.citations):
        if c.node_temp_id in rejected:
            app.citations_dropped += 1
            continue
        citations.append(c)
        kept_indices.append(i)

    app.extraction = extraction.model_copy(update={
        "proposed_nodes": nodes,
        "proposed_relationships": relationships,
        "citations": citations,
    })
    app.kept_citation_indices = kept_indices
    return app
