"""Split the TICO Stat Plan extracted text into per-section files.

Each section (A General Rules, B Coding, C-G Record Layouts, F Notice Instructions)
becomes its own document the Sentinel agent can ingest in a single call.

Run via: uv run python -m scripts.split_sections
"""

import re
from pathlib import Path

INPUT = Path("synthetic_regulations/real/TX_Statistical_Plan_Residential_Risks_2026.txt")
OUTPUT_DIR = Path("synthetic_regulations/real/sections")

# Section title pattern — matches centered headings like "Section A:\nGeneral Rules"
# Allows leading whitespace (centered text from PDF extraction).
SECTION_HEADER_RE = re.compile(
    r"^[ \t]*Section\s+([A-G]):\s*\n[ \t]*(.+?)\s*$",
    re.MULTILINE,
)

SECTION_NAMES = {
    "A": "General Rules",
    "B": "Coding for Premiums and Losses",
    "C": "Record Layout for Premiums",
    "D": "Record Layout for Losses",
    "E": "Record Layout for Cancellation, Nonrenewal, and Declination Notices",
    "F": "Additional Instructions for Cancellation, Nonrenewal, and Declination Notices",
    "G": "Record Layout for Number of Actual Cancellations, Nonrenewals, and Declinations",
}


def find_section_starts(text: str) -> list[tuple[str, int]]:
    """Find the first occurrence of each section's title-page heading.

    Returns list of (letter, char_offset) sorted by offset.
    Picks the FIRST match per letter — subsequent occurrences are references in body text.
    """
    seen: dict[str, int] = {}
    for m in SECTION_HEADER_RE.finditer(text):
        letter = m.group(1)
        title_line = m.group(2).strip()
        # Filter for actual section title pages: the title line should contain the
        # known section name (or its first word). Body-text references like
        # "see Section B (Coding) of this Plan" don't match because they're inline.
        expected_first_word = SECTION_NAMES.get(letter, "").split()[0].lower()
        if expected_first_word in title_line.lower() and letter not in seen:
            seen[letter] = m.start()
    return sorted(seen.items(), key=lambda x: x[1])


def main() -> None:
    if not INPUT.exists():
        print(f"✗ Missing input: {INPUT}")
        print(f"  Run `make extract-pdfs` first.")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    text = INPUT.read_text(encoding="utf-8")

    print(f"Source: {INPUT} ({len(text):,} chars)\n")

    starts = find_section_starts(text)
    if not starts:
        print("✗ No section headers found. Check the PDF extraction.")
        return

    print(f"Found {len(starts)} sections:\n")
    boundaries = starts + [("END", len(text))]

    for i, (letter, start) in enumerate(starts):
        end = boundaries[i + 1][1]
        section_text = text[start:end]
        section_name = SECTION_NAMES.get(letter, "Unknown")
        # Header that includes provenance for downstream extraction.
        header = (
            f"# TICO Texas Statistical Plan for Residential Risks (eff. 2026-01-01)\n"
            f"# Section {letter}: {section_name}\n"
            f"# Source: TX_Statistical_Plan_Residential_Risks_2026.pdf, "
            f"chars {start}-{end} of source text\n\n"
        )
        out_path = OUTPUT_DIR / f"section_{letter}_{section_name.split()[0].lower()}.md"
        out_path.write_text(header + section_text, encoding="utf-8")
        size = out_path.stat().st_size
        print(f"  Section {letter}: {section_name}")
        print(f"    {out_path} ({size:,} bytes)")

    print(f"\nDone. {len(starts)} section files in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
