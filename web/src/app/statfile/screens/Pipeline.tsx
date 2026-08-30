// Medallion pipeline — reimagined as a native Ant Design page: Bronze/Silver/
// Gold as a Card row with Badge freshness, per-layer table inventories as
// compact Tables with Statistic footers, and the transformation contract as a
// Card-framed Table with coverage Tags. Live: /catalog for the layer cards
// (tables, row counts, last-altered); /pipeline/contract for the Bronze→Silver
// contract with live per-column coverage. Demo fixtures when the warehouse is
// cold.
import type { CSSProperties } from 'react';
import { Badge, Card, Col, Row, Statistic, Table, Tag, Typography } from 'antd';
import { medallionFrom, useCatalog, usePipelineContract } from '../api';
import { CONTRACT } from '../data';

const { Text, Paragraph } = Typography;

const MONO: CSSProperties = { fontFamily: "ui-monospace,'SFMono-Regular',Menlo,monospace" };

// Layer freshness → Badge semantics.
const layerBadge = (status: string): 'success' | 'processing' | 'warning' =>
  status === 'Fresh' ? 'success' : status === 'Rebuilding' ? 'processing' : 'warning';

// Contract coverage intensities → Tag colors by meaning: full coverage is
// settled, near-full needs a glance, a real gap demands attention.
const covColor = (tagClass: string) =>
  tagClass === 'tag-neutral' ? 'green' : tagClass === 'tag-accent' ? 'red' : 'orange';

interface ContractRow {
  field: string; silver: string; gw: string; xform: string;
  rule: string; cov: string; tagClass: string;
}

export function PipelineScreen() {
  const catQ = useCatalog();
  const medallion = medallionFrom(catQ.data?.schemas);

  const conQ = usePipelineContract();
  const liveCon = (conQ.data?.row_count ?? 0) > 0;
  const contract: ContractRow[] = liveCon
    ? conQ.data!.columns.map((c) => ({
        field: c.name.toLowerCase(),
        silver: `tspr_premium_staging.${c.name.toLowerCase()}`,
        gw: c.source ?? '—',
        xform: c.transform ?? '—',
        rule: c.rule ?? (c.domain_encoded ? 'domain-encoded' : '—'),
        cov: c.coverage_pct != null ? `${c.coverage_pct}%` : '—',
        tagClass: c.coverage_pct == null ? 'tag-outline'
          : c.coverage_pct >= 99.95 ? 'tag-neutral'
          : c.coverage_pct >= 97 ? 'tag-outline' : 'tag-accent',
      }))
    : CONTRACT;

  const layerColumns = [
    {
      title: 'Table', dataIndex: 'name', key: 'name', ellipsis: true,
      render: (v: string) => <span style={{ ...MONO, fontSize: 11.5 }}>{v}</span>,
    },
    {
      title: 'Rows', dataIndex: 'rows', key: 'rows', align: 'right' as const, width: 80,
      render: (v: string) => <Text type="secondary" style={{ ...MONO, fontSize: 11 }}>{v}</Text>,
    },
  ];

  const contractColumns = [
    {
      title: 'Stat field', dataIndex: 'field', key: 'field',
      render: (v: string) => <span style={{ ...MONO, fontSize: 12 }}>{v}</span>,
    },
    {
      title: 'Silver column', dataIndex: 'silver', key: 'silver', ellipsis: true,
      render: (v: string) => <Text type="secondary" style={{ ...MONO, fontSize: 12 }}>{v}</Text>,
    },
    {
      title: 'Guidewire source', dataIndex: 'gw', key: 'gw', ellipsis: true,
      render: (v: string) => <Text type="secondary" style={{ ...MONO, fontSize: 12 }}>{v}</Text>,
    },
    { title: 'Transform', dataIndex: 'xform', key: 'xform' },
    {
      title: 'Governing rule', dataIndex: 'rule', key: 'rule', width: 150,
      render: (v: string) => <Text code style={{ fontSize: 11.5 }}>{v}</Text>,
    },
    {
      title: 'Coverage', dataIndex: 'cov', key: 'cov', width: 100,
      render: (v: string, c: ContractRow) => <Tag color={covColor(c.tagClass)}>{v}</Tag>,
    },
  ];

  return (
    <div>
      {/* ── medallion layers ────────────────────────────────────────────── */}
      <Row gutter={[16, 16]}>
        {medallion.map((m) => (
          <Col key={m.name} xs={24} xl={8}>
            <Card
              title={m.name}
              extra={<Badge status={layerBadge(m.status)} text={m.status} />}
              style={{ height: '100%' }}
            >
              <Paragraph type="secondary" style={{ fontSize: 12.5, lineHeight: 1.6, marginBottom: 12 }}>
                {m.desc}
              </Paragraph>
              <Table
                rowKey="name"
                dataSource={m.tables.map(([name, rows]) => ({ name, rows }))}
                columns={layerColumns}
                pagination={false} size="small" showHeader={false}
              />
              <Row gutter={16} style={{ marginTop: 14 }}>
                <Col span={12}>
                  <Statistic
                    title={<Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Tables</Text>}
                    value={m.latency}
                    valueStyle={{ ...MONO, fontSize: 15 }}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title={<Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Last altered</Text>}
                    value={m.last}
                    valueStyle={{ ...MONO, fontSize: 15 }}
                  />
                </Col>
              </Row>
            </Card>
          </Col>
        ))}
      </Row>

      {/* ── transformation contract ─────────────────────────────────────── */}
      <Card
        style={{ marginTop: 16 }}
        title={liveCon
          ? <>Transformation contract — Silver <span style={{ ...MONO, fontSize: 13, fontWeight: 400 }}>tspr_premium_staging</span></>
          : <>Transformation contract — Gold <span style={{ ...MONO, fontSize: 13, fontWeight: 400 }}>tx_ho_stat_record</span></>}
        extra={liveCon
          ? <Text type="secondary" style={{ fontSize: 13 }}>live · coverage over {conQ.data!.row_count.toLocaleString('en-US')} staged records</Text>
          : <Tag color="orange" title="warehouse offline — showing design fixtures">demo data</Tag>}
        styles={{ body: { padding: 0 } }}
      >
        <Table
          rowKey="field"
          dataSource={contract}
          columns={contractColumns}
          pagination={false} size="middle"
        />
      </Card>
    </div>
  );
}
