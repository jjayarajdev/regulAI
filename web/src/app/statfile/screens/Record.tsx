// TX record inspector — the encoded TSPR submission record, field-by-field
// with provenance, submission package, and reconciliation. Live: navigates the
// policies with open edits (/validate/all), renders each one's
// SILVER.TSPR_PREMIUM_STAGING row (/submission/{policy}); the record image and
// positions are assembled from the encoded field values. Demo record when the
// warehouse is cold.
import { useEffect, useMemo, useState } from 'react';
import { Blueprint } from '../Blueprint';
import {
  can, policiesFrom, useAdvanceFiling, useApprovalState, useFilings, usePipelineContract,
  useReconciliation, useSubmission, useSubmissionPolicies, useValidateAll, whoCan, type AppUser,
} from '../api';
import { PKG, REC_FIELDS, RECON, RECORD_IMAGE } from '../data';

// Provenance for the staging columns the contract endpoint doesn't carry
// (system-populated ones the mapping agent must not touch).
const SRC: Record<string, string> = {
  record_type: 'transform (fixed)',
  stat_plan: 'transform (fixed)',
  validation_status: 'rule engine',
};

// Decode the TSPR-encoded value back to something a human can read. Only the
// deterministic encodings — dates (Rule 8), $1000s amounts, ZIP+4, constants.
const fmtUsd = (v: unknown) => '$' + Number(v).toLocaleString('en-US');
function decode(name: string, v: string | number | null): string {
  if (v == null) return '∅ null';
  const s = String(v);
  switch (name) {
    case 'effective_date':
      return s.length === 5 ? `MMDDY → ${s.slice(0, 2)}/${s.slice(2, 4)} · yr …${s[4]}` : '';
    case 'expiry_date':
      return s.length === 3 ? `MMY → ${s.slice(0, 2)} · yr …${s[2]}` : '';
    case 'amt_insurance_dw': return `Dwelling ${fmtUsd(Number(v) * 1000)}`;
    case 'amt_insurance_pp': return `Contents ${fmtUsd(Number(v) * 1000)}`;
    case 'amt_insurance_alu': return `ALE ${fmtUsd(Number(v) * 1000)}`;
    case 'fire_premium': return `Fire ${fmtUsd(v)}`;
    case 'ec_premium': return `Ext. coverage ${fmtUsd(v)}`;
    case 'deductible_1_amt': return fmtUsd(v);
    case 'zip9': return s.length >= 9 ? `${s.slice(0, 5)}-${s.slice(5)}` : s;
    case 'line_of_business': return s === '1' ? 'Homeowners' : '';
    case 'record_type': return s === '01' ? 'Premium record' : '';
    case 'stat_plan': return s === '4' ? 'TX stat plan' : '';
    case 'number_of_families': return `${s}-family`;
    default: return '';
  }
}

interface FieldRow { pos: string; name: string; val: string; dec: string; src: string; rule: string }

type RecordSet = 'edits' | 'clean' | 'all';

export function RecordScreen({ initialPolicy, user }: { initialPolicy?: string | null; user?: AppUser }) {
  const valQ = useValidateAll();
  const filingsQ = useFilings();
  const withEdits = useMemo(() => policiesFrom(valQ.data), [valQ.data]);

  // Full staged set (scoped to the active filing) → clean = staged − edits.
  const activeFiling = filingsQ.data?.filings.find((f) => f.is_active);
  const allQ = useSubmissionPolicies(activeFiling?.id ?? null);
  const allPolicies = allQ.data?.policies ?? [];
  const editSet = useMemo(() => new Set(withEdits), [withEdits]);
  const clean = useMemo(() => allPolicies.filter((p) => !editSet.has(p)), [allPolicies, editSet]);

  const [mode, setMode] = useState<RecordSet | null>(null);
  // Default: walk the problem records if any exist, else the clean set.
  const effMode: RecordSet = mode ?? (withEdits.length ? 'edits' : 'clean');
  const policies = effMode === 'edits' ? withEdits : effMode === 'clean' ? clean : allPolicies;
  const SET_LABEL: Record<RecordSet, string> = {
    edits: 'with edits', clean: 'clean — ready to submit', all: 'staged',
  };

  const [idx, setIdx] = useState(0);
  // Search overrides the failing-policy picker — any policy is inspectable.
  const [override, setOverride] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  // Deep link from the validation screen's "Trace to Guidewire".
  useEffect(() => {
    if (!initialPolicy) return;
    const i = withEdits.indexOf(initialPolicy);
    if (i >= 0) { setMode('edits'); setIdx(i); setOverride(null); }
    else setOverride(initialPolicy);
  }, [initialPolicy, withEdits]);
  const policy = override ?? (policies.length ? policies[Math.min(idx, policies.length - 1)] : null);
  const subQ = useSubmission(policy);

  const live = !!(policy && subQ.data?.found && subQ.data.fields);

  // Real Bronze→Silver provenance per column, from the same contract endpoint
  // the pipeline screen renders.
  const conQ = usePipelineContract();
  const contractBy = useMemo(() => {
    const m = new Map<string, { source: string | null; rule: string | null }>();
    for (const c of conQ.data?.columns ?? []) {
      m.set(c.name.toLowerCase(), { source: c.source, rule: c.rule });
    }
    return m;
  }, [conQ.data]);

  // Assemble the encoded record image + per-field character positions from
  // the staging row (the SDF layout metadata isn't served yet, so positions
  // are within this assembled image).
  const { image, fields } = useMemo((): { image: string; fields: FieldRow[] } => {
    if (!live) return { image: RECORD_IMAGE, fields: REC_FIELDS };
    const entries = Object.entries(subQ.data!.fields!);
    let cursor = 1;
    const rows: FieldRow[] = entries.map(([name, v]) => {
      const val = v == null ? '·' : String(v).replace(/\s+/g, '');
      const pos = `${cursor}–${cursor + val.length - 1}`;
      cursor += val.length;
      const con = contractBy.get(name);
      return {
        pos, name, val,
        dec: decode(name, v),
        src: con?.source ?? SRC[name] ?? 'SILVER.TSPR_PREMIUM_STAGING',
        rule: con?.rule ?? (name === 'validation_status' ? 'all edits' : '—'),
      };
    });
    return { image: rows.map((r) => r.val).join(''), fields: rows };
  }, [live, subQ.data, contractBy]);

  const violations = useMemo(() => {
    if (!policy || !valQ.data) return [];
    return Object.values(valQ.data.by_filing).flatMap((f) => f.violations)
      .filter((v) => v.policy_number === policy);
  }, [policy, valQ.data]);

  const active = filingsQ.data?.filings.find((f) => f.is_active);
  const approvalQ = useApprovalState(live && active ? active.id : null);
  const adv = useAdvanceFiling();
  const reconQ = useReconciliation(live && active ? active.id : null);
  const pkg = live
    ? [
        { k: 'Cycle', v: active?.id ?? '—' },
        { k: 'Policy', v: policy! },
        { k: 'Open edits', v: String(violations.length) },
        { k: 'Records with edits', v: String(policies.length) },
        { k: 'Staging table', v: 'TSPR_PREMIUM_STAGING' },
        { k: 'Channel', v: active?.channel ?? '—' },
      ]
    : PKG;

  const rulesTotal = valQ.data
    ? Object.values(valQ.data.by_filing)[0]?.summary.rules_run ?? 0
    : 0;
  const passTag = live
    ? violations.length === 0
      ? `Passes ${rulesTotal} of ${rulesTotal} edits`
      : `${violations.length} open edit${violations.length > 1 ? 's' : ''}`
    : 'Passes 214 of 214 edits';

  return (
    <div className="sc">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 }}>
        <span className="k">Record</span>
        <span className="mono" style={{ fontSize: 13 }}>
          {override ? `${override} · via search`
            : policy ? `${policy} · ${idx + 1} of ${policies.length} ${SET_LABEL[effMode]}`
            : 'HO-TX-0048817-02 · seq 000418,229'}
        </span>
        <div className="seg">
          {([['edits', `Edits ${withEdits.length}`], ['clean', `Clean ${clean.length}`], ['all', `All ${allPolicies.length}`]] as Array<[RecordSet, string]>).map(([m, label]) => (
            <label key={m} className="seg-opt">
              <input type="radio" name="rset" checked={effMode === m}
                onChange={() => { setMode(m); setIdx(0); setOverride(null); }} />
              <span>{label}</span>
            </label>
          ))}
        </div>
        <button className="btn btn-secondary" disabled={!policies.length || (!override && idx === 0)}
          onClick={() => { setOverride(null); setIdx((i) => Math.max(0, i - 1)); }}>← Prev</button>
        <button className="btn btn-secondary" disabled={!policies.length || (!override && idx >= policies.length - 1)}
          onClick={() => { setOverride(null); setIdx((i) => Math.min(policies.length - 1, i + 1)); }}>Next →</button>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && search.trim()) { setOverride(search.trim().toUpperCase()); setSearch(''); }
          }}
          placeholder="POL-…  ⏎"
          style={{
            width: 110, padding: '5px 9px', fontSize: 12, fontFamily: 'ui-monospace, Menlo, monospace',
            border: '1px solid var(--color-divider)', borderRadius: 0,
            background: 'transparent', color: 'var(--color-text)',
          }}
        />
        <span className={'tag ' + (live && violations.length ? 'tag-outline' : 'tag-accent')} style={{ marginLeft: 'auto' }}>
          {passTag}
        </span>
      </div>

      <Blueprint style={{ padding: '16px 18px', marginBottom: 26, overflowX: 'auto' }}>
        <div className="k" style={{ marginBottom: 8 }}>
          {live ? `Encoded TSPR record — ${image.length} chars · SILVER.TSPR_PREMIUM_STAGING` : 'Fixed-length record image — 80 bytes'}
        </div>
        <div className="mono" style={{ fontSize: 14, letterSpacing: '.12em', whiteSpace: 'nowrap', color: 'var(--color-accent-900)' }}>
          {subQ.isLoading ? 'loading…' : image}
        </div>
        {policy && subQ.data && !subQ.data.found && (
          <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>{subQ.data.note}</div>
        )}
      </Blueprint>

      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 30, alignItems: 'start' }}>
        <div>
          <h4 style={{ marginBottom: 10 }}>Field-by-field with provenance</h4>
          <table className="table">
            <thead>
              <tr><th>Pos</th><th>Field</th><th>Value</th><th>Decoded</th><th>Source</th><th>Rule</th></tr>
            </thead>
            <tbody>
              {fields.map((f) => (
                <tr key={f.pos + f.name} className="row">
                  <td className="mono" style={{ fontSize: 11, color: 'color-mix(in srgb,var(--color-text) 50%,transparent)' }}>{f.pos}</td>
                  <td style={{ fontSize: 12.5 }}>{f.name}</td>
                  <td className="mono" style={{ fontSize: 12, color: 'var(--color-accent-900)' }}>{f.val}</td>
                  <td style={{ fontSize: 12, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>{f.dec}</td>
                  <td className="mono muted" style={{ fontSize: 10.5 }}>{f.src}</td>
                  <td className="mono" style={{ fontSize: 10.5, color: 'var(--color-accent-700)' }}>{f.rule}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <Blueprint style={{ padding: '16px 18px' }}>
            <div className="k" style={{ marginBottom: 10 }}>Submission package</div>
            {pkg.map((p) => (
              <div key={p.k} style={{ display: 'flex', gap: 10, padding: '6px 0', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)', fontSize: 12.5 }}>
                <span className="muted" style={{ flex: 1 }}>{p.k}</span>
                <span className="mono" style={{ fontSize: 12 }}>{p.v}</span>
              </div>
            ))}
            {(() => {
              const a = approvalQ.data;
              if (!live || !active || !a) {
                return <button className="btn btn-primary btn-block" disabled={live}>Seal &amp; transmit to statistical agent</button>;
              }
              const busy = adv.approve.isPending || adv.seal.isPending || adv.ack.isPending;
              const roleLabel: Record<string, string> = {
                analyst: 'Sign off — Analyst', actuary: 'Sign off — Actuary', officer: 'Sign off — Compliance Officer',
              };
              // Which permission the next action needs, so the button can say
              // exactly who is allowed when the current persona isn't.
              const perm =
                a.status === 'submitted' ? 'ack'
                : a.can_seal ? 'seal'
                : a.next_role ? `sign_${a.next_role === 'officer' ? 'officer' : a.next_role}` : null;
              const allowed = perm == null || can(user, perm);
              const [label, action, disabled]: [string, (() => void) | null, boolean] =
                a.status === 'acked' ? ['Acknowledged by TICO ✓', null, true]
                : a.status === 'submitted' ? ['Record TICO acknowledgment', () => adv.ack.mutate(active.id), busy || !allowed]
                : a.can_seal ? ['Seal & transmit to statistical agent', () => adv.seal.mutate(active.id), busy || !allowed]
                : a.next_role ? [roleLabel[a.next_role], () => adv.approve.mutate({ filingId: active.id, role: a.next_role! }), busy || a.open_blockers > 0 || !allowed]
                : [`Blocked — state '${a.status}'`, null, true];
              return (
                <>
                  <button className="btn btn-primary btn-block" disabled={disabled} onClick={() => action?.()}
                    title={perm != null && !allowed ? `requires ${whoCan(perm)} — you are ${user?.name ?? 'Guest'}` : undefined}>
                    {busy ? 'Working…' : label}
                  </button>
                  {perm != null && !allowed && (
                    <div className="k" style={{ marginTop: 6 }}>requires {whoCan(perm)} — switch persona to act</div>
                  )}
                  <div className="mono" style={{ fontSize: 10.5, marginTop: 7, color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>
                    state {a.status}
                    {a.open_blockers > 0 ? ` · ${a.open_blockers} blocker${a.open_blockers > 1 ? 's' : ''} hold the chain` : ''}
                    {a.acked_at ? ` · acked ${a.acked_at.slice(0, 16)}` : a.submitted_at ? ` · submitted ${a.submitted_at.slice(0, 16)}` : ''}
                  </div>
                  {(adv.approve.error != null || adv.seal.error != null || adv.ack.error != null) && (
                    <div className="k" style={{ marginTop: 6, color: 'var(--color-accent-700)' }}>
                      {[adv.approve.error, adv.seal.error, adv.ack.error]
                        .filter((e): e is Error => e != null).map((e) => e.message).join(' · ')}
                    </div>
                  )}
                </>
              );
            })()}
            <div style={{ fontSize: 11, color: 'color-mix(in srgb,var(--color-text) 52%,transparent)', marginTop: 8, lineHeight: 1.55 }}>
              Sign-off chain: analyst → actuary → compliance officer, each gated on zero open
              blockers. Sealing renders the fixed-width TSPR file and writes the SHA-256-sealed
              submission row to the audit chain.
            </div>
          </Blueprint>
          {live && violations.length > 0 && (
            <Blueprint style={{ padding: '16px 18px' }}>
              <div className="k" style={{ marginBottom: 8 }}>Open edits on this record</div>
              {violations.map((v, i) => (
                <div key={i} style={{ padding: '7px 0', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)' }}>
                  <div className="mono" style={{ fontSize: 11.5, color: 'var(--color-accent-700)' }}>{v.rule_number} · {v.severity}</div>
                  <div style={{ fontSize: 12.5, lineHeight: 1.5 }}>{v.violation_reason}</div>
                </div>
              ))}
            </Blueprint>
          )}
          <Blueprint style={{ padding: '16px 18px' }}>
            <div className="k" style={{ marginBottom: 8 }}>
              Reconciliation to financials
              {live && reconQ.data ? ' — GL tie-out' : reconQ.isLoading ? ' · loading…' : !live ? '' : ' · unavailable'}
            </div>
            {live && reconQ.data ? reconQ.data.lines.map((l) => (
              <div key={l.label} style={{ display: 'flex', gap: 10, padding: '6px 0', fontSize: 12.5, borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)' }}>
                <span className="muted" style={{ flex: 1 }}>{l.label}</span>
                <span className="mono" style={{ fontSize: 12 }}>
                  {l.money ? '$' + Math.round(l.stat).toLocaleString('en-US') : l.stat.toLocaleString('en-US')}
                  {' / '}
                  {l.money ? '$' + Math.round(l.gl).toLocaleString('en-US') : l.gl.toLocaleString('en-US')}
                </span>
                <span className={'tag ' + (l.status === 'Tie' ? 'tag-neutral' : 'tag-accent')}>
                  {l.status === 'Tie' ? 'Tie' : `Δ ${l.money ? '$' : ''}${Math.round(l.delta).toLocaleString('en-US')}`}
                </span>
              </div>
            )) : RECON.map((r) => (
              <div key={r.k} style={{ display: 'flex', gap: 10, padding: '6px 0', fontSize: 12.5, borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)' }}>
                <span className="muted" style={{ flex: 1 }}>{r.k}</span>
                <span className="mono" style={{ fontSize: 12 }}>{r.v}</span>
                <span className={'tag ' + r.tagClass}>{r.d}</span>
              </div>
            ))}
          </Blueprint>
        </div>
      </div>
    </div>
  );
}
