// Validation triage — severity facets, edit-exception table, and the selected
// error's why/rule/sample detail panel.
import { useState } from 'react';
import { Blueprint } from '../Blueprint';
import { ACC, ACC9, ERR_DETAIL, ERRORS, NEU } from '../data';

const sevDot = (s: number) => (s === 2 ? ACC9 : s === 1 ? ACC : NEU);

const FACETS = [
  { name: 'All', count: '3,412', dot: NEU, sev: 'all' },
  { name: 'Blocking', count: '1,847', dot: ACC9, sev: '2' },
  { name: 'Warn', count: '500', dot: ACC, sev: '1' },
  { name: 'Info', count: '1,959', dot: NEU, sev: '0' },
];

export function ValidationScreen() {
  const [sev, setSev] = useState('all');
  const [err, setErr] = useState(0);

  const shown = ERRORS.filter((e) => (sev === 'all' ? true : String(e.sev) === sev));
  const E = ERRORS[err] ?? ERRORS[0];
  const D = ERR_DETAIL[E.code] ?? ERR_DETAIL['TX-E118'];

  return (
    <div className="sc" style={{ display: 'grid', gridTemplateColumns: '212px 1fr', gap: 28, alignItems: 'start' }}>
      <aside style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div>
          <div className="k" style={{ marginBottom: 8 }}>Severity</div>
          {FACETS.map((f) => (
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
            <div style={{ fontFamily: 'var(--font-heading)', fontSize: 31, lineHeight: 1 }}>1,847</div>
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
              <tr key={e.code} className="row" style={{ cursor: 'pointer' }} onClick={() => setErr(ERRORS.indexOf(e))}>
                <td><span style={{ display: 'inline-block', width: 8, height: 8, background: sevDot(e.sev) }} /></td>
                <td className="mono" style={{ fontSize: 11.5, color: 'var(--color-accent-700)' }}>{e.code}</td>
                <td className="mono" style={{ fontSize: 11.5 }}>{e.field}</td>
                <td style={{ fontSize: 12.5 }}>{e.desc}</td>
                <td className="mono" style={{ fontSize: 12, textAlign: 'right' }}>{e.count}</td>
                <td style={{ fontSize: 11.5, color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>{e.origin}</td>
                <td style={{ textAlign: 'right' }}>
                  <span className={'tag ' + (e.sev === 2 ? 'tag-accent' : e.sev === 1 ? 'tag-outline' : 'tag-neutral')}>{e.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <Blueprint style={{ marginTop: 26, padding: '18px 20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <span className="mono" style={{ fontSize: 12, color: 'var(--color-accent-700)' }}>{E.code}</span>
            <h4>{E.desc}</h4>
            <span className="tag tag-outline" style={{ marginLeft: 'auto' }}>{E.count} records</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
            <div>
              <div className="k" style={{ marginBottom: 7 }}>Why it fired</div>
              <div style={{ fontSize: 13, lineHeight: 1.65, marginBottom: 12 }}>{D.why}</div>
              <div className="k" style={{ marginBottom: 7 }}>Rule &amp; citation</div>
              <div className="mono" style={{ fontSize: 11.5, padding: '9px 11px', background: 'color-mix(in srgb,var(--color-text) 5%,transparent)', lineHeight: 1.65, whiteSpace: 'pre-wrap' }}>
                {D.rule}
              </div>
            </div>
            <div>
              <div className="k" style={{ marginBottom: 7 }}>Sample failing record</div>
              <div className="mono" style={{ fontSize: 11.5, lineHeight: 1.9 }}>
                {D.sample.map(([k, v, bad]) => (
                  <div key={k} style={{ display: 'flex', gap: 10, borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)' }}>
                    <span className="muted" style={{ width: 150 }}>{k}</span>
                    <span style={{ color: bad ? ACC9 : 'inherit' }}>{v}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 16, paddingTop: 13, borderTop: '1px solid var(--color-divider)' }}>
            <button className="btn btn-secondary">Trace to Guidewire</button>
            <button className="btn btn-secondary">Suppress with memo</button>
            <button className="btn btn-secondary">Assign</button>
            <button className="btn btn-primary" style={{ marginLeft: 'auto' }}>Apply agent fix to {E.count}</button>
          </div>
        </Blueprint>
      </section>
    </div>
  );
}
