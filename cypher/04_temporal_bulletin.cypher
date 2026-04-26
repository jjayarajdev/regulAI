// ─────────────────────────────────────────────────────────────────────
//  RegulAI — Temporal Pinning + Bulletin Re-evaluation
// ─────────────────────────────────────────────────────────────────────
//  The rules-level loop in action. After `make rebuild-kg && make
//  apply-bulletin ALL=1`, these queries demonstrate that the KG is
//  edition-aware: a bulletin's effect depends on the as-of date.
// ─────────────────────────────────────────────────────────────────────


// 4.1  Cause-of-Loss codes ACTIVE as of 2026-08-01 (BEFORE bulletin)
//      Should show codes 05, 10, 25 (Windstorm), 30, 32, 75.
MATCH (cl:CodeList {name: "Cause of Loss Code List"})-[:HAS_VALUE]->(n:CodeValue)
WHERE coalesce(n.effective_from, date("1970-01-01")) <= date("2026-08-01")
  AND (n.effective_to IS NULL OR n.effective_to > date("2026-08-01"))
RETURN n.code AS code, n.name AS name,
       n.effective_from AS eff_from, n.effective_to AS eff_to
ORDER BY n.code;


// 4.2  Cause-of-Loss codes ACTIVE as of 2026-11-01 (AFTER bulletin)
//      Should show codes 05, 10, 26 (Named Storm Wind), 30, 32, 75
//      — code 25 is now superseded; code 26 has taken effect.
MATCH (cl:CodeList {name: "Cause of Loss Code List"})-[:HAS_VALUE]->(n:CodeValue)
WHERE coalesce(n.effective_from, date("1970-01-01")) <= date("2026-11-01")
  AND (n.effective_to IS NULL OR n.effective_to > date("2026-11-01"))
RETURN n.code AS code, n.name AS name,
       n.effective_from AS eff_from, n.effective_to AS eff_to
ORDER BY n.code;


// 4.3  Show every BulletinOverride and what it overrides
MATCH (b:BulletinOverride)-[:OVERRIDES]->(target)
RETURN
  b.name                 AS bulletin,
  b.effective_date       AS effective,
  labels(target)[1]      AS target_type,
  target.name            AS target_name,
  target.status          AS target_status,
  target.effective_to    AS target_eff_to
ORDER BY b.name, target_type;


// 4.4  Bulletin's full impact graph (visual)
//      Renders the bulletin → rules it cites → nodes it overrides
//      → new content it introduces.
MATCH (b:BulletinOverride {name: "Named Storm Cause of Loss Reporting Override"})
OPTIONAL MATCH (b)-[r1:CITES]->(rule:Rule)
OPTIONAL MATCH (b)-[r2:OVERRIDES]->(target)
OPTIONAL MATCH (rule)<-[:CITES]-(new_node)
  WHERE NOT (b)-[:OVERRIDES]->(new_node)
  AND NOT new_node:Rule AND NOT new_node:RegulationDocument
RETURN b, r1, rule, r2, target, new_node LIMIT 50;


// 4.5  New required Loss Record fields introduced by the bulletin
//      The 3 NAMED_STORM_* fields and their effective dates.
MATCH (l:RecordLayout {name: "Loss Record Layout"})-[:REQUIRES]->(f:FieldRequirement)
WHERE f.name CONTAINS "NAMED_STORM"
RETURN
  f.position_start          AS col,
  f.position_length         AS len,
  f.name                    AS field,
  f.format                  AS format,
  f.effective_from          AS effective_from
ORDER BY f.position_start;


// 4.6  All SUPERSEDES chains (versioning history)
//      Today only one chain (B-0008-25 → A.34) — but as bulletins
//      accumulate this query shows the full edit history of any rule.
MATCH (newer)-[s:SUPERSEDES]->(older)
RETURN labels(newer)[1] AS type,
       older.name AS old, newer.name AS new,
       newer.effective_from AS new_effective_from;
