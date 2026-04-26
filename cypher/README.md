# Saved Cypher — RegulAI POC queries

Two layers of queries:

**For compliance / business stakeholders** → start with `00_business_questions.cypher`.
These are titled as plain-English questions an insurance compliance officer or
auditor would actually ask. The graph technology is invisible; what comes back
is a business answer. Run these in a demo.

**For engineers** → files `01_*` through `06_*` show the same KG from the
infrastructure side: counts, joins, hygiene checks, schema views.

Total: **7 folders, 42 queries**.

```
cypher/
├── 00_business_questions.cypher    ⭐ START HERE — 10 questions in plain English
├── 01_overview.cypher              KG infrastructure overview
├── 02_wire_format.cypher           the executable schema (records/columns/codes)
├── 03_provenance.cypher            "how do you know?" (citations + PDF rects)
├── 04_temporal_bulletin.cypher     rules-level loop (before/after bulletin)
├── 05_validation.cypher            KG hygiene checks
├── 06_demo_killer.cypher           condensed demo set (5 queries)
├── guide.html                      Neo4j Browser-loadable :play guide
├── saved-cypher.json               Browser-importable favorites JSON
└── README.md                       this file
```

## The 10 business questions

| # | Question | What the KG provides that flat tables don't |
|---|---|---|
| 0.1 | What does Texas require us to file? | Schema-as-data: the 4 reports + their structure |
| 0.2 | What are the legal Cause-of-Loss codes RIGHT NOW? | Edition pinning at "today" |
| 0.3 | What WAS legal as of August 2026? | Edition pinning at any date |
| 0.4 | What changed when the Q3 2026 bulletin took effect? | Single-query change report |
| 0.5 | What goes in column 5–6 of every Premium record? | Schema as a query |
| 0.6 | For an audit: prove the regulatory basis for one of our fields | Provenance walk to PDF |
| 0.7 | If our system emits Cause-of-Loss = 25 in Nov 2026, will TICO accept? | Edition-pinned validity check |
| 0.8 | How big is the compliance burden? | Aggregate count, schema-wide |
| 0.9 | Show me everything the bulletin changed (memo-ready) | Change summary in business prose |
| 0.10 | Are there any inconsistencies in our regulatory data? | KG hygiene as a sign-off check |

Pull up the .cypher file in any editor and the questions are at the top of every block.

---

## How to use them — three options

The Browser-favorites import is fragile across versions. Try option **A** first.

### A. Load as a Browser guide (most reliable) ✅

In Neo4j Browser at `http://localhost:7474`, run:

```cypher
:play http://localhost:8765/cypher-guide
```

You get a paginated walkthrough with explanatory text and clickable
runnable Cypher cards. Pages: 1 index slide + 32 query slides. Use ←/→
to navigate.

> **Prerequisites**: `make ui` running (FastAPI on :8765). The endpoint
> returns the HTML built from `cypher/*.cypher`. CORS is allowed for
> `localhost:7474`.

To regenerate after editing a `.cypher` file:

```bash
make cypher-guide
# rebuilds cypher/guide.html
# (the FastAPI route reads the file fresh on every request, so no restart)
```

### B. Copy-paste from the .cypher files

Each `.cypher` file is plain text, with section headers (`// N.M Title`)
above every query and a brief comment explaining what it does.
Open in any editor, copy a block, paste into Neo4j Browser, run.

### C. Browser-favorites import (fragile across versions)

```
1. Open http://localhost:7474
2. Click ☰ (top-left) → Favorites
3. Click the ⋮ menu next to "My Favorites" → "Import favorites"
4. Select cypher/saved-cypher.json
```

Some Browser versions silently reject the format. If A or B work for you,
use those instead.

To regenerate the JSON:

```bash
make cypher-favorites
```

### D. localStorage paste (if all else fails) — last resort

If the import dialog doesn't accept the file, you can write favorites
straight into the Browser's localStorage. Open Neo4j Browser, then open
DevTools (F12) → Console, and paste:

```js
fetch('http://localhost:8765/cypher-guide')
  .then(() => fetch('http://localhost:8765/cypher/saved-cypher.json'))
  .then(r => r.json())
  .then(favs => {
    localStorage.setItem('neo4j.documents', JSON.stringify({
      allDocuments: favs,
      folders: favs.filter(f => f.isFolder),
    }));
    location.reload();
  });
```

(This is hacky and may not survive Browser version upgrades. The `:play` route is the supported path.)

---

## A 90-second tour

If you only run six queries, run these:

| Question | Query | File |
|---|---|---|
| 1. What's in the KG? | `1.1 Node count by type` | `01_overview.cypher` |
| 2. What does column 5–6 of a Premium record contain? | `2.2 What does column 5–6 (RECORD TYPE) mean?` | `02_wire_format.cypher` |
| 3. How do you know? | `3.1 How a FieldRequirement traces to a regulation span` | `03_provenance.cypher` |
| 4. What changed when the bulletin landed? | `4.1` and `4.2` (before/after) | `04_temporal_bulletin.cypher` |
| 5. Is the KG clean? | `5.1 Phantom RecordLayouts` (should be empty) | `05_validation.cypher` |
| 6. The killer demo | `6.4 Bulletin diff visualization` | `06_demo_killer.cypher` |

That's the whole LHS story in six queries.

---

## Notes

- These queries assume the KG is in its post-`make rebuild-kg` state.
- Queries 4.1–4.6 require `make apply-bulletin ALL=1` (runs automatically as the last step of `make rebuild-kg`).
- All Cypher targets `GRENode`-labelled nodes; the closed vocabulary lives in `packages/core/enums.py`.
