"""Seed the Florida FHCF filing state on the active REGULAI_DB backend.

Everything goes through packages.rhs.db.query() so the same script works on
duckdb / databricks / snowflake:

  1. Seed 15 synthetic FL property policies (Lone Star Mutual) into the
     Guidewire Bronze tables — GW_PC_POLICY / GW_PC_ADDRESS /
     GW_PC_HOPOLICYLINE / GW_PC_HOCOVERAGE / GW_PC_HODWELLING — the same
     tables the TX book lives in. scripts.run_fhcf then transforms these
     rows Bronze → SILVER.FHCF_EXPOSURE_STAGING → GOLD.FHCF_EXPOSURE_RECORDS
     (the table the 10 US-FL validation rules target).
     DELETE-then-INSERT by id range keeps re-runs clean.

     Wind-mitigation attributes (FL OIR-B1-1802 inspection fields) and the
     geocode have no natural home in stock Guidewire HO tables, so nullable
     extension columns are added to BRONZE.GW_PC_HODWELLING (idempotent
     ALTER) rather than inventing a side table — real carriers carry these
     as PolicyCenter LOB extensions on the dwelling, and a side table would
     force every downstream mapping to know about a second join path.

  2. Ensure a GOLD.FILING_BATCH row for FHCF-A-2026 (status 'validated',
     0 open blockers) so the approval chain can start.
  3. Load the 10 US-FL validation rules into REFERENCE.TSPR_VALIDATION_RULES
     by parsing the generated artifact
     materialized/reference/tspr_validation_rules_us_fl.sql. That file's
     CREATE OR REPLACE + `DELETE ... WHERE jurisdiction_code='US'` would
     clobber the shared table / federal rows, so we deliberately execute only
     the INSERT payloads (minus the KG-provenance columns the runtime table
     doesn't carry), after deleting prior US-FL rows.

The pre-shaped BRONZE.FL_FHCF_POLICY shortcut is retired: on duckdb the
table is dropped; on databricks it is simply no longer referenced.

Data design (15 policies, POL-FL-1001..1015): 10 clean + 5 dirty, each
dirty row triggering exactly ONE of the FHCF Data Call validation rules
after the Bronze→Silver→Gold transform:

    POL-FL-1011  risk zip '77015' (TX prefix)          → Validation.2
    POL-FL-1012  county FIPS '99' (out of 01..67)      → Validation.3
    POL-FL-1013  hurricane deductible 1500 (>1000)     → Validation.5
    POL-FL-1014  coverage_a $12M (> $5M band)          → Validation.6
    POL-FL-1015  effective_date after expiry_date      → Validation.8

Run:  REGULAI_DB=duckdb uv run python -m scripts.seed_fl_fhcf
Idempotent — safe to re-run.
"""

from __future__ import annotations

import re
from pathlib import Path

from packages.rhs.db import backend_name, query
from packages.rhs.filings import FILINGS

FL_RULES_SQL = Path("materialized/reference/tspr_validation_rules_us_fl.sql")
FILING_ID = "FHCF-A-2026"

# ── FL Guidewire Bronze fixtures ──────────────────────────────────────────
# Deterministic id blocks far above the TX generator's ranges (policies
# 2001..2453, lines 9000..9370, coverages 9100..9470, dwellings 9200..9570).
_PID0, _ADDR0, _LINE0, _COV0, _DW0 = 5000, 85000, 95000, 96000, 97000

# One dict per policy. `wind='Y'` rows carry all four dwelling-side
# companions (the fifth, roof cover type, rides GW_PC_HOPOLICYLINE).
#   zip/fips/state → hodwelling · cov_a/ded/prem → hocoverage
#   form/dates     → hopolicyline · lat/lng in micro-degrees (BIGINT)
FL_POLICIES = [
    # ── clean (10) ──
    dict(n=1,  zip="33101", fips="25", city="Miami",           cov_a=450_000,  ded=500,  yb=2015, eff="2025-07-15", exp="2026-07-15", constr="M", ppc="3", form="HO3", wind="Y", lat=25_774_000,  lng=-80_194_000),
    dict(n=2,  zip="32308", fips="37", city="Tallahassee",     cov_a=285_000,  ded=200,  yb=2018, eff="2025-08-01", exp="2026-08-01", constr="F", ppc="4", form="HO5", wind="N", lat=30_455_000,  lng=-84_253_000),
    dict(n=3,  zip="33139", fips="25", city="Miami Beach",     cov_a=610_000,  ded=500,  yb=2009, eff="2025-07-01", exp="2026-06-30", constr="M", ppc="2", form="HO3", wind="Y", lat=25_790_000,  lng=-80_130_000),
    dict(n=4,  zip="32202", fips="31", city="Jacksonville",    cov_a=320_000,  ded=300,  yb=2001, eff="2025-09-01", exp="2026-09-01", constr="F", ppc="3", form="HO3", wind="N", lat=30_332_000,  lng=-81_656_000),
    dict(n=5,  zip="33602", fips="29", city="Tampa",           cov_a=275_000,  ded=250,  yb=1996, eff="2025-10-01", exp="2026-10-01", constr="M", ppc="3", form="HO3", wind="N", lat=27_950_000,  lng=-82_457_000),
    dict(n=6,  zip="32801", fips="48", city="Orlando",         cov_a=340_000,  ded=500,  yb=2012, eff="2025-07-20", exp="2026-07-20", constr="F", ppc="4", form="HO3", wind="Y", lat=28_538_000,  lng=-81_379_000),
    dict(n=7,  zip="33301", fips="06", city="Fort Lauderdale", cov_a=520_000,  ded=1000, yb=2016, eff="2025-08-15", exp="2026-08-15", constr="M", ppc="2", form="HO5", wind="Y", lat=26_122_000,  lng=-80_137_000),
    dict(n=8,  zip="34102", fips="11", city="Naples",          cov_a=780_000,  ded=1000, yb=2020, eff="2025-11-01", exp="2026-11-01", constr="M", ppc="2", form="HO5", wind="N", lat=26_142_000,  lng=-81_795_000),
    dict(n=9,  zip="32601", fips="01", city="Gainesville",     cov_a=195_000,  ded=200,  yb=1988, eff="2025-07-05", exp="2026-07-05", constr="F", ppc="5", form="HO3", wind="N", lat=29_651_000,  lng=-82_325_000),
    dict(n=10, zip="33040", fips="44", city="Key West",        cov_a=425_000,  ded=1000, yb=1972, eff="2025-12-01", exp="2026-12-01", constr="M", ppc="3", form="HO3", wind="Y", lat=24_555_000,  lng=-81_780_000),
    # ── dirty (5) — each trips exactly one FHCF rule post-transform ──
    # Validation.2: TX zip prefix on an FL risk
    dict(n=11, zip="77015", fips="28", city="Hialeah",         cov_a=310_000,  ded=500,  yb=2010, eff="2025-09-10", exp="2026-09-10", constr="M", ppc="3", form="HO3", wind="N", lat=25_857_000,  lng=-80_278_000),
    # Validation.3: county FIPS out of the 01..67 FL range
    dict(n=12, zip="33625", fips="99", city="Tampa",           cov_a=295_000,  ded=500,  yb=2014, eff="2025-10-15", exp="2026-10-15", constr="F", ppc="4", form="HO3", wind="N", lat=28_068_000,  lng=-82_557_000),
    # Validation.5: hurricane deductible outside [200, 1000]
    dict(n=13, zip="33480", fips="50", city="Palm Beach",      cov_a=720_000,  ded=1500, yb=2017, eff="2025-08-20", exp="2026-08-20", constr="M", ppc="3", form="HO3", wind="N", lat=26_705_000,  lng=-80_036_000),
    # Validation.6: Coverage A above the $5M plausibility band
    dict(n=14, zip="33109", fips="25", city="Fisher Island",   cov_a=12_000_000, ded=1000, yb=2021, eff="2025-07-25", exp="2026-07-25", constr="M", ppc="2", form="HO5", wind="N", lat=25_760_000,  lng=-80_140_000),
    # Validation.8: effective date after expiry date
    dict(n=15, zip="32960", fips="30", city="Vero Beach",      cov_a=265_000,  ded=500,  yb=2006, eff="2026-03-01", exp="2025-03-01", constr="F", ppc="4", form="HO3", wind="N", lat=27_638_000,  lng=-80_397_000),
]

# Wind-mitigation companion values used for wind='Y' rows (FL OIR-B1-1802
# inspection codes: FBC-rated opening protection, 8d-nail deck attachment,
# double-wrap roof-to-wall, secondary water resistance present).
_WIND_COMPANIONS = ("A", "C", "D", "Y")

# Extension columns added to BRONZE.GW_PC_HODWELLING (see module docstring
# for why they live on the dwelling row and not a side table).
_HODWELLING_EXT_COLS = [
    ("windmitigation",           "VARCHAR"),
    ("openingprotection",        "VARCHAR"),
    ("roofdeckattachment",       "VARCHAR"),
    ("rooftowallconnection",     "VARCHAR"),
    ("secondarywaterresistance", "VARCHAR"),
    ("latitude",                 "BIGINT"),
    ("longitude",                "BIGINT"),
]


def _ensure_hodwelling_ext_cols() -> None:
    """Idempotently add the FL extension columns to GW_PC_HODWELLING."""
    is_duckdb = backend_name() == "duckdb"
    for col, typ in _HODWELLING_EXT_COLS:
        try:
            if is_duckdb:
                query("ALTER TABLE INSURANCE_REGULATORY.BRONZE.GW_PC_HODWELLING "
                      f"ADD COLUMN IF NOT EXISTS {col} {typ}")
            else:
                query("ALTER TABLE INSURANCE_REGULATORY.BRONZE.GW_PC_HODWELLING "
                      f"ADD COLUMNS ({col} {typ})")
        except Exception as e:  # noqa: BLE001 — already-exists is fine on re-run
            if "already exists" not in str(e).lower():
                raise


def _pol(i: int) -> str:
    return f"POL-FL-{1000 + i:04d}"


def _seed_bronze() -> int:
    """Idempotently load the 15 FL policies into the Guidewire Bronze tables."""
    _ensure_hodwelling_ext_cols()

    # Idempotency: clear this script's id blocks before re-inserting.
    lo, hi = _PID0 + 1, _PID0 + len(FL_POLICIES)
    query(f"DELETE FROM INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY WHERE id BETWEEN {lo} AND {hi}")
    for tbl, base in (("GW_PC_ADDRESS", _ADDR0), ("GW_PC_HOPOLICYLINE", _LINE0),
                      ("GW_PC_HOCOVERAGE", _COV0), ("GW_PC_HODWELLING", _DW0)):
        query(f"DELETE FROM INSURANCE_REGULATORY.BRONZE.{tbl} "
              f"WHERE id BETWEEN {base + 1} AND {base + len(FL_POLICIES)}")

    for p in FL_POLICIES:
        i = p["n"]
        pid, addr_id, line_id = _PID0 + i, _ADDR0 + i, _LINE0 + i
        cov_id, dw_id = _COV0 + i, _DW0 + i
        polnum = _pol(i)
        opening, deck, wall, swr = (
            _WIND_COMPANIONS if p["wind"] == "Y" else (None, None, None, None)
        )

        query(
            "INSERT INTO INSURANCE_REGULATORY.BRONZE.GW_PC_POLICY "
            "(id, publicid, policynumber, retiredvalue) "
            "SELECT %s, %s, %s, 0",
            (pid, f"pol:{pid}", polnum),
        )
        query(
            "INSERT INTO INSURANCE_REGULATORY.BRONZE.GW_PC_ADDRESS "
            "(id, publicid, addressline1, city, state, postalcode, postalcodeplus4, retiredvalue) "
            "SELECT %s, %s, %s, %s, %s, %s, %s, 0",
            (addr_id, f"addr:{addr_id}", f"{100 + i} Gulf Breeze Ln",
             p["city"], "FL", p["zip"], "0000"),
        )
        query(
            "INSERT INTO INSURANCE_REGULATORY.BRONZE.GW_PC_HOPOLICYLINE "
            "(id, publicid, policy_id, policylinepatterncodeidentifier, linecategory, "
            " effectivedate, expirationdate, holineform, occupancytype, "
            " roofcoveringtype, retiredvalue) "
            "SELECT %s, %s, %s, 'HOLine', 'HO', "
            "       TO_TIMESTAMP_NTZ(%s), TO_TIMESTAMP_NTZ(%s), %s, 'OwnerOccupied', %s, 0",
            (line_id, f"hopl:{line_id}", pid, p["eff"], p["exp"], p["form"],
             # Roof cover is the 5th wind-mitigation companion; 'A' = shingle
             "A"),
        )
        query(
            "INSERT INTO INSURANCE_REGULATORY.BRONZE.GW_PC_HOCOVERAGE "
            "(id, publicid, policyline_id, coveragepatterncode, coveragecategory, "
            " coveragetype, coverageamount, tropicalcyclonedeductible, "
            " writtenpremium, retiredvalue) "
            "SELECT %s, %s, %s, 'HODW_Cov_HOE', 'Dwelling', 'A', %s, %s, %s, 0",
            (cov_id, f"hocov:{cov_id}", line_id, p["cov_a"], p["ded"],
             round(min(p["cov_a"], 5_000_000) * 0.009, 0)),
        )
        query(
            "INSERT INTO INSURANCE_REGULATORY.BRONZE.GW_PC_HODWELLING "
            "(id, publicid, policyline_id, policyaddress_id, countyfips, zip, ziplus4, "
            " state, constructiontype, yearbuilt, numberoffamilies, ppccode, "
            " windmitigation, openingprotection, roofdeckattachment, "
            " rooftowallconnection, secondarywaterresistance, latitude, longitude, "
            " retiredvalue) "
            "SELECT %s, %s, %s, %s, %s, %s, %s, 'FL', %s, %s, 1, %s, "
            "       %s, %s, %s, %s, %s, %s, %s, 0",
            (dw_id, f"hodw:{dw_id}", line_id, addr_id, p["fips"], p["zip"], "0000",
             p["constr"], p["yb"], p["ppc"],
             p["wind"], opening, deck, wall, swr, p["lat"], p["lng"]),
        )
    return len(FL_POLICIES)


def _drop_legacy_bronze() -> bool:
    """Retire the pre-shaped BRONZE.FL_FHCF_POLICY shortcut (duckdb only;
    on databricks we simply stop referencing it rather than dropping)."""
    if backend_name() != "duckdb":
        return False
    query("DROP TABLE IF EXISTS INSURANCE_REGULATORY.BRONZE.FL_FHCF_POLICY")
    return True


def _seed_filing_batch() -> bool:
    f = next((x for x in FILINGS if x["id"] == FILING_ID), None)
    if f is None:
        raise RuntimeError(f"{FILING_ID} missing from packages.rhs.filings.FILINGS")
    rows = query(
        "SELECT filing_batch_id FROM INSURANCE_REGULATORY.GOLD.FILING_BATCH "
        "WHERE filing_batch_id = %s",
        (FILING_ID,),
    )
    if rows:
        return False
    query(
        "INSERT INTO INSURANCE_REGULATORY.GOLD.FILING_BATCH "
        "(filing_batch_id, filing_id, plan_code, plan_name, "
        " reporting_period_start, reporting_period_end, cadence, due_date, "
        " channel, status, open_blockers) "
        "SELECT %s, %s, %s, %s, TO_DATE(%s), TO_DATE(%s), %s, TO_DATE(%s), %s, %s, 0",
        (f["id"], f["id"], f["plan_code"], f["plan_name"],
         f["period_start"], f["period_end"], f["cadence"], f["due_date"],
         f["channel"], "validated"),
    )
    return True


# ── FL rules loader — parse the generated artifact's INSERT payloads ──────

_INSERT_RE = re.compile(
    r"INSERT INTO TSPR_VALIDATION_RULES\s*\(\s*(?P<cols>[^)]*?)\s*\)\s*"
    r"VALUES\s*\((?P<vals>.*?)\n\);",
    re.DOTALL | re.IGNORECASE,
)

# Runtime reference-table columns (the artifact also carries KG-provenance
# columns — kg_canon_version / kg_source_document_id — that the portable
# seeds don't create; those are dropped here).
_RULE_COLUMNS = [
    "rule_id", "rule_number", "rule_name", "section", "jurisdiction_code",
    "is_federal_default", "target_table", "target_id_expr", "violation_sql",
    "violation_reason", "severity", "citation", "validation_version",
]


def _split_top_level(values: str) -> list[str]:
    """Split a SQL VALUES payload on top-level commas (quote/paren aware)."""
    out: list[str] = []
    buf: list[str] = []
    depth = 0
    in_str = False
    i = 0
    while i < len(values):
        c = values[i]
        if in_str:
            if c == "'":
                if i + 1 < len(values) and values[i + 1] == "'":
                    buf.append("''")
                    i += 2
                    continue
                in_str = False
            buf.append(c)
        elif c == "'":
            in_str = True
            buf.append(c)
        elif c == "(":
            depth += 1
            buf.append(c)
        elif c == ")":
            depth -= 1
            buf.append(c)
        elif c == "," and depth == 0:
            out.append("".join(buf).strip())
            buf = []
        else:
            buf.append(c)
        i += 1
    if buf:
        out.append("".join(buf).strip())
    return out


def _sql_literal_to_py(tok: str):
    t = tok.strip()
    up = t.upper()
    if up == "NULL":
        return None
    if up in ("TRUE", "FALSE"):
        return up == "TRUE"
    if t.startswith("'") and t.endswith("'"):
        return t[1:-1].replace("''", "'")
    try:
        return int(t)
    except ValueError:
        return t  # e.g. CURRENT_TIMESTAMP() — callers handle explicitly


def _load_fl_rules() -> int:
    text = FL_RULES_SQL.read_text(encoding="utf-8")
    inserts = list(_INSERT_RE.finditer(text))
    if not inserts:
        raise RuntimeError(f"no INSERT statements found in {FL_RULES_SQL}")

    # The artifact's own preamble does CREATE OR REPLACE + deletes US rows —
    # both would clobber shared state, so only the row payloads are executed.
    query(
        "DELETE FROM INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES "
        "WHERE jurisdiction_code = 'US-FL'"
    )

    cols_sql = ", ".join(_RULE_COLUMNS)
    slots = ", ".join(["%s"] * len(_RULE_COLUMNS))
    n = 0
    for m in inserts:
        names = [c.strip().lower() for c in m.group("cols").split(",")]
        values = [_sql_literal_to_py(v) for v in _split_top_level(m.group("vals"))]
        if len(names) != len(values):
            raise RuntimeError(
                f"column/value count mismatch in {FL_RULES_SQL} "
                f"({len(names)} cols vs {len(values)} values)"
            )
        row = dict(zip(names, values, strict=True))
        query(
            f"INSERT INTO INSURANCE_REGULATORY.REFERENCE.TSPR_VALIDATION_RULES "
            f"({cols_sql}, generated_at) SELECT {slots}, CURRENT_TIMESTAMP()",
            tuple(row.get(c) for c in _RULE_COLUMNS),
        )
        n += 1
    return n


def main() -> int:
    print(f"Seeding FL FHCF filing state on backend '{backend_name()}'\n")

    n_policies = _seed_bronze()
    print(f"  ✓ Guidewire Bronze: {n_policies} FL policies loaded "
          f"({_pol(1)}..{_pol(len(FL_POLICIES))})")

    if _drop_legacy_bronze():
        print("  ✓ BRONZE.FL_FHCF_POLICY: legacy shortcut table dropped")

    created = _seed_filing_batch()
    print(f"  ✓ GOLD.FILING_BATCH {FILING_ID}: "
          + ("created (status=validated)" if created else "already present"))

    n_rules = _load_fl_rules()
    print(f"  ✓ REFERENCE.TSPR_VALIDATION_RULES: {n_rules} US-FL rules loaded")

    # Rebuild the FHCF Silver/Gold layers so the warehouse is immediately
    # consistent with the fresh Bronze rows (also part of every run-cycle
    # via scripts.run_silver / scripts.run_gold).
    from scripts.run_fhcf import gold_fhcf, silver_fhcf
    n_silver = silver_fhcf()
    n_gold = gold_fhcf()
    print(f"  ✓ SILVER.FHCF_EXPOSURE_STAGING: {n_silver} rows · "
          f"GOLD.FHCF_EXPOSURE_RECORDS: {n_gold} rows (stamped {FILING_ID})")

    print("\nRe-run is idempotent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
