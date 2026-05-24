# Hubio regul8 + regul8 Connect — Competitive Research

**Date researched:** 2026-05-23
**Researcher:** RegulAI team
**Primary URLs:**
- https://hubio.com/regul8-connect (Guidewire connector)
- https://hubio.com/regul8 (the platform)
- The 8-page Hubio regul8 brochure on Guidewire Marketplace (©2022)

**Source quality:** marketing landing pages are thin, but the 8-page Hubio brochure (extracted and parsed from PDF) gives a substantive feature list, architecture sketch, and supported-plans list. That's the load-bearing source here.

---

## TL;DR

| | Hubio regul8 | RegulAI (this repo) |
|---|---|---|
| Tagline | *"Statistical Reporting as a Service"* | KG-driven regulatory compliance for insurance stat reporting |
| Coverage today | **Canada-heavy** (GISA, IBC, Quebec) + US commercial (ISO, NISS) + US WC (WCPOLS/WCSTAT) "upcoming" | **US homeowners** (TICO TX + FHCF FL) |
| Maturity | "20 years of production, multiple implementations" | POC, ~6 months active development |
| Rules origin | "Pre-configured rules engine" — engineers hand-encode per regulator | LLM-extracted from regulation text → versioned Knowledge Graph |
| Adding a new jurisdiction | Vendor engineering work | Ingest documents through Sentinel; framework was just proven on FL |
| Submission loop | Built — regulator acceptance, GL reconciliation, audit | Not yet — pipeline ends at violations report |
| Architectural centerpiece | **Statistical Data Mart** (canonical schema per LOB) | **Knowledge Graph** (rules + layouts + citations) |
| Customer evidence | Implied via Guidewire partnership; no logos public | None — POC |

**The headline:** regul8 and RegulAI **barely overlap today**. Hubio dominates Canadian stat reporting + US commercial; RegulAI's POC is US homeowners. But they'll converge as both expand. The bet RegulAI is making is that *KG-as-canon* is faster to add states and absorb bulletins than *pre-configured rules engine + Statistical Data Mart*.

That bet is testable but **not yet tested** — regul8 has shipped to customers for 20 years; RegulAI hasn't shipped to anyone.

---

## 1. regul8 — what it actually does (from the brochure)

### Tagline and positioning

> *"regul8 is a turnkey data platform specialized in managing and delivering regulatory and statistical reporting for Property & Casualty (P&C) insurance companies. It handles data transformation, data validation, error correction, reconciliation, submission management and regulator audit support."*

Strapline on cover page: ***"Statistical Reporting as a Service."***

### Supported regulatory submissions (definitive list from page 2)

**Currently supported (all Canadian):**
- GISA Automobile Statistical Plan
- GISA Commercial Liability Statistical Plan
- FA (Facility Association) Risk Sharing Pool (RSP)
- PSA + FCSA — Quebec GAA (Groupement des Assureurs Automobiles)
- PRR / QRSP (Quebec Risk Sharing Pool)
- CGI AutoPlus Phase 2
- IBC DASH

**"Upcoming supported plans":**
- US Workers Compensation (WCPOLS and WCSTAT)
- US ISO
- US NISS

**What is conspicuously NOT in either list:**
- TICO (Texas) — RegulAI's core POC
- FHCF (Florida) — RegulAI's Cluster D scope
- HB 2067 declination/cancellation notices
- NAIC Annual Statement / Schedule P
- Homeowners stat plans (any state)
- CA Prop 103 rate filings
- Property catastrophe data calls (OIR memos, etc.)
- **Any US personal lines reporting at all**

This isn't a small gap. Hubio's brochure is **2022-dated** and a 2026 partnership press release claims they support "all North American reporting jurisdictions" — but the published plan list contradicts that. Either the press release is aspirational, or the brochure is stale.

### Functionality components (page 3 — architecture box diagram)

The brochure shows regul8 as a vertical stack of components:

1. User Interface and Analytics
2. Process Management, Monitoring and Alerting
3. Data Transformation
4. Data Validation
5. **Submission Rules** ← rules engine sits here
6. Manual Error Correction
7. Automated Error Correction
8. Submission to Regulators
9. Submission Status
10. Reconciliation
11. **Statistical Data Mart** ← persistent canonical schema

Each component is presumably a service in their multi-tenant SaaS. The two architecturally load-bearing ones are **Submission Rules** (the validation engine) and the **Statistical Data Mart** (the canonical schema).

### Use Case diagram (page 4)

Two upstream paths feed the **Statistical Data Mart**:

- **Guidewire Cloud** → `regul8 Connect` → SDM (the fast path; this is the product the user originally asked about)
- **Legacy Core System** → `ETL` → SDM (the long path; vendor or third-party ETL feeds the SDM)

From SDM, regul8 produces the submission and delivers it to the **Statistical Agent** (GISA, IBC, etc.).

The diagram also calls out displacing **"Legacy Stat Reporting"** — the implicit competitor isn't another vendor; it's the carrier's internal hand-coded stat-reporting system that regul8 replaces.

### Benefits (page 5 — verbatim phrasing)

| Theme | Specific claims (verbatim) |
|---|---|
| Peace of mind | "20 years of production and multiple implementations"; automated alerts for late source data + out-of-balance processing; "Evergreened SaaS model to minimize technical debt" |
| Automation | "Handling of Out-Of-Sequence Endorsements and data slicing"; "Auto-correction of future transactions based on manual risk corrections"; configurable workflow + alerts |
| Rapid implementation | "Handles multiple data sources from multiple core systems"; "No-code approach"; "Single data source schema (Statistical Data Mart) per LOB to generate all statistical submissions" |
| Insight | Analytics on operational performance, data quality, errors, corrections |
| Deficiency fee reduction | "A pre-configured rules engine to validate data quality before submission" |
| Modern platform | Cloud-native, on-demand performance, multi-tenant |

**Two phrases worth highlighting** because they reveal the architectural mental model:

1. ***"Pre-configured rules engine"*** — i.e., Hubio engineers encode the rules per regulator. There's no claim that rules are derived from regulation text. New jurisdictions = vendor engineering.
2. ***"Single data source schema (Statistical Data Mart) per LOB"*** — i.e., one canonical schema per line of business that all submissions for that LOB derive from. This is how they amortize work across multiple jurisdictions covering the same LOB.

### Technical features (page 6 — verbatim list)

- Dashboard for validation of regular processing + submission to regulators
- Pre-configured rules engine for data quality validation pre-submission
- Web UI for **business users** to correct data prior to submission
- **Automated reapplication of manual corrections to future transactions** ← novel; not in RegulAI
- Self-service portal for submission/resubmission management
- **Automated data reconciliation against data source AND General Ledger** ← novel; RegulAI has no GL tie-out
- Error analytics for source-system corrective changes
- Full audit capabilities on error correction + data derivation
- **Data Interface to regulators to confirm submission status and acceptance** ← the loop RegulAI doesn't have

### UI screens called out (page 7)

- Dashboard
- Submission Management
- Submission Audit Support

(No screenshots in the extracted text — those are images.)

### Company

Toronto-based (20 Victoria Street, 6th Floor, Toronto, ON). The Canadian HQ explains the Canada-heavy coverage; their US expansion is more recent (WC/ISO/NISS "upcoming").

---

## 2. regul8 Connect — the Guidewire-specific connector

From the landing page and brochure context:

- **One sentence:** SaaS data extractor that pulls policy/claim/billing data from Guidewire InsuranceSuite into regul8's Statistical Data Mart, without bespoke ETL code.
- **Mechanism:** Guidewire Cloud Data Access (CDA) + Integration Gateway + Guidewire's metadata repository.
- **Positioning:** *"The Fast Lane to Guidewire Integration."* The competing path is a custom ETL build per carrier.
- **Distribution:** Listed on Guidewire Marketplace. Hubio is in the **first cohort of Guidewire Data Partners** (2026 press release), alongside AWS, Celonis, Google Cloud.

regul8 Connect is *the input plumbing*. regul8 is *the reporting engine*. The brochure makes clear regul8 can also ingest from legacy core systems via ETL — Connect just speeds up Guidewire onboarding.

---

## 3. How RegulAI compares — head-to-head

### Coverage

| Dimension | Hubio regul8 | RegulAI |
|---|---|---|
| Canada — auto stat | GISA ASP, IBC | None |
| Canada — Quebec | PSA, FCSA, PRR/QRSP, InfoNiv | None |
| Canada — commercial | GISA Commercial Liability | None |
| Canada — risk sharing | Facility Association RSP | None |
| US — workers comp | WCPOLS/WCSTAT (upcoming) | None |
| US — commercial | ISO, NISS (upcoming) | None |
| **US — homeowners** | **Not on roadmap** | **TX TICO (POC)** |
| **US — FHCF / catastrophe** | **Not on roadmap** | **FL FHCF (Cluster D)** |
| US — HB2067-style notices | Not on roadmap | TX HB2067 (proven) |
| Lines of business | Auto, commercial liability, WC (upcoming) | Personal property only |

**The honest read:** the two products target adjacent but **non-overlapping markets** today. Hubio is "auto + commercial + workers' comp, Canada-heavy." RegulAI is "homeowners + catastrophe, US-only." A carrier doing US homeowners filings cannot buy regul8 today and cannot buy RegulAI in production either.

### Architecture

| Aspect | Hubio regul8 | RegulAI |
|---|---|---|
| Where rules come from | Hand-coded by Hubio engineers per regulator | LLM-extracted from regulation text (Sentinel) |
| Canonical model | **Statistical Data Mart** (relational schema per LOB) | **Knowledge Graph** (Neo4j, 19 closed-vocabulary node types) |
| New jurisdiction effort | Vendor engineering: build rules, extend SDM | Ingest the regulation documents through Sentinel; framework was just proven on FL |
| Bulletin / supersession | Not described publicly | `BulletinOverride` nodes with confidence scores; version chains on every rule |
| Traceability | "Full audit capabilities" claimed; mechanism not described | Every Rule + ValidationRule cites a specific char range in a specific PDF |
| Closed vocabulary enforcement | N/A | 19 node types; parser-boundary gate prevents pollution |
| Data extraction | Guidewire CDA, Integration Gateway, ETL for legacy | Synthetic Bronze (no real connector yet) |
| Validation engine | "Pre-configured rules engine" | violation_sql per Rule, executed in Snowflake / DuckDB |

### Operational maturity

Where Hubio is **clearly ahead**:

| Capability | Hubio | RegulAI |
|---|---|---|
| Real customer deployments | Yes (20 years claimed) | None |
| Regulator submission delivery loop | Yes | No (pipeline ends at violations report) |
| Submission status + acceptance tracking | Yes | No |
| **GL reconciliation** | Yes | No |
| Auto-correction of future transactions from prior corrections | Yes | No |
| Out-of-sequence endorsement handling | Yes | No |
| Self-service business-user error correction UI | Yes | No (HITL approve only; no error-correction workflow) |
| Deficiency fee reduction track record | Claimed | N/A |
| Multi-tenant SaaS | Yes (claimed) | No — single-tenant POC |
| Authn / authz | Implied | **None** (see production-readiness assessment) |
| PII handling | Implied (regulator-grade) | **None** |

Where RegulAI's architecture is **structurally different** (not necessarily ahead — different):

| Capability | Hubio | RegulAI |
|---|---|---|
| Rule provenance back to statute text | N/A or hand-curated | Automatic — every Rule has citation char ranges |
| Time to add a new state | Vendor release cycle (months) | Documents → KG in hours (Cluster D proved FL) |
| Time to react to a new bulletin | Vendor release cycle | Same pipeline as initial ingest; BulletinOverride applied automatically |
| Rules editable vs derived | Editable code | Derived from canon, reviewable in HITL |
| Multi-jurisdiction in one KG | N/A | Designed for it (Phase 2 multi-jurisdiction proven) |

---

## 4. Where each product wins, honestly

### Where Hubio wins a head-to-head bake-off today

- A carrier already on Guidewire wanting to ship Canadian or WC submissions in 6 months
- A buyer who values 20-year track record over architectural novelty
- A compliance team that needs GL reconciliation and submission-acceptance tracking out of the box
- Any non-homeowners P&C use case

### Where RegulAI wins (with a real shipped product, not the POC)

- **US homeowners + catastrophe filings** — Hubio has nothing here, and adding them is engineering work for Hubio that's already done architecturally for RegulAI
- **Multi-state portfolio in a regulated, fast-changing environment** — if a customer files in 15 states and 3 of them bulletin every year, RegulAI's KG-as-canon model is faster
- **Audit defensibility against regulators** — "show me where in the statute this validation rule comes from" is a one-click answer in RegulAI; in Hubio it's a documentation lookup
- **Buyer with appetite for novel approaches** — the LLM-extracted-canon story is genuinely interesting to forward-leaning CIOs

### Where neither wins yet

- **L&A reporting** — both are P&C only
- **International outside Canada** — both US-and-Canada focused

---

## 5. The "20 years of production" claim deserves a closer look

regul8's biggest moat is operational, not architectural. Twenty years of running real submissions teaches you things that don't appear in a brochure:

- Which exact data quality issues blow up which exact regulator submissions
- Which manual corrections recur often enough to auto-apply
- How regulators actually respond to malformed records (vs. how the spec says they should)
- What "deficiency fees" cost in practice and which rules prevent them

RegulAI has zero of this. The framework is good; the operational know-how is missing. **A real customer engagement** — even one — would surface a list of items as long as the production-readiness assessment.

---

## 6. Strategic implications for RegulAI

Stop thinking of regul8 as a direct competitor; **today it isn't one**. They sell to Canadian and US-commercial buyers; RegulAI's POC targets US homeowners. The two products would lose to each other in entirely different sales cycles.

Where the products **will** collide is in 2-3 years, when:

- Hubio extends to US homeowners (their "20 years" pitch becomes "20 years on auto + 1 year on homeowners")
- RegulAI extends from homeowners to broader P&C (which will surface a lot of unknowns)

When that collision happens, the architectural axis is the differentiator. RegulAI's bet is: **"derived from canon" beats "hand-coded by vendor engineers"** — because regulations change faster than vendors ship.

**That bet only pays off if RegulAI can credibly demonstrate:**

1. A new state is added in days, not months (Cluster D proved this for FL; needs a third state to prove it twice)
2. A new bulletin is absorbed in hours, not a vendor release cycle (the BulletinOverride pattern works on synthetic bulletins; needs real-world stress)
3. The rules derived from canon are *as good as* hand-coded ones (Sentinel quality SLO is not yet measured — #6 in production-readiness)

If RegulAI can't show those three things on its way to GA, the "knowledge graph" pitch is differentiation without substance and Hubio wins on track record alone.

### Concrete next-step recommendations (research-driven)

| Action | Why |
|---|---|
| Ingest a third state (CA Prop 103 or NY Reg 64) | Proves "adding states is days not months" — directly challenges Hubio's "vendor engineering" model |
| Build a Sentinel quality SLO | Today we measure skip rate, not correctness. Hubio's hand-coded rules are deterministic; RegulAI needs a measurable quality floor before a buyer will trust LLM-derived rules |
| Add GL reconciliation | Hubio has it; carriers will ask for it; it's not architecturally hard |
| Add regulator submission status loop | Closes the loop Hubio has; would be a substantial differentiator if it pulls from regulator portals automatically |
| Get a Guidewire Marketplace listing | Hubio's distribution is here. Even if RegulAI's connector is different, being in the same marketplace matters |
| Find one carrier willing to do a paid pilot on TX or FL homeowners | Hubio's "20 years" comes from real customers. RegulAI needs one to start the same flywheel |

---

## 7. What's verified vs. marketing

| Claim | Confidence | Source |
|---|---|---|
| regul8 covers 7 named Canadian + Quebec plans | **High** | Brochure page 2 |
| US WC/ISO/NISS are "upcoming" not current | **High** | Brochure page 2 — explicit "upcoming" label |
| 20 years of production | **Medium** | Brochure claim, no customer logos to corroborate |
| GL reconciliation works | **Medium** | Brochure page 6 lists it; mechanism not shown |
| Submission acceptance loop with regulators | **Medium** | Brochure page 6 mentions "Data Interface to regulators to confirm submission status and acceptance" |
| Multi-tenant SaaS | **High** | Consistent across brochure + landing pages |
| Pre-configured rules engine (i.e., hand-coded rules) | **High** | Brochure verbatim |
| "All North American jurisdictions" supported | **Low** | Partnership press release — contradicted by published plan list |
| Specific customer count | Unknown | Not published |
| Pricing | Unknown | Not published |
| Implementation timeline for a real engagement | Unknown | "Rapid implementation" claimed, no number |
| How they handle a new bulletin or supersession | Unknown | Not described in brochure |
| Whether they handle US homeowners at all | **Likely no** | Not in current or upcoming plans list |

---

## 8. Open questions worth a second pass

Each of these would meaningfully shift the comparison:

1. **The 2026 Hubio brochure** (if one exists; the one I have is ©2022). Worth checking whether their plan list has expanded.
2. **A Hubio + Guidewire customer case study.** Anywhere — analyst report, conference talk, LinkedIn. Would tell us implementation timeline, real customer satisfaction.
3. **Hubio's company size + revenue.** Toronto HQ, P&C SaaS, 20-year claim. Are they 50 employees or 500? Profitable or VC-burning? Shapes how they'd respond to competition.
4. **Pricing.** Likely six-figure annual SaaS minimum. Bake-offs hinge on this.
5. **The exact rules-encoding workflow at Hubio.** If a regulator publishes a new bulletin, what's their cycle time? Days? Weeks? Months? That's the number RegulAI's pitch has to beat.
6. **NAIC annual statement coverage.** Notably absent. Is anyone in the SaaS market handling this? Both Hubio and RegulAI could expand here.
7. **Do they actually integrate with US homeowners filings at all?** A direct ask via sales channel would settle this.
8. **Their multi-state model.** "Single data source schema per LOB" suggests they amortize across states for the same LOB. How does that handle state-specific overrides? Hubio's answer here is RegulAI's `BulletinOverride` answer.

---

## Sources

- [regul8 Connect product page](https://hubio.com/regul8-connect)
- [regul8 platform product page](https://hubio.com/regul8)
- [Hubio regul8 brochure (PDF, ©2022, Guidewire Marketplace)](https://marketplace.guidewire.com/sfc/servlet.shepherd/version/download/068Kj00000Osy58IAB) — extracted via pypdf locally; 8 pages
- [Hubio Guidewire data-partner press release (2026)](https://hubio.com/news/hubio-strengthens-its-relationship-with-guidewire-by-joining-first-cohort-of-data-partners)
- [Guidewire PartnerConnect cohort announcement](https://ir.guidewire.com/news-releases/news-release-details/guidewire-welcomes-aws-celonis-google-cloud-and-hubio-its)
- [Guidewire Solution Alliance Partner press release (2017)](https://ir.guidewire.com/news-releases/news-release-details/guidewire-software-announces-hubio-new-solution-alliance-partner)
- [Hubio Exchange — workers' comp reporting page](https://hubio.com/exchange/workers-compensation-reporting/)
