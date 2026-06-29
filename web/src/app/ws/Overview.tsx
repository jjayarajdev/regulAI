// Overview screen — React port of the workstation dashboard: serif hero with
// computed counts, three KPI cards, active filing rows with sign-off progress,
// recent activity from the audit trail, and the fixed-width wire preview.

import { useApprovalStates, useAudit, useBronzeCancellations, useFilings, useValidate, useValidateAll } from '../../api/hooks';
import { ENGINE_LABEL } from '../../api/client';
import type { FilingStatus } from '../../api/types';

interface OverviewProps {
  activeFilingId: string | null;
  onOpenFiling: (filingId: string) => void;
}

const STATUS_META: Record<FilingStatus, { pct: number; stage: string; step: string }> = {
  draft:            { pct: 15,  stage: 'Drafting',           step: 'step 1 of 5' },
  validating:       { pct: 35,  stage: 'Validating',         step: 'step 2 of 5' },
  validated:        { pct: 55,  stage: 'Resolving blockers', step: 'step 3 of 5' },
  analyst_signed:   { pct: 65,  stage: 'Analyst signed',     step: 'step 4 of 5' },
  actuary_approved: { pct: 80,  stage: 'Actuary approved',   step: 'step 4 of 5' },
  officer_approved: { pct: 90,  stage: 'Awaiting seal',      step: 'step 4 of 5' },
  submitted:        { pct: 100, stage: 'Submitted',          step: 'step 5 of 5' },
  acked:            { pct: 100, stage: 'Acknowledged',       step: 'step 5 of 5' },
};

const ONES = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
  'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen'];
const TENS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety'];

/** Spell 0–99 in words ("forty-seven"); larger numbers fall back to digits. */
function spellNumber(n: number): string {
  if (n < 0 || n > 99) return String(n);
  if (n < 20) return ONES[n];
  return TENS[Math.floor(n / 10)] + (n % 10 ? `-${ONES[n % 10]}` : '');
}
const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const numberWord = (n: number) => (n === 0 ? 'No' : capitalize(spellNumber(n)));

const daysUntil = (isoDate: string) =>
  Math.round((new Date(isoDate + 'T00:00:00').getTime() - Date.now()) / 86_400_000);

const timeAgo = (iso: string) => {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso.replace(' ', 'T')).getTime()) / 60_000));
  if (mins < 60) return `${mins}m ago`;
  if (mins < 60 * 24) return `${Math.round(mins / 60)}h ago`;
  return `${Math.round(mins / (60 * 24))}d ago`;
};

export function Overview({ activeFilingId, onOpenFiling }: OverviewProps) {
  const filingsQ = useFilings();
  const filings = filingsQ.data?.filings ?? [];
  const filingIds = filings.map((f) => f.id);

  const validations = useValidateAll(filingIds);
  const approvals = useApprovalStates(filingIds);
  const activeValQ = useValidate(activeFilingId);
  const auditQ = useAudit(activeFilingId);
  const bronzeQ = useBronzeCancellations(activeFilingId);

  const activeVal = activeValQ.data;

  // ── hero numbers ──────────────────────────────────────────────
  const inFlight = filings.filter((_, i) => {
    const s = approvals[i]?.data?.status;
    return s !== 'submitted' && s !== 'acked';
  }).length;
  const soonest = filings.length
    ? Math.min(...filings.map((f) => daysUntil(f.due_date)))
    : null;

  // ── KPIs (active filing readiness/fines; blockers across all) ─
  const readiness = activeVal
    ? (activeVal.summary.rules_run
        ? Math.round((activeVal.summary.rules_passing / activeVal.summary.rules_run) * 100)
        : 100)
    : null;
  const activeViolations = activeVal?.summary.total_violations ?? null;
  const totalBlockers = validations.reduce(
    (n, q) => n + (q.data?.summary.total_violations ?? 0), 0);
  const loadedCount = validations.filter((q) => q.data).length;

  const valFailed = activeValQ.isError;
  const loadingMeta = 'loading…';

  // ── wire preview: fixed-width sample from bronze rows ─────────
  const violatingPolicies = new Set((activeVal?.violations ?? []).map((v) => v.policy_number));
  const wireRows = (bronzeQ.data?.rows ?? []).slice(0, 6);
  const pad = (s: string, n: number) => (s ?? '').padEnd(n).slice(0, n);

  return (
    <div className="screen screen-dashboard">
      <div className="dash-head">
        <div className="dash-eyebrow">
          {activeFilingId ? `${activeFilingId.split('-').slice(1).join(' ')} · Filing cycle` : 'Filing cycle'}
        </div>
        <h1 className="dash-title">
          {filingsQ.isLoading ? 'Connecting to the canon…' : `${numberWord(inFlight)} filing${inFlight === 1 ? '' : 's'} in flight.`}
          <br />
          {soonest !== null && (
            <>
              <em>{numberWord(soonest)} days</em> to file.
            </>
          )}
        </h1>
        <p className="dash-sub">
          All in-progress submissions, the bulletins waiting to be acknowledged,
          and the records that block submission — from one canon, in one place.
        </p>
      </div>

      <div className="kpis">
        <div className="kpi">
          <div className="kpi-label">Regulator readiness</div>
          <div className="kpi-value num">
            {readiness ?? '—'}<span className="unit">/ 100</span>
          </div>
          <div className="kpi-meta" style={valFailed ? { color: 'var(--warn)' } : undefined}>
            {activeVal
              ? `${activeVal.summary.rules_passing} of ${activeVal.summary.rules_run} rules passing · ${activeVal.summary.rules_failing} failing`
              : valFailed ? `${ENGINE_LABEL} warming up — retry in a moment` : loadingMeta}
          </div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Fines avoided this cycle</div>
          <div className="kpi-value num">
            ${activeViolations !== null ? activeViolations * 25 : '—'}<span className="unit">K</span>
          </div>
          <div className="kpi-meta">
            {activeViolations === null
              ? loadingMeta
              : activeViolations > 0
                ? `${activeViolations} record${activeViolations > 1 ? 's' : ''} caught before submission · $25K/record est.`
                : 'No violations to catch · estimate based on caught-before-submission'}
          </div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Blockers across filings</div>
          <div className="kpi-value num" style={totalBlockers > 0 ? { color: 'var(--bad)' } : undefined}>
            {loadedCount ? totalBlockers : '—'}
          </div>
          <div className="kpi-meta">
            {loadedCount
              ? `across ${loadedCount} of ${filings.length} filings`
              : loadingMeta}
          </div>
        </div>
      </div>

      <div>
        <div className="section-h">
          <h2>Active filings</h2>
          <a className="link">View all</a>
        </div>
        <div className="filing-list">
          {filings.map((f, i) => {
            const ap = approvals[i]?.data;
            const val = validations[i]?.data;
            const meta = ap ? STATUS_META[ap.status] : null;
            const n = val?.summary.total_violations;
            const due = daysUntil(f.due_date);
            return (
              <div key={f.id} className="filing-row" onClick={() => onOpenFiling(f.id)}>
                <div className="fr-name">
                  {f.plan_code} · {f.id.split('-').slice(1).join(' ')}
                  <span className="sub">{f.plan_name}</span>
                </div>
                <div>
                  <div className="progress"><div style={{ width: `${meta?.pct ?? 5}%` }} /></div>
                  <div className="progress-meta">
                    <b>{meta?.stage ?? 'loading…'}</b>
                    <span>{meta?.step ?? ''}</span>
                  </div>
                </div>
                <div>
                  {n === undefined ? (
                    <span className="tag">loading…</span>
                  ) : n > 0 ? (
                    <span className="tag bad">{n} blocker{n > 1 ? 's' : ''}</span>
                  ) : (
                    <span className="tag ok">ready</span>
                  )}
                </div>
                <div className="fr-due num">
                  due in<b>{due} days</b>
                </div>
              </div>
            );
          })}
          {filingsQ.isLoading && (
            <div className="filing-row" style={{ opacity: 0.5, cursor: 'default' }}>
              <div className="fr-name">loading filings…</div><div /><div /><div />
            </div>
          )}
        </div>
      </div>

      <div className="grid-2col">
        <div>
          <div className="section-h">
            <h2>Recent activity</h2>
            <a className="link">View all</a>
          </div>
          <div className="activity">
            {(auditQ.data?.actions ?? []).slice(0, 6).map((a) => (
              <div className="act" key={a.action_id}>
                <div className="act-time">{timeAgo(a.acted_at)}</div>
                <div className="act-msg">
                  <b>{a.summary}</b>
                  <span className="meta">
                    {a.action_type.replace(/_/g, ' ')} · {a.actor}
                    {a.target_record ? ` · ${a.target_record}` : ''}
                  </span>
                </div>
              </div>
            ))}
            {auditQ.data && auditQ.data.actions.length === 0 && (
              <div className="act">
                <div className="act-time">—</div>
                <div className="act-msg" style={{ color: 'var(--ink-3)' }}>No recorded actions for this filing yet.</div>
              </div>
            )}
            {auditQ.isLoading && (
              <div className="act">
                <div className="act-time">loading</div>
                <div className="act-msg" style={{ color: 'var(--ink-3)' }}>connecting to RegulAI…</div>
              </div>
            )}
            {auditQ.isError && (
              <div className="act">
                <div className="act-time">offline</div>
                <div className="act-msg" style={{ color: 'var(--warn)' }}>Cannot reach the audit trail.</div>
              </div>
            )}
          </div>
        </div>

        <div>
          <div className="section-h">
            <h2>Wire preview</h2>
            <span className="tag">section A · draft</span>
          </div>
          <div className="wire-card">
            <div className="wire-body">
              {bronzeQ.isLoading && <span className="ruler">loading sample…</span>}
              {bronzeQ.isError && <span style={{ color: 'var(--warn)' }}>{ENGINE_LABEL} warming up…</span>}
              {bronzeQ.data && (
                <>
                  <span className="ruler">{'POLICY      ACTION        CODE  NOTICE      EFFECTIVE'}</span>
                  {wireRows.map((r) => (
                    <span key={r.policy + r.noticedate} style={{ display: 'block' }}>
                      {pad(r.policy, 12)}
                      {pad(r.action, 14)}
                      {violatingPolicies.has(r.policy)
                        ? <span className="err">{pad(r.reason_code, 4)}</span>
                        : pad(r.reason_code, 4)}
                      {'  '}{pad(r.noticedate, 12)}{pad(r.effectivedate, 10)}
                    </span>
                  ))}
                  {wireRows.length === 0 && <span className="ruler">no records in scope for this filing</span>}
                </>
              )}
            </div>
            <div className="wire-foot">
              <span className="num">{bronzeQ.data ? `${bronzeQ.data.count} records` : '— records'}</span>
              {violatingPolicies.size > 0 && (
                <span style={{ color: 'var(--bad)' }}>{violatingPolicies.size} flagged</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
