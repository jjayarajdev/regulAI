// ─────────────────────────────────────────────────────────────────────
//  RegulAI — KG Hygiene & Validation
// ─────────────────────────────────────────────────────────────────────
//  Sanity checks. After `make rebuild-kg`, every result here should be
//  empty (or match expected counts). Used as a quick visual check that
//  the KG is in a clean state.
// ─────────────────────────────────────────────────────────────────────


// 5.1  Phantom RecordLayouts (no field connected)
//      Should be EMPTY after cleanup. Anything here is an LLM-extraction
//      variant of a parser-owned name.
MATCH (l:RecordLayout)
WHERE NOT (l)<-[:CONTAINED_IN]-(:FieldRequirement)
  AND NOT (l)-[:REQUIRES]->(:FieldRequirement)
RETURN l.name AS phantom_layout;


// 5.2  Orphan FieldRequirements (no layout)
//      Should be EMPTY. Anything here was extracted by Sentinel without
//      a layout binding.
MATCH (f:FieldRequirement)
WHERE NOT (f)-[:CONTAINED_IN]->(:RecordLayout)
  AND NOT (:RecordLayout)-[:REQUIRES]->(f)
RETURN f.name AS orphan_field, f.position_start AS col;


// 5.3  Fields with NULL position_start (cannot byte-validate)
//      Should be EMPTY for parser-owned layouts. A few may exist on
//      LLM-extracted prose nodes.
MATCH (f:FieldRequirement)
WHERE f.position_start IS NULL
RETURN f.name, f.field_name LIMIT 25;


// 5.4  Layout coverage map — sum of field lengths per layout
//      For every canonical layout this should add up to ~200 (after
//      excluding parents-with-subfields). Use this to spot gaps.
MATCH (l:RecordLayout)<-[:CONTAINED_IN]-(f:FieldRequirement)
RETURN l.name AS layout,
       count(f) AS fields,
       sum(coalesce(f.position_length, 0)) AS bytes_covered,
       max(f.position_start + coalesce(f.position_length, 1) - 1) AS max_col
ORDER BY l.name;


// 5.5  Citation rect coverage per document (data-quality signal)
//      Number of citations vs how many have rect data attached.
MATCH (n:GRENode)-[c:CITES]->(d:RegulationDocument)
RETURN d.name AS document,
       count(c) AS total_citations,
       count(CASE WHEN c.rects_json IS NOT NULL THEN 1 END) AS with_rects
ORDER BY d.name;


// 5.6  Duplicate detection — same name + type
//      Should be EMPTY. If anything appears, there's a dedup bug.
MATCH (a:GRENode), (b:GRENode)
WHERE a.id < b.id
  AND a.name = b.name
  AND labels(a) = labels(b)
RETURN a.name, labels(a)[1] AS type, count(*) AS duplicates;
