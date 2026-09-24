// The filing journey — one derived view of "where is this filing and what
// happens next", computed from the queries the screens already make
// (filings, validate/all, bulletins + impact, submission state, canon rules).
// Every journey-stage screen and the header rail read this so the numbers
// agree everywhere; nothing here talks to the API on its own.
import { useMemo } from 'react';
import type { Bulletin, Filing, SubmissionJourneyStatus } from '../../../api/types';
import {
  useBulletinImpact, useBulletins, useFilings, useKgRules, useSubmissionState,
  useValidateAll,
} from '../api';
import { ERRORS, type ScreenId } from '../data';

export type StageKey = 'rules' | 'validate' | 'resolve' | 'signoff' | 'seal' | 'acked';
export type StageState = 'done' | 'current' | 'blocked' | 'waiting';

export interface Stage {
  key: StageKey;
  n: number;              // 1-based position on the rail
  label: string;
  detail: string;
  state: StageState;
  goTo: ScreenId;
}

export interface NextAction { label: string; why: string; goTo: ScreenId }

export interface Journey {
  filing: Filing | null;
  filings: Filing[];
  live: boolean;                    // warehouse answered; false → design fixtures
  blockers: number;                 // ERROR violations, unsuppressed, this filing
  warnings: number;
  daysToDue: number | null;
  bulletin: Bulletin | null;        // pending bulletin for this jurisdiction
  bulletinClears: number;           // exceptions the pending bulletin would clear
  bulletinRules: Set<string>;       // rule numbers the pending bulletin touches
  bulletinLoading: boolean;
  status: SubmissionJourneyStatus;
  signed: 0 | 1 | 2 | 3;
  sealed: boolean;
  sent: boolean;
  acked: boolean;
  archived: boolean;
  rulesTotal: number | null;
  rulesPending: number | null;
  canon: string;                    // canon label shown beside the filing
  stages: Stage[];
  current: StageKey;                // the raised stage on the rail
  next: NextAction;
}

// Design fixture for a cold warehouse — the same filing the rest of the
// design content assumes, so the demo tells one story.
const DEMO_FILING: Filing = {
  id: 'TPA-Q4-2025', plan_name: 'Texas Private Passenger Auto / Homeowners', plan_code: 'TPA',
  policy_id_ranges: [], cadence: 'Quarterly', period_start: '2025-10-01', period_end: '2025-12-31',
  due_date: '2026-12-08', channel: 'TICO ShareFile', is_active: true, jurisdiction_code: 'US-TX',
};

const SIGNED: Record<string, 0 | 1 | 2 | 3> = {
  validated: 0, analyst_signed: 1, actuary_approved: 2, officer_approved: 3,
  submitted: 3, sent: 3, acked: 3,
};

const num = (s: string) => parseInt(s.replace(/,/g, ''), 10) || 0;

// Which journey stage a screen belongs to — the rail marks it "you are here".
export function stageForScreen(screen: ScreenId, j: Pick<Journey, 'signed' | 'sealed' | 'sent'>): StageKey | null {
  switch (screen) {
    case 'rules': case 'graph': case 'extract': return 'rules';
    case 'val': case 'record': return 'validate';
    case 'amend': return 'resolve';
    case 'filing': return j.sent ? 'acked' : j.signed >= 3 ? 'seal' : 'signoff';
    default: return null;
  }
}

export function useJourney(filingId: string | null): Journey {
  const filingsQ = useFilings();
  const valQ = useValidateAll();
  const bulQ = useBulletins();
  const rulesQ = useKgRules();

  const filings = filingsQ.data?.filings ?? [];
  const live = filings.length > 0;
  const filing: Filing | null = live
    ? (filings.find((f) => f.id === filingId)
      ?? filings.find((f) => f.id === filingsQ.data?.default && f.is_active)
      ?? filings.find((f) => f.is_active)
      ?? filings[0])
    : DEMO_FILING;

  const subQ = useSubmissionState(live && filing ? filing.id : null);

  const bulletin: Bulletin | null = useMemo(() => {
    const list = bulQ.data?.bulletins ?? [];
    return list.find((b) => b.status === 'pending'
      && (!filing?.jurisdiction_code || b.jurisdiction_code === filing.jurisdiction_code))
      ?? list.find((b) => b.status === 'pending') ?? null;
  }, [bulQ.data, filing?.jurisdiction_code]);
  const impactQ = useBulletinImpact(bulletin ? bulletin.name : null);

  return useMemo(() => {
    // ── exceptions on this filing ────────────────────────────────────────
    let blockers = 0, warnings = 0;
    if (valQ.data && filing) {
      const fv = valQ.data.by_filing[filing.id];
      const sup = valQ.data.suppressions ?? {};
      for (const v of fv?.violations ?? []) {
        if (v.suppressed || sup[v.rule_number]) continue;
        if (v.severity === 'ERROR') blockers += 1;
        else if (v.severity === 'WARNING') warnings += 1;
      }
    } else if (!live) {
      // Design fixtures: the demo edit package.
      blockers = ERRORS.filter((e) => e.sev === 2).reduce((n, e) => n + num(e.count), 0);
      warnings = ERRORS.filter((e) => e.sev === 1).reduce((n, e) => n + num(e.count), 0);
    }
    // The server's own count wins when validation hasn't answered yet.
    if (!valQ.data && subQ.data) blockers = subQ.data.approval.open_blockers;

    // ── submission journey ───────────────────────────────────────────────
    const sub = subQ.data;
    const status: SubmissionJourneyStatus = sub?.status ?? 'validated';
    const signed = SIGNED[status] ?? 0;
    const sealed = !!sub?.submission || ['submitted', 'sent', 'acked'].includes(status);
    const sent = !!sub?.email || ['sent', 'acked'].includes(status);
    const acked = !!sub?.ack || status === 'acked';
    const archived = !!sub?.archive;

    // ── pending bulletin ─────────────────────────────────────────────────
    const impact = impactQ.data;
    const bulletinClears = impact
      ? impact.totals.newly_passing
      : bulletin ? bulletin.targets : 0;
    // Rules whose exceptions the bulletin would clear (not every rule it touches).
    const bulletinRules = new Set<string>(
      (impact?.rule_changes ?? [])
        .filter((rc) => (rc.records?.newly_passing ?? 0) > 0)
        .map((rc) => rc.rule_number));

    // ── canon ────────────────────────────────────────────────────────────
    const rulesTotal = rulesQ.data ? rulesQ.data.counts.total : null;
    const rulesPending = rulesQ.data
      ? rulesQ.data.rules.filter((r) => r.status === 'draft').length : null;
    const canon = 'v2026.1';

    const daysToDue = filing
      ? Math.max(0, Math.round((+new Date(filing.due_date) - Date.now()) / 86400000))
      : null;

    // ── stages ───────────────────────────────────────────────────────────
    const stages: Stage[] = [
      { key: 'rules', n: 1, label: 'Rules', goTo: 'rules', state: 'done',
        detail: rulesTotal != null ? `canon ${canon} · ${rulesTotal} rules` : `canon ${canon}` },
      { key: 'validate', n: 2, label: 'Validate', goTo: 'val',
        state: blockers ? 'blocked' : 'done',
        detail: blockers ? `${blockers.toLocaleString()} blocking` : 'all edits pass' },
      { key: 'resolve', n: 3, label: 'Resolve', goTo: 'amend',
        // The bulletin is the focus only while it clears blockers; otherwise
        // it is pending work that doesn't hold the filing.
        state: !bulletin ? 'done' : (blockers && bulletinClears) ? 'current' : 'waiting',
        detail: bulletin
          ? (bulletinClears ? `bulletin clears ${bulletinClears}` : `bulletin ${bulletin.name} pending`)
          : 'nothing pending' },
      { key: 'signoff', n: 4, label: 'Sign-off', goTo: 'filing',
        state: signed >= 3 ? 'done' : blockers ? 'waiting' : 'current',
        detail: signed >= 3 ? 'officer approved' : signed ? `${signed} of 3 signed`
          : blockers ? 'waits on blockers' : 'ready' },
      { key: 'seal', n: 5, label: 'Seal & send', goTo: 'filing',
        state: sent ? 'done' : signed >= 3 ? 'current' : 'waiting',
        detail: sent ? `sent · ${filing?.channel ?? 'regulator'}` : sealed ? 'sealed · ready to send'
          : signed >= 3 ? 'ready to seal' : 'after sign-off' },
      { key: 'acked', n: 6, label: 'Acknowledged', goTo: 'filing',
        state: acked ? 'done' : 'waiting',
        detail: acked ? (archived ? 'acknowledged · archived' : 'receipt recorded') : 'awaiting receipt' },
    ];
    // The raised stage follows the next action: where the person has to look.
    const current: StageKey = blockers
      ? (bulletin && bulletinClears ? 'resolve' : 'validate')
      : signed < 3 ? 'signoff' : !sent ? 'seal' : 'acked';

    // ── next action ──────────────────────────────────────────────────────
    const chan = filing?.channel ?? 'the regulator';
    let next: NextAction;
    if (blockers) {
      if (bulletin && bulletinClears) {
        next = {
          label: `Review bulletin · clears ${Math.min(bulletinClears, blockers)} of ${blockers}`,
          why: `${bulletin.name} is pending. Applying it changes the rule and clears those exceptions with no manual fix.${blockers > bulletinClears ? ` Then fix the remaining ${blockers - bulletinClears} by hand.` : ''}`,
          goTo: 'amend',
        };
      } else {
        next = {
          label: `Triage ${blockers.toLocaleString()} blocker${blockers === 1 ? '' : 's'}`,
          why: 'No pending bulletin covers these. Each needs a manual fix, an authored remedy, or a suppression memo.',
          goTo: 'val',
        };
      }
    } else if (signed < 3) {
      next = {
        label: signed ? `Continue sign-off · ${3 - signed} left` : 'Start sign-off',
        why: 'All blocking edits pass. Analyst, actuary and officer sign in order; each signature is recorded.',
        goTo: 'filing',
      };
    } else if (!sealed) {
      next = { label: 'Seal package', why: 'Sealing freezes the fixed-width file and records its SHA-256 in the audit log.', goTo: 'filing' };
    } else if (!sent) {
      next = { label: `Send to ${chan}`, why: 'Transmits the sealed package with the sign-off chain attached.', goTo: 'filing' };
    } else if (!acked) {
      next = { label: 'Record acknowledgement', why: 'When the regulator acknowledges, the receipt closes the filing.', goTo: 'filing' };
    } else {
      next = { label: 'View archive', why: 'Nothing left to do on this cycle.', goTo: 'filing' };
    }

    return {
      filing, filings, live, blockers, warnings, daysToDue,
      bulletin, bulletinClears, bulletinRules, bulletinLoading: !!bulletin && impactQ.isPending,
      status, signed, sealed, sent, acked, archived,
      rulesTotal, rulesPending, canon, stages, current, next,
    };
  }, [filing, filings, live, valQ.data, subQ.data, bulletin, impactQ.data, impactQ.isPending, rulesQ.data]);
}
