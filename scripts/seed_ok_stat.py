"""Seed the Oklahoma demo statistical records (fixture CONTENT, not mechanism).

The OK stat plan is a data-call style feed (like FL's FHCF): records land
directly in the filing-ready GOLD.OK_STAT_RECORDS table, premium ('P') and
loss ('L') records sharing one layout. This seed loads 12 synthetic Lone
Star Mutual OK policies stamped filing_batch_id='OK-HO-2026A': two clean
rows plus one designated violator per executable rule (the FL fixture
design — tests/test_ok_rules_execute.py asserts the mapping).

The edit package itself (violation_sql on the KG rules + the reference
table rows) is attached by the GENERIC mechanism:
    uv run python -m scripts.attach_validation_rules -j US-OK

DuckDB is single-writer: stop the api container before running this against
the local warehouse. Idempotent — truncate-and-reload per run.
"""

from __future__ import annotations

from packages.rhs.db import query

FILING_ID = "OK-HO-2026A"

_COLS = (
    "policy_number, record_type, naic_code, county_fips, transaction_code, "
    "written_premium, aoi_thousands, deductible_type, wind_deductible_pct, "
    "mitigation_credit, mitigation_code, cause_of_loss, accident_date, "
    "paid_amount, disposition_code, cat_serial, reported_lag_days, "
    "effective_date, filing_batch_id"
)

# Base shapes — every dirty row is the base with exactly ONE field broken, so
# each violator trips exactly one rule (asserted in test_ok_rules_execute).
_P = dict(record_type="P", naic="23611", fips="109", txn="01", premium=1250.0,
          aoi=250, ded="2", wind=None, mit_credit=0.0, mit_code=None,
          cause=None, accident=None, paid=None, dispo=None, cat=None, lag=20)
_L = dict(record_type="L", naic="23611", fips="109", txn="30", premium=None,
          aoi=None, ded="2", wind=None, mit_credit=0.0, mit_code=None,
          cause="21", accident="2026-04-12", paid=5000.0, dispo="P", cat=0, lag=10)

# policy_number → (base, overrides). POL-OK-0001/0002 clean; 0003..0012 each
# violate the OK.N rule noted in the comment.
OK_FIXTURES: dict[str, tuple[dict, dict]] = {
    "POL-OK-0001": (_P, {}),                                        # clean premium
    "POL-OK-0002": (_L, {}),                                        # clean loss
    "POL-OK-0003": (_P, {"lag": 60}),                               # OK.1 late report
    "POL-OK-0004": (_P, {"naic": "23A11"}),                         # OK.2 bad NAIC
    "POL-OK-0005": (_P, {"fips": "9"}),                             # OK.3 bad FIPS
    "POL-OK-0006": (_P, {"premium": 1250.55}),                      # OK.4 cents
    "POL-OK-0007": (_P, {"aoi": 0}),                                # OK.5 zero AOI
    "POL-OK-0008": (_P, {"wind": 2.0}),                             # OK.6 pct wind on type 2
    "POL-OK-0009": (_P, {"mit_credit": 120.0}),                     # OK.7 credit, no code
    "POL-OK-0010": (_L, {"cause": None}),                           # OK.8 paid loss, no cause
    "POL-OK-0011": (_L, {"dispo": "C", "paid": 500.0}),             # OK.9 CWP with payment
    "POL-OK-0012": (_L, {"cat": None}),                             # OK.10 missing cat serial
}


def _row_params(policy: str, base: dict, over: dict) -> tuple:
    r = {**base, **over}
    return (
        policy, r["record_type"], r["naic"], r["fips"], r["txn"],
        r["premium"], r["aoi"], r["ded"], r["wind"],
        r["mit_credit"], r["mit_code"], r["cause"], r["accident"],
        r["paid"], r["dispo"], r["cat"], r["lag"],
        "2026-01-15", FILING_ID,
    )


def seed_records() -> int:
    query(
        "CREATE TABLE IF NOT EXISTS INSURANCE_REGULATORY.GOLD.OK_STAT_RECORDS (\n"
        "  policy_number STRING, record_type STRING, naic_code STRING,\n"
        "  county_fips STRING, transaction_code STRING, written_premium DOUBLE,\n"
        "  aoi_thousands BIGINT, deductible_type STRING, wind_deductible_pct DOUBLE,\n"
        "  mitigation_credit DOUBLE, mitigation_code STRING, cause_of_loss STRING,\n"
        "  accident_date DATE, paid_amount DOUBLE, disposition_code STRING,\n"
        "  cat_serial BIGINT, reported_lag_days BIGINT, effective_date DATE,\n"
        "  filing_batch_id STRING\n)"
    )
    query("DELETE FROM INSURANCE_REGULATORY.GOLD.OK_STAT_RECORDS WHERE filing_batch_id = %s",
          (FILING_ID,))
    placeholders = "(" + ", ".join(["%s"] * 19) + ")"
    for policy, (base, over) in OK_FIXTURES.items():
        query(
            f"INSERT INTO INSURANCE_REGULATORY.GOLD.OK_STAT_RECORDS ({_COLS}) VALUES {placeholders}",
            _row_params(policy, base, over),
        )
    return len(OK_FIXTURES)


def main() -> int:
    n = seed_records()
    print(f"  ✓ GOLD.OK_STAT_RECORDS: {n} records (filing {FILING_ID})")
    print("  (edit package: uv run python -m scripts.attach_validation_rules -j US-OK)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
