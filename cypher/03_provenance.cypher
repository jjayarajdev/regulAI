// ─────────────────────────────────────────────────────────────────────
//  RegulAI — Citation Provenance
// ─────────────────────────────────────────────────────────────────────
//  Every fact in the KG carries a CITES edge back to the regulation
//  document, with character offsets AND PyMuPDF-derived PDF rectangles.
//  These queries prove the KG is its own audit trail — "why this rule?"
//  is a graph walk, not folklore.
// ─────────────────────────────────────────────────────────────────────


// 3.1  How a FieldRequirement traces to a regulation span
//      Pick a field, see the doc it cites, the char offset, and the
//      number of bytes of stored PDF rectangle JSON.
MATCH (f:FieldRequirement {field_name: "Record Type", position_start: 5})
      -[c:CITES]->(d:RegulationDocument)
RETURN
  f.field_name                          AS field,
  d.name                                AS document,
  c.char_start                          AS span_start,
  c.char_end                            AS span_end,
  size(c.rects_json)                    AS rect_payload_bytes,
  c.rects_json                          AS rects_json;


// 3.2  Click-through chain for code 25 (Windstorm)
//      CodeValue → CodeList → FieldRequirement → RecordLayout → RegulationDocument
MATCH path = (cv:CodeValue {code: "25"})
            <-[:HAS_VALUE]-(cl:CodeList)
RETURN cv, cl, path LIMIT 5;


// 3.3  All citations carrying PDF rectangle data
//      The hard provenance — every row corresponds to a highlighted region
//      visible in the side-by-side UI.
MATCH (n:GRENode)-[c:CITES]->(d:RegulationDocument)
WHERE c.rects_json IS NOT NULL
RETURN
  labels(n)[1]              AS node_type,
  n.name                    AS name,
  d.name                    AS doc,
  c.char_start              AS char_start,
  c.char_end                AS char_end
ORDER BY d.name, c.char_start LIMIT 20;


// 3.4  Citation count per document (extraction quality at a glance)
MATCH (d:RegulationDocument)<-[c:CITES]-(n:GRENode)
RETURN d.name AS document, count(c) AS citations
ORDER BY citations DESC;


// 3.5  Show me the full provenance for ONE node — used as the audit demo
//      Walks every CITES edge from a chosen node, with span info.
MATCH (n:GRENode)-[c:CITES]->(d:RegulationDocument)
WHERE n.name CONTAINS "Cause of Loss Code 25"
RETURN n, c, d;
