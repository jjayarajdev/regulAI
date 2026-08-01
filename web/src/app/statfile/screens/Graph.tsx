// Knowledge graph — lineage chain with satellite nodes + detail rail.
// Live: pick a rule from the canon (/kg/rules), render its Neo4j neighborhood
// (/kg/neighborhood/{id}) laid out in the design's columns:
// Clause/Section → Rule → CodeValue → other nodes. Demo chain when the KG is
// unreachable.
import { useMemo, useState } from 'react';
import { Blueprint } from '../Blueprint';
import { useKgRules, useNeighborhood } from '../api';
import { ACC, GRAPH_NODES } from '../data';
import type { KgGraphEdge, KgGraphNode } from '../../../api/types';

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
const COL_LABEL: Record<string, number> = { Citation: 0, Section: 0, root: 1, Rule: 1, CodeValue: 2 };

function Edge({ x1, y1, x2, y2, on }: { x1: number; y1: number; x2: number; y2: number; on?: boolean }) {
  return (
    <path
      d={`M${x1} ${y1} C${x1 + 34} ${y1} ${x2 - 34} ${y2} ${x2} ${y2}`}
      fill="none" stroke={on ? ACC : 'rgba(29,31,32,.22)'} strokeWidth={on ? 1.6 : 1}
    />
  );
}

function NodeBox({ n, active, onSelect }: { n: Box; active: boolean; onSelect?: () => void }) {
  return (
    <g transform={`translate(${n.x},${n.y})`} style={{ cursor: onSelect ? 'pointer' : 'default' }} onClick={onSelect}>
      <rect width={n.w} height={H} fill={active ? ACC : 'rgba(242,242,243,.92)'} stroke={active ? ACC : 'rgba(29,31,32,.3)'} strokeWidth={1} />
      <text x={9} y={15} fontSize={12} fontFamily="ui-monospace, Menlo, monospace" fill={active ? '#f2f2f3' : '#1d1f20'}>
        {n.t.length > 28 ? n.t.slice(0, 27) + '…' : n.t}
      </text>
      <text x={9} y={27} fontSize={9.5} letterSpacing=".06em" fill={active ? 'rgba(242,242,243,.8)' : 'rgba(29,31,32,.5)'}>
        {n.s.length > 34 ? n.s.slice(0, 33) + '…' : n.s}
      </text>
    </g>
  );
}

export function GraphScreen() {
  const rulesQ = useKgRules();
  const executable = useMemo(
    () => (rulesQ.data?.rules ?? []).filter((r) => r.executable && r.currently_active),
    [rulesQ.data],
  );
  const [ruleIdx, setRuleIdx] = useState(0);
  const centerRule = executable[Math.min(ruleIdx, Math.max(0, executable.length - 1))];
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
          s: n.group === 'root' ? 'Rule · canon' : n.group,
        });
      });
    });
    return { boxes, edges, height };
  }, [live, nbQ.data]);

  // Detail rail content.
  const detail = useMemo(() => {
    if (!live) {
      const n = GRAPH_NODES[selId ?? 'fld-terr'] ?? GRAPH_NODES['fld-terr'];
      return n;
    }
    const node = nbQ.data!.nodes.find((n) => n.id === selId) ?? nbQ.data!.nodes.find((n) => n.group === 'root')!;
    const degree = nbQ.data!.edges.filter((e) => e.from === node.id || e.to === node.id).length;
    return {
      kind: node.group === 'root' ? 'Derived rule' : node.group,
      title: node.label,
      desc: node.title.split('\n').slice(1).join('\n') || node.label,
      props: [
        ['Node id', node.id.slice(-12)],
        ['Group', node.group],
        ['Connections', String(degree)],
        ...(centerRule && node.group === 'root'
          ? [['Severity', centerRule.severity], ['Version', String(centerRule.version)], ['Status', centerRule.status]]
          : []),
      ] as Array<[string, string]>,
      impact: `Connected to ${degree} node${degree === 1 ? '' : 's'} in the canon. ` +
        'A change here re-versions the rule and re-opens the approval gate.',
    };
  }, [live, nbQ.data, selId, centerRule]);

  return (
    <div className="sc" style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 30, alignItems: 'start' }}>
      <div>
        {executable.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <span className="k">Rule</span>
            <span className="mono" style={{ fontSize: 12 }}>{centerRule?.name}</span>
            <span style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
              <button className="btn btn-secondary" disabled={ruleIdx === 0}
                onClick={() => { setRuleIdx((i) => i - 1); setSelId(null); }}>← Prev rule</button>
              <button className="btn btn-secondary" disabled={ruleIdx >= executable.length - 1}
                onClick={() => { setRuleIdx((i) => i + 1); setSelId(null); }}>Next rule →</button>
            </span>
          </div>
        )}
        <Blueprint className="gridwash" style={{ padding: 20 }}>
          <div style={{ display: 'flex', gap: 14, marginBottom: 10 }}>
            {live
              ? ['Clause / Section', '→ Rule', '→ Code value', '→ Related'].map((l) => <span key={l} className="k">{l}</span>)
              : ['Clause', '→ Rule', '→ Stat field', '→ Silver column', '→ Guidewire source'].map((l) => <span key={l} className="k">{l}</span>)}
          </div>
          {live && layout ? (
            <svg viewBox={`0 0 1140 ${layout.height}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
              <g>
                {layout.edges.map((e, i) => {
                  const a = layout.boxes.get(e.from);
                  const b = layout.boxes.get(e.to);
                  if (!a || !b) return null;
                  const [l, r] = a.x <= b.x ? [a, b] : [b, a];
                  return <Edge key={i} x1={l.x + l.w} y1={l.y + H / 2} x2={r.x} y2={r.y + H / 2}
                    on={e.from === nbQ.data!.center || e.to === nbQ.data!.center} />;
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
        </Blueprint>
      </div>

      <aside style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
        <Blueprint style={{ padding: '15px 17px' }}>
          <div className="k">{detail.kind}</div>
          <div style={{ fontFamily: 'var(--font-heading)', fontSize: 21, margin: '4px 0 8px', overflowWrap: 'anywhere' }}>{detail.title}</div>
          <div style={{ fontSize: 13, lineHeight: 1.6, color: 'color-mix(in srgb,var(--color-text) 78%,transparent)', whiteSpace: 'pre-wrap' }}>{detail.desc}</div>
        </Blueprint>
        <Blueprint style={{ padding: '15px 17px' }}>
          <div className="k" style={{ marginBottom: 9 }}>Properties</div>
          {detail.props.map(([k, v]) => (
            <div key={k} style={{ display: 'flex', gap: 10, padding: '5px 0', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)', fontSize: 12.5 }}>
              <span className="muted" style={{ width: 104, flex: 'none' }}>{k}</span>
              <span className="mono" style={{ fontSize: 11.5, overflowWrap: 'anywhere' }}>{v}</span>
            </div>
          ))}
        </Blueprint>
        <Blueprint style={{ padding: '15px 17px' }}>
          <div className="k" style={{ marginBottom: 9 }}>Impact if changed</div>
          <div style={{ fontSize: 12.5, lineHeight: 1.6 }}>{detail.impact}</div>
        </Blueprint>
      </aside>
    </div>
  );
}
