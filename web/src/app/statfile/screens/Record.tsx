// TX record inspector — the encoded TSPR submission record, field-by-field
// with provenance, submission package, and reconciliation. Live: navigates the
// policies with open edits (/validate/all), renders each one's
// SILVER.TSPR_PREMIUM_STAGING row (/submission/{policy}); the record image and
// positions are assembled from the encoded field values. Demo record when the
// warehouse is cold.
import { useMemo, useState } from 'react';
import { Blueprint } from '../Blueprint';
import { policiesFrom, useFilings, useSubmission, useValidateAll } from '../api';
import { PKG, REC_FIELDS, RECON, RECORD_IMAGE } from '../data';

// Bronze/Guidewire provenance for each TSPR staging column — mirrors the
// Bronze→Silver transform in the pipeline.
const SRC: Record<string, string> = {
  naic_company_no: 'GW_PC_POLICYPERIOD.naic_number',
  policy_id: 'GW_PC_POLICY.policynumber',
  record_type: 'transform (fixed)',
  stat_plan: 'transform (fixed)',
  effective_date: 'GW_PC_POLICYPERIOD.startdate',
  expiry_date: 'GW_PC_POLICYPERIOD.enddate',
  amt_insurance_dw: 'GW_PC_COVERAGE.dwelling_limit',
  amt_insurance_pp: 'GW_PC_COVERAGE.contents_limit',
  line_of_business: 'GW_PC_POLICYPERIOD.termtype',
  policy_form: 'GW_PC_POLICYLINE.policyformtype',
  number_of_families: 'GW_PC_DWELLING.families',
  coverage_occupancy: 'GW_PC_DWELLING.occupancy',
  construction: 'GW_PC_DWELLING.construction',
  ppc_simple: 'GW_PC_LOCATION.ppc',
  deductible_1_amt: 'GW_PC_COVERAGE.deductible',
  fire_premium: 'GW_PC_TRANSACTION.amount',
  ec_premium: 'GW_PC_TRANSACTION.amount',
  zip9: 'GW_PC_LOCATION.postalcode',
  validation_status: 'rule engine',
};

interface FieldRow { pos: string; name: string; val: string; dec: string; src: string; rule: string }

export function RecordScreen() {
  const valQ = useValidateAll();
  const filingsQ = useFilings();
  const policies = useMemo(() => policiesFrom(valQ.data), [valQ.data]);

  const [idx, setIdx] = useState(0);
  const policy = policies.length ? policies[Math.min(idx, policies.length - 1)] : null;
  const subQ = useSubmission(policy);

  const live = !!(policy && subQ.data?.found && subQ.data.fields);

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
      return {
        pos, name, val,
        dec: v == null ? '∅ null' : '',
        src: SRC[name] ?? 'SILVER.TSPR_PREMIUM_STAGING',
        rule: name === 'validation_status' ? 'all edits' : '—',
      };
    });
    return { image: rows.map((r) => r.val).join(''), fields: rows };
  }, [live, subQ.data]);

  const violations = useMemo(() => {
    if (!policy || !valQ.data) return [];
    return Object.values(valQ.data.by_filing).flatMap((f) => f.violations)
      .filter((v) => v.policy_number === policy);
  }, [policy, valQ.data]);

  const active = filingsQ.data?.filings.find((f) => f.is_active);
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
          {policy ? `${policy} · ${idx + 1} of ${policies.length} with open edits` : 'HO-TX-0048817-02 · seq 000418,229'}
        </span>
        <button className="btn btn-secondary" disabled={!policies.length || idx === 0}
          onClick={() => setIdx((i) => Math.max(0, i - 1))}>← Prev</button>
        <button className="btn btn-secondary" disabled={!policies.length || idx >= policies.length - 1}
          onClick={() => setIdx((i) => Math.min(policies.length - 1, i + 1))}>Next →</button>
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
            <button className="btn btn-primary btn-block">Seal &amp; transmit to statistical agent</button>
            <div style={{ fontSize: 11, color: 'color-mix(in srgb,var(--color-text) 52%,transparent)', marginTop: 8, lineHeight: 1.55 }}>
              Sealing writes an immutable manifest: rulebook hash, approved-rule set, agent run ids and the gold table snapshot version.
            </div>
          </Blueprint>
          {live && violations.length > 0 ? (
            <Blueprint style={{ padding: '16px 18px' }}>
              <div className="k" style={{ marginBottom: 8 }}>Open edits on this record</div>
              {violations.map((v, i) => (
                <div key={i} style={{ padding: '7px 0', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)' }}>
                  <div className="mono" style={{ fontSize: 11.5, color: 'var(--color-accent-700)' }}>{v.rule_number} · {v.severity}</div>
                  <div style={{ fontSize: 12.5, lineHeight: 1.5 }}>{v.violation_reason}</div>
                </div>
              ))}
            </Blueprint>
          ) : (
            <Blueprint style={{ padding: '16px 18px' }}>
              <div className="k" style={{ marginBottom: 8 }}>Reconciliation to financials</div>
              {RECON.map((r) => (
                <div key={r.k} style={{ display: 'flex', gap: 10, padding: '6px 0', fontSize: 12.5, borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)' }}>
                  <span className="muted" style={{ flex: 1 }}>{r.k}</span>
                  <span className="mono" style={{ fontSize: 12 }}>{r.v}</span>
                  <span className={'tag ' + r.tagClass}>{r.d}</span>
                </div>
              ))}
            </Blueprint>
          )}
        </div>
      </div>
    </div>
  );
}
