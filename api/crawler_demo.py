"""DB Crawler + Transform API — stages 0 and 4 of agentic ETL, for the demo UI.

Backs ui/crawler.html (`/admin/crawler`):
    sources   → list the seeded local source databases
    catalog   → generic introspection (schemas/tables/columns/keys)   [deterministic]
    plan      → CrawlPlanner scores tables + finds joins               [agent]
    transform → pull a table, resolve registry transforms, run them    [agent + deterministic]

The agent stages lazy-import the LLM adapter so a missing key surfaces as a clean
502 at call time, never at import. Source access is confined to data/source_dbs.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse

from packages.rhs.mapper.crawler import connect, introspect, pull_to_profile

router = APIRouter(prefix="/api/crawler", tags=["crawler"])

SOURCE_DIR = Path("data/source_dbs")
_ENGINE_BY_SUFFIX = {".duckdb": "duckdb", ".ddb": "duckdb",
                     ".sqlite": "sqlite", ".sqlite3": "sqlite", ".db": "sqlite"}

# Friendly blurbs for the seeded demo databases.
_BLURB = {
    "pas_export.duckdb": "Modern policy-admin export — clean names, PK/FK, schema `pas`.",
    "legacy_admin.sqlite": "Legacy AS/400 dump — cryptic names, MMDDYYYY dates, money-as-text, junk table.",
}


def _safe_db(name: str) -> Path:
    """Resolve a source DB under data/source_dbs only (no path traversal)."""
    path = SOURCE_DIR / Path(name).name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"source db not found: {name}")
    if path.suffix.lower() not in _ENGINE_BY_SUFFIX:
        raise HTTPException(status_code=400, detail=f"unsupported source db: {name}")
    return path


@router.get("/sources")
def list_sources() -> JSONResponse:
    """The seeded local databases the crawler can introspect."""
    if not SOURCE_DIR.exists():
        return JSONResponse({"sources": []})
    out = []
    for p in sorted(SOURCE_DIR.iterdir()):
        eng = _ENGINE_BY_SUFFIX.get(p.suffix.lower())
        if eng:
            out.append({"name": p.name, "engine": eng, "blurb": _BLURB.get(p.name, "")})
    return JSONResponse({"sources": out})


@router.get("/catalog")
def catalog(source: str) -> JSONResponse:
    """Stage 0a — deterministic introspection of a source database."""
    path = _safe_db(source)
    try:
        cat = introspect(str(path))
    except Exception as e:  # noqa: BLE001 — surface the cause to the UI
        raise HTTPException(status_code=500, detail=f"introspection failed: {e}") from e
    return JSONResponse(cat.model_dump())


@router.post("/plan")
def plan(body: dict = Body(...)) -> JSONResponse:
    """Stage 0 agent — score every table's relevance + role, find the joins."""
    source = (body or {}).get("source")
    if not source:
        raise HTTPException(status_code=400, detail="body.source is required")
    path = _safe_db(source)
    cat = introspect(str(path))
    try:
        from packages.adapters.shared.llm.openai_adapter import OpenAIAdapter
        from packages.rhs.mapper.crawler_agent import CrawlPlanner
        crawl = CrawlPlanner(OpenAIAdapter()).plan(cat)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"crawl planner failed: {e}") from e
    return JSONResponse({"catalog": cat.model_dump(), "plan": crawl.model_dump()})


def _mem_sample(path: Path, schema: str, table: str, n: int):
    """Fetch the first `n` rows into an in-memory DuckDB `src` table (all VARCHAR
    — legacy sources arrive as text). Returns (mem_connection, column_names, rows)."""
    con = connect(str(path))
    try:
        names, rows = con.sample(schema, table, n)
    finally:
        con.close()
    mem = duckdb.connect(":memory:")
    cols_ddl = ", ".join(f'"{c}" VARCHAR' for c in names)
    mem.execute(f"CREATE TABLE src ({cols_ddl})")
    if rows:
        ph = ",".join("?" * len(names))
        mem.executemany(f"INSERT INTO src VALUES ({ph})",
                        [[None if v is None else str(v) for v in r] for r in rows])
    return mem, names, rows


def _live_samples(path: Path, schema: str, table: str, steps, n: int) -> dict:
    """Load the sample into an in-memory DuckDB and run each step's SQL, so the
    UI can show source → transformed on real rows."""
    from packages.rhs.mapper.transform_agent import compiled_sql

    mem, names, rows = _mem_sample(path, schema, table, n)

    out = []
    for s in steps:
        chain = " │ ".join(c.rule_id for c in s.rules)
        params = [{"rule": c.rule_id, "kv": [{"name": p.name, "value": p.value} for p in c.params]}
                  for c in s.rules if c.params]
        sql, err = compiled_sql(s)
        is_null = all(c.rule_id == "null" for c in s.rules) if s.rules else True
        entry = {
            "target_column": s.target_column, "source_column": s.source_column,
            "chain": chain, "params": params, "confidence": s.confidence,
            "needs_review": s.needs_review, "rationale": s.rationale,
            "sql": sql, "error": err, "samples": [],
        }
        if sql and s.source_column and not is_null:
            try:
                pairs = mem.execute(
                    f'SELECT "{s.source_column}" AS before, {sql} AS after FROM src LIMIT {n}'
                ).fetchall()
                entry["samples"] = [{"before": _s(b), "after": _s(a)} for b, a in pairs]
            except Exception as e:  # noqa: BLE001 — a bad chain shows in-row, not a 500
                entry["error"] = f"{type(e).__name__}: {e}"
        out.append(entry)

    # Raw source records — the actual rows going in, before any transform.
    preview = {"columns": names, "rows": [[_s(v) for v in r] for r in rows]}
    return {"steps": out, "preview": preview}


def _s(v) -> str:
    return "" if v is None else str(v)


@router.post("/transform")
def transform(body: dict = Body(...)) -> JSONResponse:
    """Stage 4 — pull a table, resolve registry transforms, run them live."""
    source = (body or {}).get("source")
    table = (body or {}).get("table")
    if not source or not table or "." not in table:
        raise HTTPException(status_code=400, detail="body.source and body.table (SCHEMA.TABLE) required")
    path = _safe_db(source)
    schema, tbl = table.split(".", 1)

    profile = pull_to_profile(str(path), schema, tbl, limit=5000)
    try:
        from packages.adapters.shared.llm.openai_adapter import OpenAIAdapter
        from packages.rhs.mapper.transform_agent import TransformResolver
        plan = TransformResolver(OpenAIAdapter()).resolve(profile)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"transform resolver failed: {e}") from e

    live = _live_samples(path, schema, tbl, plan.transforms, n=6)
    return JSONResponse({
        "profile": profile.model_dump(),
        "plan": plan.model_dump(),
        "live": live,
    })


@router.get("/rules")
def rules() -> JSONResponse:
    """The transform registry — the closed vocabulary the agent selects from.

    Surfacing it makes the demo legible: the agent can only pick a rule that
    exists here and is golden-tested; it never invents SQL.
    """
    from packages.rhs.mapper.transforms import REGISTRY
    out = [
        {
            "id": r.id, "category": r.category, "summary": r.summary,
            "params": [p.name if p.required else f"{p.name}?" for p in r.params],
            "example_in": r.example_in, "example_out": r.example_out,
            "needs_review": r.needs_review,
        }
        for r in REGISTRY.values()
    ]
    return JSONResponse({"rules": out, "count": len(out)})


@router.post("/apply")
def apply(body: dict = Body(...)) -> JSONResponse:
    """Re-run a reviewer's edited mapping on the real sample (the 'review' action).

    body: {source, table, source_column, rules:[{rule_id, params:{k:v}}]}
    Returns {ok, sql, error, samples} so the SME sees the corrected before→after
    before accepting. Compiles through the same registry — fail-closed on an
    unknown rule or a chain that can't run on the data.
    """
    from packages.rhs.mapper.transforms import UnknownTransformError, compile_step

    source = (body or {}).get("source")
    table = (body or {}).get("table")
    source_column = (body or {}).get("source_column") or None
    rules = (body or {}).get("rules") or []
    if not source or not table or "." not in table:
        raise HTTPException(status_code=400, detail="body.source and body.table (SCHEMA.TABLE) required")
    path = _safe_db(source)
    schema, tbl = table.split(".", 1)

    if not source_column:
        return JSONResponse({"ok": False, "sql": None, "samples": [],
                             "error": "no source column selected — this field has no source in this table"})

    # Fold the reviewer's rule chain into SQL via the registry (fail-closed).
    expr = f'"{source_column}"'
    try:
        for rc in rules:
            expr = compile_step(rc.get("rule_id"), expr, rc.get("params") or {})
    except UnknownTransformError as e:
        return JSONResponse({"ok": False, "sql": None, "samples": [], "error": f"unknown transform: {e}"})
    except (ValueError, KeyError) as e:
        return JSONResponse({"ok": False, "sql": None, "samples": [], "error": str(e)})

    mem, names, _ = _mem_sample(path, schema, tbl, 6)
    if source_column not in names:
        return JSONResponse({"ok": False, "sql": expr, "samples": [],
                             "error": f"'{source_column}' is not a column of {table}"})
    try:
        pairs = mem.execute(
            f'SELECT "{source_column}" AS before, {expr} AS after FROM src LIMIT 6'
        ).fetchall()
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"ok": False, "sql": expr, "samples": [], "error": f"{type(e).__name__}: {e}"})
    return JSONResponse({
        "ok": True, "sql": expr,
        "samples": [{"before": _s(b), "after": _s(a)} for b, a in pairs],
    })
