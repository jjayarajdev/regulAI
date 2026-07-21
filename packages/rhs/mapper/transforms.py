"""Transform rule registry — the deterministic core of stage 4 (transform).

The mapping agent used to free-write a `transform_sql` string per column. That's
the weak link in a compliance pipeline: unaudited, untested SQL the model
invented. This registry replaces it with a **closed vocabulary of named,
golden-tested transforms**. The agent (see transform_agent.py) *selects* a rule
and its parameters; deterministic code compiles the rule to SQL. An off-by-one
in an overpunch codec silently produces a rejected filing, so every rule here has
a golden-record test in tests/test_transforms.py.

This is the codec registry the ISO impact analysis called for, made concrete:
`date_to_mmddy` is the TSPR encoding; `overpunch_decode` / `iso_month_char` are
the ISO ones; `money_to_decimal` / `mmddyyyy_to_date` clean the legacy sources
the crawler surfaces. Adding an encoding = adding a rule + a golden test, nothing
else.

SQL is emitted in DuckDB dialect (the validator dry-runs on DuckDB). Production
Spark/Databricks equivalents are noted per rule; a second dialect is a follow-up.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

# ── overpunch (IBM zoned-decimal) sign+digit tables ──────────────────────────
# Final character encodes the last digit AND the sign of the amount.
_OP_POS = "{ABCDEFGHI"   # +0 … +9
_OP_NEG = "}JKLMNOPQR"   # -0 … -9

# ── ISO single-character month codes (CSP GR) ────────────────────────────────
# 1–9 = Jan–Sep, 0 = Oct, - = Nov, & = Dec
_ISO_MONTH = {1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6",
              7: "7", 8: "8", 9: "9", 10: "0", 11: "-", 12: "&"}


@dataclass(frozen=True)
class TransformParam:
    name: str
    description: str
    required: bool = True
    example: str = ""


@dataclass(frozen=True)
class TransformRule:
    id: str
    category: str                       # "basic" | "advanced"
    summary: str
    emit: Callable[[str, dict], str]    # (source_expr, params) -> DuckDB SQL
    params: list[TransformParam] = field(default_factory=list)
    example_in: str = ""
    example_out: str = ""
    needs_review: bool = False          # domain/regulatory encodings default to human sign-off


# ─────────────────────────────────────────────────────────────────────────────
# BASIC rules — shape/typing, no domain knowledge
# ─────────────────────────────────────────────────────────────────────────────
def _identity(col: str, p: dict) -> str:
    return col


def _cast(col: str, p: dict) -> str:
    return f"CAST({col} AS {p['type']})"


def _trim(col: str, p: dict) -> str:
    return f"trim({col})"


def _upper(col: str, p: dict) -> str:
    return f"upper({col})"


def _lower(col: str, p: dict) -> str:
    return f"lower({col})"


def _zero_pad(col: str, p: dict) -> str:
    return f"lpad(CAST({col} AS VARCHAR), {int(p['width'])}, '0')"


def _coalesce(col: str, p: dict) -> str:
    return f"coalesce({col}, {p['default']})"


def _substring(col: str, p: dict) -> str:
    return f"substr(CAST({col} AS VARCHAR), {int(p['start'])}, {int(p['length'])})"


def _null(col: str, p: dict) -> str:
    return "NULL"


# ─────────────────────────────────────────────────────────────────────────────
# ADVANCED rules — parsing + domain/regulatory encodings
# ─────────────────────────────────────────────────────────────────────────────
def _money_to_decimal(col: str, p: dict) -> str:
    # Strip currency symbols, thousands separators, spaces → DECIMAL. Keeps
    # digits, a decimal point and a leading minus. "$1,842.00" → 1842.00
    scale = int(p.get("scale", 2))
    return (f"CAST(regexp_replace(CAST({col} AS VARCHAR), '[^0-9.\\-]', '', 'g') "
            f"AS DECIMAL(18,{scale}))")


def _mmddyyyy_to_date(col: str, p: dict) -> str:
    # Legacy mainframe MMDDYYYY text → DATE. try_strptime → NULL on bad rows,
    # which the validator's required-non-null check then catches. Spark:
    # to_date(col, 'MMddyyyy').
    return f"try_strptime(CAST({col} AS VARCHAR), '%m%d%Y')::DATE"


def _date_to_mmddy(col: str, p: dict) -> str:
    # TSPR domain encoding: MM + DD + last digit of the year. Regulatory — the
    # agent must flag needs_review; a human confirms the century assumption.
    return (f"strftime(CAST({col} AS DATE), '%m%d') || "
            f"substr(strftime(CAST({col} AS DATE), '%Y'), 4, 1)")


def _date_to_mmy(col: str, p: dict) -> str:
    # TSPR domain encoding: MM + last digit of the year (policy-period end).
    return (f"strftime(CAST({col} AS DATE), '%m') || "
            f"substr(strftime(CAST({col} AS DATE), '%Y'), 4, 1)")


def _code_map(col: str, p: dict) -> str:
    # Value remap via CASE. params.mapping = "A=ACTIVE;C=CANCELLED;X=REWRITTEN"
    pairs = [kv.split("=", 1) for kv in p["mapping"].split(";") if "=" in kv]
    whens = " ".join(
        f"WHEN '{k.strip()}' THEN '{v.strip()}'" for k, v in pairs
    )
    return f"CASE CAST({col} AS VARCHAR) {whens} ELSE NULL END"


def _concat_ws(col: str, p: dict) -> str:
    # Combine several source columns. params.columns = "street,city,state,zip5"
    # overrides the single source column; params.sep defaults to a space.
    cols = [c.strip() for c in p.get("columns", col).split(",")]
    sep = p.get("sep", " ")
    return "concat_ws('" + sep + "', " + ", ".join(cols) + ")"


def _overpunch_decode(col: str, p: dict) -> str:
    # IBM zoned-decimal (ISO CSP GR-2.1/2.2): the final char carries the last
    # digit and the sign. "0000123{" → 1230 ; "0000123R" → -1239.
    pos_when = " ".join(f"WHEN '{c}' THEN '{i}'" for i, c in enumerate(_OP_POS))
    neg_when = " ".join(f"WHEN '{c}' THEN '{i}'" for i, c in enumerate(_OP_NEG))
    last = f"right(CAST({col} AS VARCHAR), 1)"
    head = f"left(CAST({col} AS VARCHAR), length(CAST({col} AS VARCHAR)) - 1)"
    digit = f"CASE {last} {pos_when} {neg_when} END"
    sign = f"CASE WHEN {last} IN ({', '.join(repr(c) for c in _OP_NEG)}) THEN -1 ELSE 1 END"
    return f"CAST({head} || ({digit}) AS BIGINT) * ({sign})"


def _iso_month_char(col: str, p: dict) -> str:
    # ISO CSP single-char month code from a date. 1–9=Jan–Sep, 0=Oct, -=Nov, &=Dec.
    whens = " ".join(f"WHEN {m} THEN '{c}'" for m, c in _ISO_MONTH.items())
    return f"CASE month(CAST({col} AS DATE)) {whens} END"


# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────
_RULES: list[TransformRule] = [
    # -- basic --
    TransformRule("identity", "basic", "Pass the source column through unchanged.",
                  _identity, [], "HO3", "HO3"),
    TransformRule("cast", "basic", "Cast to a target SQL type.",
                  _cast, [TransformParam("type", "Target SQL type", example="INTEGER")],
                  "'2500'", "2500"),
    TransformRule("trim", "basic", "Strip leading/trailing whitespace.",
                  _trim, [], "'  TX '", "TX"),
    TransformRule("upper", "basic", "Uppercase.", _upper, [], "'tx'", "TX"),
    TransformRule("lower", "basic", "Lowercase.", _lower, [], "'HO3'", "ho3"),
    TransformRule("zero_pad", "basic", "Left-pad to a fixed width with zeros (e.g. ZIP).",
                  _zero_pad, [TransformParam("width", "Target width", example="5")],
                  "7701", "07701"),
    TransformRule("coalesce", "basic", "Replace nulls with a default literal.",
                  _coalesce, [TransformParam("default", "Default SQL literal", example="'UNK'")],
                  "NULL", "UNK"),
    TransformRule("substring", "basic", "Take a fixed-position substring.",
                  _substring, [TransformParam("start", "1-based start", example="1"),
                               TransformParam("length", "Length", example="2")],
                  "'26522XX'", "26"),
    TransformRule("null", "basic", "Emit NULL — a required target with no source (fail-closed).",
                  _null, [], "", "NULL"),
    # -- advanced --
    TransformRule("money_to_decimal", "advanced",
                  "Parse a formatted money string ($, commas, spaces) to DECIMAL.",
                  _money_to_decimal,
                  [TransformParam("scale", "Decimal places", required=False, example="2")],
                  "$1,842.00", "1842.00"),
    TransformRule("mmddyyyy_to_date", "advanced",
                  "Parse legacy MMDDYYYY text into a DATE.",
                  _mmddyyyy_to_date, [], "01152025", "2025-01-15"),
    TransformRule("date_to_mmddy", "advanced",
                  "TSPR date encoding: MM + DD + last digit of year. Regulatory — needs review.",
                  _date_to_mmddy, [], "2025-01-15", "01155", needs_review=True),
    TransformRule("date_to_mmy", "advanced",
                  "TSPR date encoding: MM + last digit of year (period end). Regulatory — needs review.",
                  _date_to_mmy, [], "2026-01-15", "016", needs_review=True),
    TransformRule("code_map", "advanced",
                  "Remap coded values via a lookup (CASE). params.mapping='A=ACTIVE;C=CANCELLED'.",
                  _code_map, [TransformParam("mapping", "k=v pairs joined by ;",
                                             example="A=ACTIVE;C=CANCELLED")],
                  "A", "ACTIVE"),
    TransformRule("concat_ws", "advanced",
                  "Join several source columns with a separator (e.g. address parts).",
                  _concat_ws, [TransformParam("columns", "Comma-separated source columns",
                                              example="street,city,state,zip5"),
                               TransformParam("sep", "Separator", required=False, example=", ")],
                  "street,city", "1200 Rio Grande St, Austin"),
    TransformRule("overpunch_decode", "advanced",
                  "Decode IBM zoned-decimal (ISO overpunch) signed amount to an integer. Needs review.",
                  _overpunch_decode, [], "0000123R", "-1239", needs_review=True),
    TransformRule("iso_month_char", "advanced",
                  "Encode a date's month as the ISO single-char code (1-9,0,-,&). Needs review.",
                  _iso_month_char, [], "2025-11-03", "-", needs_review=True),
]

REGISTRY: dict[str, TransformRule] = {r.id: r for r in _RULES}


class UnknownTransformError(KeyError):
    """Raised when a spec references a rule id not in the registry (fail-closed)."""


def compile_step(rule_id: str, source_expr: str, params: dict | None = None) -> str:
    """Compile a (rule, source, params) selection into a DuckDB SQL expression.

    Fail-closed: an unknown rule id or missing required param raises rather than
    silently emitting something the agent guessed.
    """
    rule = REGISTRY.get(rule_id)
    if rule is None:
        raise UnknownTransformError(
            f"'{rule_id}' is not a registered transform. Known: {', '.join(REGISTRY)}"
        )
    params = params or {}
    missing = [p.name for p in rule.params if p.required and p.name not in params]
    if missing:
        raise ValueError(f"transform '{rule_id}' missing required param(s): {', '.join(missing)}")
    return rule.emit(source_expr, params)


def render_catalog() -> str:
    """Render the rule vocabulary for the agent's system prompt."""
    lines: list[str] = []
    for cat in ("basic", "advanced"):
        lines.append(f"\n[{cat.upper()}]")
        for r in _RULES:
            if r.category != cat:
                continue
            ps = ", ".join(
                f"{p.name}{'' if p.required else '?'}" for p in r.params
            ) or "—"
            flag = " (needs_review)" if r.needs_review else ""
            eg = f"  e.g. {r.example_in!r}→{r.example_out!r}" if r.example_in else ""
            lines.append(f"  {r.id:<18} params: {ps:<24} {r.summary}{flag}{eg}")
    return "\n".join(lines)
