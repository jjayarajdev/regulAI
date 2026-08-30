// Filing dashboard — reimagined as a native Ant Design page: Statistic KPI
// cards with tinted icon wells, a Card-framed Table with Badge statuses for
// the filing cycles, dashboard-gauge Progress for medallion freshness, and
// the human queue as a List with severity avatars.
// Live: /filings + /validate/all + /pipeline/state + /kg/rules; falls back to
// the design fixtures per section while loading or when the warehouse is cold.
import type { ReactNode } from 'react';
import {
  AuditOutlined, ClockCircleOutlined, DatabaseOutlined, ExceptionOutlined,
  NodeIndexOutlined, RightOutlined, RocketOutlined, WarningOutlined,
} from '@ant-design/icons';
import { Avatar, Badge, Card, Col, List, Progress, Row, Statistic, Table, Tag, Typography } from 'antd';
import {
  cyclesFromFilings, groupViolations, kpisFrom, layersFrom, queueFrom,
  useFilings, useKgRules, usePipelineState, useValidateAll,
} from '../api';
import type { Cycle, ScreenId } from '../data';

const { Text } = Typography;

// KPI dressing by position: staged volume, exceptions, approvals, deadline.
const KPI_META: Array<{ icon: ReactNode; color: string }> = [
  { icon: <DatabaseOutlined />, color: '#1677ff' },
  { icon: <ExceptionOutlined />, color: '#fa541c' },
  { icon: <AuditOutlined />, color: '#722ed1' },
  { icon: <ClockCircleOutlined />, color: '#13c2c2' },
];

// The design's three tag intensities → Badge semantics: accent is the active
// working state, outline is in progress elsewhere, neutral is settled.
const BADGE_STATUS: Record<string, 'processing' | 'warning' | 'success'> = {
  'tag-accent': 'processing', 'tag-outline': 'warning', 'tag-neutral': 'success',
};

// Review-queue dressing by kicker.
const QUEUE_META: Record<string, { icon: ReactNode; color: string }> = {
  'Approval gate': { icon: <AuditOutlined />, color: '#722ed1' },
  'Exception': { icon: <WarningOutlined />, color: '#fa541c' },
  'Mapping gap': { icon: <NodeIndexOutlined />, color: '#fa8c16' },
  'Onboarding': { icon: <RocketOutlined />, color: '#1677ff' },
};

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

  const cycleColumns = [
    {
      title: 'Jurisdiction', dataIndex: 'state', key: 'state', width: 110,
      render: (s: string) => <Tag color="geekblue">{s}</Tag>,
    },
    { title: 'Line', dataIndex: 'line', key: 'line', ellipsis: true },
    {
      title: 'Standard', dataIndex: 'std', key: 'std',
      render: (v: string) => <Text code style={{ fontSize: 12 }}>{v}</Text>,
    },
    { title: 'Period', dataIndex: 'period', key: 'period' },
    { title: 'Due', dataIndex: 'due', key: 'due' },
    {
      title: 'Exceptions', dataIndex: 'records', key: 'records', align: 'right' as const,
      render: (v: string) => <Text strong>{v}</Text>,
    },
    {
      title: 'Status', dataIndex: 'status', key: 'status', width: 150,
      render: (_: string, c: Cycle) => (
        <Badge status={BADGE_STATUS[c.tagClass] ?? 'default'} text={c.status} />
      ),
    },
  ];

  return (
    <div>
      {/* KPI row */}
      <Row gutter={[16, 16]}>
        {kpis.map((k, i) => {
          const meta = KPI_META[i % KPI_META.length];
          return (
            <Col key={k.label} xs={12} xl={6}>
              <Card hoverable onClick={go(k.goTo)}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                  <Avatar
                    shape="square" size={44}
                    style={{ background: `${meta.color}1a`, color: meta.color, fontSize: 20, flexShrink: 0 }}
                    icon={meta.icon}
                  />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <Statistic
                      title={k.label} value={k.value}
                      valueStyle={{ fontSize: 26, lineHeight: 1.15 }}
                    />
                  </div>
                  <RightOutlined style={{ color: 'rgba(0,0,0,0.25)', fontSize: 12, marginTop: 4 }} />
                </div>
                {k.note != null && (
                  <div style={{ borderTop: '1px solid rgba(5,5,5,0.06)', marginTop: 12, paddingTop: 8 }}>
                    <Text type="secondary" style={{ fontSize: 12 }} ellipsis>{k.note}</Text>
                  </div>
                )}
              </Card>
            </Col>
          );
        })}
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} xl={15}>
          <Card
            title="Filing cycles"
            extra={
              <span style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}>
                {!filingsQ.data?.filings.length && (
                  <Tag color="orange" title="warehouse filings unavailable — showing design fixtures">demo data</Tag>
                )}
                <Text type="secondary" style={{ fontSize: 13 }}>
                  {filings.length ? 'live · all jurisdictions' : 'All jurisdictions · all standards'}
                </Text>
              </span>
            }
            styles={{ body: { padding: 0 } }}
          >
            <Table
              dataSource={cycles.map((c, i) => ({ ...c, key: i }))}
              columns={cycleColumns}
              pagination={false} size="middle"
              onRow={(c) => ({ onClick: go(c.goTo), style: { cursor: 'pointer' } })}
            />
          </Card>

          <Card title="Medallion freshness" style={{ marginTop: 16 }}>
            <Row gutter={16} justify="space-around">
              {layers.map((l) => (
                <Col key={l.name} style={{ textAlign: 'center' }}>
                  <Progress
                    type="dashboard" size={104}
                    percent={parseInt(l.pct, 10)}
                    strokeColor={parseInt(l.pct, 10) === 100 ? '#52c41a' : '#1677ff'}
                  />
                  <div style={{ marginTop: 4 }}>
                    <Text strong>{l.name}</Text>
                    <br />
                    <Text type="secondary" style={{ fontSize: 12 }}>{l.meta}</Text>
                  </div>
                </Col>
              ))}
            </Row>
          </Card>
        </Col>

        <Col xs={24} xl={9}>
          <Card title="Requires review" styles={{ body: { padding: 0 } }}>
            <List
              itemLayout="horizontal"
              dataSource={queue}
              renderItem={(q) => {
                const meta = QUEUE_META[q.kicker] ?? { icon: <ExceptionOutlined />, color: '#1677ff' };
                return (
                  <List.Item
                    onClick={go(q.goTo)}
                    style={{ cursor: 'pointer', padding: '14px 20px' }}
                    extra={<RightOutlined style={{ color: 'rgba(0,0,0,0.25)', fontSize: 12 }} />}
                  >
                    <List.Item.Meta
                      avatar={
                        <Avatar shape="square" size={38}
                          style={{ background: `${meta.color}1a`, color: meta.color, fontSize: 17 }}
                          icon={meta.icon}
                        />
                      }
                      title={
                        <span style={{ display: 'inline-flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                          {q.title}
                          <Tag style={{ marginInlineEnd: 0 }} color={meta.color}>{q.meta}</Tag>
                        </span>
                      }
                      description={
                        <>
                          <Text type="secondary" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                            {q.kicker}
                          </Text>
                          <div style={{ fontSize: 13 }}>{q.body}</div>
                        </>
                      }
                    />
                  </List.Item>
                );
              }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
