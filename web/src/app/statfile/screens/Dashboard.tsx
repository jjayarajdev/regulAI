// Filing dashboard — "what happens next, per filing". The active filing's
// journey is the hero: its stage in a sentence, the numbers that matter, and
// one next action. Below it the review queue grouped by stage (blocking first,
// rulebook approvals muted because they gate nothing) and every filing cycle
// with a mini journey bar. Live: /filings + /validate/all + /bulletins +
// /filing/{id}/submission + /kg/rules via useJourney; design fixtures when
// the warehouse is cold.
import { RightOutlined } from '@ant-design/icons';
import { Badge, Button, Card, Col, Row, Table, Tag, Typography } from 'antd';
import { groupViolations, useKgRules, useValidateAll, type GroupedError } from '../api';
import type { Filing } from '../../../api/types';
import type { ScreenId } from '../data';
import { useJourney, type Journey } from '../journey/useJourney';

const { Text } = Typography;
const juris = (code?: string | null) => (code ?? '').replace(/^US-/, '') || '—';
const MONO: React.CSSProperties = { fontFamily: "ui-monospace,'SFMono-Regular',Menlo,monospace" };

// Six-segment journey bar for a filing row. 1 = done, 2 = current, 0 = ahead.
function MiniJourney({ prog, blocked }: { prog: number[]; blocked: boolean }) {
  return (
    <span style={{ display: 'inline-flex', gap: 3, alignItems: 'center' }}>
      {prog.map((p, i) => (
        <i key={i} style={{
          display: 'block', width: 14, height: 6, borderRadius: 2,
          background: p === 1 ? '#52c41a' : p === 2 ? (blocked ? '#cf1322' : '#1677ff') : 'rgba(5,5,5,0.15)',
        }} />
      ))}
    </span>
  );
}

// A non-active filing's journey, approximated from what the list endpoints
// know (validation per filing; submission state only loads for the active
// one). Settled filings read as complete.
function rowJourney(f: Filing, blockers: number, j: Journey): { prog: number[]; next: string; goTo: ScreenId } {
  if (j.filing?.id === f.id) {
    const s = j.stages.map((st) => (st.state === 'done' ? 1 : st.key === j.current ? 2 : 0));
    return { prog: s, next: j.next.label, goTo: j.next.goTo };
  }
  if (!f.is_active) return { prog: [1, 1, 1, 1, 1, 1], next: 'Filed', goTo: 'dash' };
  if (blockers > 0) return { prog: [1, 2, 0, 0, 0, 0], next: `Triage ${blockers.toLocaleString()}`, goTo: 'val' };
  return { prog: [1, 1, 1, 2, 0, 0], next: 'Start sign-off', goTo: 'filing' };
}

export function DashboardScreen({ go, filingId, onSelectFiling }: {
  go: (s: ScreenId) => () => void;
  filingId: string | null;
  onSelectFiling: (id: string) => void;
}) {
  const j = useJourney(filingId);
  const valQ = useValidateAll();
  const rulesQ = useKgRules();
  const F = j.filing;

  // Blocking exceptions on the active filing, grouped by rule.
  const errors: GroupedError[] = (() => {
    if (!valQ.data || !F) return groupViolations(undefined).filter((e) => e.sev === 2);
    const only = { ...valQ.data, by_filing: { [F.id]: valQ.data.by_filing[F.id] } };
    if (!only.by_filing[F.id]) return [];
    return groupViolations(only).filter((e) => e.sev === 2 && !e.suppressed && e.violations.length > 0);
  })();

  const pendingRules = rulesQ.data?.rules.filter((r) => r.status === 'draft') ?? [];
  const pendingBreakdown = Object.entries(pendingRules.reduce<Record<string, number>>((m, r) => {
    const k = juris(r.jurisdiction_code) || 'US';
    m[k] = (m[k] ?? 0) + 1;
    return m;
  }, {})).sort((a, b) => b[1] - a[1]).map(([k, n]) => `${n} ${k}`).join(' · ');

  // Stage sentence for the hero.
  const stageLine = j.blockers
    ? <><b>Validation.</b> {j.blockers.toLocaleString()} blocking exception{j.blockers === 1 ? '' : 's'} hold the package.</>
    : j.signed < 3 ? <><b>Validated.</b> Ready for sign-off.</>
    : !j.sealed ? <><b>Officer approved.</b> Ready to seal.</>
    : !j.sent ? <><b>Sealed.</b> Ready to transmit.</>
    : !j.acked ? <><b>Sent.</b> Awaiting acknowledgement.</>
    : <><b>Acknowledged.</b> Filing complete.</>;

  // Every filing, active one first.
  const rows = [...j.filings].sort((a, b) => Number(b.id === F?.id) - Number(a.id === F?.id) || Number(b.is_active) - Number(a.is_active));
  const cycleColumns = [
    {
      title: 'Filing', key: 'id', width: 190,
      render: (_: unknown, f: Filing) => (
        <div style={{ minWidth: 0 }}>
          <span style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}>
            <span style={{ ...MONO, fontSize: 12.5 }}>{f.id}</span>
            {f.id === F?.id && <Tag color="blue" style={{ marginInlineEnd: 0 }}>active</Tag>}
          </span>
          <Text type="secondary" ellipsis style={{ display: 'block', fontSize: 11.5, maxWidth: 220 }}>
            {juris(f.jurisdiction_code)} · {f.plan_name}
          </Text>
        </div>
      ),
    },
    { title: 'Due', dataIndex: 'due_date', key: 'due', width: 110, render: (v: string) => <span style={{ ...MONO, fontSize: 12 }}>{v}</span> },
    {
      title: 'Journey', key: 'journey', width: 120,
      render: (_: unknown, f: Filing) => {
        const b = blockersFor(f);
        return <MiniJourney prog={rowJourney(f, b, j).prog} blocked={b > 0} />;
      },
    },
    {
      title: 'Blk', key: 'blk', width: 60, align: 'right' as const,
      render: (_: unknown, f: Filing) => {
        const b = blockersFor(f);
        return <span style={{ color: b ? '#cf1322' : 'rgba(0,0,0,0.35)', fontVariantNumeric: 'tabular-nums' }}>{b.toLocaleString()}</span>;
      },
    },
    {
      title: 'Next', key: 'next', width: 200,
      render: (_: unknown, f: Filing) => <Text style={{ color: '#1677ff', fontSize: 12.5 }}>{rowJourney(f, blockersFor(f), j).next} →</Text>,
    },
  ];
  function blockersFor(f: Filing): number {
    if (f.id === F?.id) return j.blockers;
    const fv = valQ.data?.by_filing[f.id];
    const sup = valQ.data?.suppressions ?? {};
    return (fv?.violations ?? []).filter((v) => v.severity === 'ERROR' && !v.suppressed && !sup[v.rule_number]).length;
  }

  return (
    <div>
      {/* ── hero: the active filing and its one next action ────────────── */}
      <div className="hero">
        <div>
          <span className="k">Active filing</span>
          <div className="hero-id">
            {F?.id ?? '—'}
            {F && <Tag>{juris(F.jurisdiction_code)} · {F.plan_name} · {F.plan_code} · canon {j.canon}</Tag>}
            {!j.live && <Tag title="warehouse offline — showing design fixtures">demo data</Tag>}
          </div>
          <div className="hero-stage">{stageLine}</div>
          <div className="hero-facts">
            <div className={`hero-f ${j.blockers ? 'crit' : 'ok'}`}><div className="v">{j.blockers.toLocaleString()}</div><div className="l">blocking</div></div>
            <div className="hero-f"><div className="v">{j.warnings.toLocaleString()}</div><div className="l">warnings</div></div>
            <div className="hero-f"><div className="v">{j.bulletin ? 1 : 0}</div><div className="l">pending bulletin</div></div>
            <div className="hero-f"><div className="v">{j.signed}<small>/3</small></div><div className="l">signatures</div></div>
            <div className="hero-f"><div className="v">{j.daysToDue ?? '—'}</div><div className="l">days to due</div></div>
          </div>
        </div>
        <div className="hero-next">
          <span className="k">Next action</span>
          <Button type="primary" size="large" onClick={go(j.next.goTo)}>{j.next.label} →</Button>
          <div className="hero-why">{j.next.why}</div>
        </div>
      </div>

      <Row gutter={[16, 16]}>
        {/* ── review queue, grouped by stage ──────────────────────────────── */}
        <Col xs={24} xl={13}>
          <Card title="Requires review" extra={<Text type="secondary" style={{ fontSize: 12 }}>grouped by stage · most urgent first</Text>} styles={{ body: { padding: 0 } }}>
            <QueueGroup tone="error" title="Blocking the package" count={j.blockers}>
              {errors.length ? errors.map((e) => (
                <QueueItem key={e.code} hot onClick={go('val')}
                  title={`${e.code} — ${e.field}`}
                  desc={<>{e.count} record{e.count === '1' ? '' : 's'} · {e.origin}{j.bulletinRules.has(e.code) && j.bulletin
                    ? <> · <Tag color="orange" style={{ marginInlineStart: 4 }}>clears with bulletin</Tag></>
                    : ' · manual fix or memo'}</>} />
              )) : <QueueEmpty>Nothing blocking. The package can move to sign-off.</QueueEmpty>}
            </QueueGroup>
            <QueueGroup tone="warning" title="Pending bulletin" count={j.bulletin ? 1 : 0}>
              {j.bulletin ? (
                <QueueItem onClick={go('amend')}
                  title={`${j.bulletin.name} — ${j.bulletin.title}`}
                  desc={<>{juris(j.bulletin.jurisdiction_code)} · effective {j.bulletin.effective_date} · {j.bulletinLoading ? 'computing impact…' : j.bulletinClears ? `clears ${j.bulletinClears} exception${j.bulletinClears === 1 ? '' : 's'} on ${F?.id}` : `${j.bulletin.targets} rule target${j.bulletin.targets === 1 ? '' : 's'}`}</>} />
              ) : <QueueEmpty>No bulletin pending. The canon is current.</QueueEmpty>}
            </QueueGroup>
            <QueueGroup tone="default" title="Rulebook approvals" count={j.rulesPending ?? 0} muted>
              <QueueItem muted onClick={go('rules')}
                title="Draft rules awaiting human approval"
                desc={<>{pendingBreakdown || 'none pending'} — not enforced until approved; does not block any filing</>} />
            </QueueGroup>
          </Card>
        </Col>

        {/* ── every cycle with a mini journey ─────────────────────────────── */}
        <Col xs={24} xl={11}>
          <Card title="All filing cycles" extra={<Text type="secondary" style={{ fontSize: 12 }}>{j.live ? `live · ${rows.length}` : 'demo'}</Text>} styles={{ body: { padding: 0 } }}>
            <Table
              rowKey="id"
              dataSource={rows}
              columns={cycleColumns}
              pagination={false} size="small"
              onRow={(f) => ({
                onClick: () => { onSelectFiling(f.id); if (f.id === F?.id) go(j.next.goTo)(); },
                style: { cursor: 'pointer' },
              })}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}

function QueueGroup({ tone, title, count, muted, children }: {
  tone: 'error' | 'warning' | 'default'; title: string; count: number; muted?: boolean; children: React.ReactNode;
}) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px 6px' }}>
        <Badge status={tone} />
        <span style={{ fontFamily: 'var(--font-heading)', fontSize: 15, fontWeight: 600, color: muted ? 'rgba(0,0,0,0.45)' : undefined }}>{title}</span>
        <Tag color={tone === 'error' ? 'red' : tone === 'warning' ? 'orange' : undefined} style={{ marginInlineEnd: 0 }}>{count.toLocaleString()}</Tag>
      </div>
      {children}
    </div>
  );
}

function QueueItem({ title, desc, hot, muted, onClick }: {
  title: string; desc: React.ReactNode; hot?: boolean; muted?: boolean; onClick: () => void;
}) {
  return (
    <div onClick={onClick} style={{
      display: 'flex', gap: 12, padding: '10px 16px', borderTop: '1px solid rgba(5,5,5,0.06)', alignItems: 'flex-start',
      cursor: 'pointer', background: hot ? '#fff1f0' : undefined,
    }}>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontWeight: 600, fontSize: 13, color: muted ? 'rgba(0,0,0,0.45)' : undefined }}>{title}</div>
        <div style={{ fontSize: 12, color: 'rgba(0,0,0,0.55)' }}>{desc}</div>
      </div>
      <RightOutlined style={{ color: 'rgba(0,0,0,0.25)', fontSize: 11, marginTop: 4 }} />
    </div>
  );
}

function QueueEmpty({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ padding: '8px 16px 10px', borderTop: '1px solid rgba(5,5,5,0.06)', fontSize: 12, color: 'rgba(0,0,0,0.55)' }}>
      {children}
    </div>
  );
}
