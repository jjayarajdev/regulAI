"""Extract regulation PDFs to plain text files.

Run once after dropping a new PDF into references/regulations/. Output goes to
synthetic_regulations/real/ — those text files are what the Sentinel agent
ingests (LLMs can't read PDFs natively in our pipeline).

Convention: one text file per source PDF, with page markers so citation char
offsets remain stable across re-runs.

Run via: uv run python -m scripts.extract_pdfs
"""

from pathlib import Path

import fitz  # PyMuPDF — same library the parser uses, so extracted text matches what
              # parse_record_layout walks. Using pypdf here would produce a different
              # tokenization and break the parser's regexes / citation offsets.

REFERENCES = Path("references/regulations")
OUTPUT_DIR = Path("synthetic_regulations/real")


def extract_pdf(pdf_path: Path, out_path: Path) -> None:
    chunks: list[str] = []
    chunks.append(f"# {pdf_path.stem}\n")
    chunks.append(f"# Source: {pdf_path.name}\n")
    with fitz.open(pdf_path) as pdf:
        chunks.append(f"# Pages: {pdf.page_count}\n\n")
        for i in range(pdf.page_count):
            chunks.append(f"\n\n===== PAGE {i + 1} =====\n\n")
            chunks.append(pdf.load_page(i).get_text())
    out_path.write_text("".join(chunks), encoding="utf-8")
    with fitz.open(pdf_path) as pdf_for_count:
        n_pages = pdf_for_count.page_count
    print(f"  ✓ {pdf_path.name} → {out_path} "
          f"({n_pages} pages, {out_path.stat().st_size} bytes)")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(REFERENCES.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs in {REFERENCES}")
        return
    print(f"Extracting {len(pdfs)} PDF(s) to {OUTPUT_DIR}/\n")
    for pdf in pdfs:
        out = OUTPUT_DIR / f"{pdf.stem}.txt"
        extract_pdf(pdf, out)
    print(f"\nDone. Text files in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
