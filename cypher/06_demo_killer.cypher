// ─────────────────────────────────────────────────────────────────────
//  RegulAI — The Killer Demo Queries
// ─────────────────────────────────────────────────────────────────────
//  When demoing to a compliance audience, run these in order. They
//  tell the whole story in five queries.
// ─────────────────────────────────────────────────────────────────────


// 6.1  ONE QUERY — Premium record's entire schema
//      "What does TICO actually want in a Premium submission?"
MATCH (l:RecordLayout {name: "Premium Record Layout"})<-[:CONTAINED_IN]-(f:FieldRequirement)
OPTIONAL MATCH (f)-[:CODED_BY]->(cl:CodeList)-[:HAS_VALUE]->(cv:CodeValue)
RETURN
  f.position_start AS col,
  f.field_name     AS field,
  f.format         AS format,
  collect(DISTINCT cv.code)[..6] AS first_6_codes
ORDER BY f.position_start;


// 6.2  ONE QUERY — what goes in column 5–6 today?
//      Live point-in-time question, answered in ms.
MATCH (f:FieldRequirement {field_name: "Record Type", position_start: 5})
      -[:CODED_BY]->(:CodeList)-[:HAS_VALUE]->(cv:CodeValue)
WHERE coalesce(cv.effective_from, date("1970-01-01")) <= date()
  AND (cv.effective_to IS NULL OR cv.effective_to > date())
RETURN cv.code AS code, cv.notes AS meaning
ORDER BY cv.code;


// 6.3  ONE QUERY — full provenance for a single fact
//      "How do you know Cause-of-Loss code 26 means Named Storm Wind?"
//      Walks all the way from the value, through the codelist, to the
//      bulletin override that introduced it, to the bulletin's effective
//      date and the rule it cites.
MATCH (cv:CodeValue {code: "26"})
WHERE cv.name CONTAINS "Named Storm"
OPTIONAL MATCH (cl:CodeList)-[:HAS_VALUE]->(cv)
OPTIONAL MATCH (b:BulletinOverride)
  WHERE (b)-[:OVERRIDES]->(cl) OR (b)-[:OVERRIDES]->(:CodeValue)
OPTIONAL MATCH (cv)-[:CITES]->(rule:Rule)-[:CONTAINED_IN]->(d:RegulationDocument)
RETURN cv, cl, b, rule, d;


// 6.4  ONE QUERY — bulletin diff visualization
//      Renders: bulletin → CodeList it overrides → before/after CodeValues.
//      The most visually punchy slide in Browser's graph view.
MATCH (b:BulletinOverride {name: "Named Storm Cause of Loss Reporting Override"})
OPTIONAL MATCH (b)-[o:OVERRIDES]->(target)
OPTIONAL MATCH (cl:CodeList {name: "Cause of Loss Code List"})-[:HAS_VALUE]->(cv:CodeValue)
RETURN b, o, target, cl, cv LIMIT 30;


// 6.5  ONE QUERY — KG can simulate an insurer submission
//      Returns the data the sample-record generator uses to produce
//      a compliant 200-char Premium record.
MATCH (l:RecordLayout {name: "Premium Record Layout"})<-[:CONTAINED_IN]-(f:FieldRequirement)
OPTIONAL MATCH (f)-[:CODED_BY]->(:CodeList)-[:HAS_VALUE]->(cv:CodeValue)
  WHERE coalesce(cv.effective_from, date("1970-01-01")) <= date()
    AND (cv.effective_to IS NULL OR cv.effective_to > date())
RETURN
  f.position_start AS col,
  f.position_length AS len,
  f.field_name AS field,
  collect(DISTINCT cv.code) AS legal_codes_today
ORDER BY f.position_start;
