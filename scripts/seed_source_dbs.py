"""Seed three local *source* databases for the DB Crawler demo.

These stand in for the heterogeneous systems a carrier actually runs — a modern
policy-admin export, a legacy mainframe dump, and a cloud policy DB — each with
its own naming, encodings and mess. The crawler introspects them generically and
an agent decides which tables feed the canonical model.

  data/source_dbs/pas_export.duckdb   — DuckDB · "modern PAS", clean names, schema `pas`, PK/FK
  data/source_dbs/legacy_admin.sqlite — SQLite · "AS/400 dump", cryptic names, money-as-text, junk table
  (Postgres)                          — "cloud policy DB", multi-schema, FKs — seeded only if reachable

Run:
    uv run python -m scripts.seed_source_dbs
    uv run python -m scripts.seed_source_dbs --postgres-dsn postgresql://localhost/regulai_src

Postgres is optional and skipped cleanly when no DSN is given / it's unreachable
(set --postgres-dsn, or the SOURCE_PG_DSN / DATABASE_URL env var). DuckDB + SQLite
are file-based and always built — zero server, zero billing.

Idempotent: recreates the files from scratch each run.

Then crawl one:
    uv run python -m scripts.crawl_source data/source_dbs/pas_export.duckdb --profile-only
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

import duckdb

OUT = Path("data/source_dbs")


# ── shared demo data (homeowners) — same reality, three different shapes ──────
# (policy_no, naic, insured, product, eff, exp, state, zip5, status)
POLICIES = [
    ("HO-2025-000101", "26522", "Rivera, Marcus",     "HO3", "2025-01-15", "2026-01-15", "TX", "78701", "ACTIVE"),
    ("HO-2025-000102", "26522", "Okafor, Amara",       "HO3", "2025-02-01", "2026-02-01", "TX", "75201", "ACTIVE"),
    ("HO-2025-000103", "26522", "Nguyen, Thi",         "HO5", "2025-02-14", "2026-02-14", "TX", "77002", "ACTIVE"),
    ("HO-2025-000104", "26522", "Delgado, Sofia",      "HO3", "2025-03-03", "2026-03-03", "TX", "78205", "ACTIVE"),
    ("HO-2025-000105", "26522", "Brooks, Daniel",      "HO6", "2025-03-20", "2026-03-20", "TX", "79901", "ACTIVE"),
    ("HO-2025-000106", "26522", "Haddad, Leila",       "HO3", "2025-04-11", "2026-04-11", "TX", "76102", "CANCELLED"),
    ("HO-2025-000107", "26522", "Petrov, Anton",       "HO5", "2025-05-01", "2026-05-01", "TX", "78501", "ACTIVE"),
    ("HO-2025-000108", "26522", "Washington, Carla",   "HO3", "2025-05-22", "2026-05-22", "TX", "75601", "ACTIVE"),
    ("HO-2025-000109", "26522", "Ibarra, Ruben",       "HO3", "2025-06-09", "2026-06-09", "TX", "78040", "ACTIVE"),
    ("HO-2025-000110", "26522", "Sørensen, Erik",      "HO5", "2025-06-30", "2026-06-30", "TX", "77494", "ACTIVE"),
]

# (policy_no, coverage_a, coverage_c, deductible, written_premium, term_months, txn_type)
PREMIUMS = [
    ("HO-2025-000101", 325000, 162500, 2500, 1842.00, 12, "NEW"),
    ("HO-2025-000102", 410000, 205000, 2500, 2190.50, 12, "NEW"),
    ("HO-2025-000103", 560000, 280000, 5000, 3025.00, 12, "NEW"),
    ("HO-2025-000104", 289000, 144500, 1000, 1655.75, 12, "NEW"),
    ("HO-2025-000105", 175000,  87500, 1000,  980.00, 12, "NEW"),
    ("HO-2025-000106", 305000, 152500, 2500, 1720.00, 12, "CANCEL"),
    ("HO-2025-000107", 495000, 247500, 5000, 2760.25, 12, "NEW"),
    ("HO-2025-000108", 362000, 181000, 2500, 1988.00, 12, "NEW"),
    ("HO-2025-000109", 268000, 134000, 1000, 1512.50, 12, "NEW"),
    ("HO-2025-000110", 540000, 270000, 5000, 2934.00, 12, "NEW"),
]

# (policy_no, street, city, zip5, protection_class, construction, year_built)
LOCATIONS = [
    ("HO-2025-000101", "1200 Rio Grande St", "Austin",      "78701", "3", "FRAME",   1998),
    ("HO-2025-000102", "4400 Cedar Springs",  "Dallas",      "75201", "4", "MASONRY", 2005),
    ("HO-2025-000103", "8100 Kirby Dr",       "Houston",     "77002", "2", "FRAME",   2012),
    ("HO-2025-000104", "615 E Commerce St",   "San Antonio", "78205", "3", "MASONRY", 1988),
    ("HO-2025-000105", "300 N Mesa St",       "El Paso",     "79901", "5", "FRAME",   1975),
    ("HO-2025-000106", "500 Main St",         "Fort Worth",  "76102", "4", "MASONRY", 2001),
    ("HO-2025-000107", "1101 S 10th St",      "McAllen",     "78501", "3", "FRAME",   2018),
    ("HO-2025-000108", "220 N Green St",      "Longview",    "75601", "6", "FRAME",   1969),
    ("HO-2025-000109", "900 Water St",        "Laredo",      "78040", "4", "MASONRY", 2009),
    ("HO-2025-000110", "24000 Westheimer",    "Katy",        "77494", "3", "FRAME",   2015),
]


def seed_duckdb() -> Path:
    """Modern PAS export — clean names, a `pas` schema, real PK/FK constraints."""
    path = OUT / "pas_export.duckdb"
    if path.exists():
        path.unlink()
    con = duckdb.connect(str(path))
    con.execute("CREATE SCHEMA IF NOT EXISTS pas")

    con.execute("""
        CREATE TABLE pas.policy (
            policy_number   VARCHAR PRIMARY KEY,
            carrier_naic    VARCHAR,
            insured_name    VARCHAR,
            product_code    VARCHAR,
            effective_date  DATE,
            expiration_date DATE,
            state_code      VARCHAR,
            zip5            VARCHAR,
            status          VARCHAR
        )""")
    con.executemany("INSERT INTO pas.policy VALUES (?,?,?,?,?,?,?,?,?)", POLICIES)

    con.execute("""
        CREATE TABLE pas.premium (
            premium_id       INTEGER PRIMARY KEY,
            policy_number    VARCHAR REFERENCES pas.policy(policy_number),
            coverage_a_dwelling DOUBLE,
            coverage_c_contents DOUBLE,
            deductible       DOUBLE,
            written_premium  DOUBLE,
            term_months      INTEGER,
            transaction_type VARCHAR
        )""")
    con.executemany(
        "INSERT INTO pas.premium VALUES (?,?,?,?,?,?,?,?)",
        [(i + 1, *row) for i, row in enumerate(PREMIUMS)],
    )

    con.execute("""
        CREATE TABLE pas.location (
            location_id      INTEGER PRIMARY KEY,
            policy_number    VARCHAR REFERENCES pas.policy(policy_number),
            street           VARCHAR,
            city             VARCHAR,
            zip5             VARCHAR,
            protection_class VARCHAR,
            construction_type VARCHAR,
            year_built       INTEGER
        )""")
    con.executemany(
        "INSERT INTO pas.location VALUES (?,?,?,?,?,?,?,?)",
        [(i + 1, *row) for i, row in enumerate(LOCATIONS)],
    )
    con.close()
    return path


def seed_sqlite() -> Path:
    """Legacy AS/400 dump — cryptic uppercase names, MMDDYYYY dates, money as
    text with commas, and a junk SYSLOG table the agent should reject."""
    path = OUT / "legacy_admin.sqlite"
    if path.exists():
        path.unlink()
    con = sqlite3.connect(str(path))

    con.execute("""
        CREATE TABLE POLMAST (
            POLNO  TEXT PRIMARY KEY,
            CONO   TEXT,          -- company (NAIC) code
            INSDNM TEXT,          -- insured name
            EFFDT  TEXT,          -- MMDDYYYY
            EXPDT  TEXT,
            STCD   TEXT,
            ZIPCD  TEXT,
            STAT   TEXT
        )""")
    con.executemany("INSERT INTO POLMAST VALUES (?,?,?,?,?,?,?,?)", [
        (p[0], p[1], p[2], _mmddyyyy(p[4]), _mmddyyyy(p[5]), p[6], p[7], p[8][:1])
        for p in POLICIES
    ])

    con.execute("""
        CREATE TABLE PREMDTL (
            SEQ      INTEGER PRIMARY KEY,
            POLNO    TEXT REFERENCES POLMAST(POLNO),
            COVA     TEXT,        -- dwelling limit
            COVC     TEXT,        -- contents limit
            DEDAMT   TEXT,
            WRTNPREM TEXT,        -- e.g. "1,842.00"
            TRMMO    INTEGER
        )""")
    con.executemany("INSERT INTO PREMDTL VALUES (?,?,?,?,?,?,?)", [
        (i + 1, r[0], f"{r[1]:,}", f"{r[2]:,}", f"{r[3]:,}", f"{r[4]:,.2f}", r[5])
        for i, r in enumerate(PREMIUMS)
    ])

    # Junk operational table — noise the relevance agent should flag as 'junk'.
    con.execute("CREATE TABLE SYSLOG (LOGID INTEGER PRIMARY KEY, TSTAMP TEXT, MSG TEXT)")
    con.executemany("INSERT INTO SYSLOG VALUES (?,?,?)", [
        (1, "2025-06-30 02:00:01", "NIGHTLY BATCH OK"),
        (2, "2025-06-30 02:04:17", "3182 ROWS EXPORTED"),
    ])
    con.commit()
    con.close()
    return path


def seed_postgres(dsn: str) -> str:
    """Cloud policy DB — normalized across a `reference` and an `underwriting`
    schema, with a FK from policies to carriers. Requires a reachable Postgres."""
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as con:
        con.execute("DROP SCHEMA IF EXISTS underwriting CASCADE")
        con.execute("DROP SCHEMA IF EXISTS reference CASCADE")
        con.execute("CREATE SCHEMA reference")
        con.execute("CREATE SCHEMA underwriting")

        con.execute("""
            CREATE TABLE reference.carriers (
                naic          TEXT PRIMARY KEY,
                carrier_name  TEXT,
                domicile_state TEXT
            )""")
        con.execute(
            "INSERT INTO reference.carriers VALUES (%s,%s,%s)",
            ("26522", "Lone Star Mutual Insurance Co", "TX"),
        )

        con.execute("""
            CREATE TABLE underwriting.policies (
                policy_id    TEXT PRIMARY KEY,
                naic         TEXT REFERENCES reference.carriers(naic),
                insured_name TEXT,
                product_code TEXT,
                eff_date     DATE,
                exp_date     DATE,
                state        TEXT,
                zip          TEXT,
                status       TEXT
            )""")
        con.executemany(
            "INSERT INTO underwriting.policies VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            [(p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], p[8]) for p in POLICIES],
        )

        con.execute("""
            CREATE TABLE underwriting.premiums (
                premium_id       SERIAL PRIMARY KEY,
                policy_id        TEXT REFERENCES underwriting.policies(policy_id),
                coverage_a       NUMERIC,
                coverage_c       NUMERIC,
                deductible       NUMERIC,
                written_premium  NUMERIC,
                transaction_type TEXT
            )""")
        con.executemany(
            "INSERT INTO underwriting.premiums "
            "(policy_id, coverage_a, coverage_c, deductible, written_premium, transaction_type) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            [(r[0], r[1], r[2], r[3], r[4], r[6]) for r in PREMIUMS],
        )
    return dsn


def _mmddyyyy(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{m}{d}{y}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Seed local source DBs for the DB Crawler demo.")
    ap.add_argument("--postgres-dsn", default=os.getenv("SOURCE_PG_DSN") or os.getenv("DATABASE_URL"),
                    help="Postgres DSN to seed (optional). Skipped if unset/unreachable.")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)

    d = seed_duckdb()
    print(f"  ✓ DuckDB  {d}  (schema pas · policy/premium/location · {len(POLICIES)} policies)")

    s = seed_sqlite()
    print(f"  ✓ SQLite  {s}  (POLMAST/PREMDTL + junk SYSLOG · MMDDYYYY dates · money-as-text)")

    if args.postgres_dsn:
        try:
            seed_postgres(args.postgres_dsn)
            print(f"  ✓ Postgres {args.postgres_dsn}  (schemas reference + underwriting)")
        except ImportError:
            print("  ⤫ Postgres skipped — psycopg not installed (uv sync --extra crawler).")
        except Exception as e:
            print(f"  ⤫ Postgres skipped — {type(e).__name__}: {e}")
    else:
        print("  · Postgres skipped — pass --postgres-dsn or set SOURCE_PG_DSN to seed one.")

    print("\n  Crawl one:")
    print("    uv run python -m scripts.crawl_source data/source_dbs/pas_export.duckdb --profile-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
