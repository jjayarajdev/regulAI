# Saved Cypher — RegulAI POC queries

Curated Cypher queries that exercise every facet of the LHS slice. Use them
in Neo4j Browser to demo, audit, and debug the KG.

```
cypher/
├── 01_overview.cypher              what's in the KG
├── 02_wire_format.cypher           the executable schema (records/columns/codes)
├── 03_provenance.cypher            "how do you know?" (citations + PDF rects)
├── 04_temporal_bulletin.cypher     rules-level loop (before/after bulletin)
├── 05_validation.cypher            KG hygiene checks
├── 06_demo_killer.cypher           the 5 queries to run during a demo
├── saved-cypher.json               Neo4j Browser-importable favorites
└── README.md                       this file
```

Total: **6 folders, 32 queries**.

---

## Two ways to use them

### A) Import as Neo4j Browser favorites (recommended for a demo)

This is the "saved Cypher by default" path. Import `cypher/saved-cypher.json`
once into your Browser instance and every query appears in the favorites
panel, organized by folder.

```
1. Open Neo4j Browser at http://localhost:7474
2. Click ☰ (top-left) → Favorites
3. Click the ⋮ menu next to "My Favorites" → "Import favorites"
4. Select cypher/saved-cypher.json
```

You'll see six folders ("KG Overview", "Wire Format Exploration", etc.).
Click any saved query to load it into the editor; press Cmd/Ctrl-Enter to run.

To regenerate the JSON (e.g. after editing a `.cypher` file):

```bash
make cypher-favorites
# writes a fresh cypher/saved-cypher.json
```

### B) Copy-paste from the .cypher files

Each `.cypher` file is human-readable, with section headers (`// N.M  Title`)
above every query and a brief comment explaining what it does. Open in any
editor, copy a block, paste into Neo4j Browser, run.

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
| 6. The killer demo | `6.3 Full provenance for a single fact` | `06_demo_killer.cypher` |

That's the whole LHS story in six queries.

---

## Notes

- These queries assume the KG is in its post-`make rebuild-kg` state.
  If you've manually mutated the KG, results will diverge.
- Queries 4.1–4.6 require `make apply-bulletin ALL=1` to have run (it
  runs automatically as the last step of `make rebuild-kg`).
- The `:play` Browser command can also load these as a guided walkthrough
  (we don't ship a guide HTML today; PRs welcome).
- All Cypher targets `GRENode`-labelled nodes; the closed vocabulary lives
  in `packages/core/enums.py`.
