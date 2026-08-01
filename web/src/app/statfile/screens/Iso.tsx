// ISO projection — the same silver layer projected through a second standard:
// TDI ↔ ISO crosswalk, ISO record image, and the gaps the agents flagged.
import { Blueprint } from '../Blueprint';
import { CROSSWALK, ISO_GAPS, ISO_IMAGE } from '../data';

export function IsoScreen() {
  return (
    <div className="sc">
      <Blueprint style={{ padding: '16px 18px', marginBottom: 26, display: 'flex', gap: 26, alignItems: 'center' }}>
        <div style={{ flex: 1 }}>
          <div className="k">Standard</div>
          <div style={{ fontFamily: 'var(--font-heading)', fontSize: 22 }}>ISO Personal Lines Statistical Plan — Homeowners</div>
          <div style={{ fontSize: 12.5, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>
            The same silver layer, projected through a second standard. Nothing upstream is rebuilt — only the mapping and the edit package differ.
          </div>
        </div>
        <div style={{ display: 'flex', gap: 22 }}>
          <div><div className="k">Shared silver columns</div><div style={{ fontFamily: 'var(--font-heading)', fontSize: 28 }}>41 / 47</div></div>
          <div><div className="k">Standard-specific</div><div style={{ fontFamily: 'var(--font-heading)', fontSize: 28 }}>6</div></div>
        </div>
      </Blueprint>

      <h4 style={{ marginBottom: 10 }}>Crosswalk — TDI ↔ ISO</h4>
      <table className="table">
        <thead>
          <tr><th>Silver column</th><th>TDI HO field</th><th>ISO PL field</th><th>Relationship</th><th>Bridge</th></tr>
        </thead>
        <tbody>
          {CROSSWALK.map((c) => (
            <tr key={c.silver} className="row">
              <td className="mono" style={{ fontSize: 12 }}>{c.silver}</td>
              <td className="mono" style={{ fontSize: 12, color: 'color-mix(in srgb,var(--color-text) 68%,transparent)' }}>{c.tdi}</td>
              <td className="mono" style={{ fontSize: 12, color: 'color-mix(in srgb,var(--color-text) 68%,transparent)' }}>{c.iso}</td>
              <td><span className={'tag ' + c.tagClass}>{c.rel}</span></td>
              <td style={{ fontSize: 12, color: 'color-mix(in srgb,var(--color-text) 65%,transparent)' }}>{c.bridge}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 26, marginTop: 30 }}>
        <Blueprint style={{ padding: '16px 18px' }}>
          <div className="k" style={{ marginBottom: 8 }}>ISO record image — same policy, 118 bytes</div>
          <div className="mono" style={{ fontSize: 13, letterSpacing: '.1em', wordBreak: 'break-all', lineHeight: 1.9, color: 'var(--color-accent-900)' }}>
            {ISO_IMAGE}
          </div>
        </Blueprint>
        <Blueprint style={{ padding: '16px 18px' }}>
          <div className="k" style={{ marginBottom: 10 }}>Gaps the agents flagged</div>
          {ISO_GAPS.map((g) => (
            <div key={g.title} style={{ padding: '9px 0', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)' }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <span style={{ width: 7, height: 7, background: g.dot }} />
                <span style={{ fontSize: 13, fontWeight: 500 }}>{g.title}</span>
              </div>
              <div style={{ fontSize: 12, lineHeight: 1.6, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)', marginTop: 3 }}>{g.body}</div>
            </div>
          ))}
        </Blueprint>
      </div>
    </div>
  );
}
