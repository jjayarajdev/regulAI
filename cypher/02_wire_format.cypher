// ─────────────────────────────────────────────────────────────────────
//  RegulAI — Wire Format Exploration
// ─────────────────────────────────────────────────────────────────────
//  The KG as the executable schema for TICO submissions. These queries
//  walk a record layout column-by-column and prove the KG is operationally
//  complete (every byte of every record has a FieldRequirement).
// ─────────────────────────────────────────────────────────────────────


// 2.1  Premium Record Layout — full column-by-column structure
//      The 71 fields covering cols 1..200 of a Premium record, with
//      their format and code-list size.
MATCH (l:RecordLayout {name: "Premium Record Layout"})<-[:CONTAINED_IN]-(f:FieldRequirement)
OPTIONAL MATCH (f)-[:CODED_BY]->(cl:CodeList)
OPTIONAL MATCH (cl)-[:HAS_VALUE]->(cv:CodeValue)
RETURN
  f.position_start          AS col,
  f.position_length         AS len,
  f.field_name              AS field,
  f.format                  AS format,
  count(DISTINCT cv)        AS n_codes
ORDER BY f.position_start;


// 2.2  What does column 5–6 (RECORD TYPE) mean?
//      The KG's answer to "what are the legal values at this column?"
MATCH (f:FieldRequirement {field_name: "Record Type", position_start: 5})
      -[:CODED_BY]->(cl:CodeList)-[:HAS_VALUE]->(cv:CodeValue)
RETURN cv.code AS code, cv.notes AS meaning
ORDER BY cv.code;


// 2.3  Compare Stat Plan Premium Record vs Homeowners Premium Record
//      The Stat Plan layout is the broad residential schema; the HO layout
//      is the operational subset insurers actually ship.
MATCH (l:RecordLayout)
WHERE l.name IN ["Premium Record Layout", "Homeowners Premium Record Layout"]
OPTIONAL MATCH (l)<-[:CONTAINED_IN]-(f:FieldRequirement)
RETURN l.name AS layout, count(DISTINCT f) AS fields
ORDER BY l.name;


// 2.4  Which fields have NO code list (free-form)?
//      Useful as a coverage check: free-form fields can't be enum-validated;
//      in the demo they're things like POLICY identifiers, dates, dollar amounts.
MATCH (l:RecordLayout {name: "Premium Record Layout"})<-[:CONTAINED_IN]-(f:FieldRequirement)
WHERE NOT (f)-[:CODED_BY]->(:CodeList)
  AND NOT f.name STARTS WITH "SKIP"
RETURN f.position_start AS col, f.field_name AS field, f.format AS format
ORDER BY f.position_start;


// 2.5  Show the whole graph slice for one layout — visual rendering in Browser
//      Triggers the graph-view canvas: layout → fields → codelists → codevalues.
MATCH (l:RecordLayout {name: "Notice Record Layout"})<-[:CONTAINED_IN]-(f:FieldRequirement)
OPTIONAL MATCH (f)-[:CODED_BY]->(cl:CodeList)-[:HAS_VALUE]->(cv:CodeValue)
RETURN l, f, cl, cv LIMIT 200;
