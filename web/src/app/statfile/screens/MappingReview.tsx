// Mapping review — "agent proposes, human governs" for schema mappings. The
// schema-mapper LLM proposed every Guidewire→FHCF column expression; a human
// review accepted most and overrode the rest. Left rail lists the reviewed
// mapping specs; the main pane shows every proposal with its confidence and
// rationale, and for the overridden columns a proposed-vs-accepted SQL diff
// with the reviewer's reason. Live: /mappings + /mapping/{name} (file-backed
// on the server — works on any warehouse).
import { useState, type CSSProperties } from 'react';
import { Blueprint } from '../Blueprint';
import { DetailModal } from '../DetailModal';
import { Stat, StatRow } from '../ui';
import { SelectList } from '../SelectList';
import { useMappingDetail, useMappings } from '../api';
import type { MappingColumn, MappingDetail, MappingTransformType } from '../../../api/types';
import { ACC, ACC9, NEU } from '../data';

const fmt = (n: number) => n.toLocaleString('en-US');
const stamp = (s?: string | null) => (s ? s.replace('T', ' ').slice(0, 16) : '—');

// Confidence banding: high reads quiet, the band the reviewer must look at
// reads loud — same palette logic as the severity dots elsewhere.
const confDot = (c: number) => (c >= 0.9 ? NEU : c >= 0.7 ? ACC : ACC9);

const XFORM_TAG: Record<MappingTransformType, string> = {
  direct: 'tag-neutral', lookup: 'tag-accent', composite: 'tag-outline',
};

const sqlBlock: CSSProperties = {
  fontSize: 11, lineHeight: 1.65, padding: '9px 11px', whiteSpace: 'pre-wrap',
  overflowWrap: 'anywhere', margin: 0,
  background: 'color-mix(in srgb,var(--color-text) 5%,transparent)',
};

// Overridden rows first (the story), then alphabetical.
const sortCols = (cols: MappingColumn[]): MappingColumn[] =>
  [...cols].sort((a, b) =>
    Number(b.overridden) - Number(a.overridden)
    || a.target_column.localeCompare(b.target_column));

function ConfidenceCell({ c }: { c: number }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>
      <span className="mono" style={{ fontSize: 11.5 }}>{c.toFixed(2)}</span>
      <span style={{ width: 8, height: 8, background: confDot(c), flex: 'none' }} />
    </span>
  );
}

// One side of the proposed/accepted diff — the accepted side carries the
// accent left-border, the discarded proposal reads muted.
function SqlCol({ label, sql, accepted }: { label: string; sql: string; accepted?: boolean }) {
  return (
    <div style={accepted
      ? { borderLeft: '3px solid var(--color-accent)', paddingLeft: 12 }
      : { opacity: 0.62 }}>
      <div className="k" style={{ marginBottom: 7 }}>{label}</div>
      <pre className="mono" style={sqlBlock}>{sql}</pre>
    </div>
  );
}

function ColumnDetailBody({ col }: { col: MappingColumn }) {
  return (
    <>
      {/* the agent's reasoning, quoted */}
      {col.rationale && (
        <div style={{ marginBottom: 14, paddingLeft: 12, borderLeft: `3px solid ${NEU}` }}>
          <div className="k" style={{ marginBottom: 5 }}>Agent rationale</div>
          <div style={{ fontSize: 12.5, lineHeight: 1.6, fontStyle: 'italic', opacity: 0.85 }}>
            {col.rationale}
          </div>
        </div>
      )}

      {col.overridden && col.proposed_sql ? (
        <>
          {/* the money shot: what the agent wrote vs what the human shipped */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            <SqlCol label="Proposed · agent" sql={col.proposed_sql} />
            <SqlCol label="Accepted · review" sql={col.accepted_sql} accepted />
          </div>
          {col.override_reason && (
            <div style={{
              marginTop: 14, padding: '11px 13px',
              borderLeft: '3px solid var(--color-accent)',
              background: 'color-mix(in srgb,var(--color-accent) 7%,transparent)',
            }}>
              <div className="k" style={{ marginBottom: 5 }}>Reviewer</div>
              <div style={{ fontSize: 12.5, lineHeight: 1.6 }}>{col.override_reason}</div>
            </div>
          )}
        </>
      ) : (
        <>
          <SqlCol label="Accepted · as proposed" sql={col.accepted_sql} accepted />
          {col.review_note && (
            <div style={{
              marginTop: 14, padding: '11px 13px',
              borderLeft: `3px solid ${NEU}`,
              background: 'color-mix(in srgb,var(--color-text) 4%,transparent)',
            }}>
              <div className="k" style={{ marginBottom: 5 }}>Review note</div>
              <div style={{ fontSize: 12.5, lineHeight: 1.6 }}>{col.review_note}</div>
            </div>
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
    <Blueprint style={{ padding: '16px 18px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div className="k">Compiled SQL</div>
        <span className="mono muted" style={{ fontSize: 10.5 }}>
          select_sql · {d.compiled ? `compiled ${stamp(d.compiled_at)}` : 'not compiled'}
        </span>
        {d.compiled_sql && (
          <button className="btn btn-secondary" style={{ marginLeft: 'auto', padding: '3px 12px', fontSize: 11 }}
            onClick={() => setOpenSql((v) => !v)}>
            {openSql ? 'Hide' : 'Show'}
          </button>
        )}
      </div>
      {openSql && d.compiled_sql && (
        <pre className="mono" style={{
          ...sqlBlock, marginTop: 12, maxHeight: 340, overflow: 'auto',
          border: '1px solid var(--color-divider)',
        }}>
          {d.compiled_sql}
        </pre>
      )}

      {unmapped.length > 0 && (
        <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px solid var(--color-divider)' }}>
          <div className="k" style={{ marginBottom: 8 }}>
            Unmapped source columns · {unmapped.length} (deliberate — CDC metadata, join keys, rating variables)
          </div>
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            {shown.map((u) => (
              <span key={u.name} className="mono muted" title={u.reason}
                style={{
                  fontSize: 10, padding: '2px 7px',
                  border: '1px solid color-mix(in srgb,var(--color-text) 15%,transparent)',
                }}>
                {u.name}
              </span>
            ))}
            {unmapped.length > 24 && (
              <button onClick={() => setAllUnmapped((v) => !v)}
                style={{
                  background: 'none', border: 'none', padding: '2px 4px', cursor: 'pointer',
                  fontSize: 10.5, color: 'var(--color-accent-700)', textDecoration: 'underline',
                }}>
                {allUnmapped ? 'show fewer' : `+${unmapped.length - 24} more`}
              </button>
            )}
          </div>
        </div>
      )}
    </Blueprint>
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

  // Row click opens the proposal detail in a modal (overrides sort first, so
  // the interesting rows lead the table).
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

  return (
    <div className="sc" style={{ display: 'grid', gridTemplateColumns: '292px 1fr', gap: 28, alignItems: 'start' }}>
      {/* ── mapping master list — compact, searchable, scales with specs ── */}
      <SelectList
        label="Reviewed mappings"
        items={mappings.map((m) => ({
          id: m.name,
          title: m.name,
          meta: `${m.source_label} → ${m.target}`,
          tag: m.compiled ? 'Compiled' : 'Not compiled',
          tagClass: m.compiled ? 'tag-neutral' : 'tag-outline',
        }))}
        value={M?.name ?? null}
        onChange={(id) => { setSelName(id); setSelCol(null); }}
      />

      {/* ── proposals, verdicts, diffs ─────────────────────────────────── */}
      <section>
        {listQ.isPending && <span className="k">loading mappings…</span>}
        {!listQ.isPending && mappings.length === 0 && (
          <span className="k">no reviewed mappings on disk yet</span>
        )}
        {M && (
          <>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 6, flexWrap: 'wrap' }}>
              <h4>{M.source_label} → {M.target}</h4>
              <span className="k">every proposal, its confidence, and what review changed</span>
            </div>
            {M.review_summary && (
              <p style={{ fontSize: 12.5, lineHeight: 1.65, maxWidth: '92ch', margin: '0 0 16px', color: 'color-mix(in srgb,var(--color-text) 72%,transparent)' }}>
                {M.review_summary}
              </p>
            )}
          </>
        )}

        {loading && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 22, marginBottom: 24 }}>
            {[0, 1, 2, 3].map((i) => (
              <Blueprint key={i} style={{ padding: '14px 16px 12px', minHeight: 74 }}>
                <div className="k">loading…</div>
                <div style={{ height: 30, marginTop: 8, background: 'color-mix(in srgb,var(--color-text) 7%,transparent)' }} />
              </Blueprint>
            ))}
          </div>
        )}

        {!loading && !d && (
          <div className="muted" style={{ fontSize: 13, lineHeight: 1.6, maxWidth: 520 }}>
            No reviewed mappings on disk yet — run the mapper's propose + review flow to
            materialize a spec, then this screen shows every proposal and its verdict.
          </div>
        )}

        {!loading && d && (
          <>
            {/* KPI row */}
            <StatRow style={{ marginBottom: 18 }}>
              {kpis.map((k) => (
                <Stat key={k.label} label={k.label} value={k.value} note={k.note} accent={k.accent} />
              ))}
            </StatRow>

            {/* provenance strip */}
            <div className="mono muted" style={{
              fontSize: 10.5, lineHeight: 1.7, marginBottom: 20,
              display: 'flex', gap: 18, flexWrap: 'wrap',
            }}>
              <span title={d.source_relation + (d.source_filter ? `\nWHERE ${d.source_filter}` : '')}
                style={{ maxWidth: 480, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                src {relation}
              </span>
              <span>reviewed {d.reviewed_by ?? '—'}</span>
              <span>compiled {stamp(d.compiled_at)}</span>
            </div>

            {/* column table */}
            <Blueprint style={{ padding: '4px 0 0', marginBottom: 18, overflow: 'hidden' }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Target field</th><th>Source</th><th>Transform</th>
                    <th>Confidence</th><th>Review</th>
                  </tr>
                </thead>
                <tbody>
                  {cols.map((c) => {
                    return (
                      <tr key={c.target_column} className="rowlink"
                        onClick={() => setSelCol(c.target_column)}>
                        <td className="mono" style={{ fontSize: 11.5 }}>{c.target_column}</td>
                        <td className="mono" style={{ fontSize: 11.5 }}>
                          {c.source_column ?? <span className="muted">constant</span>}
                        </td>
                        <td><span className={'tag ' + XFORM_TAG[c.transform_type]}>{c.transform_type}</span></td>
                        <td><ConfidenceCell c={c.confidence} /></td>
                        <td>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                            <span className={'tag ' + (c.overridden ? 'tag-accent' : 'tag-neutral')}>
                              {c.overridden ? 'Overridden' : 'Accepted'}
                            </span>
                            {c.needs_review && (
                              <span className="mono muted" style={{ fontSize: 10 }}>⚑ flagged</span>
                            )}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </Blueprint>

            {/* row click → proposal detail in a modal, right where the user is */}
            <DetailModal
              open={!!activeCol}
              onClose={() => setSelCol(null)}
              kicker="mapping proposal · agent proposes, human governs"
              title={<span className="mono" style={{ color: 'var(--color-accent-700)' }}>{activeCol?.target_column}</span>}
              tags={activeCol && (
                <>
                  <span className={'tag ' + XFORM_TAG[activeCol.transform_type]}>{activeCol.transform_type}</span>
                  <span className={'tag ' + (activeCol.overridden ? 'tag-accent' : 'tag-neutral')}>
                    {activeCol.overridden ? 'Overridden' : 'Accepted'}
                  </span>
                  {activeCol.needs_review && <span className="mono muted" style={{ fontSize: 10.5 }}>⚑ flagged</span>}
                  <ConfidenceCell c={activeCol.confidence} />
                </>
              )}
            >
              {activeCol && <ColumnDetailBody col={activeCol} />}
            </DetailModal>

            <CompiledFooter d={d} />
          </>
        )}
      </section>
    </div>
  );
}
