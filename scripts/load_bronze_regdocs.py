"""Load regulator-source documents into BRONZE_REGDOCS.

Pulls 3 real regulations + 3 synthetic bulletins from the project's
references/regulations/ + synthetic_regulations/ trees, stamps each one as a
row in RAW_REG_DOCUMENT, and splits the TICO stat plan into per-rule
sections in RAW_REG_SECTION.

Citation-pattern conventions:
  - Stat plan rules: r"A\.34" matches both "Rule A.34" and "A.34-valid-codes"
  - Statutes:         r"559\.052" matches "Tex. Ins. Code §559.052"
  - Record layout:    r"Section [A-G]" coarse-grained for record-type lookups

Idempotent: TRUNCATEs the three tables before re-loading.

Run via:  uv run python -m scripts.load_bronze_regdocs
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from packages.rhs.db import query


ROOT = Path(__file__).resolve().parent.parent


def _doc_id(path: Path) -> str:
    return "doc-" + hashlib.sha1(str(path).encode()).hexdigest()[:12]


def _section_id(doc_id: str, citation: str, seq: int) -> str:
    return f"sec-{doc_id[-8:]}-{seq:03d}-{re.sub(r'[^a-zA-Z0-9]+', '', citation)[:12]}"


def _sql_text(s: str) -> str:
    """Escape a long text blob for Snowflake INSERT — single quotes doubled."""
    return s.replace("'", "''")


def load_documents() -> list[tuple[str, str]]:
    """Insert one row per source document. Returns [(document_id, path), ...]."""
    docs = [
        {
            "doc_type":   "stat_plan",
            "title":      "Texas Statistical Plan for Residential Risks (2026)",
            "issuing":    "TICO",
            "effective":  "2026-01-01",
            "edition":    "2026.1",
            "path":       ROOT / "synthetic_regulations/real/TX_Statistical_Plan_Residential_Risks_2026.txt",
        },
        {
            "doc_type":   "statute",
            "title":      "HB 2067 — Credit Score Declination Reporting",
            "issuing":    "Texas Legislature",
            "effective":  "2026-01-01",
            "edition":    "1",
            "path":       ROOT / "synthetic_regulations/real/HB02067I.txt",
        },
        {
            "doc_type":   "record_layout",
            "title":      "TICO Record Layout — Homeowners",
            "issuing":    "TICO",
            "effective":  "2026-01-01",
            "edition":    "2026.1",
            "path":       ROOT / "synthetic_regulations/real/tico_recordLayoutHomeOwners.txt",
        },
    ]
    # Bulletins
    bull_dir = ROOT / "synthetic_regulations/synthetic/bulletins"
    for f in sorted(bull_dir.glob("B-*.md")):
        docs.append({
            "doc_type":   "bulletin",
            "title":      f"TDI Bulletin — {f.stem}",
            "issuing":    "TDI",
            "effective":  "2026-04-01",
            "edition":    f.stem,
            "path":       f,
        })
    # Florida sources — the documents the FL extraction batch was run against,
    # so FL rules in the canon resolve to real text like the TX ones do.
    fl = ROOT / "synthetic_regulations/real/florida"
    docs += [
        {
            "doc_type":  "statute",
            "title":     "Florida Statute 627.062 — Rate Standards",
            "issuing":   "Florida Legislature",
            "effective": "2022-01-01",
            "edition":   "627.062",
            "path":      fl / "FL_627_062_rate_standards.txt",
        },
        {
            "doc_type":  "statute",
            "title":     "Florida Statute 627.351 — Insurance Risk Apportionment Plans",
            "issuing":   "Florida Legislature",
            "effective": "2022-01-01",
            "edition":   "627.351",
            "path":      fl / "FL_627_351_citizens.txt",
        },
        {
            "doc_type":  "bulletin",
            "title":     "FL OIR Informational Memorandum OIR-22-04M — Hurricane Ian Data Call",
            "issuing":   "FL OIR",
            "effective": "2022-10-05",
            "edition":   "OIR-22-04M",
            "path":      fl / "FL_OIR_22_04M_hurricane_data_call.md",
        },
        {
            "doc_type":  "stat_plan",
            "title":     "FHCF Annual Data Call Form — Personal Lines Residential",
            "issuing":   "Florida SBA",
            "effective": "2022-01-01",
            "edition":   "FHCF-D1A",
            "path":      fl / "FL_FHCF_data_call_form.md",
        },
    ]

    loaded: list[tuple[str, str]] = []
    for d in docs:
        if not d["path"].exists():
            print(f"  ⚠  skipping (missing): {d['path']}")
            continue
        text = d["path"].read_text(encoding="utf-8", errors="replace")
        doc_id = _doc_id(d["path"])
        word_count = len(text.split())
        # Page-count: rough estimate (txt files have no real pages)
        page_count = max(1, len(text) // 3000)
        query(
            "INSERT INTO INSURANCE_REGULATORY.BRONZE_REGDOCS.RAW_REG_DOCUMENT "
            "(document_id, document_type, title, issuing_body, effective_date, "
            " edition, source_path, full_text, page_count, word_count, loaded_at) "
            f"SELECT '{doc_id}', '{d['doc_type']}', '{_sql_text(d['title'])}', "
            f"       '{d['issuing']}', TO_DATE('{d['effective']}'), "
            f"       '{d['edition']}', '{_sql_text(str(d['path']))}', "
            f"       '{_sql_text(text)}', {page_count}, {word_count}, CURRENT_TIMESTAMP()"
        )
        loaded.append((doc_id, str(d["path"])))
        print(f"  ✓ loaded ({d['doc_type']}) {d['title']}  ·  {word_count} words")
    return loaded


def split_stat_plan_sections(doc_id: str, full_text: str) -> int:
    """Split TX stat plan into per-rule sections.

    Looks for patterns like "Rule 34", "Section A.34" — yields one row per
    detected rule heading, capturing text until the next heading.
    """
    # The TX stat plan uses numbered headings — "34. Reporting Reason Codes…".
    # Also accept "Section A:" / "Section A – Heading" for the broader sections.
    heading_re = re.compile(
        r"^\s*(?:(?:Section\s+([A-G]))|(\d{1,2}))\.?\s*[:—–\-]?\s*(.{0,160})$",
        re.MULTILINE,
    )
    matches = list(heading_re.finditer(full_text))
    if not matches:
        return 0

    inserted = 0
    rows = []
    for i, m in enumerate(matches):
        section_letter = m.group(1)        # "A" / "B" / … if it's a Section heading
        rule_num       = m.group(2)         # "34" / "12" / … if it's a numbered rule
        heading        = (m.group(3) or "").strip()[:200]
        # Skip lines that don't look like real headings (just stray numbers in body text)
        if rule_num and (not heading or len(heading) < 4):
            continue
        if section_letter:
            citation = f"Section {section_letter}"
            pattern  = f"Section\\\\s+{section_letter}\\\\b"
        else:
            citation = f"Rule {rule_num}"
            pattern  = f"(?:Rule\\\\s+)?{rule_num}\\\\b"
        start    = m.start()
        end      = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        body     = full_text[start:end].strip()
        if len(body) < 60:
            continue
        sec_id = _section_id(doc_id, citation, i + 1)
        rows.append(
            f"('{sec_id}', '{doc_id}', '{_sql_text(citation)}', '{pattern}', "
            f" '{_sql_text(heading)}', '{_sql_text(body[:60000])}', NULL, NULL, {i + 1})"
        )
        inserted += 1

    if rows:
        # Insert in batches to keep SQL size reasonable
        BATCH = 25
        for j in range(0, len(rows), BATCH):
            chunk = rows[j:j + BATCH]
            query(
                "INSERT INTO INSURANCE_REGULATORY.BRONZE_REGDOCS.RAW_REG_SECTION "
                "(section_id, document_id, citation_label, citation_pattern, "
                " section_heading, section_text, page_start, page_end, seq) "
                "VALUES " + ", ".join(chunk)
            )
    return inserted


def split_statute_sections(doc_id: str, full_text: str) -> int:
    """HB 2067 has §-numbered subsections. Capture each."""
    heading_re = re.compile(
        r"(?:Section|§|Sec\.?)\s+(\d{3}\.\d{3}(?:\([a-z0-9]+\))?)\s*[—–\-:.]?\s*(.{0,160})",
    )
    matches = list(heading_re.finditer(full_text))
    if not matches:
        return 0
    inserted = 0
    rows = []
    for i, m in enumerate(matches):
        citation = m.group(1)
        heading = (m.group(2) or "").strip()[:200]
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        body = full_text[start:end].strip()
        if len(body) < 30:
            continue
        sec_id = _section_id(doc_id, citation, i + 1)
        pattern = re.escape(citation).replace("\\", "\\\\")
        rows.append(
            f"('{sec_id}', '{doc_id}', '{_sql_text(citation)}', '{pattern}', "
            f" '{_sql_text(heading)}', '{_sql_text(body[:60000])}', NULL, NULL, {i + 1})"
        )
        inserted += 1
    if rows:
        BATCH = 25
        for j in range(0, len(rows), BATCH):
            chunk = rows[j:j + BATCH]
            query(
                "INSERT INTO INSURANCE_REGULATORY.BRONZE_REGDOCS.RAW_REG_SECTION "
                "(section_id, document_id, citation_label, citation_pattern, "
                " section_heading, section_text, page_start, page_end, seq) "
                "VALUES " + ", ".join(chunk)
            )
    return inserted


def split_fl_statute_sections(doc_id: str, full_text: str, statute_no: str) -> int:
    """Florida statutes mark subsections as top-level "(1)", "(5)" paragraphs.

    One section per subsection, cited as e.g. "627.351(6)" — the same anchor
    the extracted rule names carry ("Rule 627.351(6)(a) — …").
    """
    heading_re = re.compile(r"^\((\d+)\)\s*(.{0,160})$", re.MULTILINE)
    matches = list(heading_re.finditer(full_text))
    inserted = 0
    rows = []
    for i, m in enumerate(matches):
        citation = f"{statute_no}({m.group(1)})"
        heading = (m.group(2) or "").strip().rstrip(".—-").strip()[:200]
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        body = full_text[start:end].strip()
        if len(body) < 60:
            continue
        sec_id = _section_id(doc_id, citation, i + 1)
        pattern = re.escape(citation).replace("\\", "\\\\")
        rows.append(
            f"('{sec_id}', '{doc_id}', '{_sql_text(citation)}', '{pattern}', "
            f" '{_sql_text(heading)}', '{_sql_text(body[:60000])}', NULL, NULL, {i + 1})"
        )
        inserted += 1
    if rows:
        BATCH = 25
        for j in range(0, len(rows), BATCH):
            query(
                "INSERT INTO INSURANCE_REGULATORY.BRONZE_REGDOCS.RAW_REG_SECTION "
                "(section_id, document_id, citation_label, citation_pattern, "
                " section_heading, section_text, page_start, page_end, seq) "
                "VALUES " + ", ".join(rows[j:j + BATCH])
            )
    return inserted


def split_md_sections(doc_id: str, full_text: str) -> int:
    """Markdown memos/forms: one section per '##'/'###' heading.

    The citation label is the heading text itself — FL memo rules are named
    after their headings ("Special Provisions for Citizens Property Insurance
    Corporation"), so an exact/containment label match resolves them.
    """
    heading_re = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
    matches = list(heading_re.finditer(full_text))
    inserted = 0
    rows = []
    for i, m in enumerate(matches):
        heading = m.group(2).strip()
        # Letterhead lines aren't content sections
        if heading.split(":")[0] in ("TO", "FROM", "RE"):
            continue
        citation = re.sub(r"\s*\(.*\)$", "", heading)[:200]  # drop trailing "(Cols 35–36)"
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        body = full_text[start:end].strip()
        if len(body) < 40:
            continue
        sec_id = _section_id(doc_id, citation, i + 1)
        pattern = re.escape(citation).replace("\\", "\\\\")
        rows.append(
            f"('{sec_id}', '{doc_id}', '{_sql_text(citation)}', '{pattern}', "
            f" '{_sql_text(heading)}', '{_sql_text(body[:60000])}', NULL, NULL, {i + 1})"
        )
        inserted += 1
    if rows:
        BATCH = 25
        for j in range(0, len(rows), BATCH):
            query(
                "INSERT INTO INSURANCE_REGULATORY.BRONZE_REGDOCS.RAW_REG_SECTION "
                "(section_id, document_id, citation_label, citation_pattern, "
                " section_heading, section_text, page_start, page_end, seq) "
                "VALUES " + ", ".join(rows[j:j + BATCH])
            )
    return inserted


def ensure_tables() -> None:
    """Bootstrap the BRONZE_REGDOCS schema + tables (Databricks never had the
    Snowflake-era DDL applied; CREATE IF NOT EXISTS is a no-op elsewhere)."""
    query("CREATE SCHEMA IF NOT EXISTS INSURANCE_REGULATORY.BRONZE_REGDOCS")
    query(
        "CREATE TABLE IF NOT EXISTS INSURANCE_REGULATORY.BRONZE_REGDOCS.RAW_REG_DOCUMENT (\n"
        "  document_id STRING, document_type STRING, title STRING,\n"
        "  issuing_body STRING, effective_date DATE, edition STRING,\n"
        "  source_path STRING, full_text STRING, page_count INT,\n"
        "  word_count INT, loaded_at TIMESTAMP\n)"
    )
    query(
        "CREATE TABLE IF NOT EXISTS INSURANCE_REGULATORY.BRONZE_REGDOCS.RAW_REG_SECTION (\n"
        "  section_id STRING, document_id STRING, citation_label STRING,\n"
        "  citation_pattern STRING, section_heading STRING, section_text STRING,\n"
        "  page_start INT, page_end INT, seq INT\n)"
    )


def main() -> int:
    ensure_tables()
    # Idempotent reset
    query("TRUNCATE TABLE INSURANCE_REGULATORY.BRONZE_REGDOCS.RAW_REG_SECTION")
    query("TRUNCATE TABLE INSURANCE_REGULATORY.BRONZE_REGDOCS.RAW_REG_DOCUMENT")

    print("Loading BRONZE_REGDOCS:")
    print()
    docs = load_documents()
    print()

    # Splitter only runs for stat plan + statute; bulletins stay one-section-per-doc
    print("Splitting into sections:")
    total_sections = 0
    for doc_id, path in docs:
        full_text = (Path(path).read_text(encoding="utf-8", errors="replace"))
        if "TX_Statistical_Plan" in path:
            n = split_stat_plan_sections(doc_id, full_text)
            print(f"  ✓ stat plan       → {n} sections")
            total_sections += n
        elif "HB02067" in path:
            n = split_statute_sections(doc_id, full_text)
            print(f"  ✓ HB 2067         → {n} sections")
            total_sections += n
        elif "tico_recordLayout" in path:
            # Coarse split by "Section [A-G]"
            n = split_stat_plan_sections(doc_id, full_text)
            print(f"  ✓ record layout   → {n} sections")
            total_sections += n
        elif "FL_627_062" in path:
            n = split_fl_statute_sections(doc_id, full_text, "627.062")
            print(f"  ✓ FL 627.062      → {n} sections")
            total_sections += n
        elif "FL_627_351" in path:
            n = split_fl_statute_sections(doc_id, full_text, "627.351")
            print(f"  ✓ FL 627.351      → {n} sections")
            total_sections += n
        elif path.endswith(".md") and "/florida/" in path:
            n = split_md_sections(doc_id, full_text)
            print(f"  ✓ FL markdown     → {n} sections ({Path(path).stem})")
            total_sections += n
        # Bulletins: section_id = doc_id (single section)
    print()
    print(f"Total: {len(docs)} documents · {total_sections} sections")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
