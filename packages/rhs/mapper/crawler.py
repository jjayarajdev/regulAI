"""DB Crawler — stage 0 of agentic ETL.

Point it at a source database and it introspects the catalog (schemas → tables →
columns, with keys and a small peek) into a `CatalogProfile`, then — on approval
— pulls a bounded sample of a chosen table into a `SourceProfile` that the
existing profile→propose→review→compile→validate pipeline consumes unchanged.

Design:
  * **Generic introspection.** One `Connector` interface, three engines behind it
    (DuckDB, SQLite, Postgres). Adding an engine is a new subclass, nothing else.
  * **Read-only.** Every connector opens read-only where the driver allows, and
    only ever issues SELECT / catalog queries. The crawler cannot mutate a source.
  * **Schema-first.** `introspect()` reads the catalog and peeks a few rows;
    moving real volume is a separate, explicit `pull_to_profile()` call — the
    human-gated action in the workforce model.

DSN forms accepted by `connect()`:
    duckdb:///path/to.duckdb      ·  or a bare *.duckdb / *.ddb path
    sqlite:///path/to.sqlite      ·  or a bare *.sqlite / *.db / *.sqlite3 path
    postgresql://user:pw@host:port/dbname   (psycopg required: `uv sync --extra crawler`)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from packages.rhs.mapper.catalog import CatalogProfile, ColumnNode, TableNode
from packages.rhs.mapper.schema import ColumnProfile, SourceProfile

# System schemas every engine exposes but no one wants to onboard.
_SYSTEM_SCHEMAS = {"information_schema", "pg_catalog", "pg_toast", "sqlite_master"}
_SAMPLE_ROWS = 3          # catalog peek — schema-level, not a data pull
_PULL_LIMIT = 5000        # default bound for pull_to_profile
_SAMPLE_VALUES = 5


# ─────────────────────────────────────────────────────────────────────────────
# Connector interface
# ─────────────────────────────────────────────────────────────────────────────
class Connector:
    """Read-only introspection + bounded sampling over one source database."""

    engine = "abstract"

    def __init__(self, label: str) -> None:
        self.label = label

    # -- catalog --
    def tables(self) -> list[tuple[str, str]]:
        """Return [(schema, table), …] excluding system objects."""
        raise NotImplementedError

    def columns(self, schema: str, table: str) -> list[ColumnNode]:
        raise NotImplementedError

    def row_count(self, schema: str, table: str) -> int:
        raise NotImplementedError

    def sample(self, schema: str, table: str, limit: int) -> tuple[list[str], list[list]]:
        """Return (column_names, rows) for the first `limit` rows."""
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - trivial
        pass

    # -- shared helpers --
    def _quote(self, schema: str, table: str) -> str:
        # Every engine here honours double-quoted identifiers.
        return f'"{schema}"."{table}"' if schema else f'"{table}"'

    def catalog(self, sample_rows: int = _SAMPLE_ROWS) -> CatalogProfile:
        nodes: list[TableNode] = []
        for schema, table in self.tables():
            cols = self.columns(schema, table)
            try:
                n = self.row_count(schema, table)
            except Exception:
                n = -1
            peek: list[dict] = []
            if sample_rows > 0:
                try:
                    names, rows = self.sample(schema, table, sample_rows)
                    peek = [
                        {c: _stringify(v) for c, v in zip(names, row, strict=False)}
                        for row in rows
                    ]
                except Exception:
                    peek = []
            nodes.append(TableNode(
                schema_name=schema, name=table, row_count=n,
                columns=cols, sample_rows=peek,
            ))
        return CatalogProfile(engine=self.engine, database=self.label, tables=nodes)


def _stringify(v) -> str:
    if v is None:
        return ""
    s = str(v)
    return s if len(s) <= 60 else s[:57] + "…"


# ─────────────────────────────────────────────────────────────────────────────
# DuckDB
# ─────────────────────────────────────────────────────────────────────────────
class DuckDBConnector(Connector):
    engine = "duckdb"

    def __init__(self, path: str) -> None:
        import duckdb
        super().__init__(Path(path).name)
        # read_only refuses to create/modify the file.
        self._con = duckdb.connect(path, read_only=True)
        self._pk = self._load_pks()
        self._fk = self._load_fks()

    def _load_pks(self) -> set[tuple[str, str, str]]:
        try:
            rows = self._con.execute(
                "SELECT schema_name, table_name, constraint_column_names "
                "FROM duckdb_constraints() WHERE constraint_type = 'PRIMARY KEY'"
            ).fetchall()
        except Exception:
            return set()
        pks: set[tuple[str, str, str]] = set()
        for schema, table, cols in rows:
            for c in cols or []:
                pks.add((schema, table, c))
        return pks

    def _load_fks(self) -> dict[tuple[str, str, str], str]:
        try:
            rows = self._con.execute(
                "SELECT schema_name, table_name, constraint_column_names, "
                "referenced_table, referenced_column_names "
                "FROM duckdb_constraints() WHERE constraint_type = 'FOREIGN KEY'"
            ).fetchall()
        except Exception:
            return {}
        fks: dict[tuple[str, str, str], str] = {}
        for schema, table, cols, ref_table, ref_cols in rows:
            for i, c in enumerate(cols or []):
                # referenced schema isn't reported; assume same schema as the FK.
                ref_col = (ref_cols or [c])[i] if i < len(ref_cols or []) else c
                fks[(schema, table, c)] = f"{schema}.{ref_table}.{ref_col}"
        return fks

    def tables(self) -> list[tuple[str, str]]:
        rows = self._con.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_type IN ('BASE TABLE', 'VIEW') "
            "AND table_schema NOT IN ('information_schema', 'pg_catalog') "
            "ORDER BY table_schema, table_name"
        ).fetchall()
        return [(s, t) for s, t in rows]

    def columns(self, schema: str, table: str) -> list[ColumnNode]:
        rows = self._con.execute(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position",
            [schema, table],
        ).fetchall()
        return [
            ColumnNode(
                name=name, dtype=str(dtype),
                nullable=(str(nullable).upper() != "NO"),
                primary_key=(schema, table, name) in self._pk,
                references=self._fk.get((schema, table, name)),
            )
            for name, dtype, nullable in rows
        ]

    def row_count(self, schema: str, table: str) -> int:
        return self._con.execute(f"SELECT count(*) FROM {self._quote(schema, table)}").fetchone()[0]

    def sample(self, schema: str, table: str, limit: int) -> tuple[list[str], list[list]]:
        cur = self._con.execute(f"SELECT * FROM {self._quote(schema, table)} LIMIT {int(limit)}")
        names = [d[0] for d in cur.description]
        return names, [list(r) for r in cur.fetchall()]

    def close(self) -> None:
        self._con.close()


# ─────────────────────────────────────────────────────────────────────────────
# SQLite  (single schema — reported as 'main')
# ─────────────────────────────────────────────────────────────────────────────
class SQLiteConnector(Connector):
    engine = "sqlite"

    def __init__(self, path: str) -> None:
        super().__init__(Path(path).name)
        # mode=ro → the driver opens the file read-only.
        uri = f"file:{Path(path).as_posix()}?mode=ro"
        self._con = sqlite3.connect(uri, uri=True)

    def tables(self) -> list[tuple[str, str]]:
        rows = self._con.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view') "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return [("main", r[0]) for r in rows]

    def columns(self, schema: str, table: str) -> list[ColumnNode]:
        info = self._con.execute(f'PRAGMA table_info("{table}")').fetchall()
        # PRAGMA foreign_key_list → (id, seq, table, from, to, on_update, on_delete, match)
        fks = {
            fk[3]: f"main.{fk[2]}.{fk[4]}"
            for fk in self._con.execute(f'PRAGMA foreign_key_list("{table}")').fetchall()
        }
        out: list[ColumnNode] = []
        for _cid, name, ctype, notnull, _dflt, pk in info:
            out.append(ColumnNode(
                name=name, dtype=(ctype or "").upper() or "TEXT",
                nullable=not bool(notnull), primary_key=bool(pk),
                references=fks.get(name),
            ))
        return out

    def row_count(self, schema: str, table: str) -> int:
        return self._con.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]

    def sample(self, schema: str, table: str, limit: int) -> tuple[list[str], list[list]]:
        cur = self._con.execute(f'SELECT * FROM "{table}" LIMIT {int(limit)}')
        names = [d[0] for d in cur.description]
        return names, [list(r) for r in cur.fetchall()]

    def close(self) -> None:
        self._con.close()


# ─────────────────────────────────────────────────────────────────────────────
# Postgres  (psycopg — optional dep, lazy-imported)
# ─────────────────────────────────────────────────────────────────────────────
class PostgresConnector(Connector):
    engine = "postgres"

    def __init__(self, dsn: str) -> None:
        try:
            import psycopg
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "Postgres crawling needs psycopg — install with `uv sync --extra crawler`."
            ) from e
        super().__init__(urlparse(dsn).path.lstrip("/") or "postgres")
        self._con = psycopg.connect(dsn, autocommit=True)
        self._con.execute("SET default_transaction_read_only = on")

    def tables(self) -> list[tuple[str, str]]:
        rows = self._con.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_schema NOT IN ('information_schema','pg_catalog') "
            "AND table_type IN ('BASE TABLE','VIEW') ORDER BY table_schema, table_name"
        ).fetchall()
        return [(s, t) for s, t in rows]

    def columns(self, schema: str, table: str) -> list[ColumnNode]:
        cols = self._con.execute(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
            (schema, table),
        ).fetchall()
        pk = self._keys(schema, table, "PRIMARY KEY")
        fk = self._foreign_keys(schema, table)
        return [
            ColumnNode(
                name=name, dtype=str(dtype),
                nullable=(str(nullable).upper() != "NO"),
                primary_key=name in pk, references=fk.get(name),
            )
            for name, dtype, nullable in cols
        ]

    def _keys(self, schema: str, table: str, kind: str) -> set[str]:
        rows = self._con.execute(
            "SELECT kcu.column_name FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name "
            "  AND tc.table_schema = kcu.table_schema "
            "WHERE tc.constraint_type = %s AND tc.table_schema = %s AND tc.table_name = %s",
            (kind, schema, table),
        ).fetchall()
        return {r[0] for r in rows}

    def _foreign_keys(self, schema: str, table: str) -> dict[str, str]:
        rows = self._con.execute(
            "SELECT kcu.column_name, ccu.table_schema, ccu.table_name, ccu.column_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema "
            "JOIN information_schema.constraint_column_usage ccu "
            "  ON tc.constraint_name = ccu.constraint_name "
            "WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = %s AND tc.table_name = %s",
            (schema, table),
        ).fetchall()
        return {r[0]: f"{r[1]}.{r[2]}.{r[3]}" for r in rows}

    def row_count(self, schema: str, table: str) -> int:
        return self._con.execute(f'SELECT count(*) FROM {self._quote(schema, table)}').fetchone()[0]

    def sample(self, schema: str, table: str, limit: int) -> tuple[list[str], list[list]]:
        cur = self._con.execute(f'SELECT * FROM {self._quote(schema, table)} LIMIT {int(limit)}')
        names = [d.name for d in cur.description]
        return names, [list(r) for r in cur.fetchall()]

    def close(self) -> None:
        self._con.close()


# ─────────────────────────────────────────────────────────────────────────────
# Factory + public API
# ─────────────────────────────────────────────────────────────────────────────
def connect(dsn: str) -> Connector:
    """Open a read-only connector for a DSN or a bare DuckDB/SQLite file path."""
    scheme = urlparse(dsn).scheme.lower()

    if scheme in ("postgresql", "postgres"):
        return PostgresConnector(dsn)
    if scheme == "duckdb":
        return DuckDBConnector(_local_path(dsn))
    if scheme == "sqlite":
        return SQLiteConnector(_local_path(dsn))
    if scheme:
        raise ValueError(f"Unsupported source scheme '{scheme}://'. Use duckdb/sqlite/postgresql.")

    # No scheme → infer from file suffix.
    suffix = Path(dsn).suffix.lower()
    if suffix in (".duckdb", ".ddb"):
        return DuckDBConnector(dsn)
    if suffix in (".sqlite", ".sqlite3", ".db"):
        return SQLiteConnector(dsn)
    raise ValueError(
        f"Can't infer engine from '{dsn}'. Use a duckdb://, sqlite://, or postgresql:// DSN."
    )


def _local_path(dsn: str) -> str:
    """Strip a duckdb:// / sqlite:// scheme back to a filesystem path."""
    p = urlparse(dsn)
    return (p.netloc + p.path) if (p.netloc or p.path) else dsn


def introspect(dsn: str, sample_rows: int = _SAMPLE_ROWS) -> CatalogProfile:
    """Stage 0a — read the catalog of a source database into a `CatalogProfile`."""
    con = connect(dsn)
    try:
        return con.catalog(sample_rows=sample_rows)
    finally:
        con.close()


def pull_to_profile(
    dsn: str, schema: str, table: str, limit: int = _PULL_LIMIT,
) -> SourceProfile:
    """Stage 0b — the human-gated pull. Read a bounded sample of one table and
    profile it into the same `SourceProfile` the file-based pipeline consumes.
    """
    con = connect(dsn)
    try:
        total = con.row_count(schema, table)
        names, rows = con.sample(schema, table, limit)
    finally:
        con.close()

    n = len(rows)
    columns: list[ColumnProfile] = []
    for i, name in enumerate(names):
        values = [r[i] for r in rows]
        non_null = [v for v in values if v is not None and v != ""]
        distinct = len({str(v) for v in non_null})
        samples = [str(v) for v in non_null[:_SAMPLE_VALUES]]
        columns.append(ColumnProfile(
            name=name,
            inferred_type=_infer_type(non_null),
            null_rate=round((n - len(non_null)) / n, 4) if n else 0.0,
            distinct_count=distinct,
            sample_values=samples,
        ))

    return SourceProfile(
        source_label=f"{con.label}.{schema}.{table}",
        row_count=total,
        sampled_rows=n,
        columns=columns,
    )


def _infer_type(values: list) -> str:
    """Cheap physical-type guess from sampled Python values (DB metadata is not
    carried through the generic row fetch, so we infer from the data itself)."""
    if not values:
        return "null"
    if all(isinstance(v, bool) for v in values):
        return "bool"
    if all(isinstance(v, int) for v in values):
        return "int64"
    if all(isinstance(v, (int, float)) for v in values):
        return "double"
    return "string"
