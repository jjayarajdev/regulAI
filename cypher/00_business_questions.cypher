// ─────────────────────────────────────────────────────────────────────
//  RegulAI — Business Questions (Compliance Officer's View)
// ─────────────────────────────────────────────────────────────────────
//  Real questions a compliance officer, auditor, or insurance executive
//  would ask. Each query answers ONE business question. The graph
//  technology underneath is incidental — what matters is the answer.
//
//  Run them in order during a demo. Each one builds on the previous.
// ─────────────────────────────────────────────────────────────────────


// 0.1  "What does Texas require us to file?"
//      The four monthly reports an insurer must submit to TICO. Each has
//      its own record layout — a fixed-width 200-character format. This
//      is the universe of regulatory output the rest of our compliance
//      stack has to produce.
MATCH (l:RecordLayout)
WHERE l.name IN ["Premium Record Layout", "Loss Record Layout",
                 "Notice Record Layout", "Notice Count Record Layout"]
OPTIONAL MATCH (l)<-[:CONTAINED_IN]-(f:FieldRequirement)
RETURN
  l.name                           AS report_we_must_file,
  count(DISTINCT f)                AS fields_per_record,
  "200-character fixed-width"      AS wire_format
ORDER BY l.name;


// 0.2  "What are the legal Cause-of-Loss codes RIGHT NOW?"
//      Filed today (any "today"), here are the values our claim system
//      may emit. Notice this query has NO hard-coded date — it asks the
//      KG for "what's in effect at this moment" and the KG answers
//      using its versioning. Codes that have been retired or aren't
//      yet effective are excluded automatically.
MATCH (cl:CodeList {name: "Cause of Loss Code List"})-[:HAS_VALUE]->(cv:CodeValue)
WHERE coalesce(cv.effective_from, date("1970-01-01")) <= date()
  AND (cv.effective_to IS NULL OR cv.effective_to > date())
RETURN
  cv.code                AS code_value,
  cv.name                AS what_it_means,
  cv.effective_from      AS in_effect_since
ORDER BY cv.code;


// 0.3  "What WAS legal as of August 2026, before the Named Storm bulletin?"
//      Same query, different date. Compliance officers ask this all the
//      time during audits: "what was the rule on the day this claim was
//      filed?" The KG knows.
MATCH (cl:CodeList {name: "Cause of Loss Code List"})-[:HAS_VALUE]->(cv:CodeValue)
WHERE coalesce(cv.effective_from, date("1970-01-01")) <= date("2026-08-01")
  AND (cv.effective_to IS NULL OR cv.effective_to > date("2026-08-01"))
RETURN cv.code AS code_value, cv.name AS what_it_means
ORDER BY cv.code;


// 0.4  "What changed when the Q3 2026 bulletin took effect?"
//      The complete impact of one regulation event, in one query.
//      Tells you: what got retired, what's new, when the change kicks in.
//      Without the KG, this would be a multi-page memo with footnotes.
MATCH (b:BulletinOverride {name: "Named Storm Cause of Loss Reporting Override"})
WITH b, date(b.effective_date) AS eff
OPTIONAL MATCH (b)-[:OVERRIDES]->(retired)
OPTIONAL MATCH (:CodeList {name: "Cause of Loss Code List"})-[:HAS_VALUE]->(new_code:CodeValue)
  WHERE new_code.effective_from = eff
OPTIONAL MATCH (:RecordLayout {name: "Loss Record Layout"})-[:REQUIRES]->(new_field:FieldRequirement)
  WHERE new_field.effective_from = eff
RETURN
  eff                                                                                  AS change_takes_effect,
  [x IN collect(DISTINCT retired.name)   WHERE x IS NOT NULL][..10]                    AS what_was_retired,
  [x IN collect(DISTINCT new_code.name)  WHERE x IS NOT NULL][..10]                    AS new_codes_introduced,
  [x IN collect(DISTINCT new_field.name) WHERE x IS NOT NULL]                          AS new_fields_now_required;


// 0.5  "What does TICO want in column 5–6 of every Premium record?"
//      The most concrete schema question. The result IS the spec.
//      An IT system shipping anything other than these values for col 5-6
//      will be rejected.
MATCH (f:FieldRequirement {field_name: "Record Type", position_start: 5})
      -[:CODED_BY]->(:CodeList)-[:HAS_VALUE]->(cv:CodeValue)
RETURN
  cv.code                          AS valid_value,
  cv.notes                         AS meaning;


// 0.6  "For an audit: prove the regulatory basis for one of our reporting fields"
//      Pick ANY field that appears on our filings; the KG walks the chain
//      back to the page in the source PDF. This is the audit answer to
//      "why does your system code this column this way?"
//      For demo: pick the Notice Record Layout's RSI (Reason Source Indicator).
MATCH (f:FieldRequirement {field_name: "Reason Source Indicator"})
OPTIONAL MATCH (f)-[c:CITES]->(d:RegulationDocument)
RETURN
  f.field_name                     AS field_in_our_report,
  f.position_start                 AS column_position,
  f.position_length                AS column_width,
  d.name                           AS regulatory_source,
  c.char_start                     AS span_in_source,
  c.char_end                       AS span_end,
  c.rects_json IS NOT NULL         AS has_pdf_rectangle_provenance;


// 0.7  "If our claim system emits a record with Cause of Loss = 25 for a
//       loss filed November 2026, will TICO accept it?"
//      The most concrete operational compliance question. Answer the KG
//      gives: "no, code 25 was superseded effective 2026-09-30; for losses
//       on or after 2026-10-01 you must use 25 (Other Wind) or 26 (Named
//       Storm Wind) and provide the new NAMED_STORM fields."
MATCH (cv:CodeValue {code: "25"})<-[:HAS_VALUE]-(cl:CodeList {name: "Cause of Loss Code List"})
RETURN
  cv.code                                 AS code,
  cv.status                               AS status_today,
  cv.effective_to                         AS retired_on,
  CASE WHEN cv.effective_to < date("2026-11-01")
       THEN "INVALID — superseded before this filing date"
       ELSE "valid"
  END                                     AS verdict_for_2026_11_01_filing;


// 0.8  "How big is the compliance burden? How many distinct values does our
//       IT system need to know about?"
//      Headline number for the CIO. Every code listed below is a value the
//      claim/policy system must support emitting correctly.
MATCH (n:GRENode)
WHERE labels(n)[1] IN ["FieldRequirement", "CodeValue", "RecordLayout"]
WITH labels(n)[1] AS thing, count(n) AS n
RETURN
  CASE thing
    WHEN "RecordLayout"     THEN "Reports we file"
    WHEN "FieldRequirement" THEN "Distinct fields across all reports"
    WHEN "CodeValue"        THEN "Distinct enumerated values our IT must support"
  END                              AS item,
  n                                AS count
ORDER BY count;


// 0.9  "Show me everything the bulletin changed — for the change-management memo"
//      A natural-language summary of the bulletin's effects, ready to drop
//      into an email to underwriting. The KG produces the change report.
MATCH (b:BulletinOverride {name: "Named Storm Cause of Loss Reporting Override"})
OPTIONAL MATCH (b)-[:CITES]->(rule:Rule)
RETURN
  b.name                                                       AS regulation_change,
  b.effective_date                                             AS effective_from,
  collect(DISTINCT rule.name)                                  AS sections_in_bulletin,
  b.notes                                                      AS plain_english_summary;


// 0.10 "Are there any inconsistencies in our regulatory data set?"
//      Three sanity checks rolled into one. Empty result = clean.
//      This is what a compliance officer wants to see before sign-off:
//      "no orphan rules, no missing layouts, no fields without source."
CALL {
  MATCH (l:RecordLayout) WHERE NOT (l)<-[:CONTAINED_IN]-(:FieldRequirement)
                          AND NOT (l)-[:REQUIRES]->(:FieldRequirement)
  RETURN "report layout has no fields" AS issue, l.name AS detail
  UNION
  MATCH (f:FieldRequirement) WHERE NOT (f)-[:CONTAINED_IN]->(:RecordLayout)
                              AND NOT (:RecordLayout)-[:REQUIRES]->(f)
  RETURN "field not assigned to any report" AS issue, f.name AS detail
  UNION
  MATCH (n:GRENode)
  WHERE NOT (n)-[:CITES]->(:RegulationDocument)
    AND NOT n:RegulationDocument
    AND NOT n:Organization
    AND NOT n:StatPlanEdition
    AND NOT n:CodeValue
    AND NOT n:CodeList
  RETURN "node has no regulatory citation" AS issue, labels(n)[1] + ": " + n.name AS detail
}
RETURN issue, detail
ORDER BY issue, detail
LIMIT 20;
