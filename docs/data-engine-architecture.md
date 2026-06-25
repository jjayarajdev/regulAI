# Data-engine architecture — making new warehouses cheap to add

## The problem

Adding a warehouse today means writing a full driver **and** a full seed script,
copy-pasted from an existing one and re-debugged:

| Concern | snowflake_client | duckdb_client | databricks_client |
|---|---|---|---|
| Lazy connection + lock + `list[dict]` shaping | duplicated | duplicated | duplicated |
| Param style | `%s` native | `%s`→`?` | `%s` inline |
| SQL dialect rewrites | none (source) | TO_VARCHAR/DATEDIFF/PARSE_JSON | TO_VARCHAR/DATEDIFF/PARSE_JSON **again** |
| Seed | PUT + COPY INTO | `scripts/seed_duckdb.py` | `scripts/seed_databricks.py` (near-dup) |

Engine #4 ≈ a ~250-line driver + ~200-line seed. The `REGULAI_DB` seam already
makes *selecting* an engine generic; the remaining cost is the **per-engine
boilerplate**, which is 90% identical between engines.

## The shape of the fix

Pull the invariant 90% into a `BaseDriver` + generic `Seeder`. Each engine
contributes only a small **`SqlDialect`** — a declarative table of what's
genuinely different. Adding engine #4 drops to ~40 lines.

```
packages/rhs/
  db.py                 # dispatcher (unchanged surface: query/close/backend_name)
  engine/
    base.py             # BaseDriver, SqlDialect, param binding, row shaping
    snowflake.py        # SnowflakeDialect  (source dialect — no rewrites)
    duckdb.py           # DuckDBDialect     (ATTACH catalog + macros)
    databricks.py       # DatabricksDialect (inline params + catalog rewrite)
  seed/
    bronze.py           # BRONZE_TABLES, VALIDATION_RULES, REASON_CODES, GOLD DDL  (data, once)
    seeder.py           # generic: create schemas → load bronze → rules → gold DDL
scripts/
  seed_warehouse.py     # thin CLI: pick dialect from REGULAI_DB, run Seeder
```

The three existing `*_client.py` modules become 3-line shims that re-export from
`engine/` (back-compat), or `db.py` points straight at `engine/` and they're
deleted. Call sites already import only from `db.py`, so nothing else changes.

## The two interfaces

```python
# packages/rhs/engine/base.py

class SqlDialect:
    """Everything that differs between engines, declared as data."""
    name: str
    param_style: str = "pyformat"     # "pyformat" (%s passthrough) | "qmark" (%s→?) | "inline"
    catalog_rewrite: bool = False     # rewrite INSURANCE_REGULATORY. → configured catalog
    rewrites: list[tuple[re.Pattern, str | Callable]] = []   # ordered SQL text rewrites
    type_map: dict[str, str] = {}     # DuckDB-inferred type → engine DDL type (seeding)

    def connect(self): ...            # return a DBAPI-ish connection
    def on_connect(self, conn): ...   # optional: ATTACH, install macros, session settings
    def bulk_load(self, conn, table, parquet_path): ...   # the one truly engine-specific seed step

    def translate(self, sql: str) -> str:
        for pat, repl in self.rewrites:
            sql = pat.sub(repl, sql)
        return sql

    def bind(self, sql: str) -> str:  # param-marker handling
        return sql if self.param_style != "qmark" else _pyformat_to_qmark(sql)


class BaseDriver:
    """Invariant: lazy singleton connection, locking, execute, row shaping."""
    def __init__(self, dialect: SqlDialect): self.dialect, self._conn, self._lock = dialect, None, Lock()

    def _connection(self):
        with self._lock:
            if self._conn is None:
                self._conn = self.dialect.connect()
                self.dialect.on_connect(self._conn)
            return self._conn

    def query(self, sql, params=None) -> list[dict]:
        sql = self.dialect.bind(self.dialect.translate(sql))
        with self._lock:
            cur = self._connection().cursor()
            try:
                cur.execute(sql, list(params) if params else None)
                if cur.description is None: return []
                cols = [d[0].lower() for d in cur.description]
                return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
            finally:
                cur.close()

    def close(self): ...
```

`db.py` just maps a name to a dialect instance:

```python
_DIALECTS = {"snowflake": SnowflakeDialect, "duckdb": DuckDBDialect, "databricks": DatabricksDialect}
_driver = BaseDriver(_DIALECTS[backend_name()]())
def query(sql, params=None): return _driver.query(sql, params)
```

## What each existing engine becomes

Everything they already do, just classified as data instead of duplicated code.
Example (Databricks, ~35 lines instead of ~140):

```python
class DatabricksDialect(SqlDialect):
    name = "databricks"
    param_style = "inline"
    catalog_rewrite = True
    rewrites = [
        (TO_VARCHAR_FMT, lambda m: f"date_format(CAST({m[1]} AS TIMESTAMP), '{spark_fmt(m[2])}')"),
        (DATEDIFF,       lambda m: f"date_diff({m[1].upper()},"),
        (PARSE_JSON,     "("),
        (TO_DATE,        "to_date("),
    ]
    type_map = {"HUGEINT": "DECIMAL(38,0)", "VARCHAR": "STRING", "INTEGER": "INT", ...}
    def connect(self):
        c = databricks.sql.connect(**_dbx_env(), use_inline_params=True); return c
    def bulk_load(self, conn, table, pq):   # inferred DDL + chunked INSERT
        ...
```

Shared regexes (TO_VARCHAR, DATEDIFF, PARSE_JSON…) live once in `base.py`; a
dialect just lists which it uses and the replacement.

## Adding engine #4 (e.g. Postgres) — the payoff

```python
# packages/rhs/engine/postgres.py — the whole thing
class PostgresDialect(SqlDialect):
    name = "postgres"
    param_style = "pyformat"          # psycopg uses %s natively
    rewrites = [(PARSE_JSON, "("), (TO_VARCHAR_FMT, r"to_char(\1, '\2')"), (CURRENT_TS, "now()")]
    type_map = {"HUGEINT": "NUMERIC", "VARCHAR": "TEXT", ...}
    def connect(self): return psycopg.connect(os.environ["REGULAI_PG_DSN"])
    def bulk_load(self, conn, table, pq): conn.cursor().copy_expert(f"COPY {table} FROM STDIN", open(pq))
```
Register one line in `db.py`. No new driver loop, no new seed script, no new
result-shaping. ~30 lines, done.

## Rules-as-data: one canonical source

The validation rules carry raw `violation_sql`. Today `seed_duckdb` and
`seed_databricks` each hand-write them in their own dialect
(`date_diff('day',…)` vs `date_diff(DAY,…)`). Instead, author the rules **once
in the canonical (Snowflake) dialect** in `seed/bronze.py`, and let each
engine's `dialect.translate()` convert them at seed time — the same translation
the runtime path already applies. Single source of truth for the rules; the
per-engine spelling falls out of the dialect.

## Migration plan (behavior-preserving)

1. Add `engine/base.py` (BaseDriver + SqlDialect + shared regexes) — no behavior change.
2. Port each existing driver into a `*Dialect` (snowflake → duckdb → databricks),
   one at a time, keeping the old module as a shim until its dialect is verified.
3. Repoint `db.py` to the dialect registry.
4. Unify the seeds into `seed/seeder.py` + `seed/bronze.py`; replace
   `seed_duckdb.py` / `seed_databricks.py` with thin `seed_warehouse.py`.
5. **Re-verify**: rebuild DuckDB + Databricks, re-run the endpoint + mutation
   smoke checks (the same ones already used), confirm identical results.

Risk is low because it's a refactor, not a redesign — the SQL emitted to each
engine is byte-identical to today; only where it's *defined* moves. The verified
Databricks/DuckDB/Snowflake behavior is the acceptance test.

## When to reach for Ibis / SQLAlchemy instead

Those libraries are the "write once, run on 20 backends" answer and would
replace `connect()` + param handling for free. But the rules-as-data
`violation_sql` fragments are raw engine SQL that must run regardless of any ORM
— so a per-dialect translation layer (exactly the `SqlDialect` above) is needed
either way. Adopt Ibis only if you later decide to drop raw SQL across the whole
codebase; until then it's a large migration that doesn't remove the part that's
actually engine-coupled.

## Effort

~1 focused pass: base + three dialects + unified seed + re-verify. Net result:
the three drivers (~430 lines) + two seeds (~400 lines) collapse to one base +
three small dialects + one seeder, and engine #4 costs ~40 lines instead of ~450.
