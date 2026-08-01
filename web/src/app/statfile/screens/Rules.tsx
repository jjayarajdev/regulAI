// Rulebook & rules — source document viewer anchored to the selected rule's
// clause, beside the extracted-rules review queue with approve/reject.
// Live: /kg/rules for the queue, /reg/citation resolves the selected rule's
// citation to real regulator text. Demo fixtures when the canon is empty.
import { useMemo, useState } from 'react';
import { Blueprint } from '../Blueprint';
import { useCitation, useKgRules } from '../api';
import { ACC, ACC9, CLAUSES, RULES } from '../data';

type Decision = 'approved' | 'rejected';
type Filter = 'pending' | 'low' | 'all';

interface RuleCard {
  id: string; kind: string; conf: number | null; title: string;
  text: string; logic: string; cite: string; agent: string; page: number | null;
  preDecided?: Decision;
}

export function RulesScreen() {
  const rulesQ = useKgRules();

  const cards: RuleCard[] = useMemo(() => {
    const kg = rulesQ.data?.rules ?? [];
    if (!kg.length) {
      return RULES.map((r) => ({ ...r, conf: r.conf as number | null }));
    }
    return kg.map((r) => ({
      id: r.id,
      kind: r.status === 'superseded' ? 'Amended' : r.executable ? 'Validation edit' : 'Descriptive',
      conf: null,
      title: r.name,
      text: r.citation || 'No citation recorded in the canon.',
      logic: `version ${r.version} · ${r.status}` +
        (r.effective_from ? `\neffective ${r.effective_from}${r.effective_until ? ' → ' + r.effective_until : ''}` : ''),
      cite: r.section !== 'Other' ? `§${r.section} · ${r.id}` : r.id,
      agent: r.executable ? 'Edit Compiler · canon' : 'Rulebook Parser · canon',
      page: null,
      preDecided: r.currently_active && r.status === 'active' ? 'approved' as const : undefined,
    }));
  }, [rulesQ.data]);

  const live = (rulesQ.data?.rules.length ?? 0) > 0;

  const [selIdx, setSelIdx] = useState(0);
  const [page, setPage] = useState(47);
  const [filter, setFilter] = useState<Filter>(live ? 'all' : 'pending');
  const [decided, setDecided] = useState<Record<string, Decision>>({});

  const decisionOf = (r: RuleCard): Decision | undefined => decided[r.id] ?? r.preDecided;
  const pending = cards.filter((r) => !decisionOf(r)).length;
  const filtered = cards.filter((r) =>
    filter === 'all' ? true : filter === 'low' ? (r.conf ?? 100) < 90 : !decisionOf(r));

  const sel = cards[Math.min(selIdx, cards.length - 1)];

  // Clause panel: live citation lookup for the selected rule, else demo clause.
  // Section labels in regdocs are "Rule 34" — strip the section letter from
  // KG rule names like "Rule A.34 …" before querying.
  const citNum = sel?.title.match(/([A-G])\.(\d{1,3})/);
  const citQ = useCitation(live && sel ? (citNum ? `Rule ${citNum[2]}` : sel.title) : null);
  const match = citQ.data?.matches?.[0];
  const demoClause = CLAUSES[Math.min(selIdx, CLAUSES.length - 1)];
  const clause = match
    ? { t: match.section_heading || match.citation_label, r: `${match.title} · ${match.citation_label}`,
        b: match.section_text, h: `${match.issuing_body} · ${match.document_type} · ${match.edition}` }
    : demoClause;

  const decide = (id: string, d: Decision) => setDecided((s) => ({ ...s, [id]: d }));

  return (
    <div className="sc">
      <Blueprint style={{ padding: '12px 16px', marginBottom: 22, display: 'flex', alignItems: 'center', gap: 14 }}>
        <div style={{ width: 6, height: 34, background: 'var(--color-accent-900)' }} />
        <div style={{ flex: 1 }}>
          <div style={{ fontFamily: 'var(--font-heading)', fontSize: 17 }}>
            {live
              ? `Canon loaded — ${rulesQ.data!.counts.total} rules (${rulesQ.data!.counts.executable} executable, ${rulesQ.data!.counts.descriptive} descriptive)`
              : 'Rulebook version change detected — v2025.2 → v2026.1'}
          </div>
          <div className="muted" style={{ fontSize: 12 }}>
            {live
              ? `${pending} rules are not currently active — superseded versions or drafts awaiting approval.`
              : 'Parser found 9 amended clauses and 2 new clauses. 17 derived rules require re-approval before the cycle can close.'}
          </div>
        </div>
        <button className="btn btn-secondary">View full diff</button>
      </Blueprint>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.05fr', gap: 30, alignItems: 'start' }}>
        <section>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <h4>Source document</h4>
            <span className="k">
              {match ? `${match.title} · ${match.citation_label}` : `TDI-HO-STATPLAN-2026.pdf · p. ${page} of 214`}
            </span>
          </div>
          <Blueprint style={{ padding: '34px 38px', background: '#fff' }}>
            <div style={{
              fontSize: 10, letterSpacing: '.09em', textTransform: 'uppercase',
              color: 'color-mix(in srgb,var(--color-text) 45%,transparent)',
              borderBottom: '1px solid var(--color-divider)', paddingBottom: 8, marginBottom: 20,
              display: 'flex', justifyContent: 'space-between',
            }}>
              <span>{match ? match.issuing_body : 'Texas Department of Insurance'}</span>
              <span>{match ? match.document_type : 'Residential Property Statistical Plan'}</span>
            </div>
            <div style={{ fontFamily: 'var(--font-heading)', fontSize: 19, marginBottom: 4 }}>{clause.t}</div>
            <div className="mono" style={{ fontSize: 11, color: 'var(--color-accent-700)', marginBottom: 16 }}>{clause.r}</div>
            <div style={{ fontSize: 13.5, lineHeight: 1.75, textWrap: 'pretty', color: '#25282a', maxHeight: 420, overflow: 'auto' }}>
              {citQ.isLoading ? 'Resolving citation…' : clause.b}
            </div>
            <div style={{ marginTop: 20, padding: '14px 16px', background: 'var(--color-accent-100)', borderLeft: '2px solid var(--color-accent)', fontSize: 13, lineHeight: 1.7 }}>
              {clause.h}
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 26, paddingTop: 14, borderTop: '1px solid var(--color-divider)' }}>
              <button className="btn btn-secondary" onClick={() => setPage((p) => Math.max(1, p - 1))}>← Prev</button>
              <button className="btn btn-secondary" onClick={() => setPage((p) => Math.min(214, p + 1))}>Next →</button>
              <span className="muted" style={{ marginLeft: 'auto', fontSize: 11, alignSelf: 'center' }}>
                Anchored to clause the selected rule cites
              </span>
            </div>
          </Blueprint>
        </section>

        <section>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <h4>Extracted rules</h4>
            <span className="k">{pending} awaiting review</span>
            <div className="seg" style={{ marginLeft: 'auto' }}>
              {([['pending', 'Pending'], ['low', 'Low confidence'], ['all', 'All']] as Array<[Filter, string]>).map(([f, label]) => (
                <label key={f} className="seg-opt">
                  <input type="radio" name="rf" checked={filter === f} onChange={() => setFilter(f)} />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 18, maxHeight: 900, overflow: 'auto' }}>
            {filtered.map((r) => {
              const i = cards.indexOf(r);
              const d = decisionOf(r);
              return (
                <Blueprint
                  key={r.id}
                  style={{
                    padding: '16px 18px', cursor: 'pointer',
                    borderColor: i === selIdx ? ACC : 'color-mix(in srgb,#1d1f20 16%,transparent)',
                  }}
                  onClick={() => { setSelIdx(i); if (r.page) setPage(r.page); }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <span className="mono" style={{ fontSize: 11, color: 'var(--color-accent-700)' }}>{r.id}</span>
                    <span className={'tag ' + (r.kind === 'Amended' ? 'tag-outline' : 'tag-neutral')}>{r.kind}</span>
                    {r.conf != null && (
                      <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 7 }}>
                        <span className="k">confidence</span>
                        <span style={{ width: 56, height: 6, background: 'color-mix(in srgb,var(--color-text) 10%,transparent)', position: 'relative', display: 'inline-block' }}>
                          <span style={{
                            position: 'absolute', inset: '0 auto 0 0', width: r.conf + '%',
                            background: r.conf >= 90 ? ACC : r.conf >= 75 ? '#94bce3' : ACC9,
                          }} />
                        </span>
                        <span className="mono" style={{ fontSize: 12 }}>{r.conf}%</span>
                      </span>
                    )}
                  </div>
                  <div style={{ fontFamily: 'var(--font-heading)', fontSize: 18, lineHeight: 1.25, marginBottom: 6 }}>{r.title}</div>
                  <div style={{ fontSize: 13, lineHeight: 1.6, color: 'color-mix(in srgb,var(--color-text) 78%,transparent)' }}>{r.text}</div>
                  <div className="mono" style={{ marginTop: 10, padding: '9px 11px', background: 'color-mix(in srgb,var(--color-text) 5%,transparent)', fontSize: 11.5, lineHeight: 1.65, whiteSpace: 'pre-wrap' }}>
                    {r.logic}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 12, paddingTop: 11, borderTop: '1px solid var(--color-divider)' }}>
                    <span className="mono muted" style={{ fontSize: 11 }}>◱ {r.cite}</span>
                    <span className="mono" style={{ fontSize: 11, color: 'color-mix(in srgb,var(--color-text) 45%,transparent)' }}>{r.agent}</span>
                    <span style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
                      <span className={'tag ' + (d === 'approved' ? 'tag-accent' : d === 'rejected' ? 'tag-neutral' : 'tag-outline')}>
                        {d === 'approved' ? 'Approved' : d === 'rejected' ? 'Sent back' : 'Pending'}
                      </span>
                      <button className="btn btn-secondary" onClick={(e) => { e.stopPropagation(); decide(r.id, 'rejected'); }}>Reject</button>
                      <button className="btn btn-primary" onClick={(e) => { e.stopPropagation(); decide(r.id, 'approved'); }}>Approve</button>
                    </span>
                  </div>
                </Blueprint>
              );
            })}
          </div>
        </section>
      </div>
    </div>
  );
}
