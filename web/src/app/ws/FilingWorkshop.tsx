// Filing workshop — React port of the workstation's filing screen: serif
// header with live rule summary, the sign-off pipeline driven by
// approval-state, A–G section badges that filter the board, the
// severity-bucketed violation kanban, and the filing activity panel.

import { useState } from 'react';
import {
  useApprovalState, useAudit, useBackendState, useBronzeCancellations, useValidate,
} from '../../api/hooks';
import type { ValidateResponse, ValidationRule, Violation } from '../../api/types';

interface FilingWorkshopProps {
  activeFilingId: string | null;
  onBack: () => void;
}

// ── severity bucketing (mirrors violationSeverity in workstation.html) ──
type Bucket = 'high' | 'med' | 'low';
function violationSeverity(vio: Violation, rules: ValidationRule[]): Bucket {
  const r = rules.find((x) => x.rule_id === vio.rule_id);
  const sev = (r?.severity ?? vio.severity ?? 'ERROR').toUpperCase();
  if (sev === 'WARNING' || sev === 'WARN') return 'med';
  if (sev === 'INFO') return 'low';
  return 'high';
}

// Deterministic assignee per policy — same violator, same avatar every render.
const ASSIGNEE_POOL = [
  { id: 'mo', nm: 'M. Okonkwo', role: 'Actuary' },
  { id: 'dr', nm: 'D. Reyes', role: 'VP Compliance' },
  { id: 'jp', nm: 'J. Park', role: 'Officer' },
  { id: 'un', nm: '—', role: 'unassigned' },
];
function assigneeFor(vio: Violation) {
  const pn = vio.policy_number || '';
  const idx = Math.abs([...pn].reduce((a, c) => a + c.charCodeAt(0), 0)) % ASSIGNEE_POOL.length;
  return ASSIGNEE_POOL[idx];
}

// Derive the TSPR section (A–G) for a rule; plain numeric rules live in A.
function sectionForRule(rule: ValidationRule | undefined): string {
  if (!rule) return 'A';
  const num = String(rule.rule_number || '');
  const m1 = num.match(/^([A-G])\.?\d/i);
  if (m1) return m1[1].toUpperCase();
  if (/^\d+$/.test(num)) return 'A';
  const m2 = String(rule.rule_name || '').match(/\b(?:Rule|Section)\s+([A-G])\b/i);
  return m2 ? m2[1].toUpperCase() : 'A';
}

const TSPR_SECTIONS = [
  { id: 'A', label: 'A · General' },
  { id: 'B', label: 'B · Premium' },
  { id: 'C', label: 'C · Premium recs' },
  { id: 'D', label: 'D · Loss recs' },
  { id: 'E', label: 'E · Cancellation' },
  { id: 'F', label: "F · Add'l cancel" },
  { id: 'G', label: 'G · Actual counts' },
];

const PIPELINE_STAGES = [
  { id: 'draft', label: 'Drafted', when: 'auto' },
  { id: 'resolving', label: 'Resolving', when: '' },
  { id: 'validated', label: 'Validated', when: 'analyst sign-off' },
  { id: 'analyst_signed', label: 'Analyst signed', when: 'actuary sign-off' },
  { id: 'actuary_approved', label: 'Actuary approved', when: 'officer sign-off' },
  { id: 'officer_approved', label: 'Officer approved', when: 'ready to seal' },
  { id: 'submitted', label: 'Submitted', when: 'awaiting TICO ACK' },
  { id: 'acked', label: 'TICO ACKed', when: 'chain of custody complete' },
];

export function FilingWorkshop({ activeFilingId, onBack }: FilingWorkshopProps) {
  const [sectionFilter, setSectionFilter] = useState<string | null>(null);

  const valQ = useValidate(activeFilingId);
  const approvalQ = useApprovalState(activeFilingId);
  const bronzeQ = useBronzeCancellations(activeFilingId);
  const auditQ = useAudit(activeFilingId);
  const stQ = useBackendState();

  const v = valQ.data;
  const ap = approvalQ.data;
  const st = stQ.data;
  const bronzeRows = bronzeQ.data?.rows ?? [];

  const reasonCodeFor = (policy: string) =>
    bronzeRows.find((r) => r.policy === policy)?.reason_code ?? '—';

  const vios = v?.summary.total_violations ?? 0;
  const fixable = (v?.violations ?? []).filter((x) => reasonCodeFor(x.policy_number) === 'L').length;
  const manual = (v?.violations ?? []).length - fixable;
  const readiness = v
    ? (v.summary.rules_run ? Math.round((v.summary.rules_passing / v.summary.rules_run) * 100) : 100)
    : null;

  // ── pipeline geometry ─────────────────────────────────────────
  const status = (ap?.status ?? 'draft').toLowerCase();
  const showResolving = vios > 0;
  const visibleStages = PIPELINE_STAGES
    .filter((s) => s.id !== 'resolving' || showResolving)
    .map((s) => (s.id === 'resolving' ? { ...s, when: `${vios} blockers` } : s));
  const visIdx = Math.max(0, visibleStages.findIndex((s) => s.id === status));

  // ── section tallies ───────────────────────────────────────────
  const sectionCounts: Record<string, { rules: number; fails: number; vios: number }> = {};
  for (const r of v?.rules ?? []) {
    const sec = sectionForRule(r);
    const c = sectionCounts[sec] ?? (sectionCounts[sec] = { rules: 0, fails: 0, vios: 0 });
    c.rules += 1;
    if (r.violation_count > 0) c.fails += 1;
    c.vios += r.violation_count || 0;
  }

  // ── kanban buckets ────────────────────────────────────────────
  const buckets: Record<Bucket, { vio: Violation; idx: number }[]> = { high: [], med: [], low: [] };
  (v?.violations ?? []).forEach((vio, i) => {
    if (sectionFilter) {
      const rule = (v?.rules ?? []).find((r) => r.rule_id === vio.rule_id);
      if (sectionForRule(rule) !== sectionFilter) return;
    }
    buckets[violationSeverity(vio, v?.rules ?? [])].push({ vio, idx: i });
  });

  // ── activity items (synthesized like the original) ────────────
  const activity = v
    ? [
        {
          icon: 'sy', label: '!', who: 'Validation engine',
          what: <>re-ran {v.summary.rules_run} rules · <b style={{ color: 'var(--bad)' }}>{v.summary.rules_failing} failing</b> · <b>{v.summary.total_violations}</b> record violations</>,
          when: 'just now',
        },
        ...(v.violations.length
          ? [{
              icon: '', label: v.violations[0].policy_number.replace('POL-', '').slice(0, 2),
              who: v.violations[0].policy_number,
              what: <>flagged by <b>{v.violations[0].rule_number}</b> · {(v.violations[0].violation_reason || '').slice(0, 90)}</>,
              when: 'this run',
            }]
          : []),
        st?.bulletin_applied
          ? { icon: 'kg', label: 'B', who: 'KG canon', what: <>bulletin <b style={{ color: 'var(--accent)' }}>{st.bulletin_id}</b> applied · canon updated</>, when: 'earlier today' }
          : { icon: 'bul', label: 'B', who: 'TDI bulletin', what: <><b>{st?.bulletin_id ?? 'B-2026-Q4-118'}</b> received — affects A.34 L-companion rule</>, when: 'pending' },
        { icon: 'sf', label: 'S', who: 'Snowflake', what: <>Bronze ingest from PolicyCenter · <b>{bronzeRows.length} records</b> · 0 errors</>, when: 'overnight' },
        ...(auditQ.data?.actions ?? []).slice(0, 2).map((a) => ({
          icon: '', label: a.actor.slice(0, 2).toUpperCase(), who: a.actor,
          what: <>{a.summary}</>, when: a.acted_at.slice(5, 16),
        })),
      ]
    : [];

  const columns: { key: Bucket; label: string; empty: string }[] = [
    { key: 'high', label: '● Blocks submission', empty: 'no high-severity blockers' },
    { key: 'med', label: '● Needs review', empty: 'no warnings' },
    { key: 'low', label: '● Informational', empty: 'no informational issues' },
  ];

  return (
    <div className="screen">
      <div className="filing-main">
        <a className="filing-back" onClick={onBack}>← Back to overview</a>
        <div className="fm-head">
          <h1 className="fm-title">Reason-code <em>validation</em></h1>
          <div className="fm-meta">
            {valQ.isLoading && <span style={{ color: 'var(--ink-3)' }}>loading rule summary…</span>}
            {valQ.isError && <span style={{ color: 'var(--warn)' }}>Snowflake unreachable (check IP allowlist)</span>}
            {v && (
              <>
                <span><b>{readiness}/100</b> readiness</span>
                <span className="dot">·</span>
                <span style={{ color: vios > 0 ? 'var(--bad)' : 'var(--good)' }}>
                  {vios} violation{vios !== 1 ? 's' : ''}
                </span>
                <span className="dot">·</span>
                <span><b>{fixable}</b> bulletin-fixable · <b>{manual}</b> manual</span>
                <span className="dot">·</span>
                <span className="num">{bronzeRows.length} bronze records · {activeFilingId}</span>
              </>
            )}
          </div>
        </div>

        {/* sign-off pipeline */}
        <div className="pipeline">
          {visibleStages.map((s, i) => (
            <div key={s.id} className={`pp-step ${i < visIdx ? 'done' : i === visIdx ? 'active' : ''}`}>
              <div className="pp-num">{i < visIdx ? '✓' : <span>{i + 1}</span>}</div>
              <div className="pp-info">
                <div className="pp-name">{s.label}</div>
                <div className="pp-when">{approvalQ.isLoading ? '…' : s.when}</div>
              </div>
            </div>
          ))}
        </div>

        {/* A–G section badges */}
        {v && (
          <div className="section-badges">
            {TSPR_SECTIONS.map((s) => {
              const c = sectionCounts[s.id];
              const cls = `sb ${c ? 'has' : ''} ${c && c.fails > 0 ? 'fail' : ''} ${sectionFilter === s.id ? 'selected' : ''}`;
              return (
                <button
                  key={s.id}
                  className={cls}
                  disabled={!c}
                  onClick={() => setSectionFilter(sectionFilter === s.id ? null : s.id)}
                >
                  <span className="sb-top">
                    <span className="sb-label">{s.label}</span>
                    {c && <span className="sb-vios">{c.vios}v</span>}
                  </span>
                  <span className="sb-tally">
                    {c
                      ? c.fails > 0
                        ? <><span className="n">{c.fails}/{c.rules}</span><span className="lbl">fail</span></>
                        : <><span className="n">{c.rules}</span><span className="lbl">pass</span></>
                      : <span className="lbl">—</span>}
                  </span>
                </button>
              );
            })}
          </div>
        )}
        {sectionFilter && (
          <div style={{ margin: '-6px 0 14px', fontSize: 12, color: 'var(--ink-3)' }}>
            Filtering kanban to Section {sectionFilter}.{' '}
            <button style={{ color: 'var(--accent)', fontSize: 11 }} onClick={() => setSectionFilter(null)}>
              Clear filter
            </button>
          </div>
        )}

        {/* kanban + activity */}
        <div className="filing-kanban-layout">
          <div className="kanban-board">
            {columns.map(({ key, label, empty }) => (
              <div className="k-col" key={key}>
                <div className={`k-col-h ${key}`}>
                  <span>{label}</span>
                  <span className="ct">{buckets[key].length}</span>
                </div>
                <div className="k-body">
                  {valQ.isLoading && <div className="k-empty">loading…</div>}
                  {!valQ.isLoading && buckets[key].length === 0 && <div className="k-empty">{empty}</div>}
                  {buckets[key].map(({ vio, idx }) => {
                    const code = reasonCodeFor(vio.policy_number);
                    const ass = assigneeFor(vio);
                    const isFix = code === 'L';
                    return (
                      <div className="ticket" key={`${vio.rule_id}-${vio.record_id}`}>
                        <div className="ticket-head">
                          <span className="ticket-id">FILE-{String(1140 + idx).padStart(4, '0')}</span>
                          <span>{vio.policy_number}</span>
                        </div>
                        <div className="ticket-title">{vio.rule_name.replace(/^Rule\s+/, '')}</div>
                        <div className="ticket-reason">{vio.violation_reason}</div>
                        <div className="ticket-pills">
                          <span className="ticket-pill code">{code}</span>
                          <span className="ticket-pill">{vio.rule_number}</span>
                          {isFix && <span className="ticket-pill fix">bulletin-fixable</span>}
                        </div>
                        <div className="ticket-foot">
                          <div className={`ticket-assignee ${ass.id}`} title={`${ass.nm} · ${ass.role}`}>
                            {ass.id === 'un' ? '?' : ass.id.toUpperCase()}
                          </div>
                          {isFix
                            ? <button className="ticket-action fix-bul" title="Mutation endpoints land with live mode">Apply bulletin</button>
                            : <button className="ticket-action ghost" title="Mutation endpoints land with live mode">Fix manually →</button>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          <aside className="kanban-activity">
            <div className="ka-head">Filing activity</div>
            {activity.map((i, n) => (
              <div className="ka-row" key={n}>
                <div className={`icon ${i.icon}`}>{i.label}</div>
                <div>
                  <span className="who">{i.who}</span> <span className="what">{i.what}</span>
                  <span className="when">{i.when}</span>
                </div>
              </div>
            ))}
            {!v && (
              <div className="ka-row">
                <div className="icon sy">…</div>
                <div><span className="who">{valQ.isError ? 'offline' : 'Loading…'}</span></div>
              </div>
            )}
          </aside>
        </div>
      </div>
    </div>
  );
}
