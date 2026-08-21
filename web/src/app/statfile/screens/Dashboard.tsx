// Filing dashboard — KPIs, filing cycles, medallion freshness, human queue.
// Live: /filings + /validate/all + /pipeline/state + /kg/rules; falls back to
// the design fixtures per section while loading or when the warehouse is cold.
import { Blueprint } from '../Blueprint';
import { DemoTag, Stat, StatRow } from '../ui';
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
  // Rules genuinely awaiting a decision — drafts only (superseded/rejected
  // versions are history, not work).
  const pendingRules = rulesQ.data?.rules.filter((r) => r.status === 'draft') ?? [];
  const rulesPending = rulesQ.data ? pendingRules.length : undefined;
  const pendingBreakdown = pendingRules.length
    ? Object.entries(pendingRules.reduce<Record<string, number>>((m, r) => {
        const j = (r.jurisdiction_code ?? '—').replace(/^US-/, '') || 'US';
        m[j] = (m[j] ?? 0) + 1;
        return m;
      }, {}))
      .sort((a, b) => b[1] - a[1])
      .map(([j, n]) => `${n} ${j}`)
      .join(' · ')
    : undefined;

  const kpis = kpisFrom(filings, valQ.data, pipeQ.data, rulesPending);
  const cycles = cyclesFromFilings(filings, valQ.data);
  const layers = layersFrom(pipeQ.data);
  const queue = queueFrom(groupViolations(valQ.data), rulesPending, pendingBreakdown);

  return (
    <div className="sc">
      <StatRow style={{ marginBottom: 30 }}>
        {kpis.map((k) => (
          <Stat key={k.label} label={k.label} value={k.value} note={k.note} onClick={go(k.goTo)} />
        ))}
      </StatRow>

      <div style={{ display: 'grid', gridTemplateColumns: '1.55fr 1fr', gap: 34 }}>
        <section>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 10 }}>
            <h4>Filing cycles</h4>
            {!filingsQ.data?.filings.length && <DemoTag reason="warehouse filings unavailable — showing design fixtures" />}
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
                <tr key={i} className="row rowlink" onClick={go(c.goTo)}>
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
          <h4 style={{ marginBottom: 10 }}>Requires review</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {queue.map((q) => (
              <Blueprint key={q.meta + q.title} className="card rowlink" style={{ padding: '14px 16px' }} onClick={go(q.goTo)}>
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
