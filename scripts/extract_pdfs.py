"""Extract regulation PDFs to plain text files.

Run once after dropping a new PDF into references/regulations/. Output goes to
synthetic_regulations/real/ — those text files are what the Sentinel agent
ingests (LLMs can't read PDFs natively in our pipeline).

Convention: one text file per source PDF, with page markers so citation char
offsets remain stable across re-runs.

Run via: uv run python -m scripts.extract_pdfs
"""

from pathlib import Path

from pypdf import PdfReader

REFERENCES = Path("references/regulations")
OUTPUT_DIR = Path("synthetic_regulations/real")


def extract_pdf(pdf_path: Path, out_path: Path) -> None:
    reader = PdfReader(str(pdf_path))
    chunks: list[str] = []
    chunks.append(f"# {pdf_path.stem}\n")
    chunks.append(f"# Source: {pdf_path.name}\n")
    chunks.append(f"# Pages: {len(reader.pages)}\n\n")
    for i, page in enumerate(reader.pages, start=1):
        chunks.append(f"\n\n===== PAGE {i} =====\n\n")
        text = page.extract_text() or ""
        chunks.append(text)
    out_path.write_text("".join(chunks), encoding="utf-8")
    print(f"  ✓ {pdf_path.name} → {out_path} "
          f"({len(reader.pages)} pages, {out_path.stat().st_size} bytes)")


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
