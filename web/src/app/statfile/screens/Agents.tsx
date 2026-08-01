// Agent console — cycle stats, run history, and the trace rail for the
// selected run. Live: GOLD_AUDIT.AGENT_RUN via /agents/runs — every real
// Sentinel extraction, KG materialization and edit-engine run recorded going
// forward. Demo runs until the first recorded run lands.
import { useMemo, useState } from 'react';
import { Blueprint } from '../Blueprint';
import { useAgentRuns, type AgentRunRow } from '../api';
import { ACC, ACC9, AGENT_STATS, NEU, RUNS, TRACE } from '../data';

const fmtTokens = (n: number | null) =>
  n == null || n === 0 ? '—' : n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? (n / 1e3).toFixed(0) + 'K' : String(n);
const fmtDur = (ms: number | null) => {
  if (ms == null) return '—';
  if (ms < 1000) return ms + 'ms';
  const s = Math.round(ms / 1000);
  return s < 60 ? s + 's' : `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s`;
};

interface RunView {
  agent: string; task: string; model: string; tokens: string; dur: string;
  conf: string; result: string; tagClass: string; ranAt?: string; runId?: string; status?: string;
}

export function AgentsScreen() {
  const runsQ = useAgentRuns();
  const live = (runsQ.data?.runs.length ?? 0) > 0;

  const runs: RunView[] = useMemo(() => {
    if (!live) return RUNS;
    return runsQ.data!.runs.map((r: AgentRunRow) => ({
      agent: r.agent,
      task: r.task,
      model: r.model ?? '—',
      tokens: fmtTokens(r.tokens),
      dur: fmtDur(r.duration_ms),
      conf: r.confidence != null ? Math.round(r.confidence * 100) + '%' : '—',
      result: r.result,
      tagClass: r.status === 'error' ? 'tag-accent' : r.result.includes('violation') && !r.result.startsWith('0') ? 'tag-outline' : 'tag-neutral',
      ranAt: r.ran_at,
      runId: r.run_id,
      status: r.status,
    }));
  }, [live, runsQ.data]);

  const stats = live
    ? [
        { label: 'Recorded runs', value: String(runsQ.data!.stats.runs) },
        { label: 'Tokens', value: fmtTokens(runsQ.data!.stats.tokens) },
        { label: 'Mean confidence', value: runsQ.data!.stats.mean_confidence != null ? Math.round(runsQ.data!.stats.mean_confidence * 100) + '%' : '—' },
        { label: 'Errored', value: String(runsQ.data!.stats.escalated) },
      ]
    : AGENT_STATS;

  const [run, setRun] = useState(live ? 0 : 2);
  const sel = runs[Math.min(run, runs.length - 1)];

  const trace = live && sel?.runId
    ? [
        { step: 'Queued', detail: `${sel.agent}\n${sel.task}`, dot: NEU },
        { step: 'Run', detail: `model ${sel.model}\nduration ${sel.dur}`, dot: ACC },
        { step: sel.status === 'error' ? 'Failed' : 'Result', detail: `${sel.result}\n${sel.ranAt ?? ''}`, dot: sel.status === 'error' ? ACC9 : ACC },
      ]
    : TRACE;

  return (
    <div className="sc" style={{ display: 'grid', gridTemplateColumns: '1fr 400px', gap: 30, alignItems: 'start' }}>
      <section>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 20, marginBottom: 26 }}>
          {stats.map((a) => (
            <Blueprint key={a.label} style={{ padding: '12px 14px' }}>
              <div className="k">{a.label}</div>
              <div style={{ fontFamily: 'var(--font-heading)', fontSize: 27, lineHeight: 1.1, marginTop: 4 }}>{a.value}</div>
            </Blueprint>
          ))}
        </div>
        <h4 style={{ marginBottom: 10 }}>
          {live ? 'Run history — GOLD_AUDIT.AGENT_RUN' : 'Run history — cycle TX-HO-2026A'}
        </h4>
        <table className="table">
          <thead>
            <tr><th>Agent</th><th>Task</th><th>Model</th><th>Tokens</th><th>Dur</th><th>Conf</th><th>Result</th></tr>
          </thead>
          <tbody>
            {runs.map((r, i) => (
              <tr key={r.runId ?? r.agent + i} className="row" style={{ cursor: 'pointer' }} onClick={() => setRun(i)}>
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
        <div style={{ fontFamily: 'var(--font-heading)', fontSize: 20, margin: '3px 0 2px' }}>{sel?.agent}</div>
        <div className="mono muted" style={{ fontSize: 11, marginBottom: 14 }}>
          {live && sel?.runId ? `${sel.runId} · ${sel.ranAt}` : `run_01JZ${4820 + run}K · cycle TX-HO-2026A`}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {trace.map((t) => (
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
