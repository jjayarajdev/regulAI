// Regulations screen — rule tree (KG canon merged with executable rules),
// rule detail with KG→Snowflake bridge, generated SQL, the live KG
// neighborhood graph (vis-network), and the violators side pane.

import { useEffect, useMemo, useRef, useState } from 'react';
import { Network } from 'vis-network';
import {
  useBronzeCancellations, useKgNeighborhood, useKgRules, useValidate,
} from '../../api/hooks';
import type { KgRule, ValidationRule } from '../../api/types';

interface RegulationsProps {
  activeFilingId: string | null;
}

const GROUP_COLORS: Record<string, { background: string; border: string; font: string }> = {
  root: { background: '#6366f1', border: '#4338ca', font: '#fff' },
  Rule: { background: '#dbeafe', border: '#3b82f6', font: '#1e3a8a' },
  Citation: { background: '#fef3c7', border: '#f59e0b', font: '#78350f' },
  Section: { background: '#f3e8ff', border: '#a855f7', font: '#581c87' },
  CodeValue: { background: '#f0fdf4', border: '#22c55e', font: '#14532d' },
};

function KgGraph({ ruleId }: { ruleId: string | null }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const { data, isLoading } = useKgNeighborhood(ruleId);

  useEffect(() => {
    if (!hostRef.current || !data) return;
    networkRef.current?.destroy();
    const nodes = data.nodes.map((n) => {
      const c = GROUP_COLORS[n.group] ?? { background: '#f1f5f9', border: '#94a3b8', font: '#334155' };
      return {
        id: n.id, label: n.label, title: n.title, shape: n.shape,
        color: c, font: { color: n.group === 'root' ? '#fff' : c.font, size: 12 },
        borderWidth: n.group === 'root' ? 3 : 1,
      };
    });
    const edges = data.edges.map((e, i) => ({
      id: `e${i}`, from: e.from, to: e.to,
      label: e.label.toLowerCase().replace(/_/g, ' '),
      font: { size: 9, color: '#64748b', strokeWidth: 0 },
      arrows: { to: { enabled: true, scaleFactor: 0.5 } },
      color: { color: '#cbd5e1' },
      smooth: { type: 'continuous' as const },
    }));
    networkRef.current = new Network(hostRef.current, { nodes, edges }, {
      layout: { improvedLayout: true },
      physics: { stabilization: { iterations: 80 }, barnesHut: { gravitationalConstant: -2400, springLength: 110 } },
      interaction: { hover: true, tooltipDelay: 200 },
      nodes: { font: { face: 'system-ui, -apple-system, sans-serif' } },
    });
    return () => { networkRef.current?.destroy(); networkRef.current = null; };
  }, [data]);

  return (
    <div className="kg-graph-host" ref={hostRef}>
      {isLoading && <div style={{ padding: 20, color: 'var(--ink-3)', fontSize: 13 }}>Loading neighborhood…</div>}
      {!ruleId && <div style={{ padding: 20, color: 'var(--ink-3)', fontSize: 13 }}>Pick a rule to see its canon neighborhood.</div>}
    </div>
  );
}

export function Regulations({ activeFilingId }: RegulationsProps) {
  const valQ = useValidate(activeFilingId);
  const kgQ = useKgRules();
  const bronzeQ = useBronzeCancellations(activeFilingId);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  const v = valQ.data;
  const kgRules = kgQ.data?.rules ?? [];

  // Merge: KG canon is the spine; an executable rule attaches by name.
  const execByName = useMemo(
    () => new Map((v?.rules ?? []).map((r) => [r.rule_name, r])),
    [v],
  );
  const merged = useMemo(() => {
    const rows: { kg: KgRule; exec: ValidationRule | undefined }[] =
      kgRules.map((kg) => ({ kg, exec: execByName.get(kg.name) }));
    // Executable rules with no KG twin still belong in the tree.
    const kgNames = new Set(kgRules.map((r) => r.name));
    for (const r of v?.rules ?? []) {
      if (!kgNames.has(r.rule_name)) {
        rows.push({
          kg: {
            id: r.rule_id, name: r.rule_name, severity: r.severity, version: 1,
            status: 'active', effective_from: null, effective_until: null,
            citation: r.citation, section: r.rule_number.match(/^([A-G])/i)?.[1]?.toUpperCase() ?? 'A',
            executable: true, currently_active: true,
          },
          exec: r,
        });
      }
    }
    return rows.filter(({ kg }) =>
      !search || kg.name.toLowerCase().includes(search.toLowerCase()));
  }, [kgRules, execByName, v, search]);

  const sections = useMemo(() => {
    const bySection = new Map<string, typeof merged>();
    for (const row of merged) {
      const sec = row.kg.section || 'Other';
      if (!bySection.has(sec)) bySection.set(sec, []);
      bySection.get(sec)!.push(row);
    }
    return [...bySection.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [merged]);

  const selected = merged.find((r) => r.kg.id === selectedId)
    ?? merged.find((r) => r.exec && r.exec.violation_count > 0)
    ?? merged[0];
  const exec = selected?.exec;
  const kg = selected?.kg;

  const violators = (v?.violations ?? []).filter((x) => exec && x.rule_id === exec.rule_id);
  const bronzeRows = bronzeQ.data?.rows ?? [];
  const violatingPolicies = new Set(violators.map((x) => x.policy_number));

  return (
    <div className="screen screen-regulations">
      {/* ── tree ─────────────────────────────────── */}
      <aside className="reg-side">
        <div className="reg-search">
          <svg className="ic" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg>
          <input placeholder="Search rules, citations…" value={search} onChange={(e) => setSearch(e.target.value)} />
          <span className="kbd">⌘K</span>
        </div>
        <div className="tree-group">
          <div className="tree-h">Texas statistical plan · canon</div>
          {kgQ.isLoading && <div className="tree-node">loading rules…</div>}
          {sections.map(([sec, rows]) => {
            const fails = rows.reduce((n, r) => n + (r.exec?.violation_count ?? 0), 0);
            return (
              <div key={sec}>
                <div className="tree-node section">
                  Section {sec}
                  <span className={`ct ${fails > 0 ? 'bad' : ''}`}>{fails > 0 ? `${fails}v` : rows.length}</span>
                </div>
                {rows.map(({ kg: k, exec: e }) => (
                  <button
                    key={k.id}
                    className={`tree-node rule ${selected?.kg.id === k.id ? 'active' : ''} ${e ? '' : 'descriptive'}`}
                    onClick={() => setSelectedId(k.id)}
                  >
                    <span className="code">{e?.rule_number ?? '·'}</span>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {k.name.replace(/^Rule\s+[A-G]?\.?\d*\s*[—-]?\s*/, '')}
                    </span>
                    {k.version > 1 && <span className="vpill">v{k.version}</span>}
                    <span className={`ct ${e && e.violation_count > 0 ? 'bad' : ''}`}>
                      {e ? (e.violation_count > 0 ? e.violation_count : '✓') : '—'}
                    </span>
                  </button>
                ))}
              </div>
            );
          })}
        </div>
      </aside>

      {/* ── detail ───────────────────────────────── */}
      <div className="reg-main">
        {!selected && <div style={{ color: 'var(--ink-3)' }}>{valQ.isLoading ? 'Loading rules…' : 'Select a rule from the tree.'}</div>}
        {selected && kg && (
          <>
            <div className="reg-crumb">
              Texas statistical plan<span className="sep">/</span>Section {kg.section}
              <span className="sep">/</span><span className="now">{exec?.rule_number ?? kg.id}</span>
            </div>
            <div className="reg-titlerow">
              <span className="reg-code">{exec?.rule_number ?? 'KG'}</span>
              <h1 className="reg-title">{kg.name.replace(/^Rule\s+[A-G]?\.?\d*\s*[—-]?\s*/, '')}</h1>
            </div>
            <div className="reg-citation">
              Authority <b>{kg.citation}</b> · Severity <b>{kg.severity}</b>
              {exec && <> · Target <b className="mono">{exec.target_table}</b></>}
              {' · '}
              {exec
                ? <span style={{ color: 'var(--good)' }}>● executable</span>
                : <span style={{ color: 'var(--ink-3)' }}>○ descriptive only · not yet executable</span>}
              {!kg.currently_active && <span style={{ color: 'var(--warn)' }}> · superseded</span>}
            </div>

            <div className="reg-section">
              <div className="reg-h">Plain-language explanation</div>
              <div className="reg-plain">
                {exec
                  ? exec.violation_reason
                  : 'This rule exists in the knowledge-graph canon but has no SQL attached yet — it documents an obligation that is not (yet) machine-checked.'}
              </div>
            </div>

            <div className="reg-section">
              <div className="reg-h">Deploys to</div>
              <div className="bridge">
                <div className="br-cell left">
                  <div className="br-key k">Knowledge graph</div>
                  <div className="br-val">(:Rule {'{'} id: "{kg.id}" {'}'})</div>
                  <div className="br-sub">canon v{kg.version} · {kg.status}</div>
                </div>
                <div className="br-arrow">→</div>
                <div className="br-cell" style={exec ? undefined : { opacity: 0.4 }}>
                  <div className="br-key s">Snowflake</div>
                  <div className="br-val">{exec?.target_table ?? 'no SQL attached'}</div>
                  {exec && <div className="br-sub">REFERENCE.TSPR_VALIDATION_RULES</div>}
                </div>
              </div>
            </div>

            {exec && (
              <div className="reg-section">
                <div className="reg-h">Executable check</div>
                <div className="sql">
                  <div className="sql-head">
                    <span>generated from KG · runs against {exec.target_table}</span>
                    <span className="num">{exec.violation_count} violation{exec.violation_count !== 1 ? 's' : ''}</span>
                  </div>
                  <div className="sql-body">
                    <span className="cmt">-- {exec.rule_number} · {exec.rule_name}{'\n'}</span>
                    <span className="kw">select</span> {exec.target_id_expr} <span className="kw">as</span> record_id{'\n'}
                    <span className="kw">from</span> {exec.target_table}{'\n'}
                    <span className="kw">where</span> {exec.violation_sql};
                  </div>
                </div>
              </div>
            )}

            <div className="reg-section">
              <div className="reg-h">KG neighborhood</div>
              <KgGraph ruleId={kg.id} />
            </div>
          </>
        )}
      </div>

      {/* ── violators pane ───────────────────────── */}
      <aside className="reg-violations-pane">
        <h4>
          {exec
            ? `Violators of ${exec.rule_number} · ${violators.length} on ${activeFilingId}`
            : 'Violators · pick an executable rule'}
        </h4>
        {exec && violators.length === 0 && (
          <div className="rvp-row pass">
            <span className="rvp-policy">✓ no violators</span>
            <span className="rvp-reason">every record passes this rule on {activeFilingId}</span>
          </div>
        )}
        {violators.map((x) => (
          <div className="rvp-row" key={x.record_id + x.rule_id}>
            <span className="rvp-policy">{x.policy_number}</span>
            <span className="rvp-reason">{x.violation_reason}</span>
          </div>
        ))}
        <h4 style={{ marginTop: 22 }}>Live records · {exec?.target_table ?? '—'}</h4>
        {bronzeRows.slice(0, 12).map((r) => (
          <div className={`rvp-row ${violatingPolicies.has(r.policy) ? '' : 'pass'}`} key={r.policy + r.noticedate}>
            <span className="rvp-policy">{r.policy} · {r.reason_code}</span>
            <span className="rvp-reason">{r.action.toLowerCase()} · notice {r.noticedate}</span>
          </div>
        ))}
      </aside>
    </div>
  );
}
