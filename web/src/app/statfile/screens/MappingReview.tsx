// Mapping review — "agent proposes, human governs" for schema mappings,
// reimagined as a native Ant Design page: mapping specs as a selectable
// Card+List rail, verdict KPIs as Statistic-style cards, every proposal in an
// antd Table (confidence as Badge dots, verdicts as Tags), and the
// proposed-vs-accepted SQL diff with the reviewer's reason in a right-side
// Drawer. Live: /mappings + /mapping/{name} (file-backed on the server —
// works on any warehouse).
import { useMemo, useState, type CSSProperties } from 'react';
import {
  Badge, Button, Card, Col, Divider, Drawer, Empty, Input, List, Row,
  Skeleton, Space, Table, Tag, Typography,
} from 'antd';
import { useMappingDetail, useMappings } from '../api';
import type { MappingColumn, MappingDetail, MappingSummary, MappingTransformType } from '../../../api/types';

const { Text, Title, Paragraph } = Typography;

const MONO: CSSProperties = { fontFamily: "ui-monospace,'SFMono-Regular',Menlo,monospace" };
const KICKER: CSSProperties = { fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em' };

const fmt = (n: number) => n.toLocaleString('en-US');
const stamp = (s?: string | null) => (s ? s.replace('T', ' ').slice(0, 16) : '—');

// Confidence banding: high reads quiet, the band the reviewer must look at
// reads loud — same palette logic as the severity badges elsewhere.
const confBadge = (c: number): 'success' | 'warning' | 'error' =>
  c >= 0.9 ? 'success' : c >= 0.7 ? 'warning' : 'error';

// transform kind → Tag color by meaning: direct is plain, lookup is an
// active join (blue), composite is the special multi-source case (purple).
const XFORM_COLOR: Record<MappingTransformType, string | undefined> = {
  direct: undefined, lookup: 'blue', composite: 'purple',
};

const sqlBlock: CSSProperties = {
  ...MONO, fontSize: 11, lineHeight: 1.65, padding: '9px 11px', whiteSpace: 'pre-wrap',
  overflowWrap: 'anywhere', margin: 0, background: 'rgba(5,5,5,0.04)', borderRadius: 6,
};

// Overridden rows first (the story), then alphabetical.
const sortCols = (cols: MappingColumn[]): MappingColumn[] =>
  [...cols].sort((a, b) =>
    Number(b.overridden) - Number(a.overridden)
    || a.target_column.localeCompare(b.target_column));

function ConfidenceCell({ c }: { c: number }) {
  return (
    <Space size={7}>
      <span style={{ ...MONO, fontSize: 11.5 }}>{c.toFixed(2)}</span>
      <Badge status={confBadge(c)} />
    </Space>
  );
}

// One side of the proposed/accepted diff — the accepted side carries the
// primary left-border, the discarded proposal reads muted.
function SqlCol({ label, sql, accepted }: { label: string; sql: string; accepted?: boolean }) {
  return (
    <div style={accepted
      ? { borderLeft: '3px solid #1677ff', paddingLeft: 12 }
      : { opacity: 0.62 }}>
      <Text type="secondary" style={{ ...KICKER, display: 'block', marginBottom: 7 }}>{label}</Text>
      <pre style={sqlBlock}>{sql}</pre>
    </div>
  );
}

function ColumnDetailBody({ col }: { col: MappingColumn }) {
  return (
    <>
      {/* the agent's reasoning, quoted */}
      {col.rationale && (
        <div style={{ marginBottom: 16, paddingLeft: 12, borderLeft: '3px solid rgba(5,5,5,0.15)' }}>
          <Text type="secondary" style={{ ...KICKER, display: 'block', marginBottom: 5 }}>Agent rationale</Text>
          <Paragraph italic type="secondary" style={{ fontSize: 12.5, lineHeight: 1.6, marginBottom: 0 }}>
            {col.rationale}
          </Paragraph>
        </div>
      )}

      {col.overridden && col.proposed_sql ? (
        <>
          {/* the money shot: what the agent wrote vs what the human shipped */}
          <Row gutter={[20, 16]}>
            <Col xs={24} md={12}>
              <SqlCol label="Proposed · agent" sql={col.proposed_sql} />
            </Col>
            <Col xs={24} md={12}>
              <SqlCol label="Accepted · review" sql={col.accepted_sql} accepted />
            </Col>
          </Row>
          {col.override_reason && (
            <Card
              size="small"
              style={{ marginTop: 16, borderColor: '#ffd591', background: '#fffbe6' }}
            >
              <Text type="secondary" style={{ ...KICKER, display: 'block', marginBottom: 5 }}>Reviewer</Text>
              <div style={{ fontSize: 12.5, lineHeight: 1.6 }}>{col.override_reason}</div>
            </Card>
          )}
        </>
      ) : (
        <>
          <SqlCol label="Accepted · as proposed" sql={col.accepted_sql} accepted />
          {col.review_note && (
            <Card size="small" style={{ marginTop: 16, background: 'rgba(5,5,5,0.02)' }}>
              <Text type="secondary" style={{ ...KICKER, display: 'block', marginBottom: 5 }}>Review note</Text>
              <div style={{ fontSize: 12.5, lineHeight: 1.6 }}>{col.review_note}</div>
            </Card>
          )}
        </>
      )}
    </>
  );
}

// Compiled SQL + unmapped source columns — the artifact footer.
function CompiledFooter({ d }: { d: MappingDetail }) {
  const [openSql, setOpenSql] = useState(false);
  const [allUnmapped, setAllUnmapped] = useState(false);
  const unmapped = (d.unmapped_source_columns ?? [])
    .map((u) => (typeof u === 'string' ? { name: u, reason: undefined } : u));
  const shown = allUnmapped ? unmapped : unmapped.slice(0, 24);

  return (
    <Card
      size="small"
      title="Compiled SQL"
      extra={
        <Space size={10}>
          <Text type="secondary" style={{ ...MONO, fontSize: 10.5 }}>
            select_sql · {d.compiled ? `compiled ${stamp(d.compiled_at)}` : 'not compiled'}
          </Text>
          {d.compiled_sql && (
            <Button size="small" onClick={() => setOpenSql((v) => !v)}>
              {openSql ? 'Hide' : 'Show'}
            </Button>
          )}
        </Space>
      }
    >
      {openSql && d.compiled_sql ? (
        <pre style={{ ...sqlBlock, maxHeight: 340, overflow: 'auto', border: '1px solid rgba(5,5,5,0.08)' }}>
          {d.compiled_sql}
        </pre>
      ) : (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {d.compiled_sql ? 'the compiled select_sql is collapsed — Show expands it' : 'no compiled select_sql on disk'}
        </Text>
      )}

      {unmapped.length > 0 && (
        <>
          <Divider style={{ margin: '14px 0 10px' }} />
          <Text type="secondary" style={{ ...KICKER, display: 'block', marginBottom: 8 }}>
            Unmapped source columns · {unmapped.length} (deliberate — CDC metadata, join keys, rating variables)
          </Text>
          <Space size={4} wrap>
            {shown.map((u) => (
              <Tag key={u.name} title={u.reason} style={{ ...MONO, fontSize: 10, marginInlineEnd: 0, color: 'rgba(0,0,0,0.45)' }}>
                {u.name}
              </Tag>
            ))}
            {unmapped.length > 24 && (
              <Button type="link" size="small" style={{ fontSize: 10.5, padding: '0 4px' }}
                onClick={() => setAllUnmapped((v) => !v)}>
                {allUnmapped ? 'show fewer' : `+${unmapped.length - 24} more`}
              </Button>
            )}
          </Space>
        </>
      )}
    </Card>
  );
}

// ── mapping master rail — Card + selectable List, filterable at scale ──────
function MappingRail({ mappings, value, onChange }: {
  mappings: MappingSummary[];
  value: string | null;
  onChange: (name: string) => void;
}) {
  const [q, setQ] = useState('');
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return mappings;
    return mappings.filter((m) =>
      `${m.name} ${m.source_label} ${m.target}`.toLowerCase().includes(needle));
  }, [mappings, q]);

  return (
    <Card title="Reviewed mappings" size="small" styles={{ body: { padding: 0 } }}>
      {mappings.length > 6 && (
        <div style={{ padding: '8px 12px 0' }}>
          <Input allowClear size="small" placeholder="filter…"
            value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      )}
      <List
        size="small"
        dataSource={filtered}
        locale={{ emptyText: 'no matches' }}
        style={{ maxHeight: 'max(360px, calc(100vh - 320px))', overflow: 'auto' }}
        renderItem={(m) => {
          const on = m.name === value;
          return (
            <List.Item
              onClick={() => onChange(m.name)}
              style={{
                cursor: 'pointer', paddingInline: 13,
                borderInlineStart: `3px solid ${on ? '#1677ff' : 'transparent'}`,
                background: on ? 'rgba(22,119,255,0.06)' : undefined,
              }}
            >
              <List.Item.Meta
                title={
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ ...MONO, flex: 1, minWidth: 0, fontSize: 12.5, fontWeight: on ? 600 : 400 }}>
                      {m.name}
                    </span>
                    <Tag color={m.compiled ? 'green' : undefined} style={{ marginInlineEnd: 0 }}>
                      {m.compiled ? 'Compiled' : 'Not compiled'}
                    </Tag>
                  </div>
                }
                description={
                  <Text type="secondary" style={{ ...MONO, fontSize: 10.5 }}>
                    {m.source_label} → {m.target}
                  </Text>
                }
              />
            </List.Item>
          );
        }}
      />
    </Card>
  );
}

export function MappingReviewScreen() {
  const listQ = useMappings();
  const mappings = listQ.data?.mappings ?? [];

  const [selName, setSelName] = useState<string | null>(null);
  const M = mappings.find((m) => m.name === selName) ?? mappings[0];

  const detailQ = useMappingDetail(M?.name ?? null);
  const d = detailQ.data;
  const loading = listQ.isPending || (!!M && detailQ.isPending);

  // Row click opens the proposal detail in a right-side drawer (overrides
  // sort first, so the interesting rows lead the table).
  const [selCol, setSelCol] = useState<string | null>(null);
  const cols = d ? sortCols(d.columns) : [];
  const activeCol = cols.find((c) => c.target_column === selCol) ?? null;

  const agentModel = (d?.proposed_by ?? M?.proposed_by ?? '—').split(':').pop() ?? '—';
  const kpis = d ? [
    { label: 'Columns mapped', value: String(d.columns.length), note: d.target_table.split('.').slice(-2).join('.'), accent: false },
    { label: 'Proposed by agent', value: agentModel, note: `${d.tokens != null ? fmt(d.tokens) : '—'} tokens · one shot`, accent: false },
    { label: 'Overridden in review', value: String(d.overridden), note: 'human corrections carried to compile', accent: d.overridden > 0 },
    { label: 'Avg confidence', value: d.avg_confidence != null ? d.avg_confidence.toFixed(2) : '—', note: `${d.needs_review_flags} self-flagged for review`, accent: false },
  ] : [];

  const relation = (d?.source_relation ?? '').replace(/\s+/g, ' ');

  const columns = [
    {
      title: 'Target field', dataIndex: 'target_column', key: 'target',
      render: (v: string) => <span style={{ ...MONO, fontSize: 11.5 }}>{v}</span>,
    },
    {
      title: 'Source', dataIndex: 'source_column', key: 'source',
      render: (v: string | null) => v
        ? <span style={{ ...MONO, fontSize: 11.5 }}>{v}</span>
        : <Text type="secondary" style={{ fontSize: 11.5 }}>constant</Text>,
    },
    {
      title: 'Transform', dataIndex: 'transform_type', key: 'xform', width: 120,
      render: (v: MappingTransformType) => <Tag color={XFORM_COLOR[v]}>{v}</Tag>,
    },
    {
      title: 'Confidence', dataIndex: 'confidence', key: 'conf', width: 120,
      render: (c: number) => <ConfidenceCell c={c} />,
    },
    {
      title: 'Review', key: 'review', width: 190,
      render: (_: unknown, c: MappingColumn) => (
        <Space size={8}>
          <Tag color={c.overridden ? 'orange' : 'green'}>
            {c.overridden ? 'Overridden' : 'Accepted'}
          </Tag>
          {c.needs_review && (
            <Text type="secondary" style={{ ...MONO, fontSize: 10 }}>⚑ flagged</Text>
          )}
        </Space>
      ),
    },
  ];

  return (
    <Row gutter={[16, 16]} wrap={false} align="top">
      {/* ── mapping master list — compact, searchable, scales with specs ── */}
      <Col flex="300px" style={{ minWidth: 0 }}>
        <MappingRail
          mappings={mappings}
          value={M?.name ?? null}
          onChange={(id) => { setSelName(id); setSelCol(null); }}
        />
      </Col>

      {/* ── proposals, verdicts, diffs ─────────────────────────────────── */}
      <Col flex="auto" style={{ minWidth: 0 }}>
        {listQ.isPending && <Text type="secondary" style={KICKER}>loading mappings…</Text>}
        {!listQ.isPending && mappings.length === 0 && (
          <Text type="secondary" style={KICKER}>no reviewed mappings on disk yet</Text>
        )}
        {M && (
          <>
            <Space size={10} align="baseline" wrap style={{ marginBottom: 4 }}>
              <Title level={4} style={{ margin: 0 }}>{M.source_label} → {M.target}</Title>
              <Text type="secondary" style={KICKER}>every proposal, its confidence, and what review changed</Text>
            </Space>
            {M.review_summary && (
              <Paragraph type="secondary" style={{ fontSize: 12.5, lineHeight: 1.65, maxWidth: '92ch', marginBottom: 16 }}>
                {M.review_summary}
              </Paragraph>
            )}
          </>
        )}

        {loading && (
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            {[0, 1, 2, 3].map((i) => (
              <Col xs={12} xl={6} key={i}>
                <Card size="small">
                  <Skeleton active title={false} paragraph={{ rows: 2 }} />
                </Card>
              </Col>
            ))}
          </Row>
        )}

        {!loading && !d && !listQ.isPending && (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            style={{ maxWidth: 520, marginTop: 32 }}
            description={
              <Text type="secondary" style={{ fontSize: 13, lineHeight: 1.6 }}>
                No reviewed mappings on disk yet — run the mapper's propose + review flow to
                materialize a spec, then this screen shows every proposal and its verdict.
              </Text>
            }
          />
        )}

        {!loading && d && (
          <>
            {/* KPI row — the review verdict at a glance */}
            <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
              {kpis.map((k) => (
                <Col xs={12} xl={6} key={k.label}>
                  <Card size="small">
                    <Text type="secondary" style={KICKER}>{k.label}</Text>
                    <div style={{
                      fontSize: 26, lineHeight: 1.2, marginTop: 4,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      color: k.accent ? '#fa8c16' : undefined,
                    }}>
                      {k.value}
                    </div>
                    <Text type="secondary" ellipsis style={{ display: 'block', fontSize: 11, marginTop: 2 }}>
                      {k.note}
                    </Text>
                  </Card>
                </Col>
              ))}
            </Row>

            {/* provenance strip */}
            <div style={{ ...MONO, fontSize: 10.5, lineHeight: 1.7, marginBottom: 16, display: 'flex', gap: 18, flexWrap: 'wrap' }}>
              <Text
                type="secondary"
                title={d.source_relation + (d.source_filter ? `\nWHERE ${d.source_filter}` : '')}
                style={{ fontSize: 10.5, maxWidth: 480, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
              >
                src {relation}
              </Text>
              <Text type="secondary" style={{ fontSize: 10.5 }}>reviewed {d.reviewed_by ?? '—'}</Text>
              <Text type="secondary" style={{ fontSize: 10.5 }}>compiled {stamp(d.compiled_at)}</Text>
            </div>

            {/* column table — row click opens the proposal detail drawer */}
            <Card size="small" style={{ marginBottom: 16 }} styles={{ body: { padding: 0 } }}>
              <Table
                rowKey="target_column"
                dataSource={cols}
                columns={columns}
                pagination={false} size="middle"
                onRow={(c) => ({ onClick: () => setSelCol(c.target_column), style: { cursor: 'pointer' } })}
              />
            </Card>

            {/* proposal detail — agent proposes, human governs */}
            <Drawer
              open={!!activeCol}
              onClose={() => setSelCol(null)}
              width={760}
              title={
                <div>
                  <Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>
                    mapping proposal · agent proposes, human governs
                  </Text>
                  <div style={{ ...MONO, fontSize: 16 }}>{activeCol?.target_column}</div>
                </div>
              }
              extra={activeCol && (
                <Space size={6}>
                  <Tag color={XFORM_COLOR[activeCol.transform_type]}>{activeCol.transform_type}</Tag>
                  <Tag color={activeCol.overridden ? 'orange' : 'green'}>
                    {activeCol.overridden ? 'Overridden' : 'Accepted'}
                  </Tag>
                  {activeCol.needs_review && (
                    <Text type="secondary" style={{ ...MONO, fontSize: 10.5 }}>⚑ flagged</Text>
                  )}
                  <ConfidenceCell c={activeCol.confidence} />
                </Space>
              )}
            >
              {activeCol && <ColumnDetailBody col={activeCol} />}
            </Drawer>

            <CompiledFooter d={d} />
          </>
        )}
      </Col>
    </Row>
  );
}
