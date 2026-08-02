"""Agentic-ETL API — profile a source, propose a mapping, review, compile, validate.

The data-plane counterpart to the regulation-extraction endpoints in main.py.
Backs ui/mapping-review.html. The heavy stages (compile, validate) are added
alongside the mapper package pieces; this router wires them to the UI.
"""

from __future__ import annotations

import json
import time as _time
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse

from packages.rhs.mapper.profiler import profile_file

router = APIRouter(prefix="/api/mapping", tags=["mapping"])

# Spec onboarding is an admin capability — reuse the RHS identity layer.
from api.rhs_demo import current_user as _user, require as _require  # noqa: E402


def _gate(user: dict) -> None:
    _require(user, "mapping")


def _rec(agent: str, task: str, **kw) -> None:
    """Best-effort agent-console telemetry — must never break the flow."""
    try:
        from api.rhs_demo import record_agent_run
        record_agent_run(agent, task, **kw)
    except Exception:  # noqa: BLE001
        pass

SAMPLES_DIR = Path("data/samples")
MAPPINGS_DIR = Path("materialized/mappings")


def _safe_source(name: str) -> Path:
    """Resolve a source file under data/samples only (no path traversal)."""
    path = SAMPLES_DIR / Path(name).name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"sample not found: {name}")
    return path


def _spec_path(label: str, suffix: str) -> Path:
    return MAPPINGS_DIR / f"{Path(label).name}.{suffix}.json"


@router.get("/samples")
def list_samples() -> JSONResponse:
    """Available source files to onboard."""
    if not SAMPLES_DIR.exists():
        return JSONResponse({"samples": []})
    files = sorted(
        p.name for p in SAMPLES_DIR.iterdir()
        if p.suffix.lower() in (".csv", ".parquet")
    )
    return JSONResponse({"samples": files})


@router.get("/preview")
def preview(source: str, limit: int = 8) -> JSONResponse:
    """Return the first `limit` rows of a source file for display."""
    path = _safe_source(source)
    import pyarrow.csv as pacsv
    import pyarrow.parquet as pq
    table = pq.read_table(path) if path.suffix.lower() == ".parquet" else pacsv.read_csv(path)
    cols = table.column_names
    head = table.slice(0, limit).to_pylist()
    rows = [["" if r.get(c) is None else str(r.get(c)) for c in cols] for r in head]
    return JSONResponse({"columns": cols, "rows": rows, "total": table.num_rows})


@router.post("/propose")
def propose(body: dict = Body(...), user: dict = Depends(_user)) -> JSONResponse:
    """Profile the source and ask the agent for a mapping spec.

    Returns {profile, spec}. Persists the raw spec so review/compile can reload
    it. The LLM call is the only slow/keyed part; profiling alone never fails.
    """
    _gate(user)
    source = (body or {}).get("source")
    if not source:
        raise HTTPException(status_code=400, detail="body.source is required")
    path = _safe_source(source)

    _t0 = _time.time()
    profile = profile_file(path)
    _rec("Schema Prober", f"Profile {source}",
         model="profiler",
         duration_ms=int((_time.time() - _t0) * 1000),
         result=f"{len(profile.columns)} columns · {profile.row_count:,} rows")

    # Lazy import so a missing key surfaces as a clean 502 at propose-time only.
    tr = None
    try:
        from api.rhs_demo import AgentTrace
        tr = AgentTrace()
        tr.step("Receive profile", f"{len(profile.columns)} source columns · {profile.row_count:,} rows")
    except Exception:  # noqa: BLE001
        pass
    try:
        from packages.adapters.shared.llm.openai_adapter import OpenAIAdapter
        from packages.rhs.mapper.agent import SchemaMapper
        llm = OpenAIAdapter()
        spec = SchemaMapper(llm).map(profile)
    except Exception as e:  # noqa: BLE001 — surface the cause to the UI
        if tr:
            tr.step("LLM propose", str(e)[:200], status="error")
            tr.finish("Field Mapper", f"Map {source} → silver contract",
                      model=getattr(locals().get("llm"), "model", None),
                      result="agent/parse failure", status="error")
        raise HTTPException(status_code=502, detail=f"mapping agent failed: {e}") from e

    confs = [m.confidence for m in spec.mappings if m.confidence is not None]
    review = sum(1 for m in spec.mappings if m.needs_review)
    if tr:
        tokens = getattr(llm, "last_total_tokens", None)
        tr.step("LLM propose", f"model {llm.model}" + (f" · {tokens:,} tokens" if tokens else ""))
        flagged = [m.target_column for m in spec.mappings if m.needs_review]
        tr.step("Self-review",
                (f"{review} mappings flagged for human review: " + ", ".join(flagged[:6])
                 + ("…" if len(flagged) > 6 else "")) if review else "no mappings flagged",
                status="review" if review else "done")
        tr.finish("Field Mapper", f"Map {source} → silver contract",
                  model=llm.model, tokens=tokens,
                  confidence=(sum(confs) / len(confs)) if confs else None,
                  result=f"{len(spec.mappings)} mapped · {review} need review" if review
                         else f"{len(spec.mappings)} mapped")

    MAPPINGS_DIR.mkdir(parents=True, exist_ok=True)
    _spec_path(profile.source_label, "mapping").write_text(
        json.dumps(spec.model_dump(), indent=2), encoding="utf-8"
    )
    return JSONResponse({"profile": profile.model_dump(), "spec": spec.model_dump()})


@router.post("/save")
def save_reviewed(body: dict = Body(...), user: dict = Depends(_user)) -> JSONResponse:
    """Persist a human-reviewed spec (with overrides + accept flags)."""
    _gate(user)
    label = (body or {}).get("label")
    spec = (body or {}).get("spec")
    if not label or spec is None:
        raise HTTPException(status_code=400, detail="body.label and body.spec are required")
    MAPPINGS_DIR.mkdir(parents=True, exist_ok=True)
    out = _spec_path(label, "reviewed")
    out.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    return JSONResponse({"ok": True, "path": str(out)})


@router.get("/spec/{label}")
def get_spec(label: str) -> JSONResponse:
    """Return the reviewed spec if present, else the raw proposed spec."""
    spec, source = _load_spec(label)
    return JSONResponse({"source": source, "spec": spec})


def _load_spec(label: str) -> tuple[dict, str]:
    for suffix in ("reviewed", "mapping"):
        p = _spec_path(label, suffix)
        if p.exists():
            return json.loads(p.read_text()), suffix
    raise HTTPException(status_code=404, detail=f"no spec for {label}")


def _resolve_source(label: str) -> Path:
    """Find the source file whose stem matches the spec label."""
    name = Path(label).name
    for p in SAMPLES_DIR.glob(f"{name}.*"):
        if p.suffix.lower() in (".csv", ".parquet"):
            return p
    raise HTTPException(status_code=404, detail=f"no source file for label {label}")


@router.post("/compile")
def compile_endpoint(body: dict = Body(...), user: dict = Depends(_user)) -> JSONResponse:
    """Compile the reviewed spec into runnable SQL (accepted rows only)."""
    _gate(user)
    label = (body or {}).get("label")
    if not label:
        raise HTTPException(status_code=400, detail="body.label is required")
    spec, _ = _load_spec(label)
    source = _resolve_source(label)
    from packages.rhs.mapper.compiler import compile_spec
    _t0 = _time.time()
    try:
        cm = compile_spec(spec, source)
    except ValueError as e:
        _rec("Edit Compiler", f"Compile {label} mapping → SQL",
             model="compiler", duration_ms=int((_time.time() - _t0) * 1000),
             result="spec rejected", status="error")
        raise HTTPException(status_code=422, detail=str(e)) from e
    _rec("Edit Compiler", f"Compile {label} mapping → SQL",
         model="compiler", duration_ms=int((_time.time() - _t0) * 1000),
         result=f"{len(cm.columns)} columns → {cm.target_table}"
                + (f" · {len(cm.excluded)} excluded" if cm.excluded else ""))
    return JSONResponse({
        "target_table": cm.target_table,
        "columns": cm.columns,
        "sql": cm.insert_sql,
        "select_sql": cm.select_sql,
        "excluded": cm.excluded,
        "source_path": cm.source_path,
    })


@router.post("/validate")
def validate_endpoint(body: dict = Body(...), user: dict = Depends(_user)) -> JSONResponse:
    """Dry-run the compiled load on ephemeral DuckDB and check it fail-closed."""
    _gate(user)
    label = (body or {}).get("label")
    if not label:
        raise HTTPException(status_code=400, detail="body.label is required")
    spec, _ = _load_spec(label)
    source = _resolve_source(label)
    from packages.rhs.mapper.compiler import compile_spec
    from packages.rhs.mapper.validator import validate_compiled
    try:
        cm = compile_spec(spec, source)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    _t0 = _time.time()
    report = validate_compiled(cm)
    ok = bool(report.get("ok"))
    _rec("Mapping Validator", f"Dry-run {label} load on DuckDB",
         model="validator", duration_ms=int((_time.time() - _t0) * 1000),
         result=f"{report.get('row_count_output', 0):,}/{report.get('row_count_source', 0):,} rows · "
                + ("all checks pass" if ok else "fail-closed"),
         status="done" if ok else "error")
    return JSONResponse(report)
