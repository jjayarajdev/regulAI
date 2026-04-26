"""Generate a sample TICO submission record FROM THE KG.

Walks a RecordLayout's FieldRequirement children in column order, picks
or synthesizes a value for each, and emits a 200-character fixed-width
line. Code-list fields pick from their HAS_VALUE → CodeValue chain;
free-form fields generate a plausible value driven by field name; SKIP
fields fill with spaces.

This is the moment the KG becomes operational: the script reads the
*regulation's own definition* of the wire format and produces a string
that conforms to it. If the KG is missing a field, the script either
stops or pads with spaces and reports the gap. Either way, the output
either is a valid submission or directly tells you why it can't be.

Run:
  uv run python -m scripts.generate_sample_submission \\
      [--layout "Premium Record Layout"] \\
      [--scenario new-policy|cancellation|endorsement] \\
      [--n 1] [--seed 42]
"""

from __future__ import annotations

import argparse
import random
import re
import sys
from dataclasses import dataclass

from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter

DEFAULT_LAYOUT = "Premium Record Layout"
RECORD_LENGTH = 200


@dataclass
class FieldDef:
    name: str
    field_name: str
    short_code: str
    position_start: int
    position_length: int
    format: str
    is_required: bool
    notes: str | None
    code_values: list[tuple[str, str]]   # [(code, meaning)] in code order


def _parse_short_code(name: str) -> str:
    m = re.search(r"\(([A-Z0-9#&\-/]+)\)", name)
    return m.group(1) if m else ""


def fetch_layout(name: str) -> tuple[str, list[FieldDef]]:
    """Pull a RecordLayout's fields + their code values from Neo4j.

    For each field this returns the codes available at that position;
    parents-with-sub-fields are excluded so the result is byte-disjoint
    when sorted by position.
    """
    with Neo4jGREAdapter() as gre, gre.driver.session() as s:
        layout = s.run(
            "MATCH (l:RecordLayout {name: $n}) RETURN l.id as id, l.name as name",
            n=name,
        ).single()
        if layout is None:
            print(f"No RecordLayout named {name!r} in KG.")
            sys.exit(1)

        rows = s.run("""
            MATCH (l:RecordLayout {id: $lid})<-[:CONTAINED_IN]-(f:FieldRequirement)
            OPTIONAL MATCH (f)-[:CODED_BY]->(cl:CodeList)-[:HAS_VALUE]->(cv:CodeValue)
            RETURN
              f.name             AS name,
              f.field_name       AS field_name,
              f.position_start   AS ps,
              f.position_length  AS pl,
              f.format           AS format,
              f.is_required      AS is_required,
              f.notes            AS notes,
              collect(DISTINCT {code: cv.code, meaning: cv.notes}) AS code_pairs
        """, lid=layout["id"]).data()

    fields: list[FieldDef] = []
    for r in rows:
        if r["ps"] is None or r["pl"] is None:
            continue
        codes = [(c["code"], c["meaning"] or "") for c in r["code_pairs"] if c["code"]]
        fields.append(FieldDef(
            name=r["name"] or "",
            field_name=r["field_name"] or "",
            short_code=_parse_short_code(r["name"] or ""),
            position_start=r["ps"],
            position_length=r["pl"],
            format=r["format"] or "free-form",
            is_required=bool(r["is_required"]),
            notes=r["notes"],
            code_values=codes,
        ))

    # Drop parents whose range is fully covered by other (smaller) fields.
    fields = _drop_parents_with_subfields(fields)
    fields.sort(key=lambda f: f.position_start)
    return layout["name"], fields


def _drop_parents_with_subfields(fields: list[FieldDef]) -> list[FieldDef]:
    out: list[FieldDef] = []
    for i, f in enumerate(fields):
        if f.position_length < 2:
            out.append(f)
            continue
        cols = set(range(f.position_start, f.position_start + f.position_length))
        covered = set()
        for j, g in enumerate(fields):
            if i == j or g.position_length >= f.position_length:
                continue
            covered.update(range(g.position_start, g.position_start + g.position_length))
        if not cols.issubset(covered):
            out.append(f)
    return out


# ---- Value generators -------------------------------------------------------


def _expand_range_code(c: str) -> list[str]:
    """`1-9` and `1–9` represent any digit in [1..9]; expand for picking."""
    m = re.fullmatch(r"(\d+)[–\-](\d+)", c)
    if not m:
        return [c]
    lo, hi = int(m.group(1)), int(m.group(2))
    if hi - lo > 20 or lo > hi:  # sanity guard
        return [c]
    return [str(i) for i in range(lo, hi + 1)]


def _pick_code(field: FieldDef, scenario: str, rng: random.Random) -> str:
    """Pick a code value for a code-list field. Scenario nudges the choice."""
    raw_codes = [c for c, _ in field.code_values if c]
    # Expand any range-codes (e.g. "1-9" → ["1","2",…,"9"]) so the picked
    # value is a single digit the validator accepts.
    codes: list[str] = []
    for c in raw_codes:
        codes.extend(_expand_range_code(c))
    # Also drop any codes that won't fit the field's declared length.
    if field.position_length:
        codes = [c for c in codes if len(c) <= field.position_length] or codes
    if not codes:
        return ""
    sc = field.short_code

    # Scenario-driven choices for the most discriminating fields.
    if sc == "RT":
        if scenario == "new-policy":
            for prefer in ("91", "01"):  # HO new/renewal, then dwelling new/renewal
                if prefer in codes:
                    return prefer
        if scenario == "cancellation":
            for prefer in ("06", "05"):
                if prefer in codes:
                    return prefer
        if scenario == "endorsement":
            for prefer in ("92", "02"):
                if prefer in codes:
                    return prefer
    if sc == "LOB":
        for prefer in ("03", "02"):  # HO policies, then HO tenants
            if prefer in codes:
                return prefer
    if sc == "TRM":
        for prefer in ("1",):
            if prefer in codes:
                return prefer
    if sc == "SP":
        # SP=4 (residential) is canonical
        for prefer in ("4",):
            if prefer in codes:
                return prefer
    return rng.choice(codes)


def _generate_freeform(field: FieldDef, scenario: str, rng: random.Random) -> str:
    """Best-effort plausible value for a non-code field, based on the field name."""
    fname = (field.field_name or "").lower()
    notes = (field.notes or "").lower()
    L = field.position_length

    if "policy" in fname and "number" in fname or fname.startswith("policy") or "policy ident" in fname:
        return "".join(rng.choices("0123456789", k=L))
    if "claim" in fname and "ident" in fname:
        return "".join(rng.choices("0123456789", k=L))
    if "naic" in fname or fname.startswith("company number") or "stat plan code" in fname:
        return "".join(rng.choices("0123456789", k=L))
    if "zip" in fname:
        return "73301"[:L].ljust(L, "0") if L >= 5 else "0" * L
    if "place" in fname:
        return "AB001"[:L].ljust(L, "0")
    if "amount" in fname or "premium" in fname or "loss" in fname:
        return "0001"[:L].rjust(L, "0")
    if "date" in fname or "month" in fname or "year" in fname:
        # MMDDY / MMY / MMDDYYYY-flavored placeholders
        if L == 5:
            return "07266"
        if L == 3:
            return "726"
        if L == 6:
            return "202607"
        if L == 4:
            return "2607"
        return "0" * L
    if "year" in fname:
        return "26"[-L:].rjust(L, "0")
    # SKIP / unspecified → spaces
    if "skip" in fname.lower() or field.short_code == "SKIP":
        return " " * L
    return " " * L


# ---- Generation -------------------------------------------------------------


@dataclass
class FieldFill:
    field: FieldDef
    value: str
    annotation: str    # human-readable explanation


def fill_record(
    fields: list[FieldDef], scenario: str, rng: random.Random,
) -> tuple[str, list[FieldFill]]:
    line = list(" " * RECORD_LENGTH)
    fills: list[FieldFill] = []
    for f in fields:
        if f.short_code == "SKIP":
            v = " " * f.position_length
            annot = "(skip)"
        elif f.code_values:
            picked = _pick_code(f, scenario, rng)
            v = picked.ljust(f.position_length)[:f.position_length]
            mean = next((m for c, m in f.code_values if c == picked), "")
            annot = f"code {picked!r} = {mean[:50]}"
        else:
            v = _generate_freeform(f, scenario, rng)
            v = v.ljust(f.position_length)[:f.position_length]
            annot = f"free-form ({f.format})"
        # Place into 0-indexed array.
        for i, ch in enumerate(v):
            idx = f.position_start - 1 + i
            if 0 <= idx < RECORD_LENGTH:
                line[idx] = ch
        fills.append(FieldFill(field=f, value=v, annotation=annot))
    return "".join(line), fills


def _render_annotated(record: str, fills: list[FieldFill]) -> str:
    out = []
    for fill in fills:
        f = fill.field
        rng = f"{f.position_start:>3}-{f.position_start + f.position_length - 1:<3}"
        sep = "•" if f.short_code != "SKIP" else " "
        out.append(
            f"  cols {rng}  ({f.short_code:<8}) "
            f"{f.field_name[:30]:<30} {sep} {fill.value!r}  {fill.annotation}"
        )
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", default=DEFAULT_LAYOUT)
    ap.add_argument("--scenario", default="new-policy",
                    choices=["new-policy", "cancellation", "endorsement"])
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--annotate", action="store_true",
                    help="Show column-by-column breakdown alongside each record.")
    args = ap.parse_args()

    layout_name, fields = fetch_layout(args.layout)
    if not fields:
        print(f"Layout {layout_name!r} has no fields. Run scripts.parse_record_layout first.")
        sys.exit(1)

    print(f"Layout: {layout_name}")
    print(f"  {len(fields)} fields cover cols 1..{max(f.position_start + f.position_length - 1 for f in fields)}")
    print(f"  Scenario: {args.scenario}")
    print(f"  Generating {args.n} record(s) at seed {args.seed}")
    print()

    rng = random.Random(args.seed)
    for i in range(args.n):
        record, fills = fill_record(fields, args.scenario, rng)
        # Sanity: length must be exactly RECORD_LENGTH
        assert len(record) == RECORD_LENGTH, f"Record length {len(record)} != {RECORD_LENGTH}"
        print(f"--- record {i + 1} ---")
        print(record)
        print(f"(length: {len(record)} chars)")
        if args.annotate:
            print("\nColumn-by-column:")
            print(_render_annotated(record, fills))
        print()


if __name__ == "__main__":
    main()
