// Mutable in-memory state behind the MSW handlers. GET handlers read from
// here; POST handlers mutate it the way the real backend mutates Snowflake +
// Neo4j, so the demo flows (apply bulletin → violations close → sign-off
// chain advances → TICO ACK) work end-to-end without a backend.

import * as fx from './fixtures';
import type {
  ApprovalRole, ApproveResponse, BronzeFixResponse, BulletinApplyResponse,
  BulletinImpact, FilingFileResponse, FilingStatus, KgNeighborhoodResponse,
  SendFilingResponse, SubmissionArchive, SubmissionEmail, SubmissionState,
  ValidateResponse,
} from '../api/types';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

export const db = {
  filings: clone(fx.filings),
  state: clone(fx.state),
  validate: clone(fx.validateByFiling),
  approval: clone(fx.approvalByFiling),
  audit: clone(fx.auditByFiling),
  kgAudit: clone(fx.kgAudit),
  kgRules: clone(fx.kgRules),
  bronze: clone(fx.bronzeByFiling),
  subExtras: clone(fx.submissionExtrasByFiling),
  bulletins: clone(fx.bulletins),
  regDocuments: clone(fx.regDocuments),
  regulations: clone(fx.regulations),
};

// ── regulation store (jurisdiction onboarding wizard) ───────────────
// Upload → extract (background job) → approve, mirroring api/main.py.
// Approve materializes draft rules into the mock KG, so the Jurisdictions
// registry picks the new state up as "Onboarding" — the story advances.

interface ExtractJob {
  status: 'running' | 'done' | 'error';
  cached?: boolean;
  result: {
    slug: string; model: string; n_nodes: number; n_relationships: number;
    n_citations: number; summary: string;
  } | null;
  error: string | null;
}
const extractJobs: Record<string, ExtractJob> = {};

// Which jurisdiction an uploaded document belongs to, guessed from its name —
// enough for the demo's story (the real backend gets this from the canon).
const JUR_HINTS: Array<[RegExp, string]> = [
  [/california|\bcdi\b/i, 'US-CA'], [/florida|fhcf|\boir\b/i, 'US-FL'],
  [/texas|tico|tdi/i, 'US-TX'], [/oklahoma|\boid\b/i, 'US-OK'],
];
const guessJur = (s: string): string =>
  JUR_HINTS.find(([re]) => re.test(s))?.[1] ?? 'US-CA';

export function uploadRegulationMock(
  fileName: string, label?: string | null, category?: string | null, jurisdiction?: string | null,
) {
  const stem = fileName.replace(/\.pdf$/i, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'regulation';
  const slug = `uploaded-${stem}`;
  const pages = 188;
  const chars = 412_308;
  const entry: fx.MockRegulation = {
    slug,
    jurisdiction_code: jurisdiction ? guessJur(jurisdiction) : guessJur(fileName),
    label: label || fileName.replace(/\.pdf$/i, ''),
    category: category || 'Uploaded regulations & bulletins',
    blurb: `Uploaded ${fileName} · ${pages} pages · ${chars.toLocaleString('en-US')} chars extracted.`,
    size_bytes: 14_890_000,
    exists: true,
    has_extraction: false,
    has_pdf: true,
  };
  const i = db.regulations.documents.findIndex((d) => d.slug === slug);
  if (i >= 0) db.regulations.documents[i] = entry;
  else db.regulations.documents.push(entry);
  delete extractJobs[slug];
  return {
    slug, label: entry.label, category: entry.category, pages, chars,
    jurisdiction_code: jurisdiction ? guessJur(jurisdiction) : guessJur(fileName),
    next: `POST /api/regulations/${slug}/extract  (Sentinel → KG)`,
  };
}

export function startExtractionMock(slug: string): { status: string } {
  if (extractJobs[slug]?.status === 'running') return { status: 'running' };
  extractJobs[slug] = { status: 'running', result: null, error: null };
  // Sentinel "runs" for a few seconds, then the cached extraction appears.
  setTimeout(() => {
    extractJobs[slug] = {
      status: 'done',
      result: {
        slug, model: 'mock-sentinel',
        n_nodes: 9, n_relationships: 14, n_citations: 12,
        summary: 'Statistical plan for residential property: territory assignment, '
          + 'mitigation-discount reporting and residual-market cross-references. '
          + '9 candidate rules with clause citations.',
      },
      error: null,
    };
    const doc = db.regulations.documents.find((d) => d.slug === slug);
    if (doc) doc.has_extraction = true;
  }, 2600);
  return { status: 'running' };
}

export function extractionStatusMock(slug: string): ExtractJob | { status: 'idle' } {
  const job = extractJobs[slug];
  if (job) return job;
  const doc = db.regulations.documents.find((d) => d.slug === slug);
  if (doc?.has_extraction) {
    return {
      status: 'done', cached: true, error: null,
      result: {
        slug, model: 'cached', n_nodes: 9, n_relationships: 14, n_citations: 12,
        summary: 'Cached extraction — 9 candidate rules with clause citations.',
      },
    };
  }
  return { status: 'idle' };
}

export function approveRegulationMock(slug: string): { status: number; body: unknown } {
  const doc = db.regulations.documents.find((d) => d.slug === slug);
  if (!doc) return { status: 404, body: { detail: `Document '${slug}' not found` } };
  if (!doc.has_extraction) {
    return { status: 400, body: { detail: 'No cached extraction. POST /api/regulations/{slug}/extract first.' } };
  }
  // Materialize: land three draft rules for the document's jurisdiction in
  // the KG (idempotent per slug), so the registry card + onboarding panel
  // pick the new state up immediately.
  const jur = guessJur(`${doc.label} ${slug}`);
  const created: string[] = [];
  for (let n = 1; n <= 3; n++) {
    const id = `RULE-${slug.toUpperCase().slice(0, 24)}-${String(n).padStart(3, '0')}`;
    if (db.kgRules.rules.some((r) => r.id === id)) continue;
    db.kgRules.rules.push({
      id,
      name: `${doc.label} — extracted rule ${n}`,
      confidence: [0.94, 0.88, 0.71][n - 1],
      short_title: null,
      jurisdiction_code: jur,
      rule_kind: 'reporting requirement',
      clause_ref: null,
      created_by: 'sentinel',
      created_at: now(),
      severity: n === 3 ? 'WARNING' : 'ERROR',
      version: 1,
      status: 'draft',
      effective_from: null,
      effective_until: null,
      citation: `${doc.label} — extracted clause ${n}`,
      section: jur.replace('US-', ''),
      executable: false,
      currently_active: false,
    });
    created.push(id);
  }
  db.kgRules.counts.total = db.kgRules.rules.length;
  db.kgRules.counts.descriptive = db.kgRules.rules.filter((r) => !r.executable).length;
  return {
    status: 200,
    body: { ok: true, nodes_created: created, relationships_created: created.length * 2 },
  };
}

// ── wizard "Go live" (mock-only endpoint) ───────────────────────────
// Materializes a filing obligation for the onboarded jurisdiction so it
// flips to Live on the Jurisdictions registry and shows up in the filing
// dashboard. Mirrors what scripts.seed_filing_obligations does for real.
const GO_LIVE_SEEDS: Record<string, { id: string; plan_name: string; plan_code: string; channel: string }> = {
  'US-CA': { id: 'CDI-HO-2026A', plan_name: 'California Homeowners — CDI Statistical Plan', plan_code: 'CDI-HO', channel: 'CDI Secure Upload' },
  'US-FL': { id: 'FLOIR-HO-2026A', plan_name: 'Florida Property — OIR Statistical Plan', plan_code: 'OIR-HO', channel: 'FL OIR Portal' },
  'US-OK': { id: 'OID-HO-2026A', plan_name: 'Oklahoma Homeowners — OID Statistical Plan', plan_code: 'OID-HO', channel: 'OID Email Submission' },
};

export function goLiveJurisdictionMock(jurisdiction: string): { status: number; body: unknown } {
  const jur = guessJur(jurisdiction || 'California');
  const seed = GO_LIVE_SEEDS[jur] ?? GO_LIVE_SEEDS['US-CA'];
  const existing = db.filings.filings.find((f) => f.jurisdiction_code === jur);
  if (existing) {
    existing.is_active = true;
    return { status: 200, body: { ok: true, filing_id: existing.id, already_live: true } };
  }
  db.filings.filings.push({
    id: seed.id,
    plan_name: seed.plan_name,
    plan_code: seed.plan_code,
    policy_id_ranges: [[2600, 2699]],
    cadence: 'Annual',
    period_start: '2026-01-01',
    period_end: '2026-12-31',
    due_date: '2027-04-01',
    channel: seed.channel,
    is_active: true,
    jurisdiction_code: jur,
  });
  db.kgAudit.entries.unshift({
    id: `audit-mock-${actionSeq++}`,
    action: 'jurisdiction_live',
    actor: 'S. Iyer',
    summary: `${jur.replace('US-', '')} certified — filing obligation ${seed.id} created, jurisdiction live`,
    occurred_at: now(),
    affected_count: 1,
  });
  db.kgAudit.count = db.kgAudit.entries.length;
  return { status: 200, body: { ok: true, filing_id: seed.id } };
}

// ── extraction review (per-proposal verdicts, mirrors api/main.py) ──
// GET merges the fixture proposals with in-memory verdicts; PUT stores a
// verdict and returns the same merged payload — exactly the live contract.
interface MockVerdict {
  verdict: 'accepted' | 'rejected' | 'overridden';
  overrides: Record<string, unknown> | null;
  reason: string | null; actor: string | null; at: string | null;
}
const reviewVerdicts: Record<string, Record<string, MockVerdict>> = {};

// The 9 candidate nodes every mock extraction "found" (n_nodes: 9 above),
// spread across the confidence bands so the review screen has work to show.
const PROPOSAL_SEED: Array<{
  temp_id: string; type: string; name: string; conf: number;
  fields: Record<string, unknown>; excerpt: string;
}> = [
  { temp_id: 'doc1', type: 'RegulationDocument', name: '__DOC__', conf: 0.99,
    fields: { kind: 'StatPlan', effective_date: '2026-01-01' },
    excerpt: 'This statistical plan is promulgated under the authority of the insurance code and applies to all residential property business written in the state.' },
  { temp_id: 'rule_territory', type: 'Rule', name: 'Territory code from property ZIP', conf: 0.96,
    fields: { section: '4.3.2', rule_number: 2, document_temp_id: 'doc1' },
    excerpt: 'Every residential property record must carry the two-digit territory assigned to the location ZIP code as of the effective date of the transaction.' },
  { temp_id: 'rule_aoi', type: 'Rule', name: 'Amount of insurance rounding', conf: 0.94,
    fields: { section: '4.5.1', rule_number: 5, document_temp_id: 'doc1' },
    excerpt: 'Amount of insurance shall be reported in whole thousands of dollars, rounded to the nearest thousand.' },
  { temp_id: 'tpl_annual', type: 'ReportTemplate', name: 'Annual statistical call', conf: 0.93,
    fields: { cadence: 'Annual', deadline_days_after_close: 90, document_temp_id: 'doc1' },
    excerpt: 'Each reporting insurer shall submit the annual call not later than ninety days after the close of the reporting period.' },
  { temp_id: 'cl_construction', type: 'CodeList', name: 'Construction codes', conf: 0.91,
    fields: { code_list_name: 'Construction', document_temp_id: 'doc1' },
    excerpt: 'Construction of the insured dwelling is reported on a six-value scale: frame, masonry veneer, masonry, superior, mixed, other.' },
  { temp_id: 'rule_wind', type: 'Rule', name: 'Windstorm exclusion requires coastal territory', conf: 0.88,
    fields: { section: '5.2.4', rule_number: 12, document_temp_id: 'doc1' },
    excerpt: 'A windstorm or hail exclusion indicator of 01 is admissible only where the territory code falls within the seacoast band enumerated in Appendix C.' },
  { temp_id: 'rule_roof', type: 'Rule', name: 'Roof age reporting', conf: 0.84,
    fields: { section: '5.4.1', rule_number: 17, document_temp_id: 'doc1' },
    excerpt: 'The age of the primary roof covering shall be reported in whole years; where the appendix table conflicts with this clause, the clause governs.' },
  { temp_id: 'rule_mitigation', type: 'Rule', name: 'Mitigation discount reporting', conf: 0.78,
    fields: { section: '6.1.3', rule_number: 22, document_temp_id: 'doc1' },
    excerpt: 'Premium credits granted for wind mitigation features shall be reported with the applicable mitigation code from the code table.' },
  { temp_id: 'rule_wildfire', type: 'Rule', name: 'Wildfire risk score derivation', conf: 0.64,
    fields: { section: '6.4', document_temp_id: 'doc1' },
    excerpt: 'Insurers using a vendor wildfire risk score shall report the score band; the clause references a bulletin this rulebook does not contain.' },
];

const bandOf = (c: number) => (c >= 0.9 ? 'auto' : c >= 0.7 ? 'queued' : 'escalated');

export function extractionReviewMock(slug: string): { status: number; body: unknown } {
  const doc = db.regulations.documents.find((d) => d.slug === slug);
  if (!doc) return { status: 404, body: { detail: `Document '${slug}' not found` } };
  if (!doc.has_extraction) {
    return { status: 400, body: { detail: 'No cached extraction. POST /api/regulations/{slug}/extract first.' } };
  }
  const verdicts = reviewVerdicts[slug] ?? {};
  let charAt = 120;
  const proposals = PROPOSAL_SEED.map((s) => {
    const v = verdicts[s.temp_id];
    const start = charAt;
    charAt += s.excerpt.length + 90;
    return {
      temp_id: s.temp_id, type: s.type,
      name: s.name === '__DOC__' ? doc.label : s.name,
      confidence: s.conf, band: bandOf(s.conf), fields: s.fields,
      citations: [{ char_start: start, char_end: start + s.excerpt.length, kind: 'defines', excerpt: s.excerpt }],
      verdict: v?.verdict ?? 'accepted',
      overrides: v?.overrides ?? null,
      reason: v?.reason ?? null, actor: v?.actor ?? null, at: v?.at ?? null,
    };
  });
  const n = proposals.length;
  const rejected = proposals.filter((p) => p.verdict === 'rejected').length;
  return {
    status: 200,
    body: {
      slug, label: doc.label,
      summary: 'Statistical plan for residential property: territory assignment, '
        + 'mitigation-discount reporting and residual-market cross-references. '
        + '9 candidate rules with clause citations.',
      proposals,
      totals: {
        proposals: n,
        accepted: n - rejected,
        rejected,
        overridden: proposals.filter((p) => p.verdict === 'overridden').length,
        queued: proposals.filter((p) => p.band === 'queued').length,
        escalated: proposals.filter((p) => p.band === 'escalated').length,
        avg_confidence: Math.round((proposals.reduce((a, p) => a + p.confidence, 0) / n) * 1000) / 1000,
      },
      updated_at: Object.values(verdicts).map((v) => v.at).sort().at(-1) ?? null,
    },
  };
}

export function putVerdictMock(
  slug: string, tempId: string, body: Record<string, unknown>,
): { status: number; body: unknown } {
  const doc = db.regulations.documents.find((d) => d.slug === slug);
  if (!doc) return { status: 404, body: { detail: `Document '${slug}' not found` } };
  if (!PROPOSAL_SEED.some((s) => s.temp_id === tempId)) {
    return { status: 404, body: { detail: `No proposal '${tempId}' in this extraction` } };
  }
  const verdict = String(body.verdict ?? '');
  if (!['accepted', 'rejected', 'overridden'].includes(verdict)) {
    return { status: 422, body: { detail: `Invalid verdict payload: ${verdict}` } };
  }
  const overrides = (body.overrides ?? null) as Record<string, unknown> | null;
  if (verdict === 'overridden' && (!overrides || !Object.keys(overrides).length)) {
    return { status: 422, body: { detail: "verdict 'overridden' requires overrides" } };
  }
  const store = (reviewVerdicts[slug] ??= {});
  if (verdict === 'accepted' && !body.reason && !overrides) {
    delete store[tempId];
  } else {
    store[tempId] = {
      verdict: verdict as MockVerdict['verdict'], overrides,
      reason: (body.reason as string) || null, actor: (body.actor as string) || null,
      at: new Date().toISOString().slice(0, 19),
    };
  }
  return extractionReviewMock(slug);
}

const now = () => new Date().toISOString().slice(0, 19).replace('T', ' ');

let actionSeq = 100;
function recordAction(filingId: string, type: string, actor: string, summary: string) {
  const audit = db.audit[filingId];
  if (!audit) return;
  audit.actions.unshift({
    action_id: `act-mock-${actionSeq++}`,
    action_type: type,
    actor,
    target_record: null,
    target_rule: null,
    summary,
    acted_at: new Date().toISOString().slice(0, 19).replace('T', ' '),
  });
}

function recomputeSummary(v: ValidateResponse) {
  const counts: Record<string, number> = {};
  for (const vio of v.violations) counts[vio.rule_id] = (counts[vio.rule_id] ?? 0) + 1;
  for (const r of v.rules) {
    r.violation_count = counts[r.rule_id] ?? 0;
    if (r.status !== 'error') r.status = r.violation_count > 0 ? 'fail' : 'pass';
  }
  // The fixture's rules array is a representative sample; rules_run counts the
  // full suite. Derive passing from the total so the readiness ratio stays
  // consistent (failing rules are all in the sample by construction).
  v.summary.rules_failing = v.rules.filter((r) => r.status === 'fail').length;
  v.summary.rules_passing = v.summary.rules_run - v.summary.rules_failing - v.summary.rules_errored;
  v.summary.total_violations = v.violations.length;
}

function syncBlockers(filingId: string) {
  const v = db.validate[filingId];
  const ap = db.approval[filingId];
  if (!v || !ap) return;
  ap.open_blockers = v.violations.filter((x) => x.severity === 'ERROR').length;
  if (db.audit[filingId]) db.audit[filingId].batch.open_blockers = ap.open_blockers;
  // Blockers cleared while still early in the chain → filing becomes signable.
  if (ap.open_blockers === 0 && (ap.status === 'validating' || ap.status === 'draft')) {
    ap.status = 'validated';
    ap.next_role = 'analyst';
  }
}

// ── bulletin apply / reset ──────────────────────────────────────────
export function applyBulletin(): BulletinApplyResponse {
  const deltas: BulletinApplyResponse['deltas'] = {};
  for (const [filingId, v] of Object.entries(db.validate)) {
    const closed = v.violations
      .filter((x) => x.rule_number === 'A.34')
      .map((x) => ({ policy_number: x.policy_number, rule_number: x.rule_number }));
    v.violations = v.violations.filter((x) => x.rule_number !== 'A.34');
    recomputeSummary(v);
    syncBlockers(filingId);
    deltas[filingId] = { closed_count: closed.length, closed };
    if (closed.length) {
      recordAction(filingId, 'bulletin_apply', 'D. Reyes · Analyst',
        `bulletin ${db.state.bulletin_id} applied — ${closed.length} exception(s) closed`);
    }
  }
  db.state.bulletin_applied = true;
  for (const b of db.bulletins.bulletins) {
    if (b.name === db.state.bulletin_id) b.status = 'applied';
  }
  db.kgAudit.entries.unshift({
    id: `audit-mock-${actionSeq++}`,
    action: 'bulletin_apply',
    actor: 'D. Reyes',
    summary: `Applied ${db.state.bulletin_id} — A.34 catastrophe-period override materialized`,
    occurred_at: new Date().toISOString().slice(0, 19).replace('T', ' '),
    affected_count: 3,
  });
  db.kgAudit.count = db.kgAudit.entries.length;
  return {
    ok: true,
    steps: [
      { step: 'materialize', ok: true },
      { step: 'version_bump', ok: true },
      { step: 'build_reference', ok: true },
      { step: 'load_reference', ok: true },
    ],
    deltas,
  };
}

export function resetBulletin() {
  db.state = clone(fx.state);
  db.validate = clone(fx.validateByFiling);
  db.approval = clone(fx.approvalByFiling);
  db.bronze = clone(fx.bronzeByFiling);
  db.subExtras = clone(fx.submissionExtrasByFiling);
  db.bulletins = clone(fx.bulletins);
  db.kgAudit.entries.unshift({
    id: `audit-mock-${actionSeq++}`,
    action: 'bulletin_reset',
    actor: 'system',
    summary: 'Canon reset to v1 baseline — bulletin amendments removed',
    occurred_at: new Date().toISOString().slice(0, 19).replace('T', ' '),
    affected_count: 3,
  });
  db.kgAudit.count = db.kgAudit.entries.length;
  return {
    ok: true,
    steps: [
      { step: 'reset', ok: true },
      { step: 'build_reference', ok: true },
      { step: 'load_reference', ok: true },
    ],
  };
}

// ── sign-off chain (mirrors APPROVAL_CHAIN in api/rhs_demo.py) ─────
const APPROVAL_CHAIN: Record<ApprovalRole, { required: FilingStatus[]; next: FilingStatus; nextRole: ApprovalRole | null; actor: string }> = {
  analyst: { required: ['validated'], next: 'analyst_signed', nextRole: 'actuary', actor: 'M. Okonkwo · Analyst' },
  actuary: { required: ['analyst_signed'], next: 'actuary_approved', nextRole: 'officer', actor: 'D. Reyes · Actuary' },
  officer: { required: ['actuary_approved'], next: 'officer_approved', nextRole: null, actor: 'J. Park · Compliance Officer' },
};

export function approve(filingId: string, role: ApprovalRole): { status: number; body: ApproveResponse | { detail: string } } {
  const chain = APPROVAL_CHAIN[role];
  const ap = db.approval[filingId];
  if (!chain) return { status: 400, body: { detail: `unknown role '${role}'` } };
  if (!ap) return { status: 404, body: { detail: `no filing batch for ${filingId}` } };
  if (!chain.required.includes(ap.status)) {
    return { status: 409, body: { detail: `cannot ${role}-approve in state '${ap.status}' — must be one of ${chain.required}` } };
  }
  if (ap.open_blockers > 0) {
    return { status: 409, body: { detail: `cannot sign off — ${ap.open_blockers} open ERROR-severity blocker(s) remain` } };
  }
  const prev = ap.status;
  ap.status = chain.next;
  ap.next_role = chain.nextRole;
  ap.can_seal = chain.next === 'officer_approved';
  if (db.audit[filingId]) db.audit[filingId].batch.status = chain.next;
  recordAction(filingId, `${role}_approved`, chain.actor,
    `${chain.actor.split(' · ')[0]} signed off — state ${prev} → ${chain.next}`);
  return { status: 200, body: { filing_id: filingId, role, prev_state: prev, new_state: chain.next, actor: chain.actor } };
}

export function ack(filingId: string) {
  const ap = db.approval[filingId];
  if (!ap) return { status: 404, body: { detail: `no filing batch for ${filingId}` } };
  if (ap.status !== 'submitted') {
    return { status: 409, body: { detail: `cannot ACK in state '${ap.status}' — filing must be 'submitted'` } };
  }
  ap.status = 'acked';
  ap.acked_at = now();
  if (db.audit[filingId]) db.audit[filingId].batch.status = 'acked';
  const receipt = `TICO-ACK-2026-${String(actionSeq++).padStart(6, '0')}`;
  const ex = db.subExtras[filingId];
  if (ex) {
    ex.ack = { receipt, acked_at: ap.acked_at, eml_path: `inbox/${filingId}/ack.eml` };
  }
  recordAction(filingId, 'regulator_ack', 'TICO ShareFile', `ACK received · receipt ${receipt}`);
  return { status: 200, body: { filing_id: filingId, receipt, new_state: 'acked' as const } };
}

// ── KG neighborhood fixture graph ──────────────────────────────────
export function neighborhood(ruleId: string): KgNeighborhoodResponse {
  const rule = db.kgRules.rules.find((r) => r.id === ruleId)
    ?? db.validate['TPA-Q4-2025'].rules.find((r) => r.rule_id === ruleId);
  const name = rule ? ('name' in rule ? rule.name : rule.rule_name) : ruleId;
  const citation = rule?.citation ?? '§34 Notice Record Layout';
  return {
    center: ruleId,
    nodes: [
      { id: ruleId, label: name.slice(0, 55), group: 'root', title: `Rule\n${name}`, shape: 'box' },
      { id: 'cit-1', label: citation.slice(0, 55), group: 'Citation', title: `Citation\n${citation}`, shape: 'dot' },
      { id: 'sec-A', label: 'Section A · General', group: 'Section', title: 'Section\nSection A', shape: 'dot' },
      { id: 'cv-L', label: 'L · credit score declination', group: 'CodeValue', title: 'CodeValue\nL', shape: 'dot' },
      { id: 'cv-LB', label: 'LB · L + companion', group: 'CodeValue', title: 'CodeValue\nLB', shape: 'dot' },
      { id: 'rule-sibling', label: 'Reason codes must match canon list', group: 'Rule', title: 'Rule\nsibling', shape: 'ellipse' },
    ],
    edges: [
      { from: ruleId, to: 'cit-1', label: 'CITES' },
      { from: 'sec-A', to: ruleId, label: 'CONTAINS' },
      { from: ruleId, to: 'cv-L', label: 'CONSTRAINS' },
      { from: ruleId, to: 'cv-LB', label: 'PERMITS' },
      { from: 'sec-A', to: 'rule-sibling', label: 'CONTAINS' },
    ],
  };
}

// ── manual bronze fix (mirrors POST /bronze/fix) ───────────────────
// Updates the bronze row, then re-evaluates the affected rules for that
// policy the way a real CDC propagation + revalidation would: A.34 fails
// iff the reason code is a bare 'L'; A.22 fails iff notice precedes
// effective by under 30 days.
export function fixBronze(policyNumber: string, field: string, newValue: string):
  { status: number; body: BronzeFixResponse | { detail: string } } {
  const policy = policyNumber.trim().toUpperCase();
  if (!policy.startsWith('POL-')) return { status: 400, body: { detail: 'policy_number must be like POL-0015' } };

  let filingId: string | null = null;
  let row: (typeof db.bronze)[string]['rows'][number] | undefined;
  for (const [fid, table] of Object.entries(db.bronze)) {
    row = table.rows.find((r) => r.policy === policy);
    if (row) { filingId = fid; break; }
  }
  if (!row || !filingId) return { status: 404, body: { detail: `no bronze record for ${policy}` } };

  let oldValue: string | null;
  if (field === 'reason_code') {
    const code = newValue.trim().toUpperCase();
    if (code && (!/^[A-Z]+$/.test(code) || code.length > 3)) {
      return { status: 400, body: { detail: 'reason_code must be 1–3 letters (or empty)' } };
    }
    oldValue = row.reason_code;
    row.reason_code = code;
  } else if (field === 'noticedate') {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(newValue.trim())) {
      return { status: 400, body: { detail: 'date must be YYYY-MM-DD' } };
    }
    oldValue = row.noticedate;
    row.noticedate = newValue.trim();
  } else {
    return { status: 400, body: { detail: `unknown field '${field}'; mock supports reason_code, noticedate` } };
  }

  // Re-evaluate this policy's violations against the touched rules.
  const v = db.validate[filingId];
  if (v) {
    const noticeOk =
      (new Date(row.effectivedate).getTime() - new Date(row.noticedate).getTime()) / 86_400_000 >= 30;
    v.violations = v.violations.filter((x) => {
      if (x.policy_number !== policy) return true;
      if (x.rule_number === 'A.34') return row!.reason_code === 'L'; // still bare L → still fails
      if (x.rule_number === 'A.22') return !noticeOk;
      return true;
    });
    recomputeSummary(v);
    syncBlockers(filingId);
  }

  recordAction(filingId, 'manual_fix', 'D. Reyes · Analyst',
    `${field}: ${oldValue ?? '∅'} → ${newValue || '∅'}`);
  const audit = db.audit[filingId];
  if (audit?.actions[0]) {
    audit.actions[0].target_record = policy;
    audit.actions[0].target_rule = field;
  }

  return {
    status: 200,
    body: {
      ok: true,
      policy_number: policy,
      field: field as BronzeFixResponse['field'],
      table: 'BRONZE.GW_PC_JOB',
      old_value: oldValue,
      new_value: newValue || null,
    },
  };
}

// ── submission journey (mirrors GET /filing/{id}/submission etc.) ──
const EMPTY_EXTRAS = { submission: null, email: null, ack: null, archive: null };

export function submissionState(filingId: string): SubmissionState {
  const ap = db.approval[filingId] ?? db.approval['TPA-Q4-2025'];
  const ex = db.subExtras[filingId] ?? EMPTY_EXTRAS;
  const raw = ap.status as string;
  const status = (
    raw === 'submitted' && ex.email ? 'sent'
    : raw === 'draft' || raw === 'validating' ? 'validated'
    : raw
  ) as SubmissionState['status'];
  return {
    filing_id: filingId,
    status,
    approval: { ...ap },
    submission: ex.submission,
    email: ex.email,
    sftp_path: ex.email && ex.submission ? sftpPathFor(filingId, ex.submission.file_name) : null,
    ack: ex.ack,
    archive: ex.archive,
  };
}

const sftpPathFor = (filingId: string, fileName: string) =>
  `/sftp/${filingId.startsWith('FHCF') ? 'fhcf' : 'tico'}/inbound/${fileName}`;

// Deterministic fake SHA-256 — the mock can't hash synchronously, but the
// value must be stable per filing so seal/preview/archive all agree.
const pseudoSha = (seed: string): string => {
  let h = 2166136261 >>> 0;
  let out = '';
  for (let i = 0; out.length < 64; i++) {
    h = Math.imul(h ^ seed.charCodeAt(i % seed.length) ^ i, 16777619) >>> 0;
    out += h.toString(16).padStart(8, '0');
  }
  return out.slice(0, 64);
};

const pad = (v: string | number, n: number) => String(v).padEnd(n).slice(0, n);
const num = (v: number, n: number) => String(v).padStart(n, '0').slice(-n);

// Render a plausible fixed-width TSPR file for a filing (mirrors
// GET /filing/{id}/file). persist=true seals: gates on the approval chain,
// then advances the filing to 'submitted' and stores the submission row.
const FILE_COUNTS: Record<string, [number, number, number]> = {
  'TPA-Q4-2025': [18, 6, 3],
  'RES-M03-2026': [96, 24, 12],
  'CL-Q4-2025': [11, 4, 2],
  'FHCF-A-2026': [42, 17, 0],
};

export function renderFile(filingId: string, persist: boolean):
  { status: number; body: FilingFileResponse | { detail: string } } {
  const f = fx.filings.filings.find((x) => x.id === filingId);
  if (!f) return { status: 404, body: { detail: `unknown filing ${filingId}` } };

  const naic = '10639';
  const [pc, lc, cc] = FILE_COUNTS[filingId] ?? [12, 4, 2];
  const header =
    `H${naic}${pad(f.plan_code, 5)}${pad(filingId, 14)}` +
    `${f.period_start.replace(/-/g, '')}${f.period_end.replace(/-/g, '')}` +
    `P${num(pc, 5)}L${num(lc, 5)}C${num(cc, 5)}`.padEnd(60);
  const line = (kind: string, i: number) =>
    `${kind}${naic}${pad(`POL-${2001 + i}`, 12)}1${num(19 + (i % 7), 2)}${num(140000 + i * 1735, 9)}` +
    `${num(2500 + (i % 4) * 500, 6)}${num(1, 2)}${'0'.repeat(8)}${pad('TX', 2)}${num(75001 + (i % 40), 9)}`.padEnd(70);
  const pLines = Array.from({ length: pc }, (_, i) => line('P', i));
  const lLines = Array.from({ length: lc }, (_, i) => line('L', i + 200));
  const cLines = Array.from({ length: cc }, (_, i) => line('C', i + 400));
  const body = [header, ...pLines, ...lLines, ...cLines].join('\n');
  // An already-sealed filing keeps its recorded hash — preview must agree
  // with the submission row and the archive.
  const sha256 = db.subExtras[filingId]?.submission?.sha256
    ?? pseudoSha(filingId + ':' + body.length);
  const footer = `T${naic}RECORDS${num(pc + lc + cc, 7)}SHA256:${sha256}`.padEnd(80);
  const fileText = body + '\n' + footer + '\n';
  const fileName = `TSPR_${naic}_${f.plan_code}_${filingId.replace(/-/g, '')}.txt`;

  const response: FilingFileResponse = {
    filing_id: filingId,
    file_name: fileName,
    naic,
    record_count: pc + lc + cc,
    byte_count: fileText.length,
    sha256,
    preview: fileText.slice(0, 2400),
    header,
    footer,
    p_count: pc,
    l_count: lc,
    c_count: cc,
    warning: null,
  };

  if (persist) {
    const ap = db.approval[filingId];
    if (!ap) return { status: 404, body: { detail: `no filing batch for ${filingId}` } };
    if (ap.status !== 'officer_approved' || ap.open_blockers > 0) {
      return {
        status: 409,
        body: {
          detail: `cannot seal: status is '${ap.status}' with ${ap.open_blockers} open blocker(s); ` +
            'filing must be officer_approved with 0 ERROR blockers',
        },
      };
    }
    ap.status = 'submitted';
    ap.can_seal = false;
    ap.submitted_at = now();
    if (db.audit[filingId]) {
      db.audit[filingId].batch.status = 'submitted';
      db.audit[filingId].batch.submitted_at = ap.submitted_at;
    }
    if (!db.subExtras[filingId]) db.subExtras[filingId] = { ...EMPTY_EXTRAS };
    db.subExtras[filingId].submission = {
      submission_id: 'sub-mock-' + pseudoSha(filingId).slice(0, 14),
      sha256,
      file_name: fileName,
      record_count: response.record_count,
      file_size_bytes: response.byte_count,
      sealed_at: ap.submitted_at,
    };
    recordAction(filingId, 'file_generated', 'J. Park · Compliance Officer',
      `Sealed ${response.record_count} records · ${response.byte_count} bytes · sha256:${sha256.slice(0, 12)}…`);
    response.persisted = true;
    response.submission_id = db.subExtras[filingId].submission!.submission_id;
  }

  return { status: 200, body: response };
}

// Transmit the sealed package (mirrors POST /filing/{id}/send): composes the
// email, drops the file on the regulator's channel and archives it.
export function sendFiling(
  filingId: string,
  draft: { subject?: string; body?: string; to?: string[] },
): { status: number; body: SendFilingResponse | { detail: string } } {
  const f = fx.filings.filings.find((x) => x.id === filingId);
  const ap = db.approval[filingId];
  const ex = db.subExtras[filingId];
  if (!f || !ap) return { status: 404, body: { detail: `unknown filing ${filingId}` } };
  if (!ex?.submission) return { status: 409, body: { detail: 'seal the package before sending' } };
  if (ex.email) return { status: 409, body: { detail: 'already sent — see the outbox message' } };
  if (ap.status !== 'submitted') {
    return { status: 409, body: { detail: `cannot send in state '${ap.status}' — filing must be sealed` } };
  }

  const sentAt = now();
  const s = ex.submission;
  const email: SubmissionEmail = {
    message_id: `<${Date.now()}.${filingId}@regulai.demo>`,
    from: 'filings@regulai.demo',
    to: draft.to?.length ? draft.to
      : [f.jurisdiction_code === 'US-FL' ? 'datacall@fhcf.example' : 'stat.submissions@tico.example'],
    subject: draft.subject || `${f.plan_code} statistical submission — ${filingId}`,
    body: draft.body || `Please find attached the sealed ${f.plan_code} submission for ${filingId}.`,
    attachment: { name: s.file_name, bytes: s.file_size_bytes },
    sent_at: sentAt,
    eml_path: `outbox/${filingId}/submission.eml`,
    transport: 'outbox',
  };
  const archive: SubmissionArchive = {
    path: `archive/2026/${filingId}/${s.file_name}`,
    sha256: s.sha256,
    archived_at: sentAt,
  };
  ex.email = email;
  ex.archive = archive;
  recordAction(filingId, 'submission_sent', 'J. Park · Compliance Officer',
    `Submission emailed to ${email.to.join(', ')} · ${s.file_name}`);

  return {
    status: 200,
    body: {
      filing_id: filingId,
      status: 'sent',
      email,
      sftp_path: sftpPathFor(filingId, s.file_name),
      archive,
    },
  };
}

// Bulletin impact — fixture analysis with the bulletin's live status merged in
// (so applying flips the header + apply bar without a reload).
export function bulletinImpact(name: string): BulletinImpact | null {
  const imp = fx.bulletinImpacts[name];
  if (!imp) return null;
  const b = db.bulletins.bulletins.find((x) => x.name === name);
  const out = clone(imp);
  if (b) out.bulletin = { ...b };
  return out;
}
