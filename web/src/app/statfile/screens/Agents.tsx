// Agent console — reimagined as a native Ant Design page: Statistic KPI cards
// for cycle telemetry, run history as a Card-framed Table with a Segmented
// grouped/every-run toggle, and the selected run's trace as a Timeline with
// its correlated evidence in a sticky side Card. Live: GOLD_AUDIT.AGENT_RUN
// via /agents/runs — every real Sentinel extraction, KG materialization and
// edit-engine run recorded going forward. Demo runs until the first recorded
// run lands.
import { useMemo, useState, type CSSProperties } from 'react';
import {
  Button, Card, Col, Divider, Row, Segmented, Space, Statistic, Table, Tag,
  Timeline, Typography,
} from 'antd';
import { useAgentRunDetail, useAgentRuns, type AgentRunRow } from '../api';
import { AGENT_STATS, RUNS, TRACE } from '../data';

const { Text } = Typography;

const MONO: CSSProperties = { fontFamily: "ui-monospace,'SFMono-Regular',Menlo,monospace" };

// Timeline dot palette by meaning (antd colors, not the legacy steel-blues).
const DOT_NEUTRAL = 'rgba(0,0,0,0.25)';
const DOT_ACTIVE = '#1677ff';
const DOT_EMPHASIS = '#722ed1';
const DOT_ERROR = '#ff4d4f';
// Demo TRACE fixtures carry the legacy hex constants in their `dot` field —
// map them by meaning rather than importing the constants.
const LEGACY_DOT: Record<string, string> = {
  '#5980a6': DOT_ACTIVE, '#1d2d3d': DOT_EMPHASIS, '#98989b': DOT_NEUTRAL,
};
const dotColor = (c: string) => LEGACY_DOT[c] ?? c;

// Run-result tag intensities → antd colors: settled green, needs-a-look
// orange, errored/blocked red.
const RESULT_COLOR: Record<string, string> = {
  'tag-neutral': 'green', 'tag-outline': 'orange', 'tag-accent': 'red',
};

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
        dot: s.status === 'error' ? DOT_ERROR : s.status === 'skipped' || s.status === 'review' ? DOT_NEUTRAL : DOT_ACTIVE,
      }))
    : live && sel?.runId
    ? [
        { step: 'Queued', detail: `${sel.agent}\n${sel.task}`, dot: DOT_NEUTRAL },
        { step: 'Run', detail: `model ${sel.model}\nduration ${sel.dur}`, dot: DOT_ACTIVE },
        { step: sel.status === 'error' ? 'Failed' : 'Result', detail: `${sel.result}\n${sel.ranAt ?? ''}`, dot: sel.status === 'error' ? DOT_ERROR : DOT_ACTIVE },
      ]
    : TRACE;

  type GroupRow = RunView & { key: string; i: number; count: number };
  const rows: GroupRow[] = groups.map((g) => ({
    ...g.r, key: g.r.runId ?? g.r.agent + g.i, i: g.i, count: g.count,
  }));

  const columns = [
    {
      title: 'Agent', dataIndex: 'agent', key: 'agent',
      render: (v: string, g: GroupRow) => (
        <span style={{ whiteSpace: 'nowrap' }}>
          <Text strong>{v}</Text>
          {g.count > 1 && (
            <Text type="secondary" style={{ ...MONO, fontSize: 10.5, marginLeft: 7 }}>×{g.count}</Text>
          )}
        </span>
      ),
    },
    {
      title: 'Task', dataIndex: 'task', key: 'task',
      render: (v: string) => <span style={{ fontSize: 12.5 }}>{v}</span>,
    },
    {
      title: 'Model', dataIndex: 'model', key: 'model', width: 110,
      render: (v: string) => <Text type="secondary" style={{ ...MONO, fontSize: 11 }}>{v}</Text>,
    },
    {
      title: 'Tokens', dataIndex: 'tokens', key: 'tokens', align: 'right' as const, width: 80,
      render: (v: string) => <span style={{ ...MONO, fontSize: 11.5 }}>{v}</span>,
    },
    {
      title: 'Dur', dataIndex: 'dur', key: 'dur', align: 'right' as const, width: 90,
      render: (v: string) => <span style={{ ...MONO, fontSize: 11.5 }}>{v}</span>,
    },
    {
      title: 'Conf', dataIndex: 'conf', key: 'conf', align: 'right' as const, width: 70,
      render: (v: string) => <span style={{ ...MONO, fontSize: 11.5 }}>{v}</span>,
    },
    {
      title: 'Result', dataIndex: 'result', key: 'result', width: 130,
      render: (v: string, g: GroupRow) => <Tag color={RESULT_COLOR[g.tagClass]}>{v}</Tag>,
    },
  ];

  return (
    <Row gutter={[16, 16]} align="top">
      {/* ── left: cycle stats + run history ─────────────────────────────── */}
      <Col flex="auto" style={{ minWidth: 0, maxWidth: '100%' }}>
        <Row gutter={[16, 16]}>
          {stats.map((a) => (
            <Col key={a.label} xs={12} md={6}>
              <Card>
                <Statistic title={a.label} value={a.value} valueStyle={{ fontSize: 24 }} />
              </Card>
            </Col>
          ))}
        </Row>

        <Card
          style={{ marginTop: 16 }}
          title={live ? 'Run history — GOLD_AUDIT.AGENT_RUN' : 'Run history — cycle TX-HO-2026A'}
          extra={
            <Space size={8}>
              {!live && (runsQ.isLoading
                ? <Text type="secondary" style={{ fontSize: 12 }}>connecting…</Text>
                : <Tag color="orange" title={runsQ.isError
                    ? 'telemetry store unreachable — showing design fixtures'
                    : 'no recorded runs yet — showing design fixtures'}>
                    demo data
                  </Tag>)}
              <Segmented
                value={collapse ? 'grouped' : 'every'}
                onChange={(v) => setCollapse(v === 'grouped')}
                options={[{ label: 'Grouped', value: 'grouped' }, { label: 'Every run', value: 'every' }]}
              />
            </Space>
          }
          styles={{ body: { padding: 0 } }}
        >
          <Table
            rowKey="key"
            dataSource={rows}
            columns={columns}
            pagination={false} size="middle"
            onRow={(g) => ({
              onClick: () => setRun(g.i),
              style: {
                cursor: 'pointer',
                background: g.i === runIdx ? 'rgba(22,119,255,0.08)' : undefined,
              },
            })}
          />
        </Card>
      </Col>

      {/* ── right: trace rail for the selected run ──────────────────────── */}
      <Col flex="400px">
        <Card
          style={{ position: 'sticky', top: 16, maxHeight: 'calc(100vh - 60px)', overflowY: 'auto' }}
          title={
            <div style={{ padding: '6px 0' }}>
              <Text type="secondary" style={{ fontSize: 12, fontWeight: 400, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Trace</Text>
              <div style={{ fontSize: 18 }}>{sel?.agent}</div>
              <Text type="secondary" style={{ ...MONO, fontSize: 11, fontWeight: 400 }}>
                {live && sel?.runId ? `${sel.runId} · ${sel.ranAt}` : `run_01JZ${4820 + runIdx}K · cycle TX-HO-2026A`}
              </Text>
            </div>
          }
        >
          <Timeline
            items={trace.map((t) => ({
              key: t.step,
              color: dotColor(t.dot),
              children: (
                <>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{t.step}</div>
                  <div style={{ ...MONO, fontSize: 11.5, lineHeight: 1.6, whiteSpace: 'pre-wrap', color: 'rgba(0,0,0,0.55)' }}>
                    {t.detail}
                  </div>
                </>
              ),
            }))}
          />

          {live && sel?.runId && (
            <>
              <Divider style={{ margin: '2px 0 12px' }} />
              <Text type="secondary" style={{ display: 'block', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
                Evidence{detailQ.isLoading ? ' · loading…' : ''}
              </Text>
              {evidence && evidence.actions.length === 0 && evidence.kg_entries.length === 0 && !detailQ.isLoading && (
                <Text type="secondary" style={{ display: 'block', fontSize: 11.5 }}>
                  No correlated audit records — this run left only its telemetry row.
                </Text>
              )}
              {evidence?.actions.map((a) => (
                <div key={a.action_id} style={{ padding: '6px 0', borderBottom: '1px solid rgba(5,5,5,0.06)' }}>
                  <Text type="secondary" style={{ ...MONO, display: 'block', fontSize: 10.5 }}>
                    {a.acted_at} · {a.action_type} · {a.actor}
                  </Text>
                  <div style={{ fontSize: 12, lineHeight: 1.5 }}>
                    {[a.target_record, a.target_rule].filter(Boolean).join(' · ')}
                    {a.summary ? `${a.target_record || a.target_rule ? ' — ' : ''}${a.summary}` : ''}
                  </div>
                </div>
              ))}
              {evidence?.kg_entries.map((k) => (
                <div key={k.id} style={{ padding: '6px 0', borderBottom: '1px solid rgba(5,5,5,0.06)' }}>
                  <Text type="secondary" style={{ ...MONO, display: 'block', fontSize: 10.5 }}>
                    {k.occurred_at?.slice(0, 16)} · canon · {k.action}
                  </Text>
                  <div style={{ fontSize: 12, lineHeight: 1.5 }}>
                    {k.summary}{k.affected_count ? ` · ${k.affected_count} node(s)` : ''}
                  </div>
                </div>
              ))}
            </>
          )}

          <Divider style={{ margin: '12px 0' }} />
          <Space size={8}>
            <Button>Replay</Button>
            <Button>Open prompt</Button>
          </Space>
        </Card>
      </Col>
    </Row>
  );
}
