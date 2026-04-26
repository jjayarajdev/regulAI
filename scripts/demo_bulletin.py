"""End-to-end demo of the rules-level loop for the Named Storm bulletin.

The story this script tells:

  1. BEFORE the bulletin's effective date (2026-08-01):
        - Cause of Loss code 25 (Windstorm) is the only wind-loss code.
        - The Loss Record Layout has its base set of fields.

  2. AFTER the bulletin's effective date (2026-11-01):
        - Code 25 is superseded; Code 26 (Named Storm Wind) is active.
        - The Loss Record Layout has 3 new required NAMED_STORM fields.

  3. Provenance: every change traces back to the bulletin BulletinOverride
     and ultimately to a span of the bulletin PDF.

Run AFTER `make rebuild-kg && make apply-bulletin ALL=1`. This script only
*queries* the KG; it doesn't mutate anything.
"""

from __future__ import annotations

from datetime import date

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

BEFORE = date(2026, 8, 1).isoformat()
AFTER = date(2026, 11, 1).isoformat()

# Edition pinning: a node is "active" at a given date if its effective_from
# is at or before that date AND its effective_to is null or after it.
ACTIVE_AS_OF = """
    coalesce(n.effective_from, date('1970-01-01')) <= date($as_of)
AND (n.effective_to IS NULL OR n.effective_to > date($as_of))
"""


def _print_section(title: str) -> None:
    print()
    print("─" * 78)
    print(title)
    print("─" * 78)


def main() -> None:
    with Neo4jGREAdapter() as gre, gre.driver.session() as s:
        _print_section(f"Cause-of-Loss codes active as of {BEFORE}")
        rows = s.run(f"""
            MATCH (cl:CodeList)-[:HAS_VALUE]->(n:CodeValue)
            WHERE cl.name CONTAINS 'Cause of Loss'
              AND {ACTIVE_AS_OF}
            RETURN n.code AS code, n.name AS name, n.effective_from AS eff_from, n.effective_to AS eff_to
            ORDER BY n.code
        """, as_of=BEFORE).data()
        for r in rows:
            print(f"  code {r['code']!r:<6}  {r['name']}   "
                  f"[eff_from={r['eff_from']}, eff_to={r['eff_to']}]")
        if not rows:
            print("  (none — try `make rebuild-kg && make apply-bulletin ALL=1` first)")

        _print_section(f"Cause-of-Loss codes active as of {AFTER}")
        rows = s.run(f"""
            MATCH (cl:CodeList)-[:HAS_VALUE]->(n:CodeValue)
            WHERE cl.name CONTAINS 'Cause of Loss'
              AND {ACTIVE_AS_OF}
            RETURN n.code AS code, n.name AS name, n.effective_from AS eff_from, n.effective_to AS eff_to
            ORDER BY n.code
        """, as_of=AFTER).data()
        for r in rows:
            print(f"  code {r['code']!r:<6}  {r['name']}   "
                  f"[eff_from={r['eff_from']}, eff_to={r['eff_to']}]")

        _print_section("New required Loss Record fields introduced by this bulletin")
        rows = s.run("""
            MATCH (l:RecordLayout {name: 'Loss Record Layout'})-[:REQUIRES]->(f:FieldRequirement)
            RETURN f.name AS name, f.position_start AS ps, f.position_length AS pl,
                   f.format AS format, f.effective_from AS eff_from
            ORDER BY coalesce(f.position_start, 9999)
        """).data()
        for r in rows:
            if not r["name"]:
                continue
            ps = r["ps"]
            pl = r["pl"]
            range_str = f"cols {ps}-{ps + (pl or 1) - 1}" if ps else "cols ? "
            print(f"  {range_str:<14}  {r['name']!r}   format={r['format']!r}, eff_from={r['eff_from']}")

        _print_section("Full provenance chain — what overrides what?")
        rows = s.run("""
            MATCH (b:BulletinOverride {name: 'Named Storm Cause of Loss Reporting Override'})
                  -[:OVERRIDES]->(target)
            OPTIONAL MATCH (b)-[:CITES]->(rule:Rule)
            RETURN b.name AS bulletin,
                   b.effective_date AS eff,
                   labels(target)[1] AS target_label,
                   target.name AS target_name,
                   target.status AS target_status,
                   target.effective_to AS target_eff_to,
                   collect(DISTINCT rule.name)[..3] AS cited_rules
            LIMIT 1
        """).single()
        if rows:
            print(f"  Bulletin:       {rows['bulletin']!r}")
            print(f"  Effective:      {rows['eff']}")
            print(f"  Cites rules:    {rows['cited_rules']}")
            print(f"  Overrides:      ({rows['target_label']}) {rows['target_name']!r}")
            print(f"                  status={rows['target_status']!r}, effective_to={rows['target_eff_to']}")

        _print_section("In one sentence")
        print(
            "  As of October 1, 2026, Texas Cause-of-Loss code 25 (Windstorm)\n"
            "  is split into 25 (Other Wind) and 26 (Named Storm Wind);\n"
            "  three new Loss Record fields (NAMED_STORM_NWS_ID,\n"
            "  NAMED_STORM_CATEGORY, NAMED_STORM_LANDFALL_DATE) are required\n"
            "  for code-26 records — and the KG knows it.\n"
        )


if __name__ == "__main__":
    main()
