// TX record inspector — fixed-length record image, field-by-field provenance,
// submission package, and financial reconciliation.
import { Blueprint } from '../Blueprint';
import { PKG, REC_FIELDS, RECON, RECORD_IMAGE } from '../data';

export function RecordScreen() {
  return (
    <div className="sc">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 }}>
        <span className="k">Record</span>
        <span className="mono" style={{ fontSize: 13 }}>HO-TX-0048817-02 · seq 000418,229</span>
        <button className="btn btn-secondary">← Prev</button>
        <button className="btn btn-secondary">Next →</button>
        <span className="tag tag-accent" style={{ marginLeft: 'auto' }}>Passes 214 of 214 edits</span>
      </div>

      <Blueprint style={{ padding: '16px 18px', marginBottom: 26, overflowX: 'auto' }}>
        <div className="k" style={{ marginBottom: 8 }}>Fixed-length record image — 80 bytes</div>
        <div className="mono" style={{ fontSize: 14, letterSpacing: '.12em', whiteSpace: 'nowrap', color: 'var(--color-accent-900)' }}>
          {RECORD_IMAGE}
        </div>
      </Blueprint>

      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 30, alignItems: 'start' }}>
        <div>
          <h4 style={{ marginBottom: 10 }}>Field-by-field with provenance</h4>
          <table className="table">
            <thead>
              <tr><th>Pos</th><th>Field</th><th>Value</th><th>Decoded</th><th>Source</th><th>Rule</th></tr>
            </thead>
            <tbody>
              {REC_FIELDS.map((f) => (
                <tr key={f.pos} className="row">
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
            {PKG.map((p) => (
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
        </div>
      </div>
    </div>
  );
}
