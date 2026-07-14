"""Document registry — every regulation document available to the UI.

Each entry exposes:
  - `slug` — stable URL id
  - `path` — extracted text on disk (Sentinel input)
  - `pdf_path` — the source PDF for left-pane rendering (None for markdown-only docs)
  - `pdf_start_page` / `pdf_end_page` — for sections, the page range within the parent PDF
"""

import json
from dataclasses import dataclass
from pathlib import Path

REGULATIONS_DIR = Path("references/regulations")
TICO_PDF = REGULATIONS_DIR / "TX_Statistical_Plan_Residential_Risks_2026.pdf"
HB2067_PDF = REGULATIONS_DIR / "HB02067I.pdf"
TICO_RECORDLAYOUT_HO_PDF = REGULATIONS_DIR / "tico_recordLayoutHomeOwners.pdf"


@dataclass(frozen=True)
class DocEntry:
    slug: str
    label: str
    category: str
    path: Path
    blurb: str
    pdf_path: Path | None = None
    pdf_start_page: int = 1
    pdf_end_page: int | None = None


# Section page ranges within the TICO Stat Plan PDF (computed from page markers).
DOCS: list[DocEntry] = [
    DocEntry(
        slug="tico-section-a",
        label="TICO Stat Plan — Section A: General Rules",
        category="Texas Statistical Plan for Residential Risks (eff. 2026-01-01)",
        path=Path("synthetic_regulations/real/sections/section_A_general.md"),
        blurb="35 numbered rules covering scope, identifiers, designated agent, transmittal form, and HB 2067 reasons + counts.",
        pdf_path=TICO_PDF,
        pdf_start_page=4,
        pdf_end_page=24,
    ),
    DocEntry(
        slug="tico-section-b",
        label="TICO Stat Plan — Section B: Coding for Premiums and Losses",
        category="Texas Statistical Plan for Residential Risks (eff. 2026-01-01)",
        path=Path("synthetic_regulations/real/sections/section_B_coding.md"),
        blurb="The actual code tables — Cause of Loss, Line of Business, Deductible types, Construction, Roof, etc.",
        pdf_path=TICO_PDF,
        pdf_start_page=25,
        pdf_end_page=39,
    ),
    DocEntry(
        slug="tico-section-c",
        label="TICO Stat Plan — Section C: Record Layout for Premiums",
        category="Texas Statistical Plan for Residential Risks (eff. 2026-01-01)",
        path=Path("synthetic_regulations/real/sections/section_C_record.md"),
        blurb="Field-by-field layout of premium records.",
        pdf_path=TICO_PDF,
        pdf_start_page=40,
        pdf_end_page=60,
    ),
    DocEntry(
        slug="tico-section-d",
        label="TICO Stat Plan — Section D: Record Layout for Losses",
        category="Texas Statistical Plan for Residential Risks (eff. 2026-01-01)",
        path=Path("synthetic_regulations/real/sections/section_D_record.md"),
        blurb="Field-by-field layout of loss records.",
        pdf_path=TICO_PDF,
        pdf_start_page=61,
        pdf_end_page=76,
    ),
    DocEntry(
        slug="tico-section-e",
        label="TICO Stat Plan — Section E: Record Layout for Notices",
        category="Texas Statistical Plan for Residential Risks (eff. 2026-01-01)",
        path=Path("synthetic_regulations/real/sections/section_E_record.md"),
        blurb="HB 2067 notice report layout (cancellation, nonrenewal, declination notices).",
        pdf_path=TICO_PDF,
        pdf_start_page=77,
        pdf_end_page=80,
    ),
    DocEntry(
        slug="tico-section-f",
        label="TICO Stat Plan — Section F: Notice Reason Code Instructions",
        category="Texas Statistical Plan for Residential Risks (eff. 2026-01-01)",
        path=Path("synthetic_regulations/real/sections/section_F_additional.md"),
        blurb="Full HB 2067 reason code list with definitions and source indicators.",
        pdf_path=TICO_PDF,
        pdf_start_page=81,
        pdf_end_page=86,
    ),
    DocEntry(
        slug="tico-section-g",
        label="TICO Stat Plan — Section G: Record Layout for Counts",
        category="Texas Statistical Plan for Residential Risks (eff. 2026-01-01)",
        path=Path("synthetic_regulations/real/sections/section_G_record.md"),
        blurb="HB 2067 count report layout for actual cancellations/nonrenewals/declinations.",
        pdf_path=TICO_PDF,
        pdf_start_page=87,
        pdf_end_page=89,
    ),
    DocEntry(
        slug="hb-2067",
        label="HB 2067 — Declination, Cancellation, Nonrenewal of Insurance Policies",
        category="Texas statute",
        path=Path("synthetic_regulations/real/HB02067I.txt"),
        blurb="89th Legislature, Regular Session. Authorizes the Commissioner to adopt notice and reporting rules.",
        pdf_path=HB2067_PDF,
        pdf_start_page=1,
        pdf_end_page=3,
    ),
    DocEntry(
        slug="tico-record-layout-homeowners",
        label="TICO Wire Layout — Homeowners (Premiums + Losses)",
        category="Texas Statistical Plan — Operational Wire Layouts",
        path=Path("synthetic_regulations/real/wire_layouts/tico_recordLayoutHomeOwners.txt"),
        blurb="Operational record layout TICO actually receives. Defines the 200-char fixed-width line per record, column-by-column, with all enumerated code values. Source for deterministic KG population (parser, not LLM).",
        pdf_path=TICO_RECORDLAYOUT_HO_PDF,
        pdf_start_page=1,
        pdf_end_page=25,
    ),
    DocEntry(
        slug="bulletin-2026-q3-104",
        label="Synthetic Bulletin B-2026-Q3-104 — Named Storm COL split",
        category="Synthetic change bulletin (POC demo)",
        path=Path("synthetic_regulations/synthetic/bulletins/B-2026-Q3-104.md"),
        blurb="DEMO bulletin: splits Cause of Loss code 25 (Windstorm) and adds code 26 for Named Storm Wind, plus 3 new fields.",
        pdf_path=None,  # markdown-only
    ),
    DocEntry(
        slug="bulletin-2027-q1-117",
        label="Synthetic Bulletin B-2027-Q1-117 — Reinsurance Coverage Indicator",
        category="Synthetic change bulletin (POC demo)",
        path=Path("synthetic_regulations/synthetic/bulletins/B-2027-Q1-117.md"),
        blurb="DEMO bulletin: adds a Reinsurance Coverage Indicator (Y/N/U) at column 184 of the Premium Record Layout, effective 2027-01-01. Used by `make demo-new-bulletin` to show end-to-end RAG → review → KG update.",
        pdf_path=None,  # markdown-only
    ),
    # ── Phase 3: Florida regulations (first non-Texas state intake) ──
    DocEntry(
        slug="fl-627-062",
        label="FL Statute 627.062 — Rate Standards",
        category="Florida statute",
        path=Path("synthetic_regulations/real/florida/FL_627_062_rate_standards.txt"),
        blurb="Florida statute governing rate filings for property/casualty insurance. Defines 'file and use' / 'use and file' procedures, the 15 actuarial factors the FL OIR considers, Florida Hurricane Catastrophe Fund treatment, and residential property mitigation requirements.",
        pdf_path=None,
    ),
    DocEntry(
        slug="fl-627-351",
        label="FL Statute 627.351 — Insurance Risk Apportionment Plans (Citizens)",
        category="Florida statute",
        path=Path("synthetic_regulations/real/florida/FL_627_351_citizens.txt"),
        blurb="Florida statute creating Citizens Property Insurance Corporation — the state's residual-market insurer of last resort. Defines the corporation, board, eligibility, rate cap, assessment/surcharge mechanisms, account structure (Personal Lines / Commercial Lines / Coastal), and policy-level reporting requirements.",
        pdf_path=None,
    ),
    DocEntry(
        slug="fl-oir-22-04m",
        label="FL OIR Informational Memorandum OIR-22-04M — Hurricane Ian Data Call",
        category="Florida regulator bulletin",
        path=Path("synthetic_regulations/real/florida/FL_OIR_22_04M_hurricane_data_call.md"),
        blurb="FL OIR Informational Memorandum (FL's equivalent of a TICO bulletin) imposing a weekly claims data call on all P&C insurers following Hurricane Ian. Defines 16 required per-claim data fields, an aggregate summary, special provisions for Citizens, and the CRS fixed-width ASCII submission format.",
        pdf_path=None,
    ),
    DocEntry(
        slug="fl-fhcf-data-call",
        label="FL Hurricane Catastrophe Fund — Annual Data Call Form (FHCF-D1A)",
        category="Florida statistical plan",
        path=Path("synthetic_regulations/real/florida/FL_FHCF_data_call_form.md"),
        blurb="FHCF Annual Data Call Form prescribed by the FL State Board of Administration. 320-character fixed-width record layout with 30+ field requirements, 8 code lists with FL-specific values (wind mitigation, FBC construction codes, opening protection), and 10 validation rules including TX-vs-FL ZIP-prefix detection. Structurally analogous to TICO's homeowners record layout but for FL FHCF participation under §215.555.",
        pdf_path=None,
    ),
]

DOCS_BY_SLUG: dict[str, DocEntry] = {d.slug: d for d in DOCS}


def get_doc(slug: str) -> DocEntry | None:
    return DOCS_BY_SLUG.get(slug)


def extraction_path_for(doc: DocEntry) -> Path:
    return Path("materialized/extractions") / f"{doc.path.stem}.extraction.json"


def rects_path_for(doc: DocEntry) -> Path:
    """Companion file holding citation_rects + page_dimensions for the UI."""
    return Path("materialized/extractions") / f"{doc.path.stem}.rects.json"


# Map a registry slug to the RecordLayout name(s) the parser writes for it.
# When a doc has wire-format layouts in the KG, the UI's third pane lights up
# with sample-record generation and validation against that layout.
WIRE_LAYOUTS_FOR_SLUG: dict[str, list[str]] = {
    "tico-section-c": ["Premium Record Layout"],
    "tico-section-d": ["Loss Record Layout"],
    "tico-section-e": ["Notice Record Layout"],
    "tico-section-g": ["Notice Count Record Layout"],
    "tico-record-layout-homeowners": [
        "Homeowners Premium Record Layout",
        "Homeowners Loss Record Layout",
    ],
}


def wire_layouts_for(slug: str) -> list[str]:
    return WIRE_LAYOUTS_FOR_SLUG.get(slug, [])


# ── Uploaded documents (self-serve regulation/bulletin ingestion) ──────────
# User-uploaded PDFs are registered at runtime and persisted to a manifest so
# they survive restarts. They flow through the same Sentinel-extract → KG-approve
# path as the built-in docs.
UPLOADED_MANIFEST = Path("materialized/uploaded_regulations/manifest.json")


def _entry_to_dict(d: DocEntry) -> dict:
    return {
        "slug": d.slug, "label": d.label, "category": d.category,
        "path": str(d.path), "blurb": d.blurb,
        "pdf_path": str(d.pdf_path) if d.pdf_path else None,
    }


def _entry_from_dict(x: dict) -> DocEntry:
    return DocEntry(
        slug=x["slug"], label=x["label"], category=x.get("category", "Uploaded"),
        path=Path(x["path"]), blurb=x.get("blurb", ""),
        pdf_path=Path(x["pdf_path"]) if x.get("pdf_path") else None,
    )


def _read_manifest() -> list[dict]:
    if UPLOADED_MANIFEST.exists():
        try:
            return json.loads(UPLOADED_MANIFEST.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def register_uploaded_doc(entry: DocEntry) -> None:
    """Add (or replace) an uploaded doc in the live registry + persist it.

    Mutates DOCS in place (slice-assign) rather than rebinding, so importers
    that hold a reference to the list (e.g. api/main.py) see the new entry.
    """
    DOCS[:] = [d for d in DOCS if d.slug != entry.slug]
    DOCS.append(entry)
    DOCS_BY_SLUG[entry.slug] = entry
    manifest = [m for m in _read_manifest() if m.get("slug") != entry.slug]
    manifest.append(_entry_to_dict(entry))
    UPLOADED_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    UPLOADED_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def load_uploaded_docs() -> int:
    """Restore persisted uploaded docs into the registry (called at startup)."""
    n = 0
    for x in _read_manifest():
        try:
            entry = _entry_from_dict(x)
        except Exception:
            continue
        if entry.slug not in DOCS_BY_SLUG:
            DOCS.append(entry)
            DOCS_BY_SLUG[entry.slug] = entry
            n += 1
    return n


load_uploaded_docs()
