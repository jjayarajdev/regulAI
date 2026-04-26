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


// ─────────────────────────────────────────────────────────────────────
//  Operational questions (daily decisions)
// ─────────────────────────────────────────────────────────────────────


// 0.11 "What does an HB 2067 cancellation/nonrenewal/declination notice
//       need to contain?"
//      A claims-systems analyst's question — they're building the
//      Notice extract pipeline and need the complete spec in one view.
MATCH (l:RecordLayout {name: "Notice Record Layout"})<-[:CONTAINED_IN]-(f:FieldRequirement)
WHERE NOT f.name STARTS WITH "SKIP"
OPTIONAL MATCH (f)-[:CODED_BY]->(:CodeList)-[:HAS_VALUE]->(cv:CodeValue)
RETURN
  f.position_start                          AS column,
  f.position_length                         AS width,
  f.field_name                              AS field,
  CASE WHEN f.is_required THEN "yes" ELSE "no" END  AS required,
  count(DISTINCT cv)                        AS legal_codes
ORDER BY f.position_start;


// 0.12 "Which Cause-of-Loss code applies to a wind/hail claim from a
//       named storm filed today?"
//      Decision support — "the system flagged this claim as wind, but
//      it was during a hurricane; what code is correct as of the
//      filing date?" The KG answers with the codes active right now,
//      letting the underwriter pick the right one.
MATCH (cl:CodeList {name: "Cause of Loss Code List"})-[:HAS_VALUE]->(cv:CodeValue)
WHERE coalesce(cv.effective_from, date("1970-01-01")) <= date()
  AND (cv.effective_to IS NULL OR cv.effective_to > date())
  AND (toLower(cv.name) CONTAINS "wind"
       OR toLower(cv.name) CONTAINS "storm"
       OR toLower(cv.name) CONTAINS "hail")
RETURN
  cv.code                                  AS code_to_use,
  cv.name                                  AS what_it_means,
  cv.effective_from                        AS in_effect_since;


// 0.13 "Show me all the HB 2067 reason codes our underwriters can use
//       on a non-renewal notice."
//      An underwriting team's question — they want the dropdown to
//      populate with every legal value, sorted by code.
MATCH (cl:CodeList {name: "Reason Code List (RCL) — Notice Record Layout col36"})
      -[:HAS_VALUE]->(cv:CodeValue)
RETURN cv.code AS code, cv.notes AS reason
ORDER BY cv.code;


// ─────────────────────────────────────────────────────────────────────
//  Audit & governance questions
// ─────────────────────────────────────────────────────────────────────


// 0.14 "Show me every regulatory document our Texas filings depend on."
//      Sources-of-truth catalog — what an external auditor would
//      ask to see first. One row per regulation, grouped by kind.
MATCH (d:RegulationDocument)
RETURN
  d.kind                                  AS kind,
  d.name                                  AS document,
  d.effective_from                        AS effective_from,
  d.source_url                            AS source_url
ORDER BY d.kind, d.name;


// 0.15 "Who is TICO and what authorizes them to require these filings?"
//      Provenance for the regulatory authority itself, not just the
//      rules. Walks: TICO → DESIGNATED_BY → TDI (the regulator) and
//      shows the rule that establishes the designation.
MATCH (tico:Organization {name: "TICO"})
OPTIONAL MATCH (tico)-[:DESIGNATED_BY]->(tdi:Organization)
OPTIONAL MATCH (rule:Rule) WHERE toLower(rule.name) CONTAINS "designated"
RETURN
  tico.name                                AS statistical_agent,
  tico.org_kind                            AS role,
  tdi.name                                 AS designated_by,
  collect(rule.name)[..3]                  AS authorizing_rules;


// 0.16 "Which of our reports has had the most regulatory churn?"
//      Risk indicator: reports with many superseded fields/codes are
//      the ones where IT systems are most likely to drift out of
//      compliance. Helps prioritize re-validation cycles.
MATCH (l:RecordLayout)<-[:CONTAINED_IN]-(f:FieldRequirement)
OPTIONAL MATCH (f)-[:CODED_BY]->(:CodeList)-[:HAS_VALUE]->(cv:CodeValue)
  WHERE cv.status = "superseded" OR cv.effective_from IS NOT NULL
RETURN
  l.name                                   AS report,
  count(DISTINCT cv)                       AS values_with_lifecycle_changes
ORDER BY values_with_lifecycle_changes DESC;


// ─────────────────────────────────────────────────────────────────────
//  IT planning & cost questions
// ─────────────────────────────────────────────────────────────────────


// 0.17 "Which fields require the most distinct codes?"
//      A CIO's question: "what are the high-cardinality fields our
//      claim/policy systems must support?" Top entries are the ones
//      where data-quality is hardest, reference-table maintenance
//      is most costly, and validation is most error-prone.
MATCH (f:FieldRequirement)-[:CODED_BY]->(cl:CodeList)-[:HAS_VALUE]->(cv:CodeValue)
WHERE NOT f.name STARTS WITH "SKIP"
WITH f, count(DISTINCT cv) AS n_codes
RETURN
  f.field_name                             AS field,
  f.position_start                         AS column,
  n_codes                                  AS distinct_legal_values
ORDER BY n_codes DESC LIMIT 10;


// 0.18 "Compare the broad Stat Plan Premium layout vs the Homeowners-
//       specific one — what's different?"
//      A scoping question for IT: "do we need to support the wide
//      schema or just the HO subset?" Differences below show columns
//      that exist in one but not the other.
MATCH (l1:RecordLayout {name: "Premium Record Layout"})<-[:CONTAINED_IN]-(f1:FieldRequirement)
WITH collect(DISTINCT [f1.position_start, f1.field_name]) AS broad
MATCH (l2:RecordLayout {name: "Homeowners Premium Record Layout"})<-[:CONTAINED_IN]-(f2:FieldRequirement)
WITH broad, collect(DISTINCT [f2.position_start, f2.field_name]) AS ho
RETURN
  size(broad)                              AS broad_layout_field_count,
  size(ho)                                 AS ho_specific_field_count,
  size([x IN broad WHERE NOT x IN ho])    AS in_broad_only,
  size([x IN ho WHERE NOT x IN broad])    AS in_ho_only;


// ─────────────────────────────────────────────────────────────────────
//  Strategic oversight questions
// ─────────────────────────────────────────────────────────────────────


// 0.19 "What's the latest regulation update applied to our system?"
//      Recency / freshness — answer to "when was our regulatory
//      knowledge base last updated?" Looks across BulletinOverrides
//      and document effective dates.
MATCH (b:BulletinOverride)
WITH b ORDER BY b.effective_date DESC LIMIT 5
RETURN
  b.name                                   AS update_name,
  b.effective_date                         AS effective_date,
  b.notes                                  AS summary;


// 0.20 "What's the complete spec for a Premium filing in November 2026?"
//      Point-in-time complete spec — what fields are active, what
//      codes are legal, all pinned to the as-of date. Useful for
//      "rebuild our pipeline for the November cutover" or "what
//       would we have filed if it had been November already."
WITH date("2026-11-01") AS as_of
MATCH (l:RecordLayout {name: "Premium Record Layout"})<-[:CONTAINED_IN]-(f:FieldRequirement)
WHERE coalesce(f.effective_from, date("1970-01-01")) <= as_of
  AND (f.effective_to IS NULL OR f.effective_to > as_of)
  AND NOT f.name STARTS WITH "SKIP"
OPTIONAL MATCH (f)-[:CODED_BY]->(:CodeList)-[:HAS_VALUE]->(cv:CodeValue)
  WHERE coalesce(cv.effective_from, date("1970-01-01")) <= as_of
    AND (cv.effective_to IS NULL OR cv.effective_to > as_of)
RETURN
  f.position_start                         AS column,
  f.field_name                             AS field,
  count(DISTINCT cv)                       AS active_codes_in_nov
ORDER BY f.position_start;
