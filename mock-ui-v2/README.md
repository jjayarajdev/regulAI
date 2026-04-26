# RegulAI · Mock UI · v2

**Interactive HTML mock of the RegulAI product surfaces, aligned with the April 2026
Business Plan, End-to-End Solution Architecture, and Human-in-the-Loop Compliance
Architecture documents.**

Static HTML — no build step, no framework, no backend. Open `index.html` directly,
or run a local server (recommended because Google Fonts may be blocked on `file://`):

```bash
cd mock-ui-v2
python3 -m http.server 8734
# then open http://localhost:8734
```

## What changed from v1 (`../mock-ui/`)

v2 was rewritten against three reference documents in `../references/`:

| Document | Material change reflected in v2 |
|---|---|
| **Business Plan 2026** | 3-agent model (Cortex / Bridge / Sentinel). HITL Specialists as Tier 1 / 2 / 3. Pricing tiers. TX-first GTM. |
| **Architecture 2026** | Guidewire PolicyCenter → CDA → Databricks DLT (Bronze / Silver / Gold) → Databricks Genie → ISO/Verisk Portal API → Workday Financials for GL reconciliation. Neo4j GRE sits alongside. Ten-step pipeline, L0–L5 layers, gated validation. |
| **HITL Compliance Architecture** | Eight precisely-classified trigger conditions. Three specialist tiers with SLAs (24h / 3d / no-SLA). Seven-section Genie workspace panel. Immutable `HITL_AUDIT_LOG`. GRE learning loop. |

**Gone from v1:**

- Proposer–Critic–Arbiter pattern / "Auditor (GPT-5)" — the new architecture has
  no adversarial critic. Cortex runs deterministic edit checks; ambiguous records
  route straight to HITL.
- Dagster orchestration references (now Databricks DLT).
- Snowflake references (now Databricks + Unity Catalog; Workday GL; ISO/Verisk
  Portal for filing transmission).
- The 5-agent roster. Canonical roster is **three agents** plus human specialists
  in **three tiers**.

## The six surfaces

| # | Surface | File | What it shows |
|---|---|---|---|
| 01 | **Command Center** | `dashboard.html` | L0→L5 pipeline health, 3-agent pulse + 3 HITL tiers, MR queue broken out by all 8 trigger types, Sentinel bulletin feed, carrier volume. |
| 02 | **SOP Workbench** | `workbench.html` | Guidewire CDA Bronze schema mappings **plus** CarrierSOP rule-node authoring. Retiring specialists' institutional knowledge → peer-reviewed GRE nodes. |
| 03 | **Genie HITL Workspace** | `review.html` | A WH-vs-WN case under Hurricane Beryl: 7-section record panel (Policy Header · Claim Summary · NWS Track Overlay · Named Storm Events · Adjuster Notes · Prior Similar Cases · SOP Reference), SLA clock, decision panel writing to `HITL_AUDIT_LOG`. |
| 04 | **Pipeline Monitor** | `pipeline.html` | Ten-step Databricks DLT lifecycle, four layer-boundary gates, agent ownership, GRE learning-loop post-mortem on a novel form. |
| 05 | **GRE Explorer** | `ontology.html` | Six GRE node types: `StatPlanEdition` · `COLCodeRule` · `TerritoryRule` · `EndorsementRule` · `BulletinOverride` · `CarrierSOP`. Featured node: `COLCodeRule[WH]@v1.2.4`. |
| 06 | **Filings & Reconciliation** | `filings.html` | TICO / ISO-Verisk / NAIC / NCCI filings plus **Workday GL variance bands** (auto <0.1% · HITL <0.5% · HITL+Actuarial <1% · Filing hold >1%), end-to-end L0→L5 lineage card, submission timeline. |

## Canonical entities used across the mock

- **Carriers** — ATIC, TWC, NTP, SRC.
- **Stat plans** — THSP_2019, THSP_2024, THSP_2026, TCLSP, NCCI, ISO HO 2023.
- **COL codes** — WH (named storm), WN (other wind), HA, WD2/3/4, FR, FI, TH, VMM, OT.
- **Territories** — 11–15 coastal, 21+ inland.
- **Forms / endorsements** — HO-3, HO-5, DP-3, CP-1, ISO HO 00 03, HO-15, HO-61, HO 04 90, TX-04-91.
- **8 HITL triggers** — WH/WN · Ensuing loss · >$500K · OT · Coverage dispute · Umbrella · Novel form · Edition boundary.
- **Schema refs** — `regulai_bronze.*`, `regulai_silver.*`, `regulai_gold.stat_filing`, `regulai_gold.submission_log`, `regulai_gold.HITL_AUDIT_LOG`, `regulai_reference.gl_stat_account_map`.

## The compliance narrative at a glance

A single loss record (Hurricane Beryl, Galveston, ATIC) carries through the mock:

1. **Dashboard** — one of 12 open MR records · `TRIGGER_WH_WN` · Tier 2 · 73% of 3-day SLA.
2. **Pipeline** — pinned at Step 05 (HITL Queue); blocks Gold promotion along with 16 other MR records.
3. **Review** — selected in the queue; full 7-section Genie panel; decision panel pre-populates `CONFIRM_WH` citing SOP-COAST-03 §4.2 and prior case MR-2023-04471.
4. **Ontology** — the rule node that fired (`COLCodeRule[WH]@v1.2.4`) is the featured concept; its `REFINED_BY` edge points to the CarrierSOP being authored in the Workbench.
5. **Workbench** — the `ATIC.WH-WN.Coastal-150nm.v3` CarrierSOP is in peer review; m.kim approved, j.torres pending.
6. **Filings** — record enters the Q3 TICO submission once Gold promotes; GL variance for the WH/Terr12 bucket sits in the filing-hold band, pending AVP approval.

## Interactivity

Minimal JS, intentionally. Design artifact, not a prototype. Queue rows, mapping
rows, concept-tree rows, and the decision panel's radios all respond. Rail
navigation works across all six surfaces.

## Design language

Unchanged from v1. Editorial / regulatory: Fraunces (display), Inter (UI), IBM
Plex Mono (data). Cream paper `#F4F0E4`, deep ink `#141619`, oxblood accent
`#7A2418`. See `styles/app-v2.css`.

## Not for external distribution

Internal working artifact. Reference docs in `../references/` are confidential.
