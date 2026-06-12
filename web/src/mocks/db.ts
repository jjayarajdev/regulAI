// Mutable in-memory state behind the MSW handlers. GET handlers read from
// here; POST handlers mutate it the way the real backend mutates Snowflake +
// Neo4j, so the demo flows (apply bulletin → violations close → sign-off
// chain advances → TICO ACK) work end-to-end without a backend.

import * as fx from './fixtures';
import type {
  ApprovalRole, ApproveResponse, BronzeFixResponse, BulletinApplyResponse,
  FilingStatus, KgNeighborhoodResponse, ValidateResponse,
} from '../api/types';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

export const db = {
  state: clone(fx.state),
  validate: clone(fx.validateByFiling),
  approval: clone(fx.approvalByFiling),
  audit: clone(fx.auditByFiling),
  kgAudit: clone(fx.kgAudit),
  kgRules: clone(fx.kgRules),
  bronze: clone(fx.bronzeByFiling),
};

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
  ap.acked_at = new Date().toISOString();
  if (db.audit[filingId]) db.audit[filingId].batch.status = 'acked';
  const receipt = 'TICO-ACK-MOCK0001';
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
