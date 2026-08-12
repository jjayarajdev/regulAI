// Filing dashboard — KPIs, filing cycles, medallion freshness, human queue.
// Live: /filings + /validate/all + /pipeline/state + /kg/rules; falls back to
// the design fixtures per section while loading or when the warehouse is cold.
import { Blueprint } from '../Blueprint';
import {
  cyclesFromFilings, groupViolations, kpisFrom, layersFrom, queueFrom,
  useFilings, useKgRules, usePipelineState, useValidateAll,
} from '../api';
import type { ScreenId } from '../data';

export function DashboardScreen({ go }: { go: (s: ScreenId) => () => void }) {
  const filingsQ = useFilings();
  const valQ = useValidateAll();
  const pipeQ = usePipelineState();
  const rulesQ = useKgRules();

  const filings = filingsQ.data?.filings ?? [];
  const rulesPending = rulesQ.data
    ? rulesQ.data.rules.filter((r) => r.status === 'draft' || !r.currently_active).length
    : undefined;

  const kpis = kpisFrom(filings, valQ.data, pipeQ.data, rulesPending);
  const cycles = cyclesFromFilings(filings, valQ.data);
  const layers = layersFrom(pipeQ.data);
  const queue = queueFrom(groupViolations(valQ.data), rulesPending);

  return (
    <div className="sc">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 26, marginBottom: 34 }}>
        {kpis.map((k) => (
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
            <span className="k">
              {filings.length ? 'live · all jurisdictions' : 'All jurisdictions · all standards'}
            </span>
          </div>
          <table className="table">
            <thead>
              <tr><th>Jurisdiction</th><th>Line</th><th>Standard</th><th>Period</th><th>Due</th><th>Exceptions</th><th>Status</th></tr>
            </thead>
            <tbody>
              {cycles.map((c, i) => (
                <tr key={i} className="row" style={{ cursor: 'pointer' }} onClick={go(c.goTo)}>
                  <td>
                    <span className="tag tag-outline" style={{ fontFamily: 'var(--font-heading)', fontSize: 13 }}>
                      {c.state}
                    </span>
                  </td>
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
              {layers.map((l) => (
                <div key={l.name} style={{ display: 'grid', gridTemplateColumns: '88px 1fr 160px', alignItems: 'center', gap: 14 }}>
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
            {queue.map((q) => (
              <Blueprint key={q.meta + q.title} className="card" style={{ padding: '14px 16px', cursor: 'pointer' }} onClick={go(q.goTo)}>
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
