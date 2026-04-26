"""Generate a Neo4j Browser guide HTML from the cypher/*.cypher files.

Neo4j Browser's `:play` command loads guide HTML — pages of explanatory
text with clickable `<pre class="runnable">` blocks for Cypher. Way more
reliable than the favorites import and works in every Browser version.

Usage:
    uv run python -m scripts.build_cypher_guide        # → cypher/guide.html
    uv run python -m scripts.build_cypher_guide --stdout
"""

from __future__ import annotations

import re
import sys
from html import escape as h
from pathlib import Path

CYPHER_DIR = Path("cypher")
DEFAULT_OUT = CYPHER_DIR / "guide.html"


def parse_file(path: Path) -> tuple[str, str, list[tuple[str, str, str]]]:
    """Return (folder_name, intro_paragraph, [(query_name, prose, cypher), ...])."""
    text = path.read_text(encoding="utf-8")
    folder_match = re.search(r"//\s+RegulAI\s+—\s+(.+?)$", text, re.MULTILINE)
    folder = folder_match.group(1).strip() if folder_match else path.stem

    # Intro text = the first batch of `// Description` lines after the
    # `// ─────` rule under the title.
    intro_match = re.search(
        r"//\s+─{3,}\s*\n//\s+RegulAI\s+—.+?\n//\s+─{3,}\s*\n((?://.*\n)+)",
        text,
    )
    intro = ""
    if intro_match:
        intro = "\n".join(
            ln.strip().lstrip("/").strip() for ln in intro_match.group(1).splitlines()
        ).strip()

    section_re = re.compile(r"^//\s+(\d+\.\d+)\s+(.+?)$", re.MULTILINE)
    sections = list(section_re.finditer(text))
    queries: list[tuple[str, str, str]] = []
    for i, m in enumerate(sections):
        title = f"{m.group(1)}  {m.group(2).strip()}"
        body_start = m.end()
        body_end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
        body = text[body_start:body_end]
        # Pull leading // comment lines as the prose preamble.
        prose_lines: list[str] = []
        cypher_lines: list[str] = []
        in_cypher = False
        for ln in body.splitlines():
            if not in_cypher and ln.lstrip().startswith("//"):
                prose_lines.append(ln.lstrip().lstrip("/").strip())
            elif ln.strip() == "" and not in_cypher:
                continue
            else:
                in_cypher = True
                cypher_lines.append(ln)
        cypher = "\n".join(cypher_lines).strip()
        if cypher.endswith(";"):
            cypher = cypher[:-1].rstrip()
        prose = " ".join(p for p in prose_lines if p).strip()
        if cypher:
            queries.append((title, prose, cypher))
    return folder, intro, queries


# Neo4j Browser guide format — required structure:
#   <article class="guide">
#     <carousel class="deck container-fluid">
#       <slide class="row-fluid">…</slide>
#       <slide class="row-fluid">…</slide>
#     </carousel>
#   </article>
# Cypher inside <pre class="runnable">…</pre> becomes click-to-run.
SLIDE_TEMPLATE = """    <slide class="row-fluid">
      <div class="col-sm-3">
        <h3>{number}</h3>
        <p class="lead">{folder_name}</p>
      </div>
      <div class="col-sm-9">
        <h3>{title}</h3>
        {prose_html}
        <figure>
          <pre class="runnable">{cypher}</pre>
          <figcaption>Click ▶ to run this query.</figcaption>
        </figure>
      </div>
    </slide>"""

INDEX_SLIDE = """    <slide class="row-fluid">
      <div class="col-sm-3">
        <h3>RegulAI · POC</h3>
        <p class="lead">Saved Cypher tour</p>
      </div>
      <div class="col-sm-9">
        <h3>RegulAI — Cypher Tour</h3>
        <p>Curated queries that walk every facet of the LHS slice. Click <code>▶</code> on any code block to run it. Use the slide controls (top-right of this guide) to page through.</p>
        <p>Source: <code>cypher/*.cypher</code> in the repo. Runs against the local Neo4j (use <code>make rebuild-kg</code> first).</p>
        <h4>What's in here</h4>
        <ol>{toc}</ol>
      </div>
    </slide>"""

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>RegulAI Cypher Tour</title>
</head>
<body class="black-bg">
<article class="guide">
  <carousel class="deck container-fluid">
{slides}
  </carousel>
</article>
</body>
</html>
"""


def main() -> None:
    out_to_stdout = "--stdout" in sys.argv
    files = sorted(CYPHER_DIR.glob("*.cypher"))
    if not files:
        print(f"No .cypher files found in {CYPHER_DIR}", file=sys.stderr)
        sys.exit(1)

    parsed = [parse_file(p) for p in files]

    # Build TOC for the index slide.
    toc_items = []
    for folder, _, queries in parsed:
        toc_items.append(f"<li>{h(folder)} <em>({len(queries)} queries)</em></li>")
    index_html = INDEX_SLIDE.format(toc="\n      ".join(toc_items))

    # Flat list of every query as its own slide; preserves folder context.
    slides = [index_html]
    flat: list[tuple[str, str, str, str]] = []
    for folder, _intro, queries in parsed:
        for title, prose, cypher in queries:
            flat.append((folder, title, prose, cypher))

    for i, (folder, title, prose, cypher) in enumerate(flat):
        prose_html = f"<p>{h(prose)}</p>" if prose else ""
        slides.append(SLIDE_TEMPLATE.format(
            number=f"{i + 1} / {len(flat)}",
            folder_name=h(folder),
            title=h(title),
            prose_html=prose_html,
            cypher=h(cypher),
        ))

    page = PAGE.format(slides="\n".join(slides))
    if out_to_stdout:
        sys.stdout.write(page)
        return
    DEFAULT_OUT.write_text(page, encoding="utf-8")
    print(f"Wrote {DEFAULT_OUT}  ({len(flat)} queries across {len(parsed)} folders)")
    print()
    print("To load in Neo4j Browser:")
    print(f"  :play http://localhost:8765/cypher-guide")
    print()
    print("(or, if you've copied the file into Browser's static path,")
    print(" `:play file:///path/to/guide.html` — but the HTTP route is simpler).")


if __name__ == "__main__":
    main()
