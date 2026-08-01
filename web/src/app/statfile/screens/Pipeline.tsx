// Medallion pipeline — Bronze/Silver/Gold layer cards + the Gold
// transformation contract table. Live: /catalog for the layer cards (tables,
// row counts, last-altered); the contract table stays design demo content
// until a mapping endpoint exists.
import { Blueprint } from '../Blueprint';
import { medallionFrom, useCatalog } from '../api';
import { ACC, CONTRACT } from '../data';

export function PipelineScreen() {
  const catQ = useCatalog();
  const medallion = medallionFrom(catQ.data?.schemas);

  return (
    <div className="sc">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 22 }}>
        {medallion.map((m) => (
          <Blueprint key={m.name} style={{ padding: '18px 20px' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
              <div style={{ fontFamily: 'var(--font-heading)', fontSize: 26 }}>{m.name}</div>
              <span className={'tag ' + m.tagClass}>{m.status}</span>
            </div>
            <div style={{ fontSize: 12.5, lineHeight: 1.6, color: 'color-mix(in srgb,var(--color-text) 65%,transparent)', margin: '6px 0 14px' }}>{m.desc}</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {m.tables.map(([name, rows]) => (
                <div key={name} className="row" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 8px', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 8%,transparent)' }}>
                  <span className="mono" style={{ fontSize: 11.5, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</span>
                  <span className="mono muted" style={{ fontSize: 11 }}>{rows}</span>
                  <span style={{ width: 7, height: 7, background: m.status === 'Fresh' ? ACC : '#94bce3' }} />
                </div>
              ))}
            </div>
            <div style={{ marginTop: 14, display: 'flex', gap: 16 }}>
              <div><div className="k">Tables</div><div className="mono" style={{ fontSize: 13 }}>{m.latency}</div></div>
              <div><div className="k">Last altered</div><div className="mono" style={{ fontSize: 13 }}>{m.last}</div></div>
            </div>
          </Blueprint>
        ))}
      </div>

      <div style={{ marginTop: 34 }}>
        <h4 style={{ marginBottom: 10 }}>
          Transformation contract — Gold <span className="mono" style={{ fontSize: 13 }}>tx_ho_stat_record</span>
          {' '}<span className="k">demo — mapping endpoint pending</span>
        </h4>
        <table className="table">
          <thead>
            <tr><th>Stat field</th><th>Silver column</th><th>Guidewire source</th><th>Transform</th><th>Governing rule</th><th>Coverage</th></tr>
          </thead>
          <tbody>
            {CONTRACT.map((c) => (
              <tr key={c.field} className="row">
                <td className="mono" style={{ fontSize: 12 }}>{c.field}</td>
                <td className="mono" style={{ fontSize: 12, color: 'color-mix(in srgb,var(--color-text) 65%,transparent)' }}>{c.silver}</td>
                <td className="mono" style={{ fontSize: 12, color: 'color-mix(in srgb,var(--color-text) 65%,transparent)' }}>{c.gw}</td>
                <td style={{ fontSize: 12.5 }}>{c.xform}</td>
                <td className="mono" style={{ fontSize: 11.5, color: 'var(--color-accent-700)' }}>{c.rule}</td>
                <td><span className={'tag ' + c.tagClass}>{c.cov}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
