# RegulAI — Viability Assessment & Go-to-Market Readiness

This document captures the viability analysis of the RegulAI business plan and the follow-up stress-test on investor, pilot, and SME readiness.

---

## Part 1 — Is This a Viable Product?

**Short answer: the problem is real, the positioning is clever, but the plan is more execution-risky than it admits. Viable, not easy.**

### What's genuinely strong

- **The demand is non-discretionary.** Carriers *must* file. Regulators aren't slowing down. This isn't a "nice to have" SaaS looking for product-market fit — the mandate is the contract.
- **The retirement cliff is documented and asymmetric.** You can't hire replacements; the apprenticeship curve is 7–10 years. Time is on RegulAI's side.
- **Ecosystem-complement framing is smart.** Positioning between PAS (Guidewire/Duck Creek) and the statistical agent (Verisk/TICO) is a real gap, and "partner, don't disrupt" is the right posture in a trust-driven industry.
- **SOP capture is the actual moat.** Once a carrier's exception logic is in the graph, switching out costs them years. That's a defensible lock-in — better than most vertical SaaS.

### Where the plan is optimistic or hand-wavy

1. **"85% gross margin at scale" is a SaaS story pasted onto a services business.** Tier 2/3 explicitly includes RegulAI human specialists on call, SOP digitization, HITL review of every filing. That's closer to a 60–70% margin consulting-heavy business. The financials likely underestimate HITL headcount growth.

2. **Verisk as acquirer is a bet on someone else's decision.** Verisk has the data, relationships, capital, and engineering to build this themselves. "Complement, not compete" is RegulAI's framing — Verisk hasn't signed that contract. If Verisk decides to build, the whole exit thesis changes.

3. **Sales cycle math is aggressive.** 12–18mo cycles + 2026 launch + 22 carriers by end of 2027 means pilots need to convert at an unusually high rate. One bad TICO rejection on a pilot filing can burn a quarter of the pipeline.

4. **LLM commoditization risk is unaddressed.** The graph-native approach is differentiated *today*. But foundation models in 2026 are getting rapidly better at structured regulatory reasoning. The moat may compress faster than the plan assumes. Neo4j + Snowflake is an implementation choice, not a permanent moat.

5. **Liability exposure is real.** HITL reduces error rate but doesn't transfer carrier liability. First serious misfiling on a $500M DWP carrier could be existential. Professional liability insurance has limits, and carriers' legal teams will probe this hard in procurement.

6. **Founding team is a severe gating item.** Finding an ex-TICO/ISO Head of Regulatory Science *and* a Neo4j/Snowflake CTO *and* an insurance-tech VP Sales *and* a consulting-credible CEO is probably the real critical path. The plan treats it as a line item; in practice it's 12 months of recruiting before you write meaningful code.

7. **Market sizing is slightly stretched.** $600M SAM assumes 2,400 carriers × $250K blended ACV, but the tier breakdown doesn't cleanly produce $250K blended — small carriers (1,200 of them) are priced $80–150K, and the ~280 large carriers dominate wallet. Not fatal, but the TAM slide is doing some work.

### Bottom Line

This is a **"right thesis, hard execution"** business. The problem is genuine, the timing is defensible, and the positioning is correct. The three biggest de-risking questions:

- Can you recruit one flagship retiring stat-reporting expert as Head of Regulatory Science *before* the Series A closes?
- Is there one Texas mid-market carrier willing to sign a paid pilot LOI pre-funding?
- Is Verisk reachable early — a conversation (not a partnership) before funding, to reveal whether the "complement" positioning survives contact with reality?

If those three check out, it's fundable. If any one of them is a struggle, the plan is more wish than roadmap.

---

## Part 2 — Stress-Testing Investor / Pilot / SME Interest

When expressed interest exists in all three channels (capital, pilot customers, SMEs), the project moves from *"right thesis, hard execution"* to *"fundable"* — provided the interest is committed, not polite.

In insurance, *expressed interest* and *committed interest* are miles apart. The questions below separate real signals from noise.

### Investor Signals

- **Stage and check size?** Angel checks ($25–100K) validate the story. A $500K+ lead signals the thesis survives diligence.
- **Insurance-native?** An ex-Verisk / Guidewire / carrier CFO writing $100K is worth more than a generalist fund writing $1M — they de-risk reference calls.
- **Willing to back pre-team?** Pre-team commitment is rare and valuable. If they want to see the team first, that's a softer signal.

### Pilot / Testing Signals

- **Role of the interested party?** Chief Compliance Officer or VP Actuarial = real buyer. Director of IT = signals interest but can't sign. Innovation lab = usually a dead end in insurance.
- **Carrier size?** A $200M DWP mid-market Texas carrier is the ideal design partner. A national carrier wants 18 months of procurement before a pilot — exciting but slow.
- **Paid LOI available?** Even $25K for a scoped diagnostic beats a free pilot. Free pilots in insurance almost never convert — paid ones almost always do.

### SME Signals

- **Which seat?** Ex-TICO staff, ex-ISO statistical, ex-carrier stat reporting lead, or ACAS/FCAS with filing experience. Each unlocks different credibility.
- **Full-time, fractional, or advisory?** Head of Regulatory Science needs to be full-time or near-full-time — this person *is* the product. Advisory-only is not enough.
- **Willing to be named publicly?** That's the real test. In insurance, reputation is the currency.

---

## Part 3 — Concrete Next Steps

1. **Convert the SME first.** Before taking investor money, lock the regulatory SME with equity + some cash. Without them, the pitch is a deck. With them, it's a team.

2. **Get one paid LOI from the pilot carrier.** Even $25K for a scoped assessment — "we'll map your current TX statistical filing workflow and produce a gap analysis." That becomes the seed pitch's killer slide.

3. **Structure the raise around a 9–12 month milestone, not 18.** Target: GRE v1 covering TX TICO residential lines + one paid pilot filing submitted. That's a Series A trigger.

4. **Don't over-raise at seed.** $1.5–2.5M is enough to hit that milestone. Taking $5M+ at this stage usually means giving up too much at the wrong valuation — and insurance pilots don't move faster with more money.

5. **Have one exploratory Verisk conversation before funding.** Not a partnership ask — a listening meeting. "Here's what we're building; we see ourselves upstream of your statistical services; we'd like to stay coordinated." Their reaction tells you whether the complement thesis holds.
