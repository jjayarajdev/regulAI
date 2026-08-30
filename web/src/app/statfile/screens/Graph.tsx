// Knowledge graph — reimagined as a native Ant Design page: rule Select +
// pager in the toolbar, the lineage SVG (layout engine and data wiring
// unchanged) framed in a Card with a column legend, and the node detail rail
// as Cards — Descriptions for properties, mono relationship list, and an
// impact Alert. Live: pick a rule from the canon (/kg/rules), render its
// Neo4j neighborhood (/kg/neighborhood/{id}) laid out in the design's
// columns: Clause/Section → Rule → CodeValue → other nodes. Demo chain when
// the KG is unreachable.
import { useMemo, useState } from 'react';
import { LeftOutlined, RightOutlined } from '@ant-design/icons';
import { Alert, Button, Card, Col, Descriptions, Row, Select, Space, Tag, Typography } from 'antd';
import { useKgRules, useNeighborhood } from '../api';
import { GRAPH_NODES } from '../data';
import type { KgGraphEdge, KgGraphNode } from '../../../api/types';

const { Text, Title, Paragraph } = Typography;

const MONO = "ui-monospace,'SFMono-Regular',Menlo,monospace";
const K: React.CSSProperties = { fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em' };

// Active node/edge color inside the SVG — graph node colors are data, mapped
// to the antd primary.
const ACTIVE = '#1677ff';

interface Box { id?: string; x: number; y: number; w: number; t: string; s: string }

const DEMO_COLS: Box[] = [
  { id: 'cl-432', x: 40, y: 150, w: 150, t: '§4.3.2', s: 'Clause · p.47' },
  { id: 'rl-412', x: 250, y: 150, w: 150, t: 'R-TX-HO-0412', s: 'Rule · 96%' },
  { id: 'fld-terr', x: 460, y: 150, w: 160, t: 'territory_code', s: 'Field · pos 32–33' },
  { id: 'sil-zip', x: 680, y: 150, w: 190, t: 'postal_code', s: 'silver.risk_location' },
  { id: 'gw-loc', x: 930, y: 150, w: 180, t: 'PolicyLocation', s: 'PolicyCenter CDC' },
];

const DEMO_SATS: Box[] = [
  { x: 250, y: 40, w: 150, t: 'R-TX-HO-0418', s: 'Rule · 71% ⚠' },
  { x: 250, y: 262, w: 150, t: 'R-TX-HO-0433', s: 'Rule · 88%' },
  { x: 460, y: 40, w: 160, t: 'wind_excl_ind', s: 'Field · pos 68–69' },
  { x: 460, y: 262, w: 160, t: 'construction_code', s: 'Field · pos 39–40' },
  { x: 680, y: 262, w: 190, t: 'coverage_detail', s: 'silver · 5.9M rows' },
  { x: 930, y: 262, w: 180, t: 'HOPDwelling', s: 'PolicyCenter CDC' },
  { x: 460, y: 372, w: 160, t: 'iso_pl_ho_record', s: 'Gold · ISO projection' },
];

const H = 34;
const COL_X = [40, 300, 560, 820];
const COL_W = [230, 230, 230, 230];
const COL_LABEL: Record<string, number> = {
  Citation: 0, Section: 0, RegulationDocument: 0, StatPlanEdition: 0,
  root: 1, Rule: 1, EndorsementRule: 1, HITLTriggerRule: 1, BulletinOverride: 1,
  CodeList: 2, CodeValue: 2, FieldRequirement: 2, RecordLayout: 2,
};

function Edge({ x1, y1, x2, y2, on }: { x1: number; y1: number; x2: number; y2: number; on?: boolean }) {
  return (
    <path
      d={`M${x1} ${y1} C${x1 + 34} ${y1} ${x2 - 34} ${y2} ${x2} ${y2}`}
      fill="none" stroke={on ? ACTIVE : 'rgba(29,31,32,.22)'} strokeWidth={on ? 1.6 : 1}
    />
  );
}

function NodeBox({ n, active, onSelect }: { n: Box; active: boolean; onSelect?: () => void }) {
  return (
    <g transform={`translate(${n.x},${n.y})`} style={{ cursor: onSelect ? 'pointer' : 'default' }} onClick={onSelect}>
      <rect width={n.w} height={H} rx={4} fill={active ? ACTIVE : 'rgba(242,242,243,.92)'} stroke={active ? ACTIVE : 'rgba(29,31,32,.3)'} strokeWidth={1} />
      <text x={9} y={15} fontSize={12} fontFamily="ui-monospace, Menlo, monospace" fill={active ? '#fff' : '#1d1f20'}>
        {n.t.length > 28 ? n.t.slice(0, 27) + '…' : n.t}
      </text>
      <text x={9} y={27} fontSize={9.5} letterSpacing=".06em" fill={active ? 'rgba(255,255,255,.82)' : 'rgba(29,31,32,.5)'}>
        {/* tail-truncate: the distinguishing part (col ref, layout) is at the end */}
        {n.s.length > 34 ? '…' + n.s.slice(-33) : n.s}
      </text>
    </g>
  );
}

export function GraphScreen() {
  const rulesQ = useKgRules();
  // Every rule in the canon — executable edits first, then by name — so the
  // whole rulebook's lineage is explorable, not just the 11 edits.
  const pickable = useMemo(
    () => [...(rulesQ.data?.rules ?? [])].sort((a, b) =>
      Number(b.executable) - Number(a.executable) || a.name.localeCompare(b.name)),
    [rulesQ.data],
  );
  const [ruleIdx, setRuleIdx] = useState(0);
  const centerRule = pickable[Math.min(ruleIdx, Math.max(0, pickable.length - 1))];
  const nbQ = useNeighborhood(centerRule?.id ?? null);
  const live = !!(nbQ.data && nbQ.data.nodes.length > 0);

  const [selId, setSelId] = useState<string | null>(null);

  // Lay the live neighborhood out in columns by node group.
  const layout = useMemo(() => {
    if (!live) return null;
    const nodes: KgGraphNode[] = nbQ.data!.nodes;
    const edges: KgGraphEdge[] = nbQ.data!.edges;
    const cols: KgGraphNode[][] = [[], [], [], []];
    for (const n of nodes) cols[COL_LABEL[n.group] ?? 3].push(n);
    const boxes = new Map<string, Box>();
    const maxRows = Math.max(...cols.map((c) => c.length), 1);
    const height = Math.max(430, maxRows * 56 + 80);
    cols.forEach((col, ci) => {
      const top = (height - col.length * 56) / 2;
      col.forEach((n, ri) => {
        boxes.set(n.id, {
          id: n.id, x: COL_X[ci], y: top + ri * 56, w: COL_W[ci],
          t: n.label,
          s: n.group === 'root' ? 'Rule · canon' : (n.sublabel ?? n.group),
        });
      });
    });
    return { boxes, edges, height };
  }, [live, nbQ.data]);

  // Detail rail content.
  const detail = useMemo(() => {
    if (!live) {
      const n = GRAPH_NODES[selId ?? 'fld-terr'] ?? GRAPH_NODES['fld-terr'];
      return { ...n, rels: [] as string[] };
    }
    const nodes = nbQ.data!.nodes;
    const node = nodes.find((n) => n.id === selId) ?? nodes.find((n) => n.group === 'root')!;
    const byId = new Map(nodes.map((n) => [n.id, n]));
    // The selected node's relationships, with direction and type spelled out.
    const rels = nbQ.data!.edges
      .filter((e) => e.from === node.id || e.to === node.id)
      .map((e) => {
        const out = e.from === node.id;
        const other = byId.get(out ? e.to : e.from);
        return other ? `${out ? '→' : '←'} ${e.label} · ${other.label}` : null;
      })
      .filter((s): s is string => s != null);
    const isRoot = node.group === 'root';
    const desc = node.title.split('\n').slice(1).join('\n');
    const props: Array<[string, string | null | undefined]> = isRoot && centerRule
      ? [
          ['Rule id', centerRule.id.slice(0, 8)],
          ['Jurisdiction', centerRule.jurisdiction_code],
          ['Kind', centerRule.rule_kind],
          ['Confidence', centerRule.confidence != null ? Math.round(centerRule.confidence * 100) + '%' : null],
          ['Severity', centerRule.severity],
          ['Version', String(centerRule.version)],
          ['Status', centerRule.status],
          ['Connections', String(rels.length)],
        ]
      : [
          ['Type', node.group],
          ['Connections', String(rels.length)],
        ];
    return {
      kind: isRoot ? 'Derived rule' : node.group,
      title: node.label,
      desc: desc && desc !== node.label ? desc : '',
      props: props.filter((p): p is [string, string] => p[1] != null && p[1] !== ''),
      rels: rels.slice(0, 10),
      impact: `Connected to ${rels.length} node${rels.length === 1 ? '' : 's'} in the canon. ` +
        'A change here re-versions the rule and re-opens the approval gate.',
    };
  }, [live, nbQ.data, selId, centerRule]);

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} xl={17} style={{ minWidth: 0 }}>
        {pickable.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Text type="secondary" style={K}>Rule</Text>
            <Select
              value={ruleIdx}
              onChange={(v) => { setRuleIdx(v); setSelId(null); }}
              showSearch
              optionFilterProp="label"
              style={{ flex: 1, minWidth: 0 }}
              options={pickable.map((r, i) => ({
                value: i,
                label: (r.executable ? '⚙ ' : '') + (r.jurisdiction_code ? r.jurisdiction_code.replace('US-', '') + ' · ' : '') + r.name,
              }))}
            />
            <Space size={6}>
              <Button icon={<LeftOutlined />} disabled={ruleIdx === 0}
                onClick={() => { setRuleIdx((i) => i - 1); setSelId(null); }}>Prev</Button>
              <Button disabled={ruleIdx >= pickable.length - 1}
                onClick={() => { setRuleIdx((i) => i + 1); setSelId(null); }}>Next <RightOutlined /></Button>
            </Space>
          </div>
        )}
        <Card
          title={
            <Space size={14} wrap>
              {(live
                ? ['Source document', '→ Rule', '→ Codes & fields', '→ Related']
                : ['Clause', '→ Rule', '→ Stat field', '→ Silver column', '→ Guidewire source']
              ).map((l) => (
                <Text key={l} type="secondary" style={{ ...K, fontWeight: 400 }}>{l}</Text>
              ))}
            </Space>
          }
          extra={
            !live ? (
              <Tag color="orange" title="knowledge graph unreachable — showing the design chain">demo data</Tag>
            ) : nbQ.data?.truncated && Object.keys(nbQ.data.truncated).length > 0 ? (
              <Text type="secondary" style={{ ...K, opacity: 0.7 }}>
                capped: {Object.entries(nbQ.data.truncated).map(([l, n]) => `+${n} ${l}`).join(' · ')}
              </Text>
            ) : null
          }
        >
          {live && layout ? (
            <svg viewBox={`0 0 1140 ${layout.height}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
              <g>
                {layout.edges.map((e, i) => {
                  const a = layout.boxes.get(e.from);
                  const b = layout.boxes.get(e.to);
                  if (!a || !b) return null;
                  const [l, r] = a.x <= b.x ? [a, b] : [b, a];
                  const focus = selId ?? nbQ.data!.center;
                  return <Edge key={i} x1={l.x + l.w} y1={l.y + H / 2} x2={r.x} y2={r.y + H / 2}
                    on={e.from === focus || e.to === focus} />;
                })}
              </g>
              <g>
                {[...layout.boxes.values()].map((b) => (
                  <NodeBox key={b.id} n={b} active={b.id === (selId ?? nbQ.data!.center)} onSelect={() => setSelId(b.id!)} />
                ))}
              </g>
            </svg>
          ) : (
            <svg viewBox="0 0 1140 430" style={{ width: '100%', height: 'auto', display: 'block' }}>
              <g>
                <Edge x1={190} y1={167} x2={250} y2={57} />
                <Edge x1={190} y1={167} x2={250} y2={279} />
                <Edge x1={400} y1={57} x2={460} y2={57} />
                <Edge x1={400} y1={279} x2={460} y2={279} />
                <Edge x1={620} y1={57} x2={680} y2={167} />
                <Edge x1={620} y1={279} x2={680} y2={279} />
                <Edge x1={870} y1={279} x2={930} y2={279} />
                <Edge x1={870} y1={167} x2={870} y2={279} />
                <Edge x1={620} y1={167} x2={620} y2={389} />
                {DEMO_COLS.slice(0, -1).map((a, i) => {
                  const b = DEMO_COLS[i + 1];
                  return <Edge key={a.t} x1={a.x + a.w} y1={a.y + H / 2} x2={b.x} y2={b.y + H / 2} on />;
                })}
              </g>
              <g>{DEMO_SATS.map((s) => <NodeBox key={s.t} n={s} active={false} />)}</g>
              <g>{DEMO_COLS.map((c) => (
                <NodeBox key={c.t} n={c} active={c.id === (selId ?? 'fld-terr')} onSelect={() => setSelId(c.id!)} />
              ))}</g>
            </svg>
          )}
        </Card>
      </Col>

      {/* ── detail rail ──────────────────────────────────────────────────── */}
      <Col xs={24} xl={7}>
        <Card>
          <Text type="secondary" style={K}>{detail.kind}</Text>
          <Title level={4} style={{ margin: '4px 0 8px', overflowWrap: 'anywhere' }}>{detail.title}</Title>
          {detail.desc && (
            <Paragraph style={{ fontSize: 13, lineHeight: 1.6, whiteSpace: 'pre-wrap', marginBottom: 0 }}>
              {detail.desc}
            </Paragraph>
          )}
        </Card>
        <Card title="Properties" style={{ marginTop: 16 }}>
          <Descriptions
            size="small"
            column={1}
            colon={false}
            styles={{ label: { width: 110 } }}
            items={detail.props.map(([k, v]) => ({
              key: k,
              label: <Text type="secondary" style={{ fontSize: 12 }}>{k}</Text>,
              children: <span style={{ fontFamily: MONO, fontSize: 11.5, overflowWrap: 'anywhere' }}>{v}</span>,
            }))}
          />
        </Card>
        {detail.rels.length > 0 && (
          <Card title="Relationships" style={{ marginTop: 16 }}>
            {detail.rels.map((r, i) => (
              <div key={i} style={{
                fontFamily: MONO, fontSize: 11, padding: '4px 0', lineHeight: 1.5,
                borderBottom: '1px solid rgba(5,5,5,0.06)', overflowWrap: 'anywhere',
              }}>
                {r}
              </div>
            ))}
          </Card>
        )}
        <Alert
          type="info"
          showIcon
          style={{ marginTop: 16 }}
          message="Impact if changed"
          description={<span style={{ fontSize: 12.5, lineHeight: 1.6 }}>{detail.impact}</span>}
        />
      </Col>
    </Row>
  );
}
