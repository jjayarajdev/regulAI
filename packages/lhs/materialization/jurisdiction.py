"""Jurisdiction tagging for materialized extractions — the generalized form
of scripts/materialize_florida_extraction.py.

materialize() writes nodes with the GRENodeBase default jurisdiction_code
(US-TX). When a document belongs to another state, the approve flow calls
these helpers to:

  1. resolve whatever the user typed ("Oklahoma", "ok", "US-OK") to a code
  2. ensure the Jurisdiction node exists (MERGE — idempotent)
  3. snapshot node ids before materialize, diff after
  4. re-tag the newly created nodes and re-point their APPLIES_IN edge

Tagging is a no-op for US-TX (already the default) and for unresolvable
input — approve never fails because a jurisdiction couldn't be parsed; it
just materializes untagged and reports that back.
"""

from __future__ import annotations

import datetime as dt

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

# state name (lowered) → USPS code. Covers the 50 states + DC.
_STATE_CODES: dict[str, str] = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "district of columbia": "DC", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN",
    "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI",
    "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "montana": "MT",
    "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}
_CODE_TO_NAME: dict[str, str] = {v: k.title() for k, v in _STATE_CODES.items()}
_VALID_CODES = set(_STATE_CODES.values())


def resolve_jurisdiction(text: str | None) -> tuple[str, str] | None:
    """Best-effort parse of user input to (code, name), e.g. ('US-OK', 'Oklahoma').

    Accepts 'US-OK', 'OK', 'Oklahoma', 'Oklahoma — Insurance Department', in
    any case. Returns None when nothing matches — callers treat that as
    "materialize untagged", never as an error.
    """
    if not text or not text.strip():
        return None
    raw = text.strip()
    # 'US-XX' / bare 'XX'
    compact = raw.upper().replace("US-", "", 1) if raw.upper().startswith("US-") else raw.upper()
    if compact in _VALID_CODES:
        return f"US-{compact}", _CODE_TO_NAME[compact]
    # Full state name, possibly with trailing decoration ('California — DOI')
    lowered = raw.lower()
    for name, code in _STATE_CODES.items():
        if lowered == name or lowered.startswith(name + " ") or lowered.startswith(name + "—") or lowered.startswith(name + " —"):
            return f"US-{code}", name.title()
    return None


def ensure_jurisdiction(gre: Neo4jGREAdapter, code: str, name: str) -> None:
    """MERGE the Jurisdiction node for `code` (idempotent, mirrors seed shape)."""
    now_iso = dt.datetime.now(dt.UTC).isoformat()
    with gre.driver.session(database=gre.database) as s:
        s.run(
            """
            MERGE (j:GRENode:Jurisdiction {id: $jid})
            ON CREATE SET
                j.type = 'Jurisdiction',
                j.name = $name,
                j.jurisdiction_code = $code,
                j.jurisdiction_name = $name,
                j.jurisdiction_type = 'state',
                j.parent_jurisdiction_code = 'US',
                j.version = 1,
                j.status = 'approved',
                j.created_at = $now,
                j.created_by = 'approve_jurisdiction_tagging'
            """,
            jid=f"jur:{code}", code=code, name=name, now=now_iso,
        )


def snapshot_node_ids(gre: Neo4jGREAdapter) -> set[str]:
    """All GRENode ids — diffed after materialize to find the new nodes."""
    with gre.driver.session(database=gre.database) as s:
        return {r["id"] for r in s.run("MATCH (n:GRENode) RETURN n.id AS id")}


def retag_new_nodes(gre: Neo4jGREAdapter, new_ids: set[str], code: str) -> dict:
    """Set jurisdiction_code on the new nodes and re-point APPLIES_IN.

    Removes any APPLIES_IN edge to a *different* state jurisdiction (the
    US-TX default, typically) before adding the target edge — federal (US)
    scoping, if any, is left alone.
    """
    if not new_ids:
        return {"retagged": 0, "edges_rewired": 0}
    with gre.driver.session(database=gre.database) as s:
        retagged = s.run(
            """
            MATCH (n:GRENode)
            WHERE n.id IN $ids
              AND NOT 'Jurisdiction' IN labels(n)
              AND NOT 'Regulator' IN labels(n)
              AND NOT 'KGAuditEntry' IN labels(n)
            SET n.jurisdiction_code = $code
            RETURN count(n) AS n
            """,
            ids=list(new_ids), code=code,
        ).single()["n"]
        edges_rewired = s.run(
            """
            MATCH (n:GRENode)
            WHERE n.id IN $ids
              AND NOT 'Jurisdiction' IN labels(n)
              AND NOT 'KGAuditEntry' IN labels(n)
            OPTIONAL MATCH (n)-[old:APPLIES_IN]->(other:Jurisdiction)
            WHERE other.jurisdiction_code <> $code AND other.jurisdiction_code <> 'US'
            DELETE old
            WITH DISTINCT n
            MATCH (j:Jurisdiction {jurisdiction_code: $code})
            MERGE (n)-[:APPLIES_IN]->(j)
            RETURN count(n) AS n
            """,
            ids=list(new_ids), code=code,
        ).single()["n"]
    return {"retagged": retagged, "edges_rewired": edges_rewired}
