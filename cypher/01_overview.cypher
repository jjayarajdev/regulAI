// ─────────────────────────────────────────────────────────────────────
//  RegulAI — KG Overview
// ─────────────────────────────────────────────────────────────────────
//  Everything in the graph at a glance. Run these first to orient
//  yourself when opening Neo4j Browser.
// ─────────────────────────────────────────────────────────────────────


// 1.1  Node count by type
//      What is in the KG, in one row per node type.
MATCH (n:GRENode)
RETURN labels(n)[1] AS type, count(n) AS count
ORDER BY count DESC;


// 1.2  Relationship count by type
MATCH ()-[r]->()
RETURN type(r) AS rel_type, count(r) AS count
ORDER BY count DESC;


// 1.3  All RegulationDocuments + their kind
MATCH (d:RegulationDocument)
RETURN d.name AS document, d.kind AS kind, d.effective_from AS effective_from
ORDER BY d.name;


// 1.4  All RecordLayouts with their connected field counts
//      (any layout with 0 fields is a phantom — `make rebuild-kg` keeps the canonical 6)
MATCH (l:RecordLayout)
OPTIONAL MATCH (f:FieldRequirement)
  WHERE (f)-[:CONTAINED_IN]->(l) OR (l)-[:REQUIRES]->(f)
RETURN l.name AS layout, count(DISTINCT f) AS field_count
ORDER BY field_count DESC, l.name;


// 1.5  Top 20 nodes with the most outgoing relationships (graph hubs)
MATCH (n:GRENode)-[r]->()
RETURN labels(n)[1] AS type, n.name AS name, count(r) AS out_degree
ORDER BY out_degree DESC LIMIT 20;
