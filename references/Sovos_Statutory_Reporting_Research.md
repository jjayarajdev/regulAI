# Sovos Statutory Reporting — Product Research (for regulAI)

> Research date: August 2026 · Source page: https://sovos.com/trr/products/statutory-reporting/
> Context: Input for Syntegreti's **regulAI** initiative. Sovos Statutory Reporting is the dominant incumbent in US insurance statutory/NAIC reporting — useful both as a competitive/partnership reference for regulAI and as a product-line hook in the broader Sovos BOT proposal (see `../Sovos/Sovos_Research_BOT_Opportunity_Syntegreti.docx`).

---

## 1. What the Product Is

Sovos Statutory Reporting (part of Sovos's **Tax and Regulatory Reporting — "TRR"** product line) automates the preparation and filing of **statutory financial statements** that US insurance companies must submit to state insurance departments and the **NAIC** (National Association of Insurance Commissioners).

- Streamlines financial statement preparation for insurers, automating compliance with regulatory filing requirements and reducing manual workload.
- Covers **NAIC annual/quarterly statements**, **state-specific compliance forms**, and connects to premium tax workflows (adjacent Sovos products).

## 2. Market Position

| Claim | Detail |
|---|---|
| **"60% of US insurers rely on Sovos Statutory Reporting"** | Headline claim on the product page |
| **70%+ of the US insurance market** | Uses Sovos compliance software + educational resources (per Sovos press release) |
| Segment leadership | Became the category leader via back-to-back acquisitions (see §4) |

This is a **near-monopoly incumbent position** in a niche, mandatory, recurring-revenue compliance market — the kind of segment where an AI-native challenger or AI augmentation layer (regulAI's thesis) can attack manual residual work the incumbent hasn't automated.

## 3. Key Features & Capabilities

- **Real-time data validations** — catches errors before filing.
- **Dynamic linking across NAIC statements and state compliance forms** — enter data once, it propagates; eliminates re-keying across multiple filings.
- **Automatic adaptation to NAIC and regulatory changes** — Sovos maintains the regulatory content so forms/rules stay current.
- **Comprehensive handbooks** for statement preparation (embedded guidance).
- **Data connectivity** options for automated updates and internal reporting.
- **Education services** — seminars and training for insurance accounting staff (Booke heritage; Sovos even sells an education catalog and is currently hiring a "Regulatory Education Director" with insurance accounting expertise).

### Pricing model
- Priced by **number of insurance companies (legal entities) requiring statutory filings** — per-entity licensing.
- Personalized demos; education/seminars sold alongside.

## 4. How Sovos Built This Business (Acquisition Heritage)

| Year | Acquisition | What it added |
|---|---|---|
| 2019 | **Eagle Technology Management (ETM)** | High-volume statutory reporting software + unclaimed property compliance |
| 2020 | **Booke Seminars** | 50+ years of insurance accounting education (P&C, life, health) + federal income tax (FIT) filing software for insurers |

Sources: Sovos press releases ([ETM/Booke](https://sovos.com/press-releases/sovos-acquires-booke-seminars-becomes-leading-provider-of-statutory-reporting-solutions-and-educational-services-for-insurers/), [blog](https://sovos.com/blog/trr/sovos-makes-back-to-back-statutory-reporting-acquisitions-with-purchase-of-booke/))

## 5. Competitive Landscape (NAIC Statutory Reporting Software)

| Vendor | Positioning |
|---|---|
| **Sovos Statutory Reporting** | Incumbent leader (~60% of US insurers); full statement prep + state forms + education |
| **Gain Compliance** | Modern cloud-native challenger; first statutory reporting vendor approved by the NAIC since 2001; 2024 partnership with NAIC and Pennsylvania Insurance Dept to streamline state reporting |
| **Clearwater Analytics (CWAN)** | Automates the **investment schedules** side of NAIC reporting (aggregating/reconciling/validating investment data for Schedule D etc.) |
| **Wolters Kluwer FRR** | Global finance/risk/regulatory reporting suite (broader than insurance statutory) |
| **Flexi** | Insurance-focused accounting platform with NAIC-importable exports |

Notable: Gain Compliance's blog ("Stat. Filing Software: The Changing of the Guard") explicitly positions against the legacy Sovos/ETM stack — evidence the incumbent product is perceived as **dated tech with a strong content moat**.

## 6. Relevance to regulAI

Why this product/segment matters for regulAI:

1. **The moat is regulatory content, not software.** Sovos wins because it maintains NAIC/state form changes and embeds guidance (handbooks, seminars). An LLM-based regulatory-intelligence engine (regulAI) attacks exactly this moat: ingesting NAIC SSAP updates, state bulletins, and instructions, and generating validated guidance/mappings automatically — the work Sovos does with human regulatory analysts.
2. **Residual manual pain persists even for Sovos customers:** narrative disclosures and notes to financial statements, cross-form reconciliation explanations, jurat/interrogatories, handling of regulatory change deltas each cycle. These are LLM-shaped problems (drafting, cross-checking, explaining) that the incumbent product doesn't solve.
3. **Proof-of-concept surface for regulAI:** NAIC statutory reporting is rule-dense, document-heavy, public-source-rich (NAIC publishes instructions/SSAPs), and cyclical (quarterly/annual) — ideal for a demonstrable regulAI use case: *"AI copilot for statutory statement preparation and regulatory change management."*
4. **Two go-to-market angles:**
   - **Partner/sell to Sovos** — pitch regulAI capability as an AI layer for their TRR line (fits their Sovi® AI roadmap, which so far focuses on indirect tax, not statutory reporting — a visible gap). This dovetails with the Syntegreti BOT proposal: a regulAI-powered pod for the TRR/statutory product line.
   - **Compete/partner with challengers** — Gain Compliance et al. lack AI-driven regulatory content operations; regulAI could power a challenger.
5. **Education angle:** Sovos monetizes training (Booke). regulAI-style conversational guidance ("Ask" experience for statutory accounting questions grounded in SSAP/NAIC instructions) could disrupt or complement this revenue stream.

### Suggested next steps for regulAI
- [ ] Build a small demo: ingest public NAIC annual statement instructions + a sample SSAP update; show change-impact summarization and disclosure drafting.
- [ ] Map Sovi® AI's announced capabilities (indirect tax focus) vs. the TRR/statutory line to confirm the whitespace.
- [ ] Decide GTM: AI layer pitched to Sovos (ties into BOT proposal) vs. independent regulAI product for insurers.

## 7. Sources

- Product page: https://sovos.com/trr/products/statutory-reporting/
- Sovos TRR overview: https://sovos.com/content-library/trr/the-industry-leader-in-tax-and-regulatory-reporting/
- Booke acquisition PR: https://sovos.com/press-releases/sovos-acquires-booke-seminars-becomes-leading-provider-of-statutory-reporting-solutions-and-educational-services-for-insurers/
- ETM/Booke blog: https://sovos.com/blog/trr/sovos-makes-back-to-back-statutory-reporting-acquisitions-with-purchase-of-booke/
- Sovos Education catalog (PDF): https://go.sovos.com/rs/334-HVN-249/images/Sovos%202022%20Education%20Catalog%20Final.pdf
- Gain Compliance (competitor): https://gaincompliance.com/ · https://gaincompliance.com/blog/stat-filing-software-the-changing-of-the-guard/
- Clearwater Analytics NAIC: https://clearwateranalytics.com/naic-info-and-resources
- Flexi NAIC reporting: https://www.flexi.com/naic-reporting/
