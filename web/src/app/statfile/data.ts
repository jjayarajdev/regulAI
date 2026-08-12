// STATFILE demo content — ported verbatim from the Statistical Filing Platform
// design (claude.ai/design). This is the render source the screens were
// designed around; API wiring replaces sections of it screen by screen.

export const ACC = '#5980a6';
export const ACC9 = '#1d2d3d';
export const NEU = '#98989b';

export type ScreenId =
  | 'dash' | 'rules' | 'amend' | 'graph' | 'pipe' | 'agents'
  | 'val' | 'record' | 'filing' | 'iso' | 'config' | 'users';

// 'iso' stays routable (direct state) but is no longer in the nav.
export const NAV: Array<[ScreenId, string]> = [
  ['dash', 'Filing dashboard'], ['rules', 'Rulebook & rules'], ['amend', 'Amendments & impact'],
  ['graph', 'Knowledge graph'], ['pipe', 'Medallion pipeline'], ['agents', 'Agent console'],
  ['val', 'Validation triage'], ['record', 'TX stat record'], ['filing', 'Filing & submission'],
  ['config', 'States & standards'],
  ['users', 'Users & access'],   // admin/cco only — filtered in the shell
];

export const TITLES: Record<ScreenId, [string, string]> = {
  dash: ['Cycle overview', 'Texas residential property — 2026 annual call'],
  rules: ['Rulebook ingestion', 'TDI Residential Property Statistical Plan'],
  graph: ['Lineage', 'Clause → rule → field → source'],
  pipe: ['Medallion pipeline', 'Bronze · Silver · Gold'],
  agents: ['Agent console', 'Extraction, mapping and validation runs'],
  val: ['Validation triage', 'Edit-package exceptions'],
  record: ['Record inspector', 'TDI HO statistical record'],
  filing: ['Submission journey', 'Seal · transmit · acknowledge · archive'],
  amend: ['Regulatory amendments', 'Bulletin impact on the executable canon'],
  iso: ['Standard projection', 'ISO Personal Lines Statistical Plan'],
  config: ['Configuration', 'Jurisdictions & reporting standards'],
  users: ['Access control', 'Users, roles & permissions'],
};

// ── rules ──────────────────────────────────────────────────────────────────
export interface Rule {
  id: string; kind: string; conf: number; title: string;
  text: string; logic: string; cite: string; agent: string; page: number;
}
export const RULES: Rule[] = [
  { id: 'R-TX-HO-0412', kind: 'Field derivation', conf: 96, title: 'Territory code from property ZIP', page: 47,
    text: "Every residential property record must carry the two-digit TDI territory assigned to the location's ZIP code as of the effective date of the transaction.",
    logic: 'territory_code = tdi_territory_lookup(\n  zip = risk.location.postal_code,\n  as_of = txn.effective_date\n)  -- 2 digits, zero-padded',
    cite: 'p. 47 · §4.3.2 ¶2', agent: 'Rule Extractor · sonnet-4.5' },
  { id: 'R-TX-HO-0418', kind: 'Validation edit', conf: 71, title: 'Windstorm exclusion requires coastal territory', page: 51,
    text: 'A windstorm/hail exclusion indicator of 01 is only admissible where the territory code is within the seacoast band. The clause enumerates the band by county, not by territory.',
    logic: "if wind_excl_ind == '01'\n  require territory_code in COASTAL_SET\n  -- COASTAL_SET derived from county list,\n  --  clause names counties not territories",
    cite: 'p. 51 · §4.6.1 tbl.9', agent: 'Rule Extractor · sonnet-4.5' },
  { id: 'R-TX-HO-0433', kind: 'Code translation', conf: 88, title: 'Construction code mapping', page: 44,
    text: "Construction is reported on a six-value scale. Guidewire's HOP construction type carries eleven values, so the mapping collapses masonry veneer variants.",
    logic: 'map HOPDwelling.ConstructionType →\n  Frame|FrameSiding      → 01\n  MasonryVeneer|Brick    → 02\n  Masonry|Concrete       → 03\n  FireResistive          → 04',
    cite: 'p. 44 · §4.2.7 tbl.4', agent: 'Field Mapper · sonnet-4.5' },
  { id: 'R-TX-HO-0451', kind: 'Amended', conf: 63, title: 'Roof age band — new in v2026.1', page: 63,
    text: 'The 2026 plan introduces a roof-age band in positions 70–71. The clause defines four bands but the appendix table lists five; the parser could not resolve the conflict.',
    logic: 'roof_age_band = band(\n  years = effective_year - roof_install_year\n)  -- ⚠ clause: 4 bands, appendix A-7: 5 bands\n   -- unresolved, human decision required',
    cite: 'p. 63 · §5.1.4 + app. A-7', agent: 'Rulebook Parser · opus-4' },
  { id: 'R-TX-HO-0208', kind: 'Field derivation', conf: 99, title: 'Written premium sign convention', page: 39,
    text: 'Return premium on cancellations and mid-term reductions is reported as a negative amount with a trailing sign overpunch.',
    logic: 'written_premium = signed_overpunch(\n  txn.premium_amount * 100\n)  -- implied 2 decimals',
    cite: 'p. 39 · §3.8.1', agent: 'Rule Extractor · sonnet-4.5' },
];

export interface Clause { t: string; r: string; b: string; h: string }
export const CLAUSES: Clause[] = [
  { t: '4.3.2  Territory Assignment', r: 'TDI-HO-STATPLAN-2026.1 · p. 47',
    b: 'Each exposure shall be assigned to a territory in accordance with the territory definitions published in Appendix B. Territory is determined by the postal code of the insured location as that code stood on the effective date of the transaction being reported, without regard to any subsequent postal reassignment.',
    h: "Where a postal code spans two or more territories, the territory containing the greater portion of the postal code's residential exposure shall govern. Carriers may not elect an alternative assignment." },
  { t: '4.6.1  Windstorm and Hail Exclusion', r: 'TDI-HO-STATPLAN-2026.1 · p. 51',
    b: 'A windstorm and hail exclusion indicator shall be reported for every residential property exposure. Code 01 denotes an exclusion in force; code 02 denotes coverage included.',
    h: 'Code 01 is admissible only for exposures located in Aransas, Brazoria, Calhoun, Cameron, Chambers, Galveston, Jefferson, Kenedy, Kleberg, Matagorda, Nueces, Refugio, San Patricio, Willacy counties, and in the portion of Harris County east of State Highway 146.' },
  { t: '4.2.7  Construction', r: 'TDI-HO-STATPLAN-2026.1 · p. 44',
    b: 'Construction shall be reported using the codes in Table 4. Where a dwelling exhibits more than one construction type, the predominant type by exterior wall area governs.',
    h: 'Masonry veneer over frame is reported as code 02, notwithstanding the underlying frame structure.' },
  { t: '5.1.4  Roof Characteristics', r: 'TDI-HO-STATPLAN-2026.1 · p. 63',
    b: 'Effective with the 2026 reporting period, carriers shall report the age of the roof covering at the effective date of the transaction, expressed as a band.',
    h: 'Bands are: 0–5 years, 6–10 years, 11–20 years, and over 20 years. (Appendix A-7 lists a fifth band, 21–30 years, together with over 30 years — reconcile before reporting.)' },
  { t: '3.8.1  Premium Sign Convention', r: 'TDI-HO-STATPLAN-2026.1 · p. 39',
    b: 'All premium and loss amounts shall be reported in whole cents with two implied decimal places, right-justified and zero-filled.',
    h: 'Negative amounts shall carry a trailing sign overpunch in the units position. Separate negative-indicator fields are not accepted and will reject the record.' },
];

// ── knowledge graph ────────────────────────────────────────────────────────
export interface GraphNodeInfo {
  kind: string; title: string; desc: string;
  props: Array<[string, string]>; impact: string;
}
export const GRAPH_NODES: Record<string, GraphNodeInfo> = {
  'cl-432': { kind: 'Rulebook clause', title: '§4.3.2 Territory Assignment',
    desc: 'The governing text in the TDI residential property statistical plan. Parsed once per rulebook version; every downstream node inherits its version stamp.',
    props: [['Document', 'TDI-HO-2026.1.pdf'], ['Page', '47'], ['Hash', 'sha256:9c41…e2b0'], ['Parsed', '12 Jun 2026'], ['Amended', 'no']],
    impact: 'A change here invalidates 1 rule, 1 stat field and 1.28M gold rows. Re-approval required before the cycle can seal.' },
  'rl-412': { kind: 'Derived rule', title: 'R-TX-HO-0412',
    desc: 'Extracted derivation rule, human-approved. Compiles to a Databricks SQL expression and to a validation edit executed on the silver layer.',
    props: [['Confidence', '96%'], ['Approved by', 'd.okafor'], ['Approved', '18 Jun 2026'], ['Compiled', 'expr + edit'], ['Runs', '1,284,930']],
    impact: 'Feeds territory_code and, transitively, edit TX-E118 on windstorm exclusion.' },
  'fld-terr': { kind: 'Statistical field', title: 'Territory Code · pos 32–33',
    desc: 'Two-digit TDI territory. Reported on every residential property exposure record and used by the department to build the loss-cost relativities.',
    props: [['Positions', '32–33'], ['Type', 'N(2), zero-fill'], ['Nullable', 'no'], ['Domain', '01–41'], ['Std', 'TDI HO 2026.1'], ['ISO peer', 'PL Terr (pos 26–29)']],
    impact: 'Blocking. A null or out-of-domain value holds the record from the package.' },
  'sil-zip': { kind: 'Silver column', title: 'silver.policy_exposure.postal_code',
    desc: 'Conformed, jurisdiction-agnostic exposure table. This is the seam that makes a new state a configuration change: the column exists once, every standard reads it.',
    props: [['Table', 'silver.policy_exposure'], ['Column', 'postal_code'], ['Rows', '1,284,930'], ['Freshness', '14 min'], ['Consumers', 'TDI, ISO, NAIC'], ['Contract', 'v4 · frozen']],
    impact: 'Shared by three standards. Schema changes go through the contract review, not a filing cycle.' },
  'gw-loc': { kind: 'Guidewire source', title: 'PolicyCenter · PolicyLocation',
    desc: 'Change-data-capture stream landed raw in bronze. Never read directly by a stat rule — only through the silver contract.',
    props: [['System', 'PolicyCenter 10.2'], ['Entity', 'PolicyLocation'], ['Field', 'PostalCode'], ['Ingest', 'CDC · 15 min'], ['Bronze', 'bronze.pc_policylocation']],
    impact: 'An upstream schema drift here is caught by the bronze contract test before it reaches silver.' },
};

// ── validation ─────────────────────────────────────────────────────────────
export interface EditError {
  code: string; field: string; desc: string; count: string;
  origin: string; sev: 0 | 1 | 2; status: string;
}
export const ERRORS: EditError[] = [
  { code: 'TX-E118', field: 'wind_excl_ind', desc: 'Windstorm exclusion outside coastal territory band', count: '1,204', origin: 'Rule R-TX-HO-0418', sev: 2, status: 'Blocking' },
  { code: 'TX-E204', field: 'roof_age_band', desc: 'Value not in domain — band 05 emitted', count: '643', origin: 'Rule R-TX-HO-0451', sev: 2, status: 'Blocking' },
  { code: 'TX-E077', field: 'amount_of_insurance', desc: 'Coverage A below plan minimum for form 003', count: '312', origin: 'Rule R-TX-HO-0119', sev: 1, status: 'Warn' },
  { code: 'TX-E031', field: 'written_exposure', desc: 'Exposure does not tie to policy term fraction', count: '188', origin: 'Reconciliation agent', sev: 1, status: 'Warn' },
  { code: 'TX-E402', field: 'construction_code', desc: "Guidewire value 'MasonryVeneerICF' unmapped", count: '96', origin: 'Rule R-TX-HO-0433', sev: 2, status: 'Blocking' },
  { code: 'TX-E009', field: 'policy_number', desc: 'Format differs from prior submission for same risk', count: '44', origin: 'Prior-year diff', sev: 0, status: 'Info' },
  { code: 'TX-E155', field: 'deductible_code', desc: 'Percentage deductible rounded to nearest plan code', count: '1,915', origin: 'Field Mapper', sev: 0, status: 'Info' },
];

export interface ErrDetail { why: string; rule: string; sample: Array<[string, string, 0 | 1]> }
export const ERR_DETAIL: Record<string, ErrDetail> = {
  'TX-E118': {
    why: 'The approved rule restricts exclusion code 01 to the seacoast band. These 1,204 exposures carry the exclusion but map to inland territories. In 1,190 of them the underlying Guidewire location sits in a coastal county whose ZIP was reassigned in 2025 — the territory lookup used the current postal table rather than the effective-date table.',
    rule: "R-TX-HO-0418 · approved 18 Jun 2026\nif wind_excl_ind == '01'\n  require territory_code in COASTAL_SET\ncite: TDI-HO-2026.1 p.51 §4.6.1 tbl.9",
    sample: [['policy_number', 'HO-TX-0071204-01', 0], ['territory_code', '34  (inland)', 1], ['wind_excl_ind', '01  (excluded)', 1], ['risk_county', 'Galveston', 0], ['postal_code', '77551', 0], ['gw_source', 'PolicyLocation:pc:8841072', 0]] },
  'TX-E204': {
    why: "The roof-age band rule was extracted at 63% confidence because the clause body and Appendix A-7 disagree on the number of bands. The compiler emitted the appendix's five-band domain; the edit package enforces the clause's four. Approve one reading to clear all 643.",
    rule: 'R-TX-HO-0451 · PENDING APPROVAL\nroof_age_band ∈ {01,02,03,04}   (clause §5.1.4)\nroof_age_band ∈ {01..05}        (appendix A-7)\ncite: TDI-HO-2026.1 p.63',
    sample: [['policy_number', 'HO-TX-0033918-04', 0], ['roof_age_band', '05  (not in clause domain)', 1], ['roof_install_year', '2001', 0], ['effective_date', '2026-03-14', 0], ['derived_age', '25 years', 0], ['gw_source', 'HOPDwelling:pc:2210934', 0]] },
};

// ── dashboard ──────────────────────────────────────────────────────────────
export interface Cycle {
  state: string; line: string; std: string; period: string; due: string;
  records: string; status: string; tagClass: string; goTo: ScreenId;
}
export const CYCLES: Cycle[] = [
  { state: 'TX', line: 'Homeowners', std: 'TDI HO 2026.1', period: '2025 CY', due: '2026-09-15', records: '1,284,930', status: 'In validation', tagClass: 'tag-accent', goTo: 'val' },
  { state: 'TX', line: 'Homeowners', std: 'ISO PL SP', period: '2025 CY', due: '2026-09-30', records: '1,284,930', status: 'Mapping', tagClass: 'tag-outline', goTo: 'iso' },
  { state: 'TX', line: 'Dwelling fire', std: 'TDI DF 2026.1', period: '2025 CY', due: '2026-09-15', records: '218,004', status: 'Extracting rules', tagClass: 'tag-outline', goTo: 'rules' },
  { state: 'OK', line: 'Homeowners', std: 'NAIC MCAS', period: '2025 CY', due: '2026-04-30', records: '402,117', status: 'Filed', tagClass: 'tag-neutral', goTo: 'dash' },
  { state: 'LA', line: 'Homeowners', std: 'LDI HO 2025', period: '2025 CY', due: '2026-05-31', records: '311,880', status: 'Filed', tagClass: 'tag-neutral', goTo: 'dash' },
  { state: 'CA', line: 'Homeowners', std: 'CDI HO 2026', period: '2026 CY', due: '2027-04-01', records: '—', status: 'Onboarding', tagClass: 'tag-outline', goTo: 'config' },
];

export const LAYERS = [
  { name: 'Bronze', pct: '100%', meta: '14 min · 41 tables' },
  { name: 'Silver', pct: '97%', meta: '26 min · 12 tables' },
  { name: 'Gold', pct: '84%', meta: '2 h 08 · 3 tables' },
];

export interface QueueItem { kicker: string; title: string; body: string; meta: string; goTo: ScreenId }
export const QUEUE: QueueItem[] = [
  { kicker: 'Approval gate', title: '17 rules await sign-off', body: 'Four were amended by rulebook v2026.1 and one has an unresolved conflict between clause and appendix.', meta: 'Blocks seal', goTo: 'rules' },
  { kicker: 'Exception', title: '1,204 windstorm-exclusion conflicts', body: 'Territory lookup used the current postal table, not the effective-date table. Agent proposes a bulk correction.', meta: 'TX-E118', goTo: 'val' },
  { kicker: 'Mapping gap', title: 'Unmapped Guidewire construction value', body: "'MasonryVeneerICF' appeared in PolicyCenter after the last mapping run — 96 exposures affected.", meta: 'TX-E402', goTo: 'pipe' },
  { kicker: 'Onboarding', title: 'California is at step 3 of 5', body: 'Rulebook parsed, 214 candidate rules extracted, mapping to silver in progress.', meta: 'CDI HO 2026', goTo: 'config' },
];

// ── pipeline ───────────────────────────────────────────────────────────────
export interface MedallionLayer {
  name: string; status: string; tagClass: string; desc: string;
  latency: string; last: string; tables: Array<[string, string]>;
}
export const MEDALLION: MedallionLayer[] = [
  { name: 'BRONZE', status: 'Fresh', tagClass: 'tag-neutral', desc: 'Guidewire CDC landed as-is. Append-only, schema-on-read, full replay from the transaction log.', latency: '14 min', last: '07:41',
    tables: [['bronze.pc_policyperiod', '4.1M'], ['bronze.pc_hopdwelling', '1.9M'], ['bronze.pc_policylocation', '2.2M'], ['bronze.pc_transaction', '11.4M'], ['bronze.cc_claim', '382K'], ['bronze.cc_exposure', '614K'], ['bronze.bc_invoiceitem', '8.8M']] },
  { name: 'SILVER', status: 'Fresh', tagClass: 'tag-neutral', desc: 'Conformed, jurisdiction-agnostic entities. Deduplicated, effective-dated, contract-tested. Every standard reads from here.', latency: '26 min', last: '07:53',
    tables: [['silver.policy_exposure', '1.28M'], ['silver.premium_transaction', '3.4M'], ['silver.loss_transaction', '612K'], ['silver.risk_location', '1.21M'], ['silver.coverage_detail', '5.9M'], ['silver.party', '981K']] },
  { name: 'GOLD', status: 'Rebuilding', tagClass: 'tag-outline', desc: 'One table per standard per jurisdiction. Purely a projection — the record layout, the codes and the edits all come from approved rules.', latency: '2 h 08', last: '06:12',
    tables: [['gold.tx_ho_stat_record', '1.28M'], ['gold.iso_pl_ho_record', '1.28M'], ['gold.filing_exception', '3.4K']] },
];

export const CONTRACT = [
  { field: 'territory_code', silver: 'risk_location.postal_code', gw: 'PolicyLocation.PostalCode', xform: 'Effective-dated TDI territory lookup', rule: 'R-TX-HO-0412', cov: '100%', tagClass: 'tag-neutral' },
  { field: 'construction_code', silver: 'coverage_detail.construction', gw: 'HOPDwelling.ConstructionType', xform: '11 → 6 value collapse', rule: 'R-TX-HO-0433', cov: '99.9%', tagClass: 'tag-outline' },
  { field: 'amount_of_insurance', silver: 'coverage_detail.cov_a_limit', gw: 'HOPCoverage.CovALimit', xform: 'Whole dollars, zero-filled N(7)', rule: 'R-TX-HO-0119', cov: '100%', tagClass: 'tag-neutral' },
  { field: 'written_premium', silver: 'premium_transaction.amount', gw: 'Transaction.Amount', xform: 'Cents, trailing sign overpunch', rule: 'R-TX-HO-0208', cov: '100%', tagClass: 'tag-neutral' },
  { field: 'written_exposure', silver: 'premium_transaction.term_fraction', gw: 'PolicyPeriod term dates', xform: 'Term days ÷ 365, 5 implied decimals', rule: 'R-TX-HO-0211', cov: '100%', tagClass: 'tag-neutral' },
  { field: 'wind_excl_ind', silver: 'coverage_detail.wind_excluded', gw: 'HOPExclusion (HOPWindHail)', xform: 'Presence of exclusion → 01/02', rule: 'R-TX-HO-0418', cov: '100%', tagClass: 'tag-neutral' },
  { field: 'roof_age_band', silver: 'coverage_detail.roof_year', gw: 'HOPDwelling.RoofYearBuilt', xform: 'Age band — domain unresolved', rule: 'R-TX-HO-0451', cov: '94.1%', tagClass: 'tag-accent' },
];

// ── agents ─────────────────────────────────────────────────────────────────
export const AGENT_STATS = [
  { label: 'Runs this cycle', value: '1,847' }, { label: 'Tokens', value: '42.8M' },
  { label: 'Mean confidence', value: '91%' }, { label: 'Escalated', value: '23' },
];

export interface AgentRun {
  agent: string; task: string; model: string; tokens: string;
  dur: string; conf: string; result: string; tagClass: string;
}
export const RUNS: AgentRun[] = [
  { agent: 'Rulebook Parser', task: 'Segment TDI HO 2026.1 · 214 pp', model: 'opus-4', tokens: '1.9M', dur: '8m 12s', conf: '—', result: 'Complete', tagClass: 'tag-neutral' },
  { agent: 'Rule Extractor', task: 'Derive rules from §3–§5', model: 'sonnet-4.5', tokens: '6.2M', dur: '21m 04s', conf: '92%', result: 'Complete', tagClass: 'tag-neutral' },
  { agent: 'Diff Agent', task: 'v2025.2 → v2026.1 clause diff', model: 'sonnet-4.5', tokens: '880K', dur: '3m 41s', conf: '97%', result: '11 changes', tagClass: 'tag-outline' },
  { agent: 'Field Mapper', task: 'Map stat fields → silver contract', model: 'sonnet-4.5', tokens: '2.4M', dur: '11m 55s', conf: '88%', result: '1 gap', tagClass: 'tag-outline' },
  { agent: 'Schema Prober', task: 'Guidewire PolicyCenter introspection', model: 'haiku-4', tokens: '410K', dur: '1m 18s', conf: '99%', result: 'Complete', tagClass: 'tag-neutral' },
  { agent: 'Edit Compiler', task: 'Compile 214 edits to Spark SQL', model: 'sonnet-4.5', tokens: '3.1M', dur: '6m 33s', conf: '95%', result: 'Complete', tagClass: 'tag-neutral' },
  { agent: 'Reconciler', task: 'Tie premium to GL 2025 CY', model: 'sonnet-4.5', tokens: '1.2M', dur: '14m 09s', conf: '84%', result: 'Variance', tagClass: 'tag-accent' },
  { agent: 'Package Builder', task: 'Assemble TDI submission', model: 'haiku-4', tokens: '220K', dur: '—', conf: '—', result: 'Blocked', tagClass: 'tag-accent' },
  { agent: 'ISO Projector', task: 'Project silver → ISO PL layout', model: 'sonnet-4.5', tokens: '1.8M', dur: '9m 27s', conf: '90%', result: '6 gaps', tagClass: 'tag-outline' },
];

export const TRACE = [
  { step: 'Retrieve', detail: 'clause §4.6.1 + tbl.9 + appendix B\n3 chunks · 4,102 tokens', dot: NEU },
  { step: 'Ground', detail: 'resolved 14 county names → 9 territory codes\nvia gold.tdi_territory_ref', dot: NEU },
  { step: 'Draft rule', detail: 'emitted predicate + edit skeleton\nself-consistency n=5, agreement 3/5', dot: ACC },
  { step: 'Self-critique', detail: 'flagged: clause enumerates counties,\nrecord carries territory — mapping is lossy\nfor Harris County (partial)', dot: ACC },
  { step: 'Confidence', detail: '0.71 — below 0.90 auto-approve threshold', dot: ACC9 },
  { step: 'Escalate', detail: 'routed to compliance queue\nassignee d.okafor · 18 Jun 2026 09:14', dot: ACC9 },
];

// ── record inspector ───────────────────────────────────────────────────────
export const RECORD_IMAGE = '88412HO20260601HO-TX-0048817-0221003040103850001000120142387+0100000020301';

export const REC_FIELDS = [
  { pos: '1–5', name: 'Company code', val: '88412', dec: 'NAIC 88412', src: 'config', rule: '—' },
  { pos: '6–7', name: 'Statistical plan', val: 'HO', dec: 'Residential property', src: 'config', rule: '—' },
  { pos: '8–13', name: 'Accounting period', val: '202606', dec: 'Jun 2026', src: 'premium_transaction', rule: 'R-0102' },
  { pos: '14–15', name: 'Transaction code', val: '01', dec: 'New business', src: 'Transaction.Subtype', rule: 'R-0107' },
  { pos: '16–31', name: 'Policy number', val: 'HO-TX-0048817-02', dec: '—', src: 'PolicyPeriod.PolicyNumber', rule: 'R-0101' },
  { pos: '32–33', name: 'Territory code', val: '21', dec: 'Harris — inner', src: 'PolicyLocation.PostalCode', rule: 'R-0412' },
  { pos: '34–36', name: 'Form code', val: '003', dec: 'HO-3 special', src: 'HOPLine.PolicyFormType', rule: 'R-0121' },
  { pos: '37–38', name: 'Protection class', val: '04', dec: 'PPC 4', src: 'risk_location.ppc', rule: 'R-0126' },
  { pos: '39–40', name: 'Construction', val: '01', dec: 'Frame', src: 'HOPDwelling.ConstructionType', rule: 'R-0433' },
  { pos: '41–47', name: 'Amount of insurance', val: '0385000', dec: '$385,000', src: 'HOPCoverage.CovALimit', rule: 'R-0119' },
  { pos: '48–51', name: 'Deductible code', val: '1000', dec: '$1,000 flat', src: 'HOPDeductible', rule: 'R-0155' },
  { pos: '52–53', name: 'Policy term', val: '12', dec: '12 months', src: 'PolicyPeriod term', rule: 'R-0104' },
  { pos: '54–60', name: 'Written premium', val: '0142387', dec: '$1,423.87', src: 'Transaction.Amount', rule: 'R-0208' },
  { pos: '61–67', name: 'Written exposure', val: '+0100000', dec: '1.00000 house-yr', src: 'term_fraction', rule: 'R-0211' },
  { pos: '68–69', name: 'Windstorm excl.', val: '02', dec: 'Coverage included', src: 'HOPExclusion', rule: 'R-0418' },
  { pos: '70–71', name: 'Roof age band', val: '03', dec: '11–20 years ⚠', src: 'HOPDwelling.RoofYearBuilt', rule: 'R-0451' },
  { pos: '72–73', name: 'Rating method', val: '01', dec: 'Filed rate', src: 'HOPLine.RatingMethod', rule: 'R-0131' },
];

export const PKG = [
  { k: 'Cycle', v: 'TX-HO-2026A' }, { k: 'Records', v: '1,284,930' },
  { k: 'Held', v: '1,847' }, { k: 'Rulebook hash', v: '9c41…e2b0' },
  { k: 'Approved rules', v: '197 / 214' }, { k: 'Gold snapshot', v: 'v418 · 07:53' },
  { k: 'Statistical agent', v: 'ISO / NISS' },
];

export const RECON = [
  { k: 'Written premium', v: '$412,880,114', d: '0.00%', tagClass: 'tag-neutral' },
  { k: 'Written exposure', v: '1,241,908.4', d: '0.00%', tagClass: 'tag-neutral' },
  { k: 'Paid loss', v: '$288,401,772', d: '0.14%', tagClass: 'tag-outline' },
];

// ── ISO projection ─────────────────────────────────────────────────────────
export const CROSSWALK = [
  { silver: 'risk_location.postal_code', tdi: 'territory_code (32–33)', iso: 'terr_code (26–29)', rel: 'Recoded', bridge: 'TDI 2-digit → ISO 4-digit territory', tagClass: 'tag-outline' },
  { silver: 'coverage_detail.cov_a_limit', tdi: 'amount_of_insurance (41–47)', iso: 'amt_ins (44–51)', rel: 'Direct', bridge: 'Width change only', tagClass: 'tag-neutral' },
  { silver: 'coverage_detail.construction', tdi: 'construction_code (39–40)', iso: 'constr_code (38–39)', rel: 'Recoded', bridge: '6-value → 4-value collapse', tagClass: 'tag-outline' },
  { silver: 'premium_transaction.amount', tdi: 'written_premium (54–60)', iso: 'prem_amt (60–68)', rel: 'Direct', bridge: 'Same sign convention', tagClass: 'tag-neutral' },
  { silver: 'coverage_detail.wind_excluded', tdi: 'wind_excl_ind (68–69)', iso: '—', rel: 'TDI only', bridge: 'No ISO peer; dropped', tagClass: 'tag-neutral' },
  { silver: 'coverage_detail.roof_year', tdi: 'roof_age_band (70–71)', iso: 'roof_cd (96–97)', rel: 'Recoded', bridge: 'Band vs. material+age composite', tagClass: 'tag-outline' },
  { silver: 'party.producer_code', tdi: '—', iso: 'agency_cd (100–105)', rel: 'ISO only', bridge: 'Sourced from PolicyPeriod.ProducerCode', tagClass: 'tag-accent' },
  { silver: 'coverage_detail.ppc', tdi: 'protection_class (37–38)', iso: 'prot_cl (40–41)', rel: 'Direct', bridge: '—', tagClass: 'tag-neutral' },
  { silver: 'policy_exposure.form_type', tdi: 'form_code (34–36)', iso: 'form_cd (32–34)', rel: 'Direct', bridge: 'Shared ISO form taxonomy', tagClass: 'tag-neutral' },
];

export const ISO_IMAGE = '8841204452026061HO-TX-0048817-02 0214 003 04 01 000385000 1000 12 000142387+ 0100000 03 01 A2210 000000';

export const ISO_GAPS = [
  { title: 'Agency code has no TDI peer', body: 'ISO requires a producer/agency code the Texas plan never asked for. Sourced from PolicyPeriod.ProducerCode — 4.2% of records are null in Guidewire.', dot: ACC9 },
  { title: 'Roof coding is not a band', body: 'ISO codes roof material and age as a composite; TDI wants a band. The mapper proposes a lookup table rather than a transform.', dot: ACC },
  { title: 'Territory granularity', body: "ISO territories are finer than TDI's. The 2-to-4 digit expansion is one-to-many for 6 TDI territories and needs a documented tie-break.", dot: ACC },
];

// ── config ─────────────────────────────────────────────────────────────────
export const STATES = [
  { code: 'TX', name: 'Texas — Department of Insurance', detail: 'Homeowners, dwelling fire · TDI plan v2026.1 · 214 rules', status: 'Live', tagClass: 'tag-accent', color: ACC9 },
  { code: 'OK', name: 'Oklahoma — Insurance Department', detail: 'Homeowners · NAIC MCAS · 88 rules', status: 'Live', tagClass: 'tag-neutral', color: ACC9 },
  { code: 'LA', name: 'Louisiana — Department of Insurance', detail: 'Homeowners · LDI plan v2025.1 · 176 rules', status: 'Live', tagClass: 'tag-neutral', color: ACC9 },
  { code: 'CA', name: 'California — Department of Insurance', detail: 'Homeowners · CDI plan v2026 · 214 candidate rules', status: 'Onboarding', tagClass: 'tag-outline', color: ACC },
];

export const STANDARDS = [
  { name: 'TDI Residential Property Statistical Plan', ver: '2026.1', rules: '214', owner: 'Texas DOI' },
  { name: 'ISO Personal Lines Statistical Plan', ver: '2026 ed.', rules: '301', owner: 'ISO / Verisk' },
  { name: 'NAIC Market Conduct Annual Statement', ver: '2025', rules: '88', owner: 'NAIC' },
  { name: 'LDI Homeowners Statistical Plan', ver: '2025.1', rules: '176', owner: 'Louisiana DOI' },
];

export const ONBOARD_STEPS = [
  { n: '1', title: 'Ingest rulebook', status: 'Done', body: 'CDI residential property plan · 188 pp · parsed and hashed.', tagClass: 'tag-neutral', ring: ACC, fill: ACC, num: '#f2f2f3' },
  { n: '2', title: 'Extract candidate rules', status: 'Done', body: '214 rules derived. 168 auto-approved above the 0.90 threshold, 46 queued for a human.', tagClass: 'tag-neutral', ring: ACC, fill: ACC, num: '#f2f2f3' },
  { n: '3', title: 'Map to the silver contract', status: 'In progress', body: '39 of 47 fields resolve to existing silver columns. 8 need new derivations — none need new Guidewire extracts.', tagClass: 'tag-outline', ring: ACC, fill: 'transparent', num: ACC9 },
  { n: '4', title: 'Compile the edit package', status: 'Queued', body: 'Validation edits compile to Spark SQL and run against a silver sample before the first real cycle.', tagClass: 'tag-neutral', ring: 'color-mix(in srgb,#1d1f20 20%,transparent)', fill: 'transparent', num: NEU },
  { n: '5', title: 'Dry-run and certify', status: 'Queued', body: 'Shadow cycle against 2025 data, reconciled to the financials, reviewed by compliance before the first live filing.', tagClass: 'tag-neutral', ring: 'color-mix(in srgb,#1d1f20 20%,transparent)', fill: 'transparent', num: NEU },
];
