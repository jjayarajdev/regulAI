"""RegulAI LHS FastAPI app.

Endpoints:
  GET  /                                serve the side-by-side UI
  GET  /api/regulations                 list all documents
  GET  /api/regulations/{slug}          metadata + raw text + (cached extraction if any)
  POST /api/regulations/{slug}/extract  run Sentinel (writes extraction JSON)
  POST /api/regulations/{slug}/approve  materialize the cached extraction to KG
  GET  /api/kg/stats                    counts by type (for status bar / Neo4j health)

Run: make ui
"""

import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import random as _random

from fastapi import Body

from api.registry import (
    DOCS,
    REGULATIONS_DIR,
    WIRE_LAYOUTS_FOR_SLUG,
    DocEntry,
    extraction_path_for,
    get_doc,
    register_uploaded_doc,
    rects_path_for,
    wire_layouts_for,
)
from api.rhs_demo import router as rhs_router
from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
from packages.adapters.shared.llm.openai_adapter import OpenAIAdapter
from packages.config.settings import settings
from packages.lhs.citations.pdf_highlight import CitationRectsBundle, compute_rects_bundle
from packages.lhs.materialization.materialize import materialize
from packages.lhs.materialization.parser_boundary import ParserBoundaryViolation
from packages.lhs.sentinel.agent import Sentinel
from packages.lhs.sentinel.filter import strip_parser_owned
from packages.lhs.sentinel.schema import SentinelExtraction
from scripts.generate_sample_submission import fetch_layout, fill_record
from scripts.validate_submission import validate_record

logger = logging.getLogger("regulai.api")

app = FastAPI(title="RegulAI LHS", version="0.1.0")


# ── Keep-warm (opt-in via REGULAI_KEEPWARM=1) ────────────────────────────────
# A serverless warehouse (Databricks) auto-stops when idle, so the first request
# after a lull pays a ~15-45s cold start. When enabled, ping the warehouse on an
# interval shorter than its auto-stop so the demo never hits a cold load. Touches
# the bronze tables the /validate path scans, to keep the data + plan cache warm.
# OFF by default — leaving it on holds the warehouse open continuously (cost /
# Free-Edition quota). Enable for demo days, disable after.
import asyncio as _asyncio  # noqa: E402
import os as _os  # noqa: E402
import threading as _threading  # noqa: E402


def _keep_warm_query() -> None:
    from packages.rhs.db import query
    query("SELECT 1")  # wakes / keeps the warehouse session alive
    for tbl in ("GW_PC_JOB", "GW_PC_POLICY", "GW_CC_CLAIM"):
        query(f"SELECT count(*) FROM INSURANCE_REGULATORY.BRONZE.{tbl}")


@app.on_event("startup")
async def _start_keep_warm() -> None:
    if _os.environ.get("REGULAI_KEEPWARM", "").strip().lower() not in ("1", "true", "yes"):
        return
    interval = int(_os.environ.get("REGULAI_KEEPWARM_SECONDS", "240"))

    async def _loop() -> None:
        while True:
            try:
                await _asyncio.to_thread(_keep_warm_query)
            except Exception:
                logging.getLogger("keepwarm").warning("keep-warm ping failed", exc_info=True)
            await _asyncio.sleep(interval)

    _asyncio.create_task(_loop())
    logging.getLogger("keepwarm").info("keep-warm enabled · every %ss", interval)

# CORS — Neo4j Browser is served from :7474 and needs to fetch the
# Cypher guide HTML from our :8765. Local-dev origins only.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:7474",
        "http://127.0.0.1:7474",
        "http://localhost:8765",
        "http://127.0.0.1:8765",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)


# -- Databricks-unavailable handler ------------------------------------------
# When the warehouse can't start (paused, serverless disabled, cold-start
# timeout), every query raises. Return a clean 503 with the reason instead of a
# raw 500, so the UI can show "data unavailable" rather than a mystery error.
try:
    from databricks.sql.exc import Error as _DbxError  # type: ignore
except Exception:  # noqa: BLE001 — databricks extra not installed (e.g. duckdb runs)
    _DbxError = None

if _DbxError is not None:
    @app.exception_handler(_DbxError)
    async def _databricks_unavailable(_request, exc):  # noqa: ANN001
        msg = str(exc)
        hint = (" The Databricks serverless warehouse may be disabled — re-enable "
                "'Serverless compute for SQL' in the account console."
                if "Cannot start warehouse" in msg or "disabled" in msg else "")
        return JSONResponse(
            status_code=503,
            content={"detail": f"Databricks warehouse unavailable.{hint} ({msg[:160]})"},
        )


UI_DIR = Path("ui")
MOCK_UI_DIR = Path("mock-ui-v2")


# -- UI serving ---------------------------------------------------------------

if UI_DIR.exists():
    app.mount("/static/ui", StaticFiles(directory=UI_DIR), name="ui_static")

# React workstation (web/) — built into web/dist by the Docker image and served
# at /app. html=True serves index.html for the SPA; assets resolve via Vite
# base '/app/'. Guarded so a source checkout without a build still boots (the
# legacy single-file UI at / keeps working either way).
WEB_DIST = Path("web/dist")
if WEB_DIST.exists():
    app.mount("/app", StaticFiles(directory=WEB_DIST, html=True), name="react_app")

if MOCK_UI_DIR.exists():
    # mount mock-ui-v2's styles directory so we can reuse the design language
    if (MOCK_UI_DIR / "styles").exists():
        app.mount("/static/styles", StaticFiles(directory=MOCK_UI_DIR / "styles"), name="mock_styles")


@app.get("/")
def root() -> FileResponse:
    """Stakeholder-friendly landing page."""
    return FileResponse(UI_DIR / "index.html")


@app.get("/explore")
def explore() -> FileResponse:
    """Side-by-side regulation review UI (the working tool)."""
    return FileResponse(UI_DIR / "regulations.html")


@app.get("/demo")
def demo() -> FileResponse:
    """End-to-end RHS demo: KG → reference → Snowflake → validation flip."""
    return FileResponse(UI_DIR / "demo.html")


@app.get("/validate")
def validate_page() -> FileResponse:
    """Validation engine: live evaluation of REFERENCE.TSPR_VALIDATION_RULES."""
    return FileResponse(UI_DIR / "validate.html")


@app.get("/pipeline")
def pipeline_page() -> FileResponse:
    """Medallion pipeline runner: Bronze → Silver → Gold."""
    return FileResponse(UI_DIR / "pipeline.html")


@app.get("/workstation")
def workstation_page() -> FileResponse:
    """Unified regulatory workstation — single UI binding all RHS endpoints."""
    return FileResponse(UI_DIR / "workstation.html")


@app.get("/admin/schedule")
def admin_schedule_page() -> FileResponse:
    """Admin-only: cron-style schedule editor for the Dagster pipeline.

    Compliance officers see this form, not Dagster's UI. Underneath, the
    schedule is implemented by dagster_project/schedules.py reading the
    same runtime_config.json this page writes to."""
    return FileResponse(UI_DIR / "admin-schedule.html")


@app.get("/admin/upload")
def admin_upload_page() -> FileResponse:
    """Admin-only: upload Excel → land in Bronze → run medallion via Dagster."""
    return FileResponse(UI_DIR / "admin-upload.html")


@app.get("/admin/mapping")
def admin_mapping_page() -> FileResponse:
    """Admin-only: agentic source onboarding — profile → propose → review → compile → validate."""
    return FileResponse(UI_DIR / "mapping-review.html")


@app.get("/admin/crawler")
def admin_crawler_page() -> FileResponse:
    """Admin-only: DB crawler + transform — introspect → plan → pull → resolve transforms."""
    return FileResponse(UI_DIR / "crawler.html")


@app.get("/admin/regulations")
def admin_regulations_page() -> FileResponse:
    """Self-serve regulation/bulletin ingestion — upload PDF → Sentinel (LLM)
    extract → review → approve into the Knowledge Graph."""
    return FileResponse(UI_DIR / "reg-upload.html")


@app.get("/experience")
def experience_page() -> FileResponse:
    """New-experience design reference — CBRE-style compliance workstation
    (dark header, icon rail, KPI dashboard, stage-tab records, record detail
    with decision reasoning + edit). Mock-first; the React /app follows this."""
    return FileResponse(UI_DIR / "experience.html")


# -- Design explorations (feature/ui-designs) ----------------------------------
# Three takes on the regulatory-compliance UX: Jira-style workspace, TurboTax
# wizard, Stripe-style portfolio cockpit. Static mockups, no backend wiring.


@app.get("/designs", response_class=HTMLResponse)
@app.get("/designs/", response_class=HTMLResponse)
def designs_index() -> FileResponse:
    return FileResponse(UI_DIR / "designs" / "index.html")


@app.get("/designs/01-workspace-jira", response_class=HTMLResponse)
def design_01() -> FileResponse:
    return FileResponse(UI_DIR / "designs" / "01-workspace-jira.html")


@app.get("/designs/02-wizard-turbotax", response_class=HTMLResponse)
def design_02() -> FileResponse:
    return FileResponse(UI_DIR / "designs" / "02-wizard-turbotax.html")


@app.get("/designs/03-cockpit-stripe", response_class=HTMLResponse)
def design_03() -> FileResponse:
    return FileResponse(UI_DIR / "designs" / "03-cockpit-stripe.html")


app.include_router(rhs_router)

from api.mapping_demo import router as mapping_router  # noqa: E402

app.include_router(mapping_router)

from api.crawler_demo import router as crawler_router  # noqa: E402

app.include_router(crawler_router)


# -- KG GraphQL surface (Phase 1.6) -------------------------------------------
# Read-only GraphQL at /api/lhs/kg/graphql with introspection enabled. Schema
# lives in packages/lhs/kg/graphql_schema.py.
from strawberry.fastapi import GraphQLRouter  # noqa: E402

from packages.lhs.kg.graphql_schema import schema as _kg_schema  # noqa: E402

app.include_router(GraphQLRouter(_kg_schema), prefix="/api/lhs/kg/graphql")


# -- Regulations API ----------------------------------------------------------


@app.get("/api/regulations")
def list_regulations() -> JSONResponse:
    """List every document in the registry, with extraction-cache flags."""
    items = []
    for d in DOCS:
        ext_path = extraction_path_for(d)
        items.append({
            "slug": d.slug,
            "label": d.label,
            "category": d.category,
            "blurb": d.blurb,
            "size_bytes": d.path.stat().st_size if d.path.exists() else 0,
            "exists": d.path.exists(),
            "has_extraction": ext_path.exists(),
            "has_pdf": d.pdf_path is not None and d.pdf_path.exists(),
        })
    return JSONResponse({"documents": items})


@app.get("/api/regulations/{slug}")
def get_regulation(slug: str) -> JSONResponse:
    doc = get_doc(slug)
    if doc is None or not doc.path.exists():
        raise HTTPException(status_code=404, detail=f"Document {slug!r} not found")
    text = doc.path.read_text(encoding="utf-8")
    ext_path = extraction_path_for(doc)
    extraction: dict | None = None
    if ext_path.exists():
        extraction = json.loads(ext_path.read_text(encoding="utf-8"))
    rects_path = rects_path_for(doc)
    rects_bundle: dict | None = None
    if rects_path.exists():
        rects_bundle = json.loads(rects_path.read_text(encoding="utf-8"))
    return JSONResponse({
        "slug": doc.slug,
        "label": doc.label,
        "category": doc.category,
        "blurb": doc.blurb,
        "text": text,
        "extraction": extraction,
        "extraction_path": str(ext_path) if ext_path.exists() else None,
        "citation_rects": rects_bundle["citation_rects"] if rects_bundle else None,
        "page_dimensions": rects_bundle["page_dimensions"] if rects_bundle else None,
        "has_pdf": doc.pdf_path is not None and doc.pdf_path.exists(),
        "pdf_url": f"/api/regulations/{doc.slug}/pdf" if (doc.pdf_path and doc.pdf_path.exists()) else None,
        "pdf_start_page": doc.pdf_start_page,
        "pdf_end_page": doc.pdf_end_page,
        "wire_layouts": wire_layouts_for(doc.slug),
    })


@app.get("/api/regulations/{slug}/pdf")
def get_regulation_pdf(slug: str):
    """Serve the source PDF for a document, if it has one."""
    doc = get_doc(slug)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {slug!r} not found")
    if doc.pdf_path is None or not doc.pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"No PDF for {slug!r}")
    return FileResponse(
        doc.pdf_path,
        media_type="application/pdf",
        # Inline so the browser/PDF.js renders rather than downloads.
        headers={"Content-Disposition": f'inline; filename="{doc.pdf_path.name}"'},
    )


@app.post("/api/regulations/upload")
async def upload_regulation(
    file: UploadFile = File(...),
    label: str | None = Form(None),
    category: str | None = Form(None),
) -> JSONResponse:
    """Upload a regulation/bulletin PDF and register it for Sentinel extraction.

    Saves the PDF, extracts its text (PyMuPDF) as the Sentinel input, and adds a
    DocEntry to the registry. From here the existing `/extract` (LLM → KG) and
    `/approve` endpoints take over — same path as the built-in documents.
    """
    name = (file.filename or "").strip()
    if not name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported.")

    import re as _re
    stem = _re.sub(r"[^a-z0-9]+", "-", Path(name).stem.lower()).strip("-") or "regulation"
    slug = f"uploaded-{stem}"

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")

    REGULATIONS_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = REGULATIONS_DIR / f"{slug}.pdf"
    pdf_path.write_bytes(data)

    # Extract text (PyMuPDF) → the Sentinel input file.
    try:
        import fitz  # PyMuPDF
        with fitz.open(stream=data, filetype="pdf") as pdf:
            pages = pdf.page_count
            text = "\n\n".join(page.get_text() for page in pdf)
    except Exception as e:  # noqa: BLE001 — surface a clean error
        raise HTTPException(status_code=422, detail=f"Could not read PDF text: {e}") from e
    if not text.strip():
        raise HTTPException(status_code=422, detail="No extractable text (scanned PDF?). OCR not supported yet.")

    text_dir = Path("materialized/uploaded_regulations")
    text_dir.mkdir(parents=True, exist_ok=True)
    text_path = text_dir / f"{slug}.md"
    text_path.write_text(text, encoding="utf-8")

    entry = DocEntry(
        slug=slug,
        label=label or Path(name).stem,
        category=category or "Uploaded regulations & bulletins",
        path=text_path,
        blurb=f"Uploaded {name} · {pages} pages · {len(text):,} chars extracted.",
        pdf_path=pdf_path,
    )
    register_uploaded_doc(entry)

    return JSONResponse({
        "slug": slug, "label": entry.label, "category": entry.category,
        "pages": pages, "chars": len(text),
        "next": f"POST /api/regulations/{slug}/extract  (Sentinel → KG)",
    })


# Background extraction jobs: slug → {status: running|done|error, result, error}.
# The Sentinel LLM call takes ~1–2 min; the UI starts a job and polls /status so
# it never holds a long request open.
_EXTRACT_JOBS: dict[str, dict] = {}


def _run_extraction(doc) -> dict:
    """Run Sentinel on a document, persist the extraction + citation rects, and
    return the result payload. Raises on LLM/parse failure."""
    import time as _t
    from api.rhs_demo import record_agent_run
    _t0 = _t.time()
    text = doc.path.read_text(encoding="utf-8")
    llm = OpenAIAdapter()
    try:
        extraction = Sentinel(llm).extract(text, document_label=doc.path.name)
    except Exception:
        record_agent_run("Rule Extractor", f"Extract {doc.slug}", model=llm.model,
                         duration_ms=int((_t.time() - _t0) * 1000),
                         result="LLM/parse failure", status="error")
        raise
    record_agent_run(
        "Rule Extractor", f"Extract {doc.slug}", model=llm.model,
        duration_ms=int((_t.time() - _t0) * 1000),
        result=f"{len(extraction.proposed_nodes)} nodes · "
               f"{len(extraction.proposed_relationships)} rels",
    )

    # Defense: for parser-owned slugs, drop RecordLayout / FieldRequirement /
    # CodeList / CodeValue Sentinel may have emitted — the parser owns those.
    if doc.slug in WIRE_LAYOUTS_FOR_SLUG:
        extraction, filter_stats = strip_parser_owned(extraction)
        if filter_stats["dropped_nodes"]:
            logger.info("[extract] %s: filtered %s parser-owned nodes (%s)",
                        doc.slug, filter_stats["dropped_nodes"], filter_stats["by_type"])

    out_path = extraction_path_for(doc)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(extraction.model_dump(mode="json"), indent=2), encoding="utf-8")

    rects_located = 0
    if doc.pdf_path and doc.pdf_path.exists():
        bundle = compute_rects_bundle(doc.pdf_path, text, extraction,
                                      page_start=doc.pdf_start_page, page_end=doc.pdf_end_page)
        rects_path_for(doc).write_text(json.dumps(bundle.model_dump(mode="json"), indent=2), encoding="utf-8")
        rects_located = sum(1 for r in bundle.citation_rects if r)

    return {
        "slug": doc.slug, "model": llm.model,
        "n_nodes": len(extraction.proposed_nodes),
        "n_relationships": len(extraction.proposed_relationships),
        "n_citations": len(extraction.citations),
        "n_citation_rects_located": rects_located,
        "summary": extraction.summary,
        "extraction": extraction.model_dump(mode="json"),
    }


def _extract_error(e: Exception) -> str:
    msg = str(e)
    if "insufficient_quota" in msg or "429" in msg:
        return "OpenAI quota exceeded (429) — check billing, or run on prod (separate key)."
    return f"Sentinel LLM extraction failed: {msg}"


@app.post("/api/regulations/{slug}/extract")
def run_extraction(slug: str) -> JSONResponse:
    """Synchronous extract (compat / CLI). The UI uses start+status below."""
    doc = get_doc(slug)
    if doc is None or not doc.path.exists():
        raise HTTPException(status_code=404, detail=f"Document {slug!r} not found")
    try:
        return JSONResponse(_run_extraction(doc))
    except Exception as e:  # noqa: BLE001 — clean JSON, not a 500 page
        raise HTTPException(status_code=502, detail=_extract_error(e)) from e


@app.post("/api/regulations/{slug}/extract/start")
def start_extraction(slug: str) -> JSONResponse:
    """Kick off extraction in the background and return immediately."""
    doc = get_doc(slug)
    if doc is None or not doc.path.exists():
        raise HTTPException(status_code=404, detail=f"Document {slug!r} not found")
    if (_EXTRACT_JOBS.get(slug) or {}).get("status") == "running":
        return JSONResponse({"status": "running"})
    _EXTRACT_JOBS[slug] = {"status": "running", "result": None, "error": None}

    def _work() -> None:
        try:
            _EXTRACT_JOBS[slug] = {"status": "done", "result": _run_extraction(doc), "error": None}
        except Exception as e:  # noqa: BLE001
            _EXTRACT_JOBS[slug] = {"status": "error", "result": None, "error": _extract_error(e)}

    _threading.Thread(target=_work, daemon=True).start()
    return JSONResponse({"status": "running"})


@app.get("/api/regulations/{slug}/extract/status")
def extraction_status(slug: str) -> JSONResponse:
    """Poll target for the background job. Falls back to a cached extraction."""
    job = _EXTRACT_JOBS.get(slug)
    if job:
        return JSONResponse(job)
    doc = get_doc(slug)
    if doc and extraction_path_for(doc).exists():
        ex = json.loads(extraction_path_for(doc).read_text(encoding="utf-8"))
        return JSONResponse({"status": "done", "cached": True, "result": {
            "slug": slug, "model": "cached",
            "n_nodes": len(ex.get("proposed_nodes", [])),
            "n_relationships": len(ex.get("proposed_relationships", [])),
            "n_citations": len(ex.get("citations", [])),
            "summary": ex.get("summary", ""),
            "extraction": ex,
        }})
    return JSONResponse({"status": "idle"})


@app.post("/api/regulations/{slug}/approve")
def approve_extraction(slug: str) -> JSONResponse:
    doc = get_doc(slug)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {slug!r} not found")
    ext_path = extraction_path_for(doc)
    if not ext_path.exists():
        raise HTTPException(
            status_code=400,
            detail="No cached extraction. POST /api/regulations/{slug}/extract first.",
        )
    extraction = SentinelExtraction.model_validate(
        json.loads(ext_path.read_text(encoding="utf-8"))
    )

    rects_bundle: CitationRectsBundle | None = None
    rects_path = rects_path_for(doc)
    if rects_path.exists():
        rects_bundle = CitationRectsBundle.model_validate(
            json.loads(rects_path.read_text(encoding="utf-8"))
        )

    try:
        import time as _t
        from api.rhs_demo import record_agent_run
        _t0 = _t.time()
        with Neo4jGREAdapter() as gre:
            result = materialize(
                extraction, gre, document_label=doc.slug, rects_bundle=rects_bundle
            )
        record_agent_run(
            "KG Materializer", f"Approve {doc.slug} → canon",
            model="graph writer", duration_ms=int((_t.time() - _t0) * 1000),
            result=f"{len(result.nodes_created)} nodes · "
                   f"{result.relationships_created} rels",
        )
    except ParserBoundaryViolation as e:
        # Cluster C: the cached extraction proposes RecordLayout /
        # FieldRequirement on a parser-owned slug. Return a clean 400
        # so the UI can surface the boundary violation instead of a
        # generic 500. The fix is either re-running batch_extract with
        # strip_parser_owned, or relaxing PARSER_OWNED_SLUGS (rare).
        raise HTTPException(
            status_code=400,
            detail={
                "error": "parser_boundary_violation",
                "document_label": e.document_label,
                "offender_count": len(e.offenders),
                "first_offenders": [
                    {"type": t, "name": n} for t, n in e.offenders[:5]
                ],
                "message": str(e),
            },
        ) from e
    except Exception as e:  # noqa: BLE001 — Neo4j unreachable / write error → clean JSON, not a 500 page
        msg = str(e)
        if "already exists" in msg or "ConstraintValidationFailed" in msg:
            raise HTTPException(
                status_code=409,
                detail=f"'{doc.label}' is already approved into the Knowledge Graph.",
            ) from e
        raise HTTPException(
            status_code=502,
            detail=f"Knowledge Graph write failed: {e}. Is Neo4j running and reachable? "
                   "(locally: ./run-docker.sh api neo4j)",
        ) from e

    return JSONResponse({
        "slug": slug,
        "nodes_created": [{"type": t, "name": n} for t, n in result.nodes_created],
        "nodes_reused": [{"type": t, "name": n} for t, n in result.nodes_reused],
        "relationships_created": result.relationships_created,
        "citations_created": result.citations_created,
        "skipped": [
            {"type": s.type, "name": s.name, "reason": s.reason}
            for s in result.skipped_proposals
        ],
        "snapshot_path": str(result.materialized_path) if result.materialized_path else None,
    })


# -- Admin: Dagster schedule -------------------------------------------------
#
# The /admin/schedule UI is a thin layer over Dagster's GraphQL surface +
# the JSON config file Dagster's schedule reads at every tick. The
# endpoints below are intentionally simple — the goal is to let a
# compliance officer set up "run nightly at 2am" without ever seeing
# Dagster's UI. Dagster's web UI on :3000 is still available for the
# data team to dig deeper.


@app.get("/api/admin/schedule")
def get_schedule() -> JSONResponse:
    """Current schedule config + recent Dagster runs + Dagster reachability."""
    from packages.scheduling import config_path, load
    from packages.scheduling.dagster_client import (
        DagsterUnreachable,
        is_reachable,
        list_recent_runs,
    )

    config = load()
    dagster_up = is_reachable()
    runs: list[dict] = []
    if dagster_up:
        try:
            runs = [
                {
                    "run_id": r.run_id,
                    "status": r.status,
                    "job_name": r.job_name,
                    "started_at": r.started_at,
                    "ended_at": r.ended_at,
                    "duration_s": r.duration_s,
                }
                for r in list_recent_runs(limit=10)
            ]
        except (DagsterUnreachable, RuntimeError):
            # Don't 500 the page if Dagster has a transient issue.
            runs = []
    return JSONResponse({
        "config": config.model_dump(mode="json"),
        "config_path": str(config_path()),
        "dagster_url": "http://localhost:3000",
        "dagster_reachable": dagster_up,
        "recent_runs": runs,
    })


@app.put("/api/admin/schedule")
def put_schedule(body: dict = Body(...)) -> JSONResponse:
    """Save a new schedule config. Validates the cron string and the
    pipeline name; Dagster's schedule picks up the new config on its
    next tick (~30s) with no restart."""
    from croniter import croniter as _croniter

    from packages.scheduling import ScheduleConfig, load, save

    current = load()
    incoming = current.model_dump()
    # Accept partial updates — only override the fields the body provides.
    for field in ("schedule_type", "cron_schedule", "enabled", "pipeline"):
        if field in body:
            incoming[field] = body[field]
    # Stamp who/when. Until authn lands (#1 in production-readiness),
    # the user is whatever the UI says it is.
    incoming["updated_by"] = body.get("updated_by") or "admin"

    try:
        new_config = ScheduleConfig.model_validate(incoming)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid schedule config: {e}")

    # Validate cron — refuse bad expressions before they trip Dagster.
    try:
        _croniter(new_config.cron_schedule)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid cron_schedule {new_config.cron_schedule!r}: {e}")

    save(new_config)
    return JSONResponse({
        "ok": True,
        "config": new_config.model_dump(mode="json"),
        "note": "Dagster's schedule will pick up this change on its next tick (~30s).",
    })


@app.post("/api/admin/schedule/run-now")
def run_now() -> JSONResponse:
    """Trigger an immediate run of the full pipeline via Dagster."""
    from packages.scheduling.dagster_client import (
        DagsterUnreachable,
        launch_run,
    )

    try:
        run_id = launch_run("full_pipeline_job")
    except DagsterUnreachable as e:
        raise HTTPException(
            status_code=503,
            detail=f"Dagster is not reachable. Is `make dagster` running? ({e})",
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return JSONResponse({"ok": True, "run_id": run_id})


# -- Admin: uploads (Phase 2A) ------------------------------------------------
#
# Upload-driven Bronze ingest. The /admin/upload page calls these routes.
#
#   GET  /api/admin/upload-templates              — list of templates
#   GET  /api/admin/upload-templates/{table}      — download .xlsx
#   POST /api/admin/uploads                       — upload + convert
#   GET  /api/admin/uploads                       — list past uploads
#   POST /api/admin/uploads/{id}/process          — launch Dagster job


@app.get("/api/admin/upload-templates")
def list_upload_templates() -> JSONResponse:
    """Templates the admin UI can offer for download. Drives the
    dropdown on /admin/upload."""
    from packages.uploads import TEMPLATES

    return JSONResponse({
        "templates": [
            {
                "bronze_table": t.bronze_table,
                "sheet_name": t.sheet_name,
                "description": t.description,
                "column_count": len(t.columns),
                "required_columns": [c.name for c in t.columns if c.required],
                "download_url": f"/api/admin/upload-templates/{t.bronze_table}",
            }
            for t in TEMPLATES
        ],
    })


@app.get("/api/admin/upload-templates/{bronze_table}")
def download_upload_template(bronze_table: str) -> Response:
    """Serve a generated .xlsx for the given Bronze table."""
    from packages.uploads import generate_template_workbook
    from packages.uploads.templates import template_filename_for

    try:
        xlsx_bytes = generate_template_workbook(bronze_table)
        filename = template_filename_for(bronze_table)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"No template registered for {bronze_table!r}. See /api/admin/upload-templates for valid names.",
        )

    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/admin/uploads")
async def upload_xlsx(
    bronze_table: str = Body(..., embed=True),
    file: UploadFile = File(...),
) -> JSONResponse:
    """Accept an .xlsx upload for a Bronze table. Saves, registers,
    converts to Parquet, and returns the upload record. Fails fast on
    schema mismatch so the user sees the problem before they ever click
    'Process'."""
    from packages.uploads import (
        UploadRecord,
        convert_uploaded_xlsx_to_parquet,
        new_upload_dir,
        new_upload_id,
        record_upload,
        update_upload_status,
    )
    from packages.uploads.schemas import get_template
    from packages.uploads.xlsx_to_parquet import ConversionError

    if get_template(bronze_table) is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown bronze_table {bronze_table!r}. See /api/admin/upload-templates.",
        )
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=400,
            detail="Only .xlsx is accepted. Save your file as Excel Workbook (.xlsx), not .xls or .csv.",
        )

    upload_id = new_upload_id()
    root = new_upload_dir(upload_id)
    xlsx_path = root / "original" / file.filename
    body = await file.read()
    xlsx_path.write_bytes(body)

    record = UploadRecord(
        upload_id=upload_id,
        filename=file.filename,
        bronze_table=bronze_table,
        bytes_size=len(body),
    )
    record_upload(record)

    # Convert immediately so schema problems surface BEFORE the user
    # commits to processing. Failures update status → "failed" with the
    # error message so the UI can show what to fix.
    try:
        result = convert_uploaded_xlsx_to_parquet(record)
    except ConversionError as e:
        update_upload_status(upload_id, status="failed", error_message=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    updated = update_upload_status(
        upload_id, status="converted", row_count=result.row_count,
    )

    return JSONResponse({
        "ok": True,
        "upload": updated.to_dict() if updated else record.to_dict(),
        "row_count": result.row_count,
        "skipped_cells": result.skipped_cells,
    })


@app.get("/api/admin/uploads")
def list_uploads_endpoint() -> JSONResponse:
    """All uploads, newest first. Powers the admin UI's history table."""
    from packages.uploads import list_uploads

    return JSONResponse({
        "uploads": [r.to_dict() for r in list_uploads(limit=50)],
    })


@app.post("/api/admin/uploads/{upload_id}/process")
def process_upload(upload_id: str) -> JSONResponse:
    """Launch the Dagster upload_to_gold_job for this upload. Dagster
    reads the upload_id from run config and points Bronze loader at the
    converted Parquet."""
    from packages.scheduling.dagster_client import (
        DagsterUnreachable,
        launch_run,
    )
    from packages.uploads import get_upload, update_upload_status

    record = get_upload(upload_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Upload {upload_id!r} not found.")
    if record.status not in ("converted", "done", "failed"):
        raise HTTPException(
            status_code=400,
            detail=f"Upload {upload_id!r} status is {record.status!r}; must be 'converted', 'done', or 'failed' to (re-)process.",
        )

    # Both op_load_bronze_from_upload and op_mark_upload_done share the
    # UploadLoadConfig schema (they both need upload_id + bronze_table), so
    # Dagster requires config for both ops to be present in the run config.
    op_config = {"upload_id": upload_id, "bronze_table": record.bronze_table}
    try:
        run_id = launch_run(
            "upload_to_gold_job",
            run_config={
                "ops": {
                    "op_load_bronze_from_upload": {"config": op_config},
                    "op_mark_upload_done": {"config": op_config},
                }
            },
            tags={
                "upload.id": upload_id,
                "upload.filename": record.filename,
                "upload.bronze_table": record.bronze_table,
                "triggered_by": "admin_upload_process",
            },
        )
    except DagsterUnreachable as e:
        raise HTTPException(
            status_code=503,
            detail=f"Dagster is not reachable. Is `make dagster` running? ({e})",
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    update_upload_status(upload_id, status="processing", last_run_id=run_id)
    return JSONResponse({"ok": True, "run_id": run_id, "upload_id": upload_id})


# -- KG API -------------------------------------------------------------------


@app.get("/api/kg/stats")
def kg_stats() -> JSONResponse:
    try:
        with Neo4jGREAdapter() as gre:
            return JSONResponse({
                "total_nodes": gre.count_nodes(),
                "total_relationships": gre.count_relationships(),
                "by_type": gre.count_by_type(),
                "neo4j_browser_url": "http://localhost:7474",
            })
    except Exception as e:  # noqa: BLE001 — UI shows the error
        return JSONResponse(
            {"error": str(e), "neo4j_browser_url": "http://localhost:7474"},
            status_code=503,
        )


# -- Neo4j Browser guide served for `:play` -----------------------------------


@app.get("/cypher-guide", response_class=HTMLResponse)
@app.get("/cypher-guide.html", response_class=HTMLResponse)
def cypher_guide() -> HTMLResponse:
    """Curated Cypher tour, loaded in Neo4j Browser via `:play`.

    From a Browser cell:
        :play http://localhost:8765/cypher-guide

    Pages of explanatory text + clickable runnable Cypher cards. Same
    queries as cypher/saved-cypher.json but loaded a different way (and
    without the buggy favorites-import flow).
    """
    guide_path = Path("cypher/guide.html")
    if not guide_path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Guide not built yet. Run `make cypher-guide` to generate {guide_path}.",
        )
    return HTMLResponse(content=guide_path.read_text(encoding="utf-8"))


# -- Landing-page data --------------------------------------------------------


@app.get("/api/landing/stats")
def landing_stats() -> JSONResponse:
    """Headline numbers for the stakeholder landing page.

    Pulled live so the demo cannot accidentally show stale numbers.
    """
    try:
        with Neo4jGREAdapter() as gre, gre.driver.session() as s:
            totals = s.run("""
                MATCH (n:GRENode) WITH count(n) AS nodes
                MATCH ()-[r]->() WITH nodes, count(r) AS rels
                MATCH (l:RecordLayout)
                  WHERE l.name IN ["Premium Record Layout", "Loss Record Layout",
                                   "Notice Record Layout", "Notice Count Record Layout",
                                   "Homeowners Premium Record Layout",
                                   "Homeowners Loss Record Layout"]
                  AND (l)<-[:CONTAINED_IN]-(:FieldRequirement)
                WITH nodes, rels, count(l) AS complete_layouts
                MATCH (b:BulletinOverride)
                RETURN nodes, rels, complete_layouts, count(b) AS active_bulletins
            """).single()
            # Citation rect coverage from the on-disk artefacts
            rects_total = rects_with = 0
            for p in Path("materialized/extractions").glob("*.rects.json"):
                bundle = json.loads(p.read_text(encoding="utf-8"))
                cs = bundle.get("citation_rects") or []
                rects_total += len(cs)
                rects_with += sum(1 for r in cs if r)
            rect_pct = round(100.0 * rects_with / max(1, rects_total), 1)

            return JSONResponse({
                "kg_nodes": totals["nodes"],
                "kg_relationships": totals["rels"],
                "complete_layouts": totals["complete_layouts"],
                "total_canonical_layouts": 6,
                "active_bulletins": totals["active_bulletins"],
                "rect_coverage_pct": rect_pct,
                "rect_coverage_str": f"{rects_with}/{rects_total}",
            })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=503)


@app.get("/api/landing/sample-column")
def landing_sample_column() -> JSONResponse:
    """The 'what TICO actually requires' showcase — column 5-6 of a Premium record."""
    try:
        with Neo4jGREAdapter() as gre, gre.driver.session() as s:
            rows = s.run("""
                MATCH (f:FieldRequirement {field_name: "Record Type", position_start: 5})
                      -[:CODED_BY]->(:CodeList)-[:HAS_VALUE]->(cv:CodeValue)
                RETURN cv.code AS code, cv.notes AS meaning
                ORDER BY cv.code
            """).data()
            return JSONResponse({
                "field_name": "Record Type",
                "column_range": "5-6",
                "values": [
                    {"code": r["code"], "meaning": (r["meaning"] or "").strip()[:120]}
                    for r in rows
                ],
            })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=503)


@app.get("/api/landing/recent-change")
def landing_recent_change() -> JSONResponse:
    """The 'what changed recently' showcase — most recent BulletinOverride summary."""
    try:
        with Neo4jGREAdapter() as gre, gre.driver.session() as s:
            r = s.run("""
                MATCH (b:BulletinOverride)
                WITH b ORDER BY b.effective_date DESC LIMIT 1
                WITH b, date(b.effective_date) AS eff
                OPTIONAL MATCH (b)-[:OVERRIDES]->(retired)
                  WHERE NOT retired:RecordLayout AND NOT retired:RegulationDocument
                OPTIONAL MATCH (:CodeList)-[:HAS_VALUE]->(new_code:CodeValue)
                  WHERE new_code.effective_from = eff
                OPTIONAL MATCH (:RecordLayout)-[:REQUIRES]->(new_field:FieldRequirement)
                  WHERE new_field.effective_from = eff
                RETURN
                  b.name AS bulletin_name,
                  eff AS effective_date,
                  b.notes AS summary,
                  [x IN collect(DISTINCT retired.name)        WHERE x IS NOT NULL] AS retired_names,
                  [x IN collect(DISTINCT new_code.code)       WHERE x IS NOT NULL] AS new_codes,
                  [x IN collect(DISTINCT new_field.field_name) WHERE x IS NOT NULL] AS new_fields
            """).single()
            if r is None:
                return JSONResponse({"bulletin_name": None})
            # Provide a sensible fallback summary if the LLM/seed didn't fill notes.
            summary = r["summary"] or (
                f"Retires: {', '.join(r['retired_names'])}. "
                f"Introduces new codes and fields effective {r['effective_date']}."
                if r["retired_names"] else
                "Bulletin override applied."
            )
            return JSONResponse({
                "bulletin_name": r["bulletin_name"],
                "effective_date": str(r["effective_date"]) if r["effective_date"] else None,
                "summary": summary,
                "retired_names": r["retired_names"],
                "new_codes": r["new_codes"],
                "new_fields": r["new_fields"],
            })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=503)


# -- Landing page routes ------------------------------------------------------


@app.get("/api/health")
def health() -> dict[str, str]:
    # Deliberately sparse: no infrastructure URIs or connection details
    # (this endpoint is unauthenticated).
    return {
        "status": "ok",
        "model": settings.openai_model,
    }


# -- Wire-format Studio: sample generation + validation -----------------------


@app.get("/api/layouts/{layout_name}/sample")
def layout_sample(layout_name: str, scenario: str = "new-policy", seed: int = 42) -> JSONResponse:
    """Generate one sample record from the KG for `layout_name`.

    Returns the 200-char string + a column-by-column annotation the UI
    uses to render the third pane.
    """
    name, fields = fetch_layout(layout_name)
    if not fields:
        raise HTTPException(status_code=404, detail=f"Layout {layout_name!r} has no fields")
    rng = _random.Random(seed)
    record, fills = fill_record(fields, scenario, rng)
    return JSONResponse({
        "layout": name,
        "scenario": scenario,
        "seed": seed,
        "record": record,
        "length": len(record),
        "columns": [
            {
                "position_start": fill.field.position_start,
                "position_length": fill.field.position_length,
                "short_code": fill.field.short_code,
                "field_name": fill.field.field_name,
                "format": fill.field.format,
                "value": fill.value,
                "annotation": fill.annotation,
                "is_skip": fill.field.short_code == "SKIP",
                "field_node_name": fill.field.name,
            }
            for fill in fills
        ],
    })


@app.post("/api/layouts/{layout_name}/validate")
def layout_validate(layout_name: str, body: dict = Body(...)) -> JSONResponse:
    """Validate a single 200-char record against `layout_name`.

    Body: {"record": "<exactly 200 chars>"}.
    Returns per-column errors with kind, actual value, and human detail.
    """
    record = body.get("record")
    if not isinstance(record, str):
        raise HTTPException(status_code=400, detail="Body must include 'record' string")

    name, fields = fetch_layout(layout_name)
    if not fields:
        raise HTTPException(status_code=404, detail=f"Layout {layout_name!r} has no fields")

    res = validate_record(record, fields, record_index=0)
    return JSONResponse({
        "layout": name,
        "ok": res.ok,
        "n_errors": len(res.errors),
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
            for e in res.errors
        ],
    })
