"""Golden-record tests for the transform rule registry.

Each rule's emitted SQL is executed on an in-process DuckDB and asserted against
a known input→output pair. These are the safety net the ISO impact analysis
demanded: an off-by-one in an overpunch or month codec silently produces a
rejected regulatory filing, so the codecs must be proven before anything trusts
them.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import duckdb
import pytest

from packages.rhs.mapper.transforms import (
    REGISTRY,
    UnknownTransformError,
    compile_step,
    render_catalog,
)


def _eval(rule_id: str, value, params: dict | None = None):
    """Compile the rule to SQL and run it over a one-row DuckDB literal."""
    sql = compile_step(rule_id, "v", params)
    con = duckdb.connect(":memory:")
    lit = "NULL" if value is None else repr(value)
    return con.execute(f"SELECT {sql} AS out FROM (SELECT {lit} AS v)").fetchone()[0]


# ── basic ────────────────────────────────────────────────────────────────────
def test_identity():
    assert _eval("identity", "HO3") == "HO3"


def test_cast():
    assert _eval("cast", "2500", {"type": "INTEGER"}) == 2500


def test_trim():
    assert _eval("trim", "  TX ") == "TX"


def test_upper_lower():
    assert _eval("upper", "tx") == "TX"
    assert _eval("lower", "HO3") == "ho3"


def test_zero_pad():
    assert _eval("zero_pad", "7701", {"width": "5"}) == "07701"


def test_coalesce():
    assert _eval("coalesce", None, {"default": "'UNK'"}) == "UNK"


def test_substring():
    assert _eval("substring", "26522XX", {"start": "1", "length": "2"}) == "26"


def test_null():
    assert _eval("null", "anything") is None


# ── advanced ─────────────────────────────────────────────────────────────────
def test_money_to_decimal():
    assert _eval("money_to_decimal", "$1,842.00") == Decimal("1842.00")
    assert _eval("money_to_decimal", "325,000") == Decimal("325000.00")


def test_mmddyyyy_to_date():
    assert _eval("mmddyyyy_to_date", "01152025") == dt.date(2025, 1, 15)


def test_mmddyyyy_bad_row_is_null():
    # try_strptime → NULL on garbage, so the validator (not a crash) catches it.
    assert _eval("mmddyyyy_to_date", "notadate") is None


def test_date_to_mmddy():
    # 2025-01-15 → MM=01, DD=15, last year digit=5
    assert _eval("date_to_mmddy", "2025-01-15") == "01155"


def test_date_to_mmy():
    # 2026-01-15 → MM=01, last year digit=6
    assert _eval("date_to_mmy", "2026-01-15") == "016"


def test_code_map():
    m = {"mapping": "A=ACTIVE;C=CANCELLED;X=REWRITTEN"}
    assert _eval("code_map", "A", m) == "ACTIVE"
    assert _eval("code_map", "C", m) == "CANCELLED"
    assert _eval("code_map", "Z", m) is None  # unknown → NULL (fail-closed)


@pytest.mark.parametrize("raw,expected", [
    ("0000123{", 1230),    # { = +0  → 1230, positive
    ("0000123R", -1239),   # R = -9  → 1239, negative
    ("0000000A", 1),       # A = +1
    ("0000010}", -100),    # } = -0  → 100, negative
])
def test_overpunch_decode(raw, expected):
    assert _eval("overpunch_decode", raw) == expected


@pytest.mark.parametrize("iso,ch", [
    ("2025-01-03", "1"), ("2025-09-03", "9"), ("2025-10-03", "0"),
    ("2025-11-03", "-"), ("2025-12-03", "&"),
])
def test_iso_month_char(iso, ch):
    assert _eval("iso_month_char", iso) == ch


# ── registry contract ────────────────────────────────────────────────────────
def test_unknown_rule_fails_closed():
    with pytest.raises(UnknownTransformError):
        compile_step("totally_made_up", "v")


def test_missing_required_param_raises():
    with pytest.raises(ValueError, match="missing required param"):
        compile_step("zero_pad", "v")  # width is required


def test_catalog_renders_every_rule():
    cat = render_catalog()
    for rule_id in REGISTRY:
        assert rule_id in cat


# ── chain composition (compiled_sql folds a rule chain) ──────────────────────
def _eval_chain(rules, value):
    from packages.rhs.mapper.transform_agent import compiled_sql
    from packages.rhs.mapper.transform_schema import ParamKV, ResolvedTransform, RuleCall

    step = ResolvedTransform(
        target_column="EFFECTIVE_DATE", source_column="v",
        rules=[RuleCall(rule_id=rid, params=[ParamKV(name=k, value=x) for k, x in (p or {}).items()])
               for rid, p in rules],
        confidence=0.9, needs_review=True, rationale="test",
    )
    sql, err = compiled_sql(step)
    assert err is None, err
    con = duckdb.connect(":memory:")
    return con.execute(f"SELECT {sql} AS out FROM (SELECT {value!r} AS v)").fetchone()[0]


def test_chain_legacy_text_date_to_tspr_encoding():
    # The real failure the demo surfaced: MMDDYYYY text must be parsed to a DATE
    # before the TSPR encoding. Chain mmddyyyy_to_date → date_to_mmddy.
    # 01152025 → 2025-01-15 → MM=01, DD=15, last year digit=5 → "01155"
    assert _eval_chain([("mmddyyyy_to_date", None), ("date_to_mmddy", None)], "01152025") == "01155"


def test_chain_unknown_rule_fails_closed():
    from packages.rhs.mapper.transform_agent import compiled_sql
    from packages.rhs.mapper.transform_schema import ResolvedTransform, RuleCall

    step = ResolvedTransform(
        target_column="X", source_column="v",
        rules=[RuleCall(rule_id="made_up", params=[])],
        confidence=0.5, needs_review=True, rationale="test",
    )
    sql, err = compiled_sql(step)
    assert sql is None and "unknown transform" in err
