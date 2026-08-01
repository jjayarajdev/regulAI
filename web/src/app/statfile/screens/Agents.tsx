// Agent console — cycle stats, run history, and the trace rail for the
// selected run.
import { useState } from 'react';
import { Blueprint } from '../Blueprint';
import { AGENT_STATS, RUNS, TRACE } from '../data';

export function AgentsScreen() {
  const [run, setRun] = useState(2);

  return (
    <div className="sc" style={{ display: 'grid', gridTemplateColumns: '1fr 400px', gap: 30, alignItems: 'start' }}>
      <section>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 20, marginBottom: 26 }}>
          {AGENT_STATS.map((a) => (
            <Blueprint key={a.label} style={{ padding: '12px 14px' }}>
              <div className="k">{a.label}</div>
              <div style={{ fontFamily: 'var(--font-heading)', fontSize: 27, lineHeight: 1.1, marginTop: 4 }}>{a.value}</div>
            </Blueprint>
          ))}
        </div>
        <h4 style={{ marginBottom: 10 }}>Run history — cycle TX-HO-2026A</h4>
        <table className="table">
          <thead>
            <tr><th>Agent</th><th>Task</th><th>Model</th><th>Tokens</th><th>Dur</th><th>Conf</th><th>Result</th></tr>
          </thead>
          <tbody>
            {RUNS.map((r, i) => (
              <tr key={r.agent} className="row" style={{ cursor: 'pointer' }} onClick={() => setRun(i)}>
                <td style={{ fontFamily: 'var(--font-heading)', fontSize: 15 }}>{r.agent}</td>
                <td style={{ fontSize: 12.5 }}>{r.task}</td>
                <td className="mono muted" style={{ fontSize: 11 }}>{r.model}</td>
                <td className="mono" style={{ fontSize: 11.5, textAlign: 'right' }}>{r.tokens}</td>
                <td className="mono" style={{ fontSize: 11.5, textAlign: 'right' }}>{r.dur}</td>
                <td className="mono" style={{ fontSize: 11.5, textAlign: 'right' }}>{r.conf}</td>
                <td><span className={'tag ' + r.tagClass}>{r.result}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <Blueprint style={{ padding: '16px 18px' }}>
        <div className="k">Trace</div>
        <div style={{ fontFamily: 'var(--font-heading)', fontSize: 20, margin: '3px 0 2px' }}>{RUNS[run].agent}</div>
        <div className="mono muted" style={{ fontSize: 11, marginBottom: 14 }}>
          run_01JZ{4820 + run}K · cycle TX-HO-2026A
        </div>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {TRACE.map((t) => (
            <div key={t.step} style={{ display: 'grid', gridTemplateColumns: '14px 1fr', gap: 11, paddingBottom: 14 }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <span style={{ width: 9, height: 9, background: t.dot, marginTop: 4 }} />
                <span style={{ flex: 1, width: 1, background: 'var(--color-divider)' }} />
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{t.step}</div>
                <div className="mono" style={{ fontSize: 11.5, lineHeight: 1.6, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)', whiteSpace: 'pre-wrap' }}>{t.detail}</div>
              </div>
            </div>
          ))}
        </div>
        <div style={{ borderTop: '1px solid var(--color-divider)', paddingTop: 12, marginTop: 2, display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary">Replay</button>
          <button className="btn btn-secondary">Open prompt</button>
        </div>
      </Blueprint>
    </div>
  );
}
