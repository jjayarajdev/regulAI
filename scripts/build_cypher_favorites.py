"""Generate a Neo4j Browser-importable favorites JSON from the .cypher files.

Neo4j Browser stores saved Cypher in localStorage. There's no DBMS-side
way to seed it for Community Edition, so we deliver an importable JSON
the user loads once via Browser → ☰ → Favorites → "Import favorites".

Run:
  uv run python -m scripts.build_cypher_favorites > cypher/saved-cypher.json

Or via:
  make cypher-favorites
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path

CYPHER_DIR = Path("cypher")


def _parse_cypher_file(path: Path) -> tuple[str, list[tuple[str, str]]]:
    """Returns (folder_name, [(query_name, query_body), ...]).

    Each .cypher file is treated as a folder; queries within a file are
    delimited by `// N.M  <name>` comment headers (e.g. `// 1.4  All
    RecordLayouts ...`). The query body is everything until the next
    such header (or EOF). Header comments at the very top of the file
    become the folder description.
    """
    text = path.read_text(encoding="utf-8")
    # Folder name from the first heavy header comment
    folder_match = re.search(r"//\s+RegulAI\s+—\s+(.+)$", text, re.MULTILINE)
    folder_name = folder_match.group(1).strip() if folder_match else path.stem

    # Section markers like `// 1.4  Title text`
    section_re = re.compile(r"^//\s+(\d+\.\d+)\s+(.+?)$", re.MULTILINE)
    sections = list(section_re.finditer(text))
    queries: list[tuple[str, str]] = []
    for i, m in enumerate(sections):
        title = f"{m.group(1)}  {m.group(2).strip()}"
        body_start = m.end()
        body_end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
        body = text[body_start:body_end].strip()
        # Trim trailing semicolons + whitespace consistency
        if body.endswith(";"):
            body = body[:-1].rstrip()
        queries.append((title, body))
    return folder_name, queries


def main() -> None:
    files = sorted(CYPHER_DIR.glob("*.cypher"))
    if not files:
        print(f"No .cypher files found in {CYPHER_DIR}", file=sys.stderr)
        sys.exit(1)

    favorites: list[dict] = []
    for path in files:
        folder_name, queries = _parse_cypher_file(path)
        folder_id = str(uuid.uuid4())
        favorites.append({
            "id": folder_id,
            "name": folder_name,
            "isFolder": True,
        })
        for title, body in queries:
            favorites.append({
                "id": str(uuid.uuid4()),
                "parentId": folder_id,
                "isFolder": False,
                "name": title,
                "content": body,
            })

    # Neo4j Browser's import expects either a list directly or
    # `{"scripts": [...]}`. The list form is the most widely accepted.
    json.dump(favorites, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
