// Validation triage — severity facets, edit-exception table, and the selected
// error's why/rule/sample detail panel. Live: /validate/all grouped by rule;
// the sample panel pulls the first failing policy's bronze fields.
import { useMemo, useState } from 'react';
import { Blueprint } from '../Blueprint';
import { DetailModal } from '../DetailModal';
import {
  can, groupViolations, useApplyFix, useAssign, useBronzeFix, useClaims,
  useFilings, usePolicyFields, useReasonCodes, useSuppress, useUnsuppress,
  useValidateAll, whoCan, type AppUser, type GroupedError,
} from '../api';
import { ApiError } from '../../../api/client';
import { ACC, ACC9, ERR_DETAIL, NEU } from '../data';

const sevDot = (s: number) => (s === 2 ? ACC9 : s === 1 ? ACC : NEU);
const fmt = (n: number) => n.toLocaleString('en-US');

export function ValidationScreen({ onTrace, user }: { onTrace?: (policy: string) => void; user?: AppUser }) {
  const maySuppress = can(user, 'suppress');
  const mayFix = can(user, 'fix');
  const mayAssign = can(user, 'assign');
  const valQ = useValidateAll();
  const errors = useMemo(() => groupViolations(valQ.data), [valQ.data]);
  const live = errors.some((e) => e.violations.length > 0);

  const [sev, setSev] = useState('all');
  const [errCode, setErrCode] = useState<string | null>(null);
  const fixMut = useApplyFix();
  const suppressMut = useSuppress();
  const unsuppressMut = useUnsuppress();
  const assignMut = useAssign();
  // Inline forms for suppress-memo / assignee entry.
  const [form, setForm] = useState<'suppress' | 'assign' | null>(null);
  const [memo, setMemo] = useState('');
  const [assignee, setAssignee] = useState('');
  const pickError = (code: string) => {
    setErrCode(code); setForm(null);
    fixMut.reset(); suppressMut.reset(); unsuppressMut.reset(); assignMut.reset();
  };

  const shown = errors.filter((e) =>
    sev === 'all' ? true : sev === 'sup' ? !!e.suppressed : String(e.sev) === sev && !e.suppressed);
  const E: GroupedError = errors.find((e) => e.code === errCode) ?? errors[0];
  const demo = !live ? ERR_DETAIL[E?.code] ?? ERR_DETAIL['TX-E118'] : null;

  const firstViolation = E?.violations[0];
  const policyQ = usePolicyFields(firstViolation?.policy_number ?? null);

  // Claim context when the rule targets claims (record_id CLM-…).
  const filingsQ = useFilings();
  const activeF = filingsQ.data?.filings.find((f) => f.is_active);
  const isClaimRule = !!firstViolation?.record_id?.startsWith('CLM-');
  const claimsQ = useClaims(isClaimRule ? activeF?.id ?? null : null);
  const claim = isClaimRule
    ? (claimsQ.data?.rows ?? []).find((c) => c.claim_number === firstViolation!.record_id)
    : undefined;

  // Inline record editor: which field is being edited + its draft value.
  const bronzeFix = useBronzeFix();
  // Legal companion pairings for the reason-code editor, from the canon-derived
  // reference map (e.g. LD = 'Credit score + claims history').
  const reasonCodesQ = useReasonCodes();
  const currentReason = String(policyQ.data?.fields?.reason_code ?? '');
  const reasonRecs = (reasonCodesQ.data?.rows ?? [])
    .filter((r) => currentReason
      && r.tspr_reason_code !== currentReason
      && r.tspr_reason_code.startsWith(currentReason)
      && !r.credit_score_companion_required)
    .slice(0, 4);
  const [editField, setEditField] = useState<string | null>(null);
  const [editVal, setEditVal] = useState('');
  const EDITABLE = new Set(['reason_code', 'naic_number', 'writtenpremium', 'termtype', 'noticedate', 'reporteddate', 'lossdate']);
  // Which field each rule actually fires on — the one to edit.
  const CULPRIT: Record<string, string[]> = {
    'A.34': ['reason_code'], 'A.10': ['writtenpremium'], 'A.22': ['noticedate'], 'B.10': ['reporteddate'],
  };
  const culprits = new Set(CULPRIT[E?.code ?? ''] ?? []);
  // Prefill a sensible correction when opening the editor on the culprit.
  const suggest = (field: string, current: string): string => {
    if (field === 'reason_code' && current === 'L') return 'LD';
    if (field === 'writtenpremium' && Number(current) <= 0) return String(Math.abs(Number(current)) || 1500);
    if (field === 'reporteddate' && claim?.loss_date) {
      const d = new Date(claim.loss_date); d.setDate(d.getDate() + 45);
      return d.toISOString().slice(0, 10);
    }
    return current;
  };
  const CLAIM_FIELDS = new Set(['reporteddate', 'lossdate']);
  const saveEdit = (field: string) => {
    const body = CLAIM_FIELDS.has(field)
      ? { record_id: firstViolation!.record_id, field, new_value: editVal.trim() }
      : { policy_number: firstViolation!.policy_number, field, new_value: editVal.trim() };
    bronzeFix.mutate(body, { onSuccess: () => setEditField(null) });
  };

  const size = (e: GroupedError) => e.violations.length || parseInt(e.count.replace(/,/g, '')) || 0;
  const activeErrors = errors.filter((e) => !e.suppressed);
  const counts = {
    all: activeErrors.reduce((n, e) => n + size(e), 0),
    2: activeErrors.filter((e) => e.sev === 2).reduce((n, e) => n + size(e), 0),
    1: activeErrors.filter((e) => e.sev === 1).reduce((n, e) => n + size(e), 0),
    0: activeErrors.filter((e) => e.sev === 0).reduce((n, e) => n + size(e), 0),
    sup: errors.filter((e) => e.suppressed).reduce((n, e) => n + size(e), 0),
  };
  const facets = [
    { name: 'All', count: fmt(counts.all), dot: NEU, sev: 'all' },
    { name: 'Blocking', count: fmt(counts[2]), dot: ACC9, sev: '2' },
    { name: 'Warn', count: fmt(counts[1]), dot: ACC, sev: '1' },
    { name: 'Info', count: fmt(counts[0]), dot: NEU, sev: '0' },
    ...(counts.sup > 0 ? [{ name: 'Suppressed', count: fmt(counts.sup), dot: NEU, sev: 'sup' }] : []),
  ];

  // Sample failing record: live bronze fields when we have them, else the
  // design's demo sample for the selected code.
  const sample: Array<[string, string, 0 | 1]> = firstViolation
    ? [
        ['policy_number', firstViolation.policy_number, 0],
        ['record_id', firstViolation.record_id, 0],
        ...Object.entries(policyQ.data?.fields ?? {})
          .slice(0, 5)
          .map(([k, v]) => [k, String(v ?? '∅'), 0] as [string, string, 0 | 1]),
        ...(claim ? [
          ['lossdate', claim.loss_date ?? '∅', 0],
          ['reporteddate', claim.reported_date ?? '∅', 1],
          ['reporting_lag_days', String(claim.reporting_lag_days ?? '—'), 1],
        ] as Array<[string, string, 0 | 1]> : []),
      ]
    : demo?.sample ?? [];

  return (
    <div className="sc" style={{ display: 'grid', gridTemplateColumns: '212px 1fr', gap: 28, alignItems: 'start' }}>
      <aside style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div>
          <div className="k" style={{ marginBottom: 8 }}>Severity</div>
          {facets.map((f) => (
            <button
              key={f.sev}
              onClick={() => setSev(f.sev)}
              style={{
                display: 'flex', width: '100%', alignItems: 'center', gap: 8,
                background: sev === f.sev ? 'color-mix(in srgb,#5980a6 12%,transparent)' : 'transparent',
                border: '1px solid var(--color-divider)', borderRadius: 0,
                padding: '7px 10px', marginBottom: 6, cursor: 'pointer',
                fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--color-text)',
              }}
            >
              <span style={{ width: 8, height: 8, background: f.dot }} />
              <span>{f.name}</span>
              <span className="mono" style={{ marginLeft: 'auto', fontSize: 11.5, opacity: 0.6 }}>{f.count}</span>
            </button>
          ))}
        </div>
        <div>
          <div className="k" style={{ marginBottom: 8 }}>Blocking submission</div>
          <Blueprint style={{ padding: '12px 13px' }}>
            <div style={{ fontFamily: 'var(--font-heading)', fontSize: 31, lineHeight: 1 }}>{fmt(counts[2])}</div>
            <div style={{ fontSize: 11.5, color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>
              records held from the package until cleared
            </div>
          </Blueprint>
        </div>
      </aside>

      <section>
        <table className="table">
          <thead>
            <tr><th>Sev</th><th>Edit</th><th>Field</th><th>Description</th><th>Records</th><th>Origin</th><th /></tr>
          </thead>
          <tbody>
            {shown.map((e) => (
              <tr key={e.code} className="row rowlink" onClick={() => pickError(e.code)}>
                <td><span style={{ display: 'inline-block', width: 8, height: 8, background: sevDot(e.sev) }} /></td>
                <td className="mono" style={{ fontSize: 11.5, color: 'var(--color-accent-700)' }}>{e.code}</td>
                <td className="mono" style={{ fontSize: 11.5 }}>{e.field}</td>
                <td style={{ fontSize: 12.5 }}>{e.desc}</td>
                <td className="mono" style={{ fontSize: 12, textAlign: 'right' }}>{e.count}</td>
                <td style={{ fontSize: 11.5, color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>{e.origin}</td>
                <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                  {e.assignee && <span className="tag tag-outline" style={{ marginRight: 5 }}>{e.assignee}</span>}
                  <span className={'tag ' + (e.suppressed ? 'tag-neutral' : e.sev === 2 ? 'tag-accent' : e.sev === 1 ? 'tag-outline' : 'tag-neutral')}
                    style={e.suppressed ? { opacity: 0.65 } : undefined}>
                    {e.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Row click → the edit's full detail + actions in a modal, right
            where the user clicked (it used to render below the fold). */}
        <DetailModal
          open={!!E && errCode !== null}
          onClose={() => setErrCode(null)}
          width={920}
          kicker={E ? `edit ${E.code} · ${E.origin}` : undefined}
          title={E?.field ?? ''}
          tags={E && (
            <>
              {E.assignee && <span className="tag tag-outline">assigned · {E.assignee}</span>}
              <span className="tag tag-outline">{E.count} records</span>
              <span className={'tag ' + (E.suppressed ? 'tag-neutral' : E.sev === 2 ? 'tag-accent' : 'tag-outline')}>
                {E.status}
              </span>
            </>
          )}
        >
          {E && (
          <>
            {E.suppressed && E.memo && (
              <div style={{ fontSize: 12.5, lineHeight: 1.6, padding: '9px 12px', marginBottom: 12, background: 'color-mix(in srgb,var(--color-text) 5%,transparent)', borderLeft: '2px solid var(--color-neutral-500, #999)' }}>
                <span className="k" style={{ marginRight: 8 }}>Suppressed</span>{E.memo}
              </div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
              <div>
                <div className="k" style={{ marginBottom: 7 }}>Why it fired</div>
                <div style={{ fontSize: 13, lineHeight: 1.65, marginBottom: 12 }}>{demo ? demo.why : E.desc}</div>
                <div className="k" style={{ marginBottom: 7 }}>Rule &amp; citation</div>
                <div className="mono" style={{ fontSize: 11.5, padding: '9px 11px', background: 'color-mix(in srgb,var(--color-text) 5%,transparent)', lineHeight: 1.65, whiteSpace: 'pre-wrap' }}>
                  {demo ? demo.rule : `${E.code} · ${E.field}\n${E.origin}`}
                </div>
              </div>
              <div>
                <div className="k" style={{ marginBottom: 7 }}>Sample failing record</div>
                <div className="mono" style={{ fontSize: 11.5, lineHeight: 1.9 }}>
                  {sample.map(([k, v, bad]) => {
                    const hot = culprits.has(k);
                    return (
                    <div key={k} style={{
                      display: 'flex', gap: 10, alignItems: 'center',
                      borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)',
                      ...(hot ? {
                        background: 'color-mix(in srgb,var(--color-accent) 9%,transparent)',
                        borderLeft: '3px solid ' + ACC9, paddingLeft: 7, marginLeft: -10,
                      } : {}),
                    }}>
                      <span className="muted" style={{ width: 150, flex: 'none', fontWeight: hot ? 600 : undefined }}>{k}</span>
                      {editField === k ? (
                        <>
                          {k === 'reason_code' && reasonRecs.length > 0 && (
                            <span style={{ display: 'flex', gap: 5, flex: 'none' }}>
                              {reasonRecs.map((r) => (
                                <button key={r.tspr_reason_code}
                                  className={'tag ' + (editVal === r.tspr_reason_code ? 'tag-accent' : 'tag-outline')}
                                  style={{ cursor: 'pointer', border: 'none' }}
                                  title={r.description}
                                  onClick={() => setEditVal(r.tspr_reason_code)}>
                                  {r.tspr_reason_code}
                                </button>
                              ))}
                            </span>
                          )}
                          <input
                            value={editVal} autoFocus
                            onChange={(e) => setEditVal(e.target.value)}
                            onKeyDown={(e) => { if (e.key === 'Enter') saveEdit(k); if (e.key === 'Escape') setEditField(null); }}
                            style={{ flex: 1, padding: '2px 6px', fontSize: 11.5, fontFamily: 'inherit', border: '1px solid var(--color-accent)', borderRadius: 0, background: 'transparent', color: 'var(--color-text)' }}
                          />
                          <button className="btn btn-primary" disabled={bronzeFix.isPending} style={{ padding: '2px 8px', fontSize: 11 }}
                            onClick={() => saveEdit(k)}>{bronzeFix.isPending ? '…' : 'Save'}</button>
                          <button className="btn btn-secondary" style={{ padding: '2px 8px', fontSize: 11 }}
                            onClick={() => setEditField(null)}>✕</button>
                        </>
                      ) : (
                        <>
                          <span style={{ color: bad ? ACC9 : 'inherit', overflowWrap: 'anywhere', flex: 1 }}>{v}</span>
                          {hot && live && mayFix && (
                            <button className="btn btn-primary" style={{ padding: '1px 8px', fontSize: 10.5 }}
                              onClick={() => { setEditField(k); setEditVal(suggest(k, v === '∅' ? '' : v)); }}
                              title={`this is the field ${E.code} fires on — suggested correction prefilled`}>
                              fix here
                            </button>
                          )}
                          {!hot && live && mayFix && EDITABLE.has(k) && (
                            <button
                              onClick={() => { setEditField(k); setEditVal(v === '∅' ? '' : v); }}
                              title={`edit ${k} in Bronze (CDC correction)`}
                              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 11, color: 'var(--color-accent-700)', padding: 0 }}
                            >✎</button>
                          )}
                        </>
                      )}
                    </div>
                  ); })}
                  {bronzeFix.isSuccess && (
                    <div className="k" style={{ marginTop: 6, color: 'var(--color-accent-700)' }}>
                      saved to Bronze ✓ — revalidating (the group updates when the edit engine finishes, ~30s)
                    </div>
                  )}
                  {bronzeFix.error != null && (
                    <div className="k" style={{ marginTop: 6, color: 'var(--color-accent-700)' }}>
                      {(bronzeFix.error as Error).message}
                    </div>
                  )}
                  {firstViolation && policyQ.isLoading && (
                    <div className="muted" style={{ padding: '4px 0' }}>loading bronze fields…</div>
                  )}
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 16, paddingTop: 13, borderTop: '1px solid var(--color-divider)', alignItems: 'center' }}>
              <button className="btn btn-secondary" disabled={!firstViolation}
                onClick={() => firstViolation && onTrace?.(firstViolation.policy_number)}>
                Trace to Guidewire
              </button>
              {E.suppressed ? (
                <button className="btn btn-secondary" disabled={!live || !maySuppress || unsuppressMut.isPending}
                  title={maySuppress ? undefined : `requires ${whoCan('suppress')}`}
                  onClick={() => unsuppressMut.mutate(E.code)}>
                  {unsuppressMut.isPending ? 'Releasing…' : 'Unsuppress'}
                </button>
              ) : (
                <button className="btn btn-secondary" disabled={!live || !maySuppress}
                  title={maySuppress ? undefined : `requires ${whoCan('suppress')}`}
                  onClick={() => { setForm(form === 'suppress' ? null : 'suppress'); setMemo(''); }}>
                  Suppress with memo
                </button>
              )}
              <button className="btn btn-secondary" disabled={!live || !mayAssign}
                title={mayAssign ? undefined : `requires ${whoCan('assign')}`}
                onClick={() => { setForm(form === 'assign' ? null : 'assign'); setAssignee(E.assignee ?? ''); }}>
                {E.assignee ? 'Reassign' : 'Assign'}
              </button>
              {fixMut.data && (
                <span className="k" style={{ marginLeft: 'auto' }}>
                  {fixMut.data.fixed.length} fixed · {fixMut.data.skipped.length} skipped — revalidating
                </span>
              )}
              {fixMut.error != null && (
                <span className="k" style={{ marginLeft: 'auto', color: 'var(--color-accent-700)' }}>
                  {fixMut.error instanceof ApiError ? fixMut.error.message : 'fix failed'}
                </span>
              )}
              <button
                className="btn btn-primary"
                style={{ marginLeft: fixMut.data || fixMut.error != null ? undefined : 'auto' }}
                disabled={!live || !mayFix || fixMut.isPending}
                title={mayFix ? undefined : `requires ${whoCan('fix')}`}
                onClick={() => fixMut.mutate(E.code)}
              >
                {fixMut.isPending ? 'Applying fix…' : `Apply agent fix to ${E.count}`}
              </button>
            </div>

            {form === 'suppress' && (
              <div style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'flex-start' }}>
                <textarea
                  value={memo}
                  onChange={(e) => setMemo(e.target.value)}
                  placeholder={`Why is ${E.code} being suppressed? (required — lands in the audit trail)`}
                  rows={2}
                  style={{
                    flex: 1, padding: '8px 10px', fontSize: 12.5, fontFamily: 'var(--font-body)',
                    border: '1px solid var(--color-divider)', borderRadius: 0,
                    background: 'transparent', color: 'var(--color-text)', resize: 'vertical',
                  }}
                />
                <button className="btn btn-primary" disabled={memo.trim().length < 5 || suppressMut.isPending}
                  onClick={() => suppressMut.mutate({ ruleNumber: E.code, memo: memo.trim() }, { onSuccess: () => setForm(null) })}>
                  {suppressMut.isPending ? 'Suppressing…' : 'Suppress'}
                </button>
              </div>
            )}
            {form === 'assign' && (
              <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <input
                  value={assignee}
                  onChange={(e) => setAssignee(e.target.value)}
                  placeholder="Assignee (empty to unassign)"
                  style={{
                    flex: 1, padding: '7px 10px', fontSize: 12.5, fontFamily: 'var(--font-body)',
                    border: '1px solid var(--color-divider)', borderRadius: 0,
                    background: 'transparent', color: 'var(--color-text)',
                  }}
                />
                <button className="btn btn-primary" disabled={assignMut.isPending}
                  onClick={() => assignMut.mutate({ ruleNumber: E.code, assignee: assignee.trim() }, { onSuccess: () => setForm(null) })}>
                  {assignMut.isPending ? 'Saving…' : assignee.trim() ? 'Assign' : 'Unassign'}
                </button>
              </div>
            )}
            {(suppressMut.error != null || assignMut.error != null || unsuppressMut.error != null) && (
              <div className="k" style={{ marginTop: 8, color: 'var(--color-accent-700)' }}>
                {[suppressMut.error, assignMut.error, unsuppressMut.error]
                  .filter((e): e is ApiError => e instanceof ApiError).map((e) => e.message).join(' · ') || 'action failed'}
              </div>
            )}
          </>
          )}
        </DetailModal>
      </section>
    </div>
  );
}
