// ISO projection — reimagined as a native Ant Design page: a header Card with
// shared/standard-specific Statistics, the TDI ↔ ISO crosswalk as a
// Card-framed Table with relationship Tags, and the ISO record image (code
// block) + agent-flagged gaps (List with meaning-colored dots) side by side.
// Vision demo — the same silver layer projected through a second standard.
import type { CSSProperties } from 'react';
import { Badge, Card, Col, List, Row, Space, Statistic, Table, Tag, Typography } from 'antd';
import { CROSSWALK, ISO_GAPS, ISO_IMAGE } from '../data';

const { Text, Paragraph, Title } = Typography;

const MONO: CSSProperties = { fontFamily: "ui-monospace,'SFMono-Regular',Menlo,monospace" };

// Relationship intensities → Tag colors by meaning: direct/settled green,
// recoded-with-a-bridge orange, the flagged sourcing gap red.
const REL_COLOR: Record<string, string> = {
  'tag-neutral': 'green', 'tag-outline': 'orange', 'tag-accent': 'red',
};

// Gap fixtures carry the legacy steel-blue hex dots — map by meaning:
// emphasis purple, active blue.
const GAP_DOT: Record<string, string> = { '#1d2d3d': '#722ed1', '#5980a6': '#1677ff' };

type CrossRow = (typeof CROSSWALK)[number];

const crosswalkColumns = [
  {
    title: 'Silver column', dataIndex: 'silver', key: 'silver',
    render: (v: string) => <span style={{ ...MONO, fontSize: 12 }}>{v}</span>,
  },
  {
    title: 'TDI HO field', dataIndex: 'tdi', key: 'tdi',
    render: (v: string) => <Text type="secondary" style={{ ...MONO, fontSize: 12 }}>{v}</Text>,
  },
  {
    title: 'ISO PL field', dataIndex: 'iso', key: 'iso',
    render: (v: string) => <Text type="secondary" style={{ ...MONO, fontSize: 12 }}>{v}</Text>,
  },
  {
    title: 'Relationship', dataIndex: 'rel', key: 'rel', width: 120,
    render: (v: string, c: CrossRow) => <Tag color={REL_COLOR[c.tagClass]}>{v}</Tag>,
  },
  {
    title: 'Bridge', dataIndex: 'bridge', key: 'bridge',
    render: (v: string) => <Text type="secondary" style={{ fontSize: 12 }}>{v}</Text>,
  },
];

export function IsoScreen() {
  return (
    <div>
      {/* ── standard header ─────────────────────────────────────────────── */}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={[24, 16]} align="middle">
          <Col flex="auto" style={{ minWidth: 280 }}>
            <Space size={8}>
              <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Standard
              </Text>
              <Tag color="orange" title="vision demo — no second standard in the warehouse yet">demo data</Tag>
            </Space>
            <Title level={4} style={{ margin: '4px 0 4px' }}>
              ISO Personal Lines Statistical Plan — Homeowners
            </Title>
            <Paragraph type="secondary" style={{ fontSize: 12.5, margin: 0 }}>
              The same silver layer, projected through a second standard. Nothing upstream
              is rebuilt — only the mapping and the edit package differ.
            </Paragraph>
          </Col>
          <Col flex="none">
            <Space size={32}>
              <Statistic title="Shared silver columns" value="41 / 47" valueStyle={{ fontSize: 26 }} />
              <Statistic title="Standard-specific" value={6} valueStyle={{ fontSize: 26 }} />
            </Space>
          </Col>
        </Row>
      </Card>

      {/* ── crosswalk ───────────────────────────────────────────────────── */}
      <Card title="Crosswalk — TDI ↔ ISO" styles={{ body: { padding: 0 } }}>
        <Table
          rowKey="silver"
          dataSource={CROSSWALK}
          columns={crosswalkColumns}
          pagination={false} size="middle"
        />
      </Card>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        {/* ── record image ──────────────────────────────────────────────── */}
        <Col xs={24} xl={12}>
          <Card title="ISO record image — same policy, 118 bytes" style={{ height: '100%' }}>
            <pre style={{
              ...MONO, margin: 0, padding: '12px 14px', fontSize: 13, lineHeight: 1.9,
              letterSpacing: '0.1em', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
              background: 'rgba(5,5,5,0.04)', borderRadius: 6,
            }}>
              {ISO_IMAGE}
            </pre>
          </Card>
        </Col>

        {/* ── flagged gaps ──────────────────────────────────────────────── */}
        <Col xs={24} xl={12}>
          <Card title="Gaps the agents flagged" style={{ height: '100%' }} styles={{ body: { padding: 0 } }}>
            <List
              dataSource={ISO_GAPS}
              renderItem={(g) => (
                <List.Item style={{ padding: '12px 20px' }}>
                  <List.Item.Meta
                    title={
                      <Space size={8}>
                        <Badge color={GAP_DOT[g.dot] ?? g.dot} />
                        <span style={{ fontSize: 13 }}>{g.title}</span>
                      </Space>
                    }
                    description={<span style={{ fontSize: 12, lineHeight: 1.6 }}>{g.body}</span>}
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
