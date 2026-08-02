// Agent console — cycle stats, run history, and the trace rail for the
// selected run. Live: GOLD_AUDIT.AGENT_RUN via /agents/runs — every real
// Sentinel extraction, KG materialization and edit-engine run recorded going
// forward. Demo runs until the first recorded run lands.
import { useMemo, useState } from 'react';
import { Blueprint } from '../Blueprint';
import { useAgentRunDetail, useAgentRuns, type AgentRunRow } from '../api';
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

  // null until the user picks — data arrives after mount, so a static initial
  // index would lock in the demo default (2) even once live runs load.
  const [run, setRun] = useState<number | null>(null);
  const runIdx = run ?? (live ? 0 : 2);
  const sel = runs[Math.min(runIdx, runs.length - 1)];

  // Consecutive identical runs (agent + task + result) collapse into one row
  // with a ×N count — the Edit Engine's steady heartbeat would otherwise
  // drown the interesting runs. The newest run of a group represents it.
  const [collapse, setCollapse] = useState(true);
  const groups = useMemo(() => {
    const key = (r: RunView) => `${r.agent}|${r.task}|${r.result}`;
    const gs: Array<{ r: RunView; i: number; count: number }> = [];
    runs.forEach((r, i) => {
      const last = gs[gs.length - 1];
      if (collapse && last && key(last.r) === key(r)) last.count += 1;
      else gs.push({ r, i, count: 1 });
    });
    return gs;
  }, [runs, collapse]);

  // Evidence for the selected run: audit actions + KG entries it produced.
  const detailQ = useAgentRunDetail(live ? sel?.runId ?? null : null);
  const evidence = detailQ.data;

  // Real step telemetry (AGENT_RUN_STEP) when the run recorded it; else the
  // synthesized 3-step outline; else the demo trace.
  const realSteps = evidence?.steps ?? [];
  const trace = live && sel?.runId && realSteps.length > 0
    ? realSteps.map((s) => ({
        step: s.step,
        detail: s.detail + (s.duration_ms != null && s.duration_ms > 0 ? `\n${fmtDur(s.duration_ms)}` : ''),
        dot: s.status === 'error' ? ACC9 : s.status === 'skipped' || s.status === 'review' ? NEU : ACC,
      }))
    : live && sel?.runId
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
        <h4 style={{ marginBottom: 10, display: 'flex', alignItems: 'center', gap: 10 }}>
          {live ? 'Run history — GOLD_AUDIT.AGENT_RUN' : 'Run history — cycle TX-HO-2026A'}
          {!live && (
            <span className="tag tag-outline">
              {runsQ.isLoading ? 'connecting…' : runsQ.isError ? 'demo — telemetry store unreachable' : 'demo — no recorded runs yet'}
            </span>
          )}
          <div className="seg" style={{ marginLeft: 'auto' }}>
            {([[true, 'Grouped'], [false, 'Every run']] as Array<[boolean, string]>).map(([v, label]) => (
              <label key={label} className="seg-opt">
                <input type="radio" name="rg" checked={collapse === v} onChange={() => setCollapse(v)} />
                <span>{label}</span>
              </label>
            ))}
          </div>
        </h4>
        <table className="table">
          <thead>
            <tr><th>Agent</th><th>Task</th><th>Model</th><th>Tokens</th><th>Dur</th><th>Conf</th><th>Result</th></tr>
          </thead>
          <tbody>
            {groups.map((g) => {
              const r = g.r;
              return (
                <tr
                  key={r.runId ?? r.agent + g.i}
                  className="row"
                  style={{
                    cursor: 'pointer',
                    background: g.i === runIdx ? 'color-mix(in srgb,#5980a6 10%,transparent)' : undefined,
                  }}
                  onClick={() => setRun(g.i)}
                >
                  <td style={{ fontFamily: 'var(--font-heading)', fontSize: 15, whiteSpace: 'nowrap' }}>
                    {r.agent}
                    {g.count > 1 && (
                      <span className="mono" style={{ fontSize: 10.5, marginLeft: 7, color: 'color-mix(in srgb,var(--color-text) 50%,transparent)' }}>
                        ×{g.count}
                      </span>
                    )}
                  </td>
                  <td style={{ fontSize: 12.5 }}>{r.task}</td>
                  <td className="mono muted" style={{ fontSize: 11 }}>{r.model}</td>
                  <td className="mono" style={{ fontSize: 11.5, textAlign: 'right' }}>{r.tokens}</td>
                  <td className="mono" style={{ fontSize: 11.5, textAlign: 'right' }}>{r.dur}</td>
                  <td className="mono" style={{ fontSize: 11.5, textAlign: 'right' }}>{r.conf}</td>
                  <td><span className={'tag ' + r.tagClass}>{r.result}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      <Blueprint style={{ padding: '16px 18px', position: 'sticky', top: 16, maxHeight: 'calc(100vh - 60px)', overflowY: 'auto' }}>
        <div className="k">Trace</div>
        <div style={{ fontFamily: 'var(--font-heading)', fontSize: 20, margin: '3px 0 2px' }}>{sel?.agent}</div>
        <div className="mono muted" style={{ fontSize: 11, marginBottom: 14 }}>
          {live && sel?.runId ? `${sel.runId} · ${sel.ranAt}` : `run_01JZ${4820 + runIdx}K · cycle TX-HO-2026A`}
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
        {live && sel?.runId && (
          <div style={{ borderTop: '1px solid var(--color-divider)', paddingTop: 12, marginTop: 2 }}>
            <div className="k" style={{ marginBottom: 8 }}>
              Evidence
              {detailQ.isLoading ? ' · loading…' : ''}
            </div>
            {evidence && evidence.actions.length === 0 && evidence.kg_entries.length === 0 && !detailQ.isLoading && (
              <div className="muted" style={{ fontSize: 11.5 }}>
                No correlated audit records — this run left only its telemetry row.
              </div>
            )}
            {evidence?.actions.map((a) => (
              <div key={a.action_id} style={{ padding: '6px 0', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)' }}>
                <div className="mono" style={{ fontSize: 10.5, color: 'var(--color-accent-700)' }}>
                  {a.acted_at} · {a.action_type} · {a.actor}
                </div>
                <div style={{ fontSize: 12, lineHeight: 1.5 }}>
                  {[a.target_record, a.target_rule].filter(Boolean).join(' · ')}
                  {a.summary ? `${a.target_record || a.target_rule ? ' — ' : ''}${a.summary}` : ''}
                </div>
              </div>
            ))}
            {evidence?.kg_entries.map((k) => (
              <div key={k.id} style={{ padding: '6px 0', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)' }}>
                <div className="mono" style={{ fontSize: 10.5, color: 'var(--color-accent-700)' }}>
                  {k.occurred_at?.slice(0, 16)} · canon · {k.action}
                </div>
                <div style={{ fontSize: 12, lineHeight: 1.5 }}>
                  {k.summary}{k.affected_count ? ` · ${k.affected_count} node(s)` : ''}
                </div>
              </div>
            ))}
          </div>
        )}
        <div style={{ borderTop: '1px solid var(--color-divider)', paddingTop: 12, marginTop: 12, display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary">Replay</button>
          <button className="btn btn-secondary">Open prompt</button>
        </div>
      </Blueprint>
    </div>
  );
}
