import { useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Check, ChevronLeft, Pencil } from 'lucide-react';
import type { FilingAgg } from './ExperienceApp';
import type { ValidateResponse } from '../../api/types';
import { ExpRecord, useApplyBulletin, useAudit, useBronzeFix, usePolicyFields, useSubmission } from './api';

const FIX: Record<string, { field: string; label: string; suggest: string; hint: string }> = {
  'A.34': { field: 'reason_code', label: 'Reason code', suggest: 'LB', hint: "Reason 'L' (credit-score declination) needs a companion — use LB (credit-score + companion) or LD (+ claims history)." },
  'A.10': { field: 'writtenpremium', label: 'Written premium', suggest: '', hint: 'Written premium must be positive — enter the corrected amount.' },
  'A.22': { field: 'noticedate', label: 'Notice date', suggest: '', hint: 'Notice must precede the effective date by the required days (YYYY-MM-DD).' },
};
const ruleBase = (r: ExpRecord) => (r.ruleNumber || '').split(' ')[0];
const fixSpec = (r: ExpRecord) => FIX[ruleBase(r)] || { field: 'reason_code', label: 'Reason code', suggest: '', hint: 'Correct the offending value on the source record.' };
const BULLETIN_RULES = new Set(['A.34']);

const EDITABLE = [
  { key: 'reason_code', label: 'Reason code', ph: 'e.g. L, LB, LD' },
  { key: 'naic_number', label: 'NAIC company #', ph: '5-digit NAIC' },
  { key: 'writtenpremium', label: 'Written premium', ph: 'amount' },
  { key: 'termtype', label: 'Term type', ph: 'Annual / Semi-Annual' },
  { key: 'noticedate', label: 'Notice date', ph: 'YYYY-MM-DD' },
];
const SUB_FIELDS = [
  { k: 'naic_company_no', l: 'NAIC company #' }, { k: 'policy_id', l: 'Policy ID' },
  { k: 'record_type', l: 'Record type' }, { k: 'stat_plan', l: 'Stat plan' },
  { k: 'effective_date', l: 'Effective date', e: 'MMDDY' }, { k: 'expiry_date', l: 'Expiry date', e: 'MMY' },
  { k: 'amt_insurance_dw', l: 'Coverage A', e: '$1000s' }, { k: 'amt_insurance_pp', l: 'Coverage C', e: '$1000s' },
  { k: 'line_of_business', l: 'Line of business', e: 'coded' }, { k: 'policy_form', l: 'Policy form', e: 'coded' },
  { k: 'construction', l: 'Construction', e: 'coded' }, { k: 'ppc_simple', l: 'PPC', e: 'coded' },
  { k: 'deductible_1_amt', l: 'Deductible' }, { k: 'fire_premium', l: 'Fire premium' },
  { k: 'ec_premium', l: 'EC premium' }, { k: 'zip9', l: 'Risk ZIP9' },
];
const STATUS: Record<string, { dot: string; label: string }> = {
  clean: { dot: 'green', label: 'Clean' }, blocked: { dot: 'red', label: 'Blocked' },
  warning: { dot: 'amber', label: 'Warning' }, review: { dot: 'purple', label: 'In Review' },
};

const SevTag = ({ s }: { s: string }) => {
  const col = s === 'ERROR' ? 'var(--exp-red)' : s === 'WARNING' ? 'var(--exp-amber)' : s === 'PASS' ? 'var(--exp-green)' : 'var(--exp-ink-2)';
  const bg = s === 'ERROR' ? 'var(--exp-red-bg)' : s === 'WARNING' ? 'var(--exp-amber-bg)' : s === 'PASS' ? 'var(--exp-green-bg)' : '#eef1f4';
  return <span className="tag" style={{ color: col, background: bg }}>{s}</span>;
};
const Dash = () => <span style={{ color: 'var(--exp-muted-2)' }}>—</span>;
type Msg = { cls: string; text: string } | null;
type Tab = 'details' | 'submission' | 'validation';

export function RecordDetail({ record, agg, stillFailing, bulletinApplied, bulletinId, onBack }: {
  record: ExpRecord; agg?: FilingAgg; stillFailing: boolean;
  bulletinApplied: boolean; bulletinId?: string; onBack: () => void;
}) {
  const r = record;
  const qc = useQueryClient();
  // override drives the record's state right after an action (fix/bulletin),
  // instead of waiting for the parent to recompute stillFailing across all filings.
  const [override, setOverride] = useState<boolean | null>(null); // true=resolved, false=still, null=use prop
  const resolved = override ?? (r.status === 'blocked' && !stillFailing);
  const blocked = r.status === 'blocked' && !resolved;
  const sm = agg?.summary ?? {};
  const spec = fixSpec(r);
  const canBulletin = BULLETIN_RULES.has(ruleBase(r)) && !bulletinApplied;
  const ready = !blocked;

  const policyQ = usePolicyFields(r.id);
  const subQ = useSubmission(r.id);
  const auditQ = useAudit(r.filingId || null);
  const fixMut = useBronzeFix();
  const bulletinMut = useApplyBulletin();

  const [tab, setTab] = useState<Tab>('details');
  const [editKeys, setEditKeys] = useState(false);
  const [editVals, setEditVals] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<Msg>(null);
  const fields = policyQ.data?.fields ?? {};
  const fval = (k: string) => (fields[k] != null ? String(fields[k]) : '');

  const startEdit = () => { setTab('details'); setEditVals(Object.fromEntries(EDITABLE.map((f) => [f.key, fval(f.key)]))); setMsg(null); setEditKeys(true); };

  // After an action, refetch THIS filing's validation and decide the record's
  // fate directly — reliable + fast (one query), no waiting on parent state.
  const settle = async () => {
    if (!r.filingId) return false;
    await qc.refetchQueries({ queryKey: ['exp', 'validate', r.filingId], type: 'active' });
    const data = qc.getQueryData<ValidateResponse>(['exp', 'validate', r.filingId]);
    return (data?.violations ?? []).some((v) => v.policy_number === r.id && v.rule_number === r.ruleNumber);
  };
  const applyFixes = async (changes: { field: string; new_value: string }[], label: string) => {
    setMsg({ cls: 'busy', text: `${label} + re-validating…` });
    try {
      for (const c of changes) await fixMut.mutateAsync({ policy_number: r.id, field: c.field, new_value: c.new_value });
      const still = await settle();
      setEditKeys(false);
      if (r.status === 'blocked') setOverride(!still);
      setMsg(still ? { cls: 'err', text: 'Still failing — check the value.' } : { cls: 'ok', text: '✓ Cleared — ready to file.' });
    } catch (e) { setMsg({ cls: 'err', text: 'Fix failed: ' + (e as Error).message }); }
  };
  const saveKeys = () => {
    const changes = EDITABLE.filter((f) => editVals[f.key] !== fval(f.key)).map((f) => ({ field: f.key, new_value: editVals[f.key] }));
    if (!changes.length) { setEditKeys(false); return; }
    applyFixes(changes, `Applying ${changes.length} change(s) to the source`);
  };
  const applySuggested = () => spec.suggest ? applyFixes([{ field: spec.field, new_value: spec.suggest }], `Setting ${spec.label} → ${spec.suggest}`) : startEdit();
  const applyBulletin = async () => {
    setMsg({ cls: 'busy', text: 'Applying bulletin + re-validating…' });
    try {
      await bulletinMut.mutateAsync();
      const still = await settle();
      if (r.status === 'blocked') setOverride(!still);
      setMsg(still ? { cls: 'err', text: 'Bulletin applied but record still fails.' } : { cls: 'ok', text: '✓ Cleared by bulletin.' });
    } catch (e) { setMsg({ cls: 'err', text: 'Bulletin failed: ' + (e as Error).message }); }
  };

  const st = resolved ? { dot: 'green', label: 'Cleared' } : STATUS[r.status];
  const recActs = (auditQ.data?.actions ?? []).filter((x) => x.target_record === r.id && x.action_type !== 'validation_run').slice(0, 6);

  const TabBtn = ({ id, children }: { id: Tab; children: ReactNode }) => (
    <button className={`rtab ${tab === id ? 'active' : ''}`} onClick={() => setTab(id)}>{children}</button>
  );

  return (
    <>
      <div className="dhead">
        <button className="back" onClick={onBack}><ChevronLeft className="ic" size={16} />Back</button>
        <span className="dh-item">Status <b><span className={`dot ${st.dot}`} /> {blocked ? 'Posting Blocked' : st.label}</b></span>
        <span className="dh-item">Stage <span className="stage-pill">{resolved ? 'Ready' : r.stage}</span></span>
        <span className="dh-item">Assigned to <span className="assignee"><span className="av">DR</span> diana.reyes@lonestar</span></span>
      </div>

      <div className="reason"><span className="lbl">Decision reasoning</span><span className="txt">{r.reasonFull}</span></div>

      {/* contextual action bar — resolution CTAs where they're needed */}
      <div className={`actionbar ${blocked ? 'blocked' : 'ready'}`}>
        {blocked ? <>
          <span className="lbl">Resolve blocker {r.ruleNumber}:</span>
          <button className="btn primary" onClick={applySuggested}>{spec.suggest ? `Apply fix — set ${spec.label} → ${spec.suggest}` : 'Edit & fix'}</button>
          {canBulletin && <button className="btn ghost" onClick={applyBulletin} title={`apply ${bulletinId || 'bulletin'} — clears every A.34 record`}>Apply bulletin{bulletinId ? ` ${bulletinId}` : ''}</button>}
        </> : <>
          <span className="lbl" style={{ color: 'var(--exp-green)' }}>✓ {resolved ? 'Blocker resolved' : 'No blockers'} — ready to file.</span>
          <button className="btn primary" onClick={onBack}><Check className="ic" size={15} />Approve &amp; clear</button>
        </>}
        {msg && <span className="amsg" style={{ color: msg.cls === 'err' ? 'var(--exp-red)' : msg.cls === 'busy' ? 'var(--exp-muted)' : 'var(--exp-green)' }}>{msg.text}</span>}
      </div>

      <div className="dgrid">
        {/* left: tabbed panel */}
        <div>
          <div className="panel">
            <div className="rtabs" style={{ alignItems: 'center' }}>
              <TabBtn id="details">Key details</TabBtn>
              <TabBtn id="submission">Final record{ready ? '' : ' ⚠'}</TabBtn>
              <TabBtn id="validation">Validation</TabBtn>
              <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center', paddingRight: 12 }}>
                {tab === 'details' && (editKeys
                  ? <><button className="btn plain" onClick={() => setEditKeys(false)}>Cancel</button><button className="btn primary" onClick={saveKeys}>Save &amp; re-validate</button></>
                  : <button className="btn ghost" onClick={startEdit}><Pencil className="ic" size={15} />Edit</button>)}
                {tab === 'submission' && <span className="tag" style={{ color: ready ? 'var(--exp-green)' : 'var(--exp-amber)', background: ready ? 'var(--exp-green-bg)' : 'var(--exp-amber-bg)' }}>{ready ? 'ready to file' : 'held'}</span>}
              </div>
            </div>

            {/* ── Key details ── */}
            {tab === 'details' && <>
              {blocked && (
                <div className="fixhint">
                  <span><b>{spec.label}</b> is the offending field{spec.suggest ? <> — set it to <span className="mono">{spec.suggest}</span></> : null}. <span style={{ color: 'var(--exp-muted)' }}>{spec.hint}</span> Use <b>Apply fix</b> above, or <b>Edit</b> to change it manually.</span>
                </div>
              )}
              <div className="ctx"><span><b>Jurisdiction</b>{r.jur}</span><span><b>Carrier</b>{r.carrier}</span><span><b>Plan</b>{r.plan}</span><span><b>Filing</b>{r.filingId || '—'}</span></div>
              <table className="kv"><tbody>
                <tr><td className="k">Record / Policy ID</td><td className="v"><span className="tag">{r.id}</span></td></tr>
                {policyQ.isLoading ? <tr><td className="k">loading…</td><td className="v" /></tr>
                  : EDITABLE.map((f) => (
                    <tr key={f.key} className={editKeys ? 'editing' : ''}>
                      <td className="k">{f.label}</td>
                      <td className="v">{editKeys
                        ? <input value={editVals[f.key] ?? ''} placeholder={f.ph} onChange={(e) => setEditVals({ ...editVals, [f.key]: e.target.value })} />
                        : (fval(f.key) === '' ? <Dash /> : fval(f.key))}</td>
                    </tr>
                  ))}
              </tbody></table>
              <div className="rmsg" style={{ padding: '0 18px 12px' }}>
                {msg ? <span className={`rmsg ${msg.cls}`}>{msg.text}</span> : editKeys ? 'Change any field, then Save — writes to the source record (Bronze) and re-validates.' : ''}
              </div>
              <div className="prov">Editable fields write to the source • re-validates on save</div>
            </>}

            {/* ── Final record (submission) ── */}
            {tab === 'submission' && <>
              <div style={{ padding: '11px 18px', fontSize: 12.5, borderBottom: '1px solid var(--exp-border-2)', borderLeft: `3px solid ${ready ? 'var(--exp-green)' : 'var(--exp-amber)'}`, background: ready ? 'var(--exp-green-bg)' : 'var(--exp-amber-bg)', color: 'var(--exp-ink-2)' }}>
                {ready ? '✓ Clean — this is the encoded record that will be submitted to TICO / TDI.' : 'Held — resolve the blocker(s) before this record can be filed.'}
              </div>
              <table className="kv"><tbody>
                {subQ.isLoading ? <tr><td className="k">loading…</td><td className="v" /></tr>
                  : !subQ.data?.found ? <tr><td className="k" colSpan={2} style={{ color: 'var(--exp-muted)' }}>{subQ.data?.note || 'No submission record yet.'}</td></tr>
                    : SUB_FIELDS.map((f) => {
                      const v = subQ.data!.fields![f.k];
                      return <tr key={f.k}><td className="k">{f.l}{f.e ? <span style={{ color: 'var(--exp-muted-2)', fontWeight: 400 }}> · {f.e}</span> : null}</td><td className="v mono">{v == null || v === '' ? <Dash /> : v}</td></tr>;
                    })}
              </tbody></table>
              {subQ.data?.found && (
                <div className="prov"><span style={{ color: 'var(--exp-muted-2)' }}>wire preview</span>&nbsp; <span className="mono" style={{ color: 'var(--exp-ink-2)' }}>
                  {['stat_plan', 'record_type', 'policy_id', 'effective_date', 'expiry_date', 'amt_insurance_dw', 'line_of_business', 'policy_form', 'construction', 'ppc_simple', 'zip9'].map((k) => subQ.data!.fields![k] ?? '·').join('  ')}
                </span></div>
              )}
            </>}

            {/* ── Validation ── */}
            {tab === 'validation' && <>
              <div className="ctx"><span><b>Rule</b><span className="mono">{r.ruleNumber || '—'}</span></span><span><b>Severity</b>{resolved ? <SevTag s="PASS" /> : <SevTag s={r.severity} />}</span><span><b>Citation</b>{r.citation || '—'}</span></div>
              <table className="kv"><tbody>
                <tr><td className="k">Rule name</td><td className="v">{r.ruleName || '—'}</td></tr>
                <tr><td className="k">Violation reason</td><td className="v">{resolved ? '—' : r.reasonFull.split(' (')[0]}</td></tr>
              </tbody></table>
              <div className="actbox">
                <div className="actline"><span>Rules run (filing)</span><b>{sm.rules_run ?? '—'}</b></div>
                <div className="actline"><span>Rules failing</span><b style={{ color: (sm.rules_failing || 0) ? 'var(--exp-red)' : 'var(--exp-green)' }}>{sm.rules_failing ?? '—'}</b></div>
                <div className="actline"><span>Total violations (filing)</span><b style={{ color: (sm.total_violations || 0) ? 'var(--exp-red)' : 'var(--exp-green)' }}>{sm.total_violations ?? '—'}</b></div>
                <div className="actline"><span>This record</span><b>{resolved ? <SevTag s="PASS" /> : <SevTag s={r.severity} />}</b></div>
              </div>
            </>}
          </div>
        </div>

        {/* right: History */}
        <div>
          <div className="panel">
            <div className="rtabs"><button className="rtab active">History</button><button className="rtab">Bulletins</button><button className="rtab">Email</button></div>
            <div className="hist">
              {recActs.map((x) => (
                <div className="hrow" key={x.action_id}><span className="hdot" style={{ background: 'var(--exp-purple)' }} />
                  <div><div className="ht">{x.summary || x.action_type}</div><div className="hm">{x.actor || 'system'} · {(x.acted_at || '').replace('T', ' ').slice(0, 16)}</div></div></div>
              ))}
              {resolved && <div className="hrow"><span className="hdot" style={{ background: 'var(--exp-green)' }} /><div><div className="ht">Blocker resolved</div><div className="hm">Diana Reyes · just now</div></div></div>}
              <div className="hrow"><span className="hdot" style={{ background: st.dot === 'red' ? 'var(--exp-red)' : st.dot === 'amber' ? 'var(--exp-amber)' : st.dot === 'green' ? 'var(--exp-green)' : 'var(--exp-purple)' }} />
                <div><div className="ht">Flagged by rule <b>{r.ruleNumber || '—'}</b></div><div className="hm">Validation engine · run {agg?.runId || 'current'}</div></div></div>
              <div className="hrow"><span className="hdot" style={{ background: 'var(--exp-purple)' }} /><div><div className="ht">Assigned to Diana Reyes</div><div className="hm">Auto-routing</div></div></div>
              <div className="hrow"><span className="hdot" style={{ background: 'var(--exp-green)' }} /><div><div className="ht">Part of filing <b>{r.filingId || '—'}</b></div><div className="hm">{r.jur} · {r.plan}</div></div></div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
