"""Read-only GraphQL surface on the KG (Phase 1.6).

Mounted at /api/lhs/kg/graphql. Resolvers read via Neo4jGREAdapter — no
mutations (extraction stays via the Python pipeline). Schema covers the
queries most useful for an external integrator or auditor:

    rules(section?, executable?)        list rules with filters
    rule(id)                            single rule with citations
    codeValues(codeListName?)           list code values
    codeLists(name?)                    list code lists
    documents()                         list regulation documents
    auditEntries(limit?)                recent KG audit entries

The schema is hand-defined (rather than auto-derived from Pydantic) so we
keep control over field naming, nullability, and what's exposed. Adding a
field is one entry here + one resolver line.
"""

from __future__ import annotations

from typing import Optional

import strawberry

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter


# ── Output types ──────────────────────────────────────────────────────────

@strawberry.type
class Citation:
    full_citation: Optional[str] = None
    text: Optional[str] = None
    name: Optional[str] = None
    propagated_from: Optional[str] = None  # set when CITES carries the propagation marker


@strawberry.type
class Rule:
    id: str
    name: str
    rule_number: Optional[str] = None
    section: Optional[str] = None
    severity: Optional[str] = None
    target_table: Optional[str] = None
    version: Optional[int] = None
    status: Optional[str] = None
    effective_from: Optional[str] = None
    effective_until: Optional[str] = None
    violation_reason: Optional[str] = None
    citation: Optional[str] = None


@strawberry.type
class CodeValue:
    id: str
    code: str
    name: str
    description: Optional[str] = None
    code_list_id: Optional[str] = None
    version: Optional[int] = None
    status: Optional[str] = None


@strawberry.type
class CodeList:
    id: str
    name: str
    code_list_name: Optional[str] = None
    version: Optional[int] = None


@strawberry.type
class RegulationDocument:
    id: str
    name: str
    title: Optional[str] = None
    kind: Optional[str] = None
    bulletin_ref: Optional[str] = None
    version: Optional[int] = None


@strawberry.type
class KGAuditEntry:
    id: str
    action: str
    actor: str
    summary: Optional[str] = None
    occurred_at: Optional[str] = None
    affected_count: Optional[int] = None


# ── Helpers ───────────────────────────────────────────────────────────────

def _coerce_props(record_value) -> dict:
    """Extract a plain dict + coerce neo4j.time types to ISO strings."""
    import neo4j.time as nt
    raw = dict(record_value.items()) if record_value is not None else {}
    out = {}
    for k, v in raw.items():
        if isinstance(v, (nt.Date, nt.DateTime)):
            out[k] = str(v)
        else:
            out[k] = v
    return out


def _rule_from_node(props: dict) -> Rule:
    return Rule(
        id=str(props.get("id") or ""),
        name=props.get("name") or "",
        rule_number=props.get("rule_number"),
        section=props.get("section"),
        severity=props.get("severity"),
        target_table=props.get("target_table"),
        version=props.get("version"),
        status=props.get("status"),
        effective_from=props.get("effective_from"),
        effective_until=props.get("effective_until"),
        violation_reason=props.get("violation_reason"),
        citation=props.get("citation"),
    )


# ── Query root ────────────────────────────────────────────────────────────

@strawberry.type
class Query:
    @strawberry.field(description="List Rule nodes, optionally filtered by section letter or executable flag.")
    def rules(
        self,
        section: Optional[str] = None,
        executable: Optional[bool] = None,
    ) -> list[Rule]:
        with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
            cypher = "MATCH (r:Rule) WHERE 1=1"
            if section:
                cypher += " AND r.section = $section"
            if executable is not None:
                if executable:
                    cypher += " AND r.violation_sql IS NOT NULL"
                else:
                    cypher += " AND r.violation_sql IS NULL"
            cypher += " RETURN r ORDER BY r.rule_number, r.name"
            rows = s.run(cypher, section=section)
            return [_rule_from_node(_coerce_props(r["r"])) for r in rows]

    @strawberry.field(description="Look up one Rule by id.")
    def rule(self, id: str) -> Optional[Rule]:
        with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
            row = s.run("MATCH (r:Rule {id: $id}) RETURN r", id=id).single()
            if not row:
                return None
            return _rule_from_node(_coerce_props(row["r"]))

    @strawberry.field(description="List CodeValues, optionally scoped to one CodeList by name.")
    def code_values(self, code_list_name: Optional[str] = None) -> list[CodeValue]:
        with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
            if code_list_name:
                cypher = """
                    MATCH (cl:CodeList {name: $name})-[:HAS_VALUE]->(cv:CodeValue)
                    RETURN cv ORDER BY cv.code
                """
                rows = s.run(cypher, name=code_list_name)
            else:
                rows = s.run("MATCH (cv:CodeValue) RETURN cv ORDER BY cv.code")
            out: list[CodeValue] = []
            for r in rows:
                p = _coerce_props(r["cv"])
                out.append(CodeValue(
                    id=str(p.get("id") or ""),
                    code=p.get("code") or "",
                    name=p.get("name") or "",
                    description=p.get("description") or p.get("notes"),
                    code_list_id=p.get("code_list_id"),
                    version=p.get("version"),
                    status=p.get("status"),
                ))
            return out

    @strawberry.field(description="List CodeLists, optionally matching by name.")
    def code_lists(self, name: Optional[str] = None) -> list[CodeList]:
        with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
            if name:
                rows = s.run("MATCH (cl:CodeList) WHERE cl.name CONTAINS $n RETURN cl", n=name)
            else:
                rows = s.run("MATCH (cl:CodeList) RETURN cl ORDER BY cl.name")
            out = []
            for r in rows:
                p = _coerce_props(r["cl"])
                out.append(CodeList(
                    id=str(p.get("id") or ""),
                    name=p.get("name") or "",
                    code_list_name=p.get("code_list_name"),
                    version=p.get("version"),
                ))
            return out

    @strawberry.field(description="List all loaded RegulationDocuments.")
    def documents(self) -> list[RegulationDocument]:
        with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
            rows = s.run("MATCH (d:RegulationDocument) RETURN d ORDER BY d.title")
            out = []
            for r in rows:
                p = _coerce_props(r["d"])
                out.append(RegulationDocument(
                    id=str(p.get("id") or ""),
                    name=p.get("name") or "",
                    title=p.get("title"),
                    kind=p.get("kind"),
                    bulletin_ref=p.get("bulletin_ref"),
                    version=p.get("version"),
                ))
            return out

    @strawberry.field(description="Recent KG audit entries (mutations to the canon).")
    def audit_entries(self, limit: int = 20) -> list[KGAuditEntry]:
        if limit < 1 or limit > 200:
            limit = 20
        with Neo4jGREAdapter() as gre, gre.driver.session(database=gre.database) as s:
            rows = s.run(
                "MATCH (a:KGAuditEntry) RETURN a ORDER BY a.occurred_at DESC LIMIT $limit",
                limit=limit,
            )
            out = []
            for r in rows:
                p = _coerce_props(r["a"])
                out.append(KGAuditEntry(
                    id=str(p.get("id") or ""),
                    action=p.get("action") or "",
                    actor=p.get("actor") or "system",
                    summary=p.get("summary"),
                    occurred_at=p.get("occurred_at"),
                    affected_count=p.get("affected_count"),
                ))
            return out


# Exported schema — main.py mounts it at /api/lhs/kg/graphql
schema = strawberry.Schema(query=Query)
