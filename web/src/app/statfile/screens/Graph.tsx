// Knowledge graph — SVG lineage chain (clause → rule → field → silver →
// Guidewire) with satellite nodes, plus the selected node's detail rail.
import { useState } from 'react';
import { Blueprint } from '../Blueprint';
import { ACC, GRAPH_NODES } from '../data';

interface Box { id?: string; x: number; y: number; w: number; t: string; s: string }

const COLS: Box[] = [
  { id: 'cl-432', x: 40, y: 150, w: 150, t: '§4.3.2', s: 'Clause · p.47' },
  { id: 'rl-412', x: 250, y: 150, w: 150, t: 'R-TX-HO-0412', s: 'Rule · 96%' },
  { id: 'fld-terr', x: 460, y: 150, w: 160, t: 'territory_code', s: 'Field · pos 32–33' },
  { id: 'sil-zip', x: 680, y: 150, w: 190, t: 'postal_code', s: 'silver.risk_location' },
  { id: 'gw-loc', x: 930, y: 150, w: 180, t: 'PolicyLocation', s: 'PolicyCenter CDC' },
];

const SATS: Box[] = [
  { x: 250, y: 40, w: 150, t: 'R-TX-HO-0418', s: 'Rule · 71% ⚠' },
  { x: 250, y: 262, w: 150, t: 'R-TX-HO-0433', s: 'Rule · 88%' },
  { x: 460, y: 40, w: 160, t: 'wind_excl_ind', s: 'Field · pos 68–69' },
  { x: 460, y: 262, w: 160, t: 'construction_code', s: 'Field · pos 39–40' },
  { x: 680, y: 262, w: 190, t: 'coverage_detail', s: 'silver · 5.9M rows' },
  { x: 930, y: 262, w: 180, t: 'HOPDwelling', s: 'PolicyCenter CDC' },
  { x: 460, y: 372, w: 160, t: 'iso_pl_ho_record', s: 'Gold · ISO projection' },
];

const H = 34;

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
    <g
      transform={`translate(${n.x},${n.y})`}
      style={{ cursor: onSelect ? 'pointer' : 'default' }}
      onClick={onSelect}
    >
      <rect width={n.w} height={H} fill={active ? ACC : 'rgba(242,242,243,.92)'} stroke={active ? ACC : 'rgba(29,31,32,.3)'} strokeWidth={1} />
      <text x={9} y={15} fontSize={12} fontFamily="ui-monospace, Menlo, monospace" fill={active ? '#f2f2f3' : '#1d1f20'}>{n.t}</text>
      <text x={9} y={27} fontSize={9.5} letterSpacing=".06em" fill={active ? 'rgba(242,242,243,.8)' : 'rgba(29,31,32,.5)'}>{n.s}</text>
    </g>
  );
}

export function GraphScreen() {
  const [node, setNode] = useState('fld-terr');
  const n = GRAPH_NODES[node] ?? GRAPH_NODES['fld-terr'];

  return (
    <div className="sc" style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 30, alignItems: 'start' }}>
      <Blueprint className="gridwash" style={{ padding: 20 }}>
        <div style={{ display: 'flex', gap: 14, marginBottom: 10 }}>
          <span className="k">Clause</span><span className="k">→ Rule</span><span className="k">→ Stat field</span>
          <span className="k">→ Silver column</span><span className="k">→ Guidewire source</span>
        </div>
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
            {COLS.slice(0, -1).map((a, i) => {
              const b = COLS[i + 1];
              return <Edge key={a.t} x1={a.x + a.w} y1={a.y + H / 2} x2={b.x} y2={b.y + H / 2} on />;
            })}
          </g>
          <g>{SATS.map((s) => <NodeBox key={s.t} n={s} active={false} />)}</g>
          <g>{COLS.map((c) => <NodeBox key={c.t} n={c} active={c.id === node} onSelect={() => setNode(c.id!)} />)}</g>
        </svg>
      </Blueprint>

      <aside style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
        <Blueprint style={{ padding: '15px 17px' }}>
          <div className="k">{n.kind}</div>
          <div style={{ fontFamily: 'var(--font-heading)', fontSize: 21, margin: '4px 0 8px' }}>{n.title}</div>
          <div style={{ fontSize: 13, lineHeight: 1.6, color: 'color-mix(in srgb,var(--color-text) 78%,transparent)' }}>{n.desc}</div>
        </Blueprint>
        <Blueprint style={{ padding: '15px 17px' }}>
          <div className="k" style={{ marginBottom: 9 }}>Properties</div>
          {n.props.map(([k, v]) => (
            <div key={k} style={{ display: 'flex', gap: 10, padding: '5px 0', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)', fontSize: 12.5 }}>
              <span className="muted" style={{ width: 104, flex: 'none' }}>{k}</span>
              <span className="mono" style={{ fontSize: 11.5 }}>{v}</span>
            </div>
          ))}
        </Blueprint>
        <Blueprint style={{ padding: '15px 17px' }}>
          <div className="k" style={{ marginBottom: 9 }}>Impact if changed</div>
          <div style={{ fontSize: 12.5, lineHeight: 1.6 }}>{n.impact}</div>
        </Blueprint>
      </aside>
    </div>
  );
}
