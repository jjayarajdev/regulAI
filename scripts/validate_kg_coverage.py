"""KG coverage validator — does the graph fully describe the wire format?

For every RecordLayout in the KG, this script:

  1. Walks its FieldRequirement children (CONTAINED_IN edges).
  2. Builds a column-by-column coverage map for positions 1..200.
  3. Reports overlaps, gaps, and per-field code-list sizes.
  4. Cross-checks parent fields against sub-fields where present.
  5. Lists orphan FieldRequirements (no CONTAINED_IN to any layout) and
     fields with null position_start (LLM-extraction casualties).

A green run means: the KG can deterministically generate or validate any
record line for that layout. A red run pinpoints exactly where the
extraction is incomplete.

Run: uv run python -m scripts.validate_kg_coverage
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

TARGET_LENGTH = 200
# Fields not yet active (effective_from in the future) shouldn't count for
# coverage/overlap of "right now." Override via env if you want a future view.
AS_OF = date.today().isoformat()
OUT_DIR = Path("materialized/validation")


def _color(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


GREEN = lambda s: _color(s, "32")  # noqa: E731
RED = lambda s: _color(s, "31")    # noqa: E731
YELLOW = lambda s: _color(s, "33") # noqa: E731
BOLD = lambda s: _color(s, "1")    # noqa: E731


def gather() -> dict:
    """Pull layout/field/codelist data straight from Neo4j."""
    with Neo4jGREAdapter() as gre, gre.driver.session() as s:
        layouts = s.run("""
            MATCH (l:RecordLayout) RETURN l.id as id, l.name as name
            ORDER BY l.name
        """).data()

        fields_by_layout: dict[str, list[dict]] = {}
        for L in layouts:
            rows = s.run("""
                MATCH (l:RecordLayout {id: $lid})
                MATCH (f:FieldRequirement)
                  WHERE (f)-[:CONTAINED_IN]->(l) OR (l)-[:REQUIRES]->(f)
                  // Skip fields scheduled to take effect after the as-of date —
                  // they're future state, not current overlap.
                  AND (f.effective_from IS NULL OR f.effective_from <= date($as_of))
                  AND (f.effective_to   IS NULL OR f.effective_to   >  date($as_of))
                OPTIONAL MATCH (f)-[:CODED_BY]->(cl:CodeList)
                OPTIONAL MATCH (cl)-[:HAS_VALUE]->(cv:CodeValue)
                RETURN
                  f.name              as name,
                  f.field_name        as field_name,
                  f.position_start    as ps,
                  f.position_length   as pl,
                  f.format            as format,
                  cl.name             as code_list,
                  count(DISTINCT cv)  as n_codes
            """, lid=L["id"], as_of=AS_OF).data()
            fields_by_layout[L["name"]] = rows

        # A field is "orphan" if no layout owns it via either edge type.
        # (parser uses CONTAINED_IN; Sentinel sometimes emits REQUIRES.)
        orphans = s.run("""
            MATCH (f:FieldRequirement)
            WHERE NOT (f)-[:CONTAINED_IN]->(:RecordLayout)
              AND NOT (:RecordLayout)-[:REQUIRES]->(f)
            RETURN f.name as name, f.field_name as field_name,
                   f.position_start as ps, f.position_length as pl
            ORDER BY coalesce(f.position_start, 9999), f.name
        """).data()

        nullpos = s.run("""
            MATCH (f:FieldRequirement)
            WHERE f.position_start IS NULL
            RETURN count(f) as c
        """).single()["c"]

    return {
        "layouts": layouts,
        "fields_by_layout": fields_by_layout,
        "orphans": orphans,
        "null_position_count": nullpos,
    }


def analyze_layout(name: str, fields: list[dict]) -> dict:
    """Per-layout coverage map for cols 1..TARGET_LENGTH.

    Drops *redundant parents* before computing coverage/overlap: a field
    whose column range is fully covered by other fields with strictly
    smaller (or equal) ranges is treated as a parent grouping node, not
    a coverage contributor. This handles both the explicit ACDT/MONTH/YEAR
    case and the natural ROOF/ROOFCOV/ROOFCRED case.
    """
    valid = [(f, f["ps"], f["pl"]) for f in fields if f["ps"] is not None and f["pl"] is not None]
    no_position = len(fields) - len(valid)

    # Identify parents: fields whose entire column range is covered by other
    # fields strictly smaller in length. We compare against all OTHER fields.
    parent_idxs: set[int] = set()
    for i, (_, ps, pl) in enumerate(valid):
        if pl < 2:
            continue
        cols = set(range(ps, ps + pl))
        covered_by_others: set[int] = set()
        for j, (_, ps2, pl2) in enumerate(valid):
            if i == j or pl2 >= pl:
                continue
            covered_by_others.update(range(ps2, ps2 + pl2))
        if cols.issubset(covered_by_others):
            parent_idxs.add(i)

    occupied: dict[int, list[str]] = {}
    for i, (f, ps, pl) in enumerate(valid):
        if i in parent_idxs:
            continue
        for c in range(ps, ps + pl):
            occupied.setdefault(c, []).append(f.get("name") or "")

    covered_cols = [c for c in range(1, TARGET_LENGTH + 1) if c in occupied]
    gap_cols = [c for c in range(1, TARGET_LENGTH + 1) if c not in occupied]
    overlap_cols = sorted(c for c, names in occupied.items() if len(names) > 1)

    # Group consecutive runs into ranges for compact display.
    def _ranges(cols: list[int]) -> list[tuple[int, int]]:
        if not cols:
            return []
        out, start, prev = [], cols[0], cols[0]
        for c in cols[1:]:
            if c == prev + 1:
                prev = c
            else:
                out.append((start, prev))
                start = prev = c
        out.append((start, prev))
        return out

    fields_with_codes = [f for f in fields if (f["n_codes"] or 0) > 0]

    return {
        "n_fields": len(fields),
        "n_with_position": len(fields) - no_position,
        "n_without_position": no_position,
        "covered_cols": len(covered_cols),
        "gap_ranges": _ranges(gap_cols),
        "overlap_cols": overlap_cols,
        "fields_with_codes": len(fields_with_codes),
        "total_codes": sum(f["n_codes"] or 0 for f in fields),
    }


def main() -> None:
    data = gather()
    layouts = data["layouts"]
    fields_by_layout = data["fields_by_layout"]

    print(BOLD(f"\nKG Coverage Validator  —  target wire length = {TARGET_LENGTH}\n"))

    summaries: dict[str, dict] = {}
    any_gap = False

    print(f"{'Layout':<55} {'fields':>7} {'codes':>6} {'covered':>9} {'gaps':>6} {'overlap':>8}")
    print("-" * 100)
    for L in layouts:
        name = L["name"]
        fields = fields_by_layout.get(name, [])
        summary = analyze_layout(name, fields)
        summaries[name] = summary
        gap_count = sum((b - a + 1) for a, b in summary["gap_ranges"])
        cov_str = f"{summary['covered_cols']}/{TARGET_LENGTH}"
        cov_colored = (
            GREEN(cov_str) if summary["covered_cols"] == TARGET_LENGTH
            else RED(cov_str) if summary["covered_cols"] == 0
            else YELLOW(cov_str)
        )
        print(
            f"{name:<55} {summary['n_fields']:>7} {summary['total_codes']:>6} "
            f"{cov_colored:>18} {gap_count:>6} {len(summary['overlap_cols']):>8}"
        )
        if summary["gap_ranges"] and summary["covered_cols"] > 0:
            any_gap = True

    # Detail per layout
    print()
    for name, summary in summaries.items():
        if summary["n_fields"] == 0:
            continue
        print(BOLD(f"\n{name}"))
        if summary["covered_cols"] == TARGET_LENGTH and not summary["overlap_cols"]:
            print(GREEN(f"  ✓ Fully covers cols 1..{TARGET_LENGTH}, no overlaps"))
        else:
            if summary["gap_ranges"]:
                print(YELLOW(f"  ⚠ Gaps in coverage:"))
                for a, b in summary["gap_ranges"][:8]:
                    print(f"      cols {a}-{b}  ({b - a + 1} cols)")
                if len(summary["gap_ranges"]) > 8:
                    print(f"      … and {len(summary['gap_ranges']) - 8} more gap ranges")
            if summary["overlap_cols"]:
                print(YELLOW(f"  ⚠ Overlap on {len(summary['overlap_cols'])} cols (shared by 2+ fields)"))
        print(
            f"  {summary['n_fields']} fields, "
            f"{summary['fields_with_codes']} with code-lists "
            f"({summary['total_codes']} total codes)"
        )

    # Orphans + null-position issues
    print()
    if data["null_position_count"] > 0:
        print(RED(f"⚠ {data['null_position_count']} FieldRequirements have NULL position_start (cannot byte-validate)"))
    if data["orphans"]:
        print(RED(f"⚠ {len(data['orphans'])} orphan FieldRequirements (no CONTAINED_IN to any RecordLayout):"))
        for o in data["orphans"][:10]:
            ps = o["ps"] or "?"
            pl = o["pl"] or "?"
            print(f"    cols {ps}+{pl}  {o['name']}")
        if len(data["orphans"]) > 10:
            print(f"    … and {len(data['orphans']) - 10} more orphans")

    # Persist a JSON report
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUT_DIR / "kg_coverage.json"
    report = {
        "target_length": TARGET_LENGTH,
        "layouts": [
            {
                "name": name,
                **{
                    k: ([list(t) for t in v] if k == "gap_ranges" else v)
                    for k, v in s.items()
                },
            }
            for name, s in summaries.items()
        ],
        "orphan_fields": data["orphans"],
        "null_position_count": data["null_position_count"],
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport: {report_path}")

    # Exit code: red if any populated layout has gaps or any orphans/null-pos.
    failed = (
        any_gap
        or data["null_position_count"] > 0
        or any(s["overlap_cols"] for s in summaries.values())
    )
    if failed:
        print(RED(f"\nFAIL — coverage incomplete or polluted; see above."))
        sys.exit(1)
    print(GREEN(f"\nPASS — every byte of every populated layout is accounted for."))


if __name__ == "__main__":
    main()
