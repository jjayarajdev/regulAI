"""Validate a TICO-style fixed-width submission against the KG.

The KG knows every column's FieldRequirement and (where applicable) its
allowed CodeValues. This script reads a 200-character record (or many,
one per line) and reports per-column errors:

  - length:        record is not exactly 200 chars
  - unknown_code:  code-list field has a value not in HAS_VALUE chain
  - bad_format:    free-form field violates declared format hint
  - skip_dirty:    a SKIP column contains non-space characters

Exit code is 0 when all records pass, 1 when any record has errors.

Run:
  uv run python -m scripts.validate_submission \\
      --layout "Premium Record Layout" --record "<200-char string>"
  echo "<200-char string>" | uv run python -m scripts.validate_submission \\
      --layout "Premium Record Layout"
  uv run python -m scripts.validate_submission \\
      --layout "Premium Record Layout" --file submissions.txt
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from scripts.generate_sample_submission import FieldDef, fetch_layout

RECORD_LENGTH = 200


# ---- Error model ------------------------------------------------------------


@dataclass
class FieldError:
    column_start: int
    column_end: int
    short_code: str
    field_name: str
    kind: str           # "length" | "unknown_code" | "bad_format" | "skip_dirty" | "missing_required"
    actual: str
    detail: str


@dataclass
class ValidationResult:
    record: str
    record_index: int
    errors: list[FieldError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


# ---- Format checkers --------------------------------------------------------

_FORMAT_PATTERNS: dict[str, re.Pattern[str]] = {
    # Some sample format hints we've seen in the KG; extend over time.
    "5-digit numeric": re.compile(r"^\d{5}$"),
    "two-digit numeric percentage": re.compile(r"^\d{2}$"),
    "one-digit numeric": re.compile(r"^\d$"),
}


def _check_format(field: FieldDef, value: str) -> str | None:
    fmt = (field.format or "").lower()
    # Allow padding spaces — fields are fixed-width-padded.
    stripped = value.rstrip()
    if not stripped:
        # Empty value in a non-required, non-SKIP field = blank. Skip strict check.
        return None
    pat = _FORMAT_PATTERNS.get(fmt) or _FORMAT_PATTERNS.get(field.format or "")
    if pat is None:
        return None
    if not pat.match(value.strip()):
        return f"value {value.strip()!r} does not match format {field.format!r}"
    return None


# ---- Validation -------------------------------------------------------------


def validate_record(
    record: str, fields: list[FieldDef], record_index: int = 0,
) -> ValidationResult:
    res = ValidationResult(record=record, record_index=record_index)

    if len(record) != RECORD_LENGTH:
        res.errors.append(FieldError(
            column_start=1, column_end=len(record),
            short_code="—", field_name="(whole record)",
            kind="length",
            actual=str(len(record)),
            detail=f"record length {len(record)} != {RECORD_LENGTH}",
        ))
        # Continue anyway — partial validation is still useful.

    for f in fields:
        idx0 = f.position_start - 1
        idx1 = idx0 + f.position_length
        chunk = record[idx0:idx1]
        if len(chunk) < f.position_length:
            res.errors.append(FieldError(
                column_start=f.position_start,
                column_end=f.position_start + f.position_length - 1,
                short_code=f.short_code, field_name=f.field_name,
                kind="length",
                actual=chunk,
                detail=f"only {len(chunk)} chars available, expected {f.position_length}",
            ))
            continue

        if f.short_code == "SKIP":
            if chunk.strip():
                res.errors.append(FieldError(
                    column_start=f.position_start,
                    column_end=f.position_start + f.position_length - 1,
                    short_code=f.short_code, field_name=f.field_name,
                    kind="skip_dirty",
                    actual=chunk,
                    detail=f"reserved/SKIP columns must be blank, got {chunk!r}",
                ))
            continue

        if f.code_values:
            allowed = {c for c, _ in f.code_values if c}
            # Allow padding-spaced match: code "1" in a 1-char column → trim.
            stripped = chunk.strip()
            # Code-abbreviations like "1-9" represent the range 1..9; if the
            # KG records that exact entry, treat any digit in 1..9 as valid.
            range_codes = {c for c in allowed if re.fullmatch(r"\d+[–\-]\d+", c)}
            range_ok = False
            for rc in range_codes:
                lo, hi = re.split(r"[–\-]", rc)
                if stripped.isdigit() and int(lo) <= int(stripped) <= int(hi):
                    range_ok = True
                    break
            if stripped and stripped not in allowed and not range_ok:
                # Required field gets a stronger error.
                res.errors.append(FieldError(
                    column_start=f.position_start,
                    column_end=f.position_start + f.position_length - 1,
                    short_code=f.short_code, field_name=f.field_name,
                    kind="unknown_code",
                    actual=chunk,
                    detail=f"value {stripped!r} not in CodeList for {f.short_code} (allowed: {', '.join(sorted(list(allowed))[:8])}{'…' if len(allowed) > 8 else ''})",
                ))
                continue
            if not stripped and f.is_required:
                res.errors.append(FieldError(
                    column_start=f.position_start,
                    column_end=f.position_start + f.position_length - 1,
                    short_code=f.short_code, field_name=f.field_name,
                    kind="missing_required",
                    actual=chunk,
                    detail=f"required field is blank",
                ))
                continue

        # Free-form fields: light format check.
        fmt_err = _check_format(f, chunk)
        if fmt_err:
            res.errors.append(FieldError(
                column_start=f.position_start,
                column_end=f.position_start + f.position_length - 1,
                short_code=f.short_code, field_name=f.field_name,
                kind="bad_format",
                actual=chunk,
                detail=fmt_err,
            ))

    return res


# ---- Reporting --------------------------------------------------------------


def _color(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


GREEN = lambda s: _color(s, "32")  # noqa: E731
RED = lambda s: _color(s, "31")    # noqa: E731
YELLOW = lambda s: _color(s, "33") # noqa: E731
BOLD = lambda s: _color(s, "1")    # noqa: E731


def render_text(layout_name: str, results: list[ValidationResult]) -> str:
    lines = [BOLD(f"Validating against layout: {layout_name}\n")]
    total_errors = sum(len(r.errors) for r in results)
    pass_count = sum(1 for r in results if r.ok)
    for r in results:
        head = (
            GREEN(f"✓ record {r.record_index + 1}: PASS  (200 chars)")
            if r.ok
            else RED(f"✗ record {r.record_index + 1}: {len(r.errors)} error(s)")
        )
        lines.append(head)
        if not r.ok:
            for e in r.errors[:12]:
                lines.append(
                    f"    cols {e.column_start:>3}-{e.column_end:<3} "
                    f"({e.short_code:<8}) {e.field_name[:30]:<30} "
                    f"[{e.kind}] {e.detail}"
                )
            if len(r.errors) > 12:
                lines.append(f"    … and {len(r.errors) - 12} more")
        lines.append("")
    lines.append("-" * 60)
    if pass_count == len(results):
        lines.append(GREEN(f"All {len(results)} records PASS."))
    else:
        lines.append(
            RED(f"{len(results) - pass_count} of {len(results)} records FAILED "
                f"({total_errors} total errors).")
        )
    return "\n".join(lines)


# ---- CLI -------------------------------------------------------------------


def _read_records(args: argparse.Namespace) -> list[str]:
    if args.record:
        return [args.record]
    if args.file:
        return [ln.rstrip("\n") for ln in Path(args.file).read_text().splitlines() if ln.strip()]
    if not sys.stdin.isatty():
        return [ln.rstrip("\n") for ln in sys.stdin.read().splitlines() if ln.strip()]
    print("No record provided. Use --record, --file, or pipe stdin.", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", required=True)
    ap.add_argument("--record", help="A single 200-char record.")
    ap.add_argument("--file", help="File with one record per line.")
    ap.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    args = ap.parse_args()

    layout_name, fields = fetch_layout(args.layout)
    if not fields:
        print(f"Layout {layout_name!r} has no fields. Run scripts.parse_record_layout first.")
        sys.exit(1)

    records = _read_records(args)
    results = [validate_record(r, fields, i) for i, r in enumerate(records)]

    if args.json:
        out = {
            "layout": layout_name,
            "n_records": len(results),
            "n_pass": sum(1 for r in results if r.ok),
            "results": [
                {
                    "record_index": r.record_index,
                    "ok": r.ok,
                    "errors": [
                        {
                            "column_start": e.column_start,
                            "column_end": e.column_end,
                            "short_code": e.short_code,
                            "field_name": e.field_name,
                            "kind": e.kind,
                            "actual": e.actual,
                            "detail": e.detail,
                        }
                        for e in r.errors
                    ],
                }
                for r in results
            ],
        }
        print(json.dumps(out, indent=2))
    else:
        print(render_text(layout_name, results))

    sys.exit(0 if all(r.ok for r in results) else 1)


if __name__ == "__main__":
    main()
