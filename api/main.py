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
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import random as _random

from fastapi import Body

from api.registry import (
    DOCS,
    WIRE_LAYOUTS_FOR_SLUG,
    extraction_path_for,
    get_doc,
    rects_path_for,
    wire_layouts_for,
)
from api.rhs_demo import router as rhs_router
from packages.adapters.lhs.gre.neo4j_adapter import Neo4jGREAdapter
from packages.adapters.shared.llm.openai_adapter import OpenAIAdapter
from packages.config.settings import settings
from packages.lhs.citations.pdf_highlight import CitationRectsBundle, compute_rects_bundle
from packages.lhs.materialization.materialize import materialize
from packages.lhs.sentinel.agent import Sentinel
from packages.lhs.sentinel.filter import strip_parser_owned
from packages.lhs.sentinel.schema import SentinelExtraction
from scripts.generate_sample_submission import fetch_layout, fill_record
from scripts.validate_submission import validate_record

app = FastAPI(title="RegulAI LHS", version="0.1.0")

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
    allow_headers=["*"],
)

UI_DIR = Path("ui")
MOCK_UI_DIR = Path("mock-ui-v2")


# -- UI serving ---------------------------------------------------------------

if UI_DIR.exists():
    app.mount("/static/ui", StaticFiles(directory=UI_DIR), name="ui_static")
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


@app.post("/api/regulations/{slug}/extract")
def run_extraction(slug: str) -> JSONResponse:
    doc = get_doc(slug)
    if doc is None or not doc.path.exists():
        raise HTTPException(status_code=404, detail=f"Document {slug!r} not found")

    text = doc.path.read_text(encoding="utf-8")
    llm = OpenAIAdapter()
    sentinel = Sentinel(llm)
    extraction = sentinel.extract(text, document_label=doc.path.name)

    # Defense: for parser-owned slugs, drop any RecordLayout / FieldRequirement /
    # CodeList / CodeValue Sentinel may have emitted. The deterministic parser
    # owns those; LLM variants of the same content cause phantom layouts.
    if doc.slug in WIRE_LAYOUTS_FOR_SLUG:
        extraction, filter_stats = strip_parser_owned(extraction)
        if filter_stats["dropped_nodes"]:
            print(
                f"[extract] {slug}: filtered out {filter_stats['dropped_nodes']} "
                f"parser-owned nodes ({filter_stats['by_type']})"
            )

    out_path = extraction_path_for(doc)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(extraction.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )

    # Pixel-perfect citation rects via PyMuPDF — proves provenance and gives
    # the UI exact coordinates instead of fragile text-layer matching.
    rects_located = 0
    if doc.pdf_path and doc.pdf_path.exists():
        bundle = compute_rects_bundle(
            doc.pdf_path,
            text,
            extraction,
            page_start=doc.pdf_start_page,
            page_end=doc.pdf_end_page,
        )
        rects_path_for(doc).write_text(
            json.dumps(bundle.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        rects_located = sum(1 for r in bundle.citation_rects if r)

    return JSONResponse({
        "slug": slug,
        "model": llm.model,
        "n_nodes": len(extraction.proposed_nodes),
        "n_relationships": len(extraction.proposed_relationships),
        "n_citations": len(extraction.citations),
        "n_citation_rects_located": rects_located,
        "summary": extraction.summary,
        "extraction": extraction.model_dump(mode="json"),
    })


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

    with Neo4jGREAdapter() as gre:
        result = materialize(
            extraction, gre, document_label=doc.slug, rects_bundle=rects_bundle
        )

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
    return {
        "status": "ok",
        "model": settings.openai_model,
        "neo4j": settings.neo4j_uri,
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
