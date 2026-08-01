// Filing dashboard — KPIs, filing cycles, medallion freshness, human queue.
import { Blueprint } from '../Blueprint';
import { CYCLES, LAYERS, QUEUE, type ScreenId } from '../data';

const KPIS = [
  { label: 'Records staged', value: '1,284,930', note: 'gold · tx_ho_stat_record' },
  { label: 'Open exceptions', value: '3,412', note: '1,847 blocking the package' },
  { label: 'Rules pending', value: '5', note: 'human approval gate' },
  { label: 'Days to due', value: '42', note: 'TDI · 15 Sep 2026' },
];

export function DashboardScreen({ go }: { go: (s: ScreenId) => () => void }) {
  return (
    <div className="sc">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 26, marginBottom: 34 }}>
        {KPIS.map((k) => (
          <Blueprint key={k.label} style={{ padding: '14px 16px 12px' }}>
            <div className="k">{k.label}</div>
            <div style={{ fontFamily: 'var(--font-heading)', fontSize: 36, lineHeight: 1.05, marginTop: 6 }}>{k.value}</div>
            <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>{k.note}</div>
          </Blueprint>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.55fr 1fr', gap: 34 }}>
        <section>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 10 }}>
            <h4>Filing cycles</h4>
            <span className="k">All jurisdictions · all standards</span>
          </div>
          <table className="table">
            <thead>
              <tr><th>Jurisdiction</th><th>Line</th><th>Standard</th><th>Period</th><th>Due</th><th>Records</th><th>Status</th></tr>
            </thead>
            <tbody>
              {CYCLES.map((c, i) => (
                <tr key={i} className="row" style={{ cursor: 'pointer' }} onClick={go(c.goTo)}>
                  <td style={{ fontFamily: 'var(--font-heading)', fontSize: 16 }}>{c.state}</td>
                  <td>{c.line}</td>
                  <td className="mono" style={{ fontSize: 12 }}>{c.std}</td>
                  <td className="mono" style={{ fontSize: 12 }}>{c.period}</td>
                  <td className="mono" style={{ fontSize: 12 }}>{c.due}</td>
                  <td className="mono" style={{ fontSize: 12, textAlign: 'right' }}>{c.records}</td>
                  <td><span className={'tag ' + c.tagClass}>{c.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>

          <div style={{ marginTop: 34 }}>
            <h4 style={{ marginBottom: 10 }}>Medallion freshness</h4>
            <Blueprint className="gridwash" style={{ padding: '18px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
              {LAYERS.map((l) => (
                <div key={l.name} style={{ display: 'grid', gridTemplateColumns: '88px 1fr 120px', alignItems: 'center', gap: 14 }}>
                  <div className="k">{l.name}</div>
                  <div style={{ height: 9, background: 'color-mix(in srgb,var(--color-text) 9%,transparent)', position: 'relative' }}>
                    <div style={{ position: 'absolute', inset: '0 auto 0 0', width: l.pct, background: 'var(--color-accent)' }} />
                  </div>
                  <div className="mono muted" style={{ fontSize: 11, textAlign: 'right' }}>{l.meta}</div>
                </div>
              ))}
            </Blueprint>
          </div>
        </section>

        <section>
          <h4 style={{ marginBottom: 10 }}>Needs a human</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {QUEUE.map((q) => (
              <Blueprint key={q.meta} className="card" style={{ padding: '14px 16px', cursor: 'pointer' }} onClick={go(q.goTo)}>
                <div className="card-kicker">{q.kicker}</div>
                <div className="card-title">{q.title}</div>
                <p className="card-body">{q.body}</p>
                <div className="card-meta"><span className="mono">{q.meta}</span></div>
              </Blueprint>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
