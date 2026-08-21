// Rulebook & rules — source document viewer anchored to the selected rule's
// clause, beside the extracted-rules review queue with approve/reject.
// Live: /kg/rules for the queue, /reg/citation resolves the selected rule's
// citation to real regulator text. Demo fixtures when the canon is empty.
import { useMemo, useState } from 'react';
import { Blueprint } from '../Blueprint';
import { DetailModal } from '../DetailModal';
import {
  can, useAuthorExecutable, useCitation, useKgDiff, useKgRules, useRuleDecision,
  whoCan, type AppUser,
} from '../api';
import { ACC, ACC9, CLAUSES, RULES } from '../data';
import type { KgRule } from '../../../api/types';

// In-product authoring of a rule's executable form — the edit-package fields
// that scripts.attach_validation_rules used to require a JSON file for.
function ExecutableFormModal({ rule, onClose }: { rule: KgRule; onClose: () => void }) {
  const mut = useAuthorExecutable();
  const short = (rule.jurisdiction_code ?? '').replace('US-', '');
  const [f, setF] = useState({
    target_table: rule.target_table ?? (short && short !== 'US' ? `GOLD.${short}_STAT_RECORDS` : 'GOLD.'),
    target_id_expr: 'j.policy_number',
    violation_sql: rule.violation_sql ?? '',
    violation_reason: '',
    severity: (rule.severity as 'ERROR' | 'WARNING') ?? 'ERROR',
    citation: rule.citation ?? '',
  });
  const set = (k: keyof typeof f) => (v: string) => setF((s) => ({ ...s, [k]: v }));
  const valid = f.target_table.trim().length > 5 && f.target_id_expr.trim()
    && f.violation_sql.trim() && f.violation_reason.trim();

  const inp = (v: string, on: (x: string) => void, mono = false, rows = 0) => rows > 0 ? (
    <textarea value={v} rows={rows} onChange={(e) => on(e.target.value)}
      style={{ display: 'block', width: '100%', boxSizing: 'border-box', marginTop: 4, padding: '8px 10px',
        fontSize: 12, fontFamily: mono ? 'var(--font-mono, monospace)' : 'var(--font-body)',
        border: '1px solid var(--color-divider)', borderRadius: 0, resize: 'vertical',
        background: 'color-mix(in srgb,var(--color-text) 4%,transparent)', color: 'var(--color-text)' }} />
  ) : (
    <input value={v} onChange={(e) => on(e.target.value)}
      style={{ display: 'block', width: '100%', boxSizing: 'border-box', marginTop: 4, padding: '8px 10px',
        fontSize: 12, fontFamily: mono ? 'var(--font-mono, monospace)' : 'var(--font-body)',
        border: '1px solid var(--color-divider)', borderRadius: 0,
        background: 'color-mix(in srgb,var(--color-text) 4%,transparent)', color: 'var(--color-text)' }} />
  );
  const lbl = { fontSize: 11.5, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' } as const;

  return (
    <DetailModal open onClose={onClose} width={720}
      kicker={`executable form · ${rule.jurisdiction_code ?? '—'} · runs in /validate once saved`}
      title={rule.name}
      tags={<span className={'tag ' + (rule.violation_sql ? 'tag-neutral' : 'tag-outline')}>
        {rule.violation_sql ? 'editing' : 'not yet executable'}
      </span>}
      footer={
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button className="btn btn-primary" disabled={!valid || mut.isPending}
            onClick={() => mut.mutate(
              { ruleId: rule.id, ...f, citation: f.citation || undefined },
              { onSuccess: onClose },
            )}>
            {mut.isPending ? 'Saving…' : 'Save — compile into the edit package'}
          </button>
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          {mut.error != null && (
            <span style={{ fontSize: 11.5, color: '#a33' }}>{(mut.error as Error).message}</span>
          )}
        </div>
      }>
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '12px 16px', marginBottom: 12 }}>
        <label style={lbl}>Target table{inp(f.target_table, set('target_table'), true)}</label>
        <label style={lbl}>Record id expression{inp(f.target_id_expr, set('target_id_expr'), true)}</label>
      </div>
      <label style={{ ...lbl, display: 'block', marginBottom: 12 }}>
        Violation SQL — predicate over alias <span className="mono">j</span>; TRUE means the record violates the rule
        {inp(f.violation_sql, set('violation_sql'), true, 5)}
      </label>
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '12px 16px', marginBottom: 12 }}>
        <label style={lbl}>Violation reason (analyst-facing){inp(f.violation_reason, set('violation_reason'))}</label>
        <label style={lbl}>Severity
          <select value={f.severity} onChange={(e) => setF((s) => ({ ...s, severity: e.target.value as 'ERROR' | 'WARNING' }))}
            style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px', fontSize: 12,
              border: '1px solid var(--color-divider)', borderRadius: 0,
              background: 'var(--color-bg, transparent)', color: 'var(--color-text)' }}>
            <option value="ERROR">ERROR — blocks sealing</option>
            <option value="WARNING">WARNING — flagged only</option>
          </select>
        </label>
      </div>
      <label style={{ ...lbl, display: 'block' }}>Citation{inp(f.citation, set('citation'))}</label>
      <p className="muted" style={{ fontSize: 11.5, lineHeight: 1.6, marginTop: 14 }}>
        Saving writes the executable properties onto the KG rule (audited as a manual edit),
        bumps its validation version, and refreshes the jurisdiction's validation reference —
        the edit runs on the next validation pass. No scripts, no JSON files.
      </p>
    </DetailModal>
  );
}

const JUR: Record<string, string> = {
  'US-TX': 'Texas', 'US-FL': 'Florida', 'US-OK': 'Oklahoma', 'US-LA': 'Louisiana',
  US: 'Federal / NAIC',
};

type Decision = 'approved' | 'rejected';
type Filter = 'pending' | 'low' | 'all';

interface RuleCard {
  id: string; kind: string; conf: number | null; title: string;
  text: string; logic: string; cite: string; agent: string; page: number | null;
  section: string;
  hasCite?: boolean;
  raw?: KgRule;
  preDecided?: Decision;
}

export function RulesScreen({ user }: { user?: AppUser }) {
  const mayDecide = can(user, 'rule_decision');
  const rulesQ = useKgRules();

  const cards: RuleCard[] = useMemo(() => {
    const kg = rulesQ.data?.rules ?? [];
    if (!kg.length) {
      return RULES.map((r) => ({ ...r, conf: r.conf as number | null, section: 'Other' }));
    }
    return kg.map((r) => ({
      id: r.id,
      raw: r,
      section: r.section,
      kind: r.status === 'superseded' ? 'Amended' : r.executable ? 'Validation edit' : 'Descriptive',
      conf: r.confidence != null ? Math.round(r.confidence * 100) : null,
      title: r.name,
      hasCite: !!r.citation,
      text: r.citation || 'No citation recorded in the canon.',
      logic: `version ${r.version} · ${r.status}` +
        (r.effective_from ? `\neffective ${r.effective_from}${r.effective_until ? ' → ' + r.effective_until : ''}` : ''),
      cite: r.section !== 'Other' ? `§${r.section} · ${r.id}` : r.id,
      agent: r.executable ? 'Edit Compiler · canon' : 'Rulebook Parser · canon',
      page: null,
      preDecided: r.status === 'approved' ? 'approved' as const
        : r.status === 'rejected' ? 'rejected' as const : undefined,
    }));
  }, [rulesQ.data]);

  const live = (rulesQ.data?.rules.length ?? 0) > 0;

  const [selIdx, setSelIdx] = useState(0);
  const [page, setPage] = useState(47);
  const [filter, setFilter] = useState<Filter>(live ? 'all' : 'pending');
  const [decided, setDecided] = useState<Record<string, Decision>>({});
  const [query, setQuery] = useState('');
  const [section, setSection] = useState('all');

  const decisionOf = (r: RuleCard): Decision | undefined => decided[r.id] ?? r.preDecided;
  const pending = cards.filter((r) => !decisionOf(r)).length;

  const sections = useMemo(() => {
    const by = new Map<string, number>();
    for (const r of cards) by.set(r.section, (by.get(r.section) ?? 0) + 1);
    return [...by.entries()].sort(([a], [b]) => (a === 'Other' ? 1 : b === 'Other' ? -1 : a.localeCompare(b)));
  }, [cards]);

  const q = query.trim().toLowerCase();
  const filtered = cards.filter((r) =>
    (filter === 'all' ? true : filter === 'low' ? (r.conf ?? 100) < 90 : !decisionOf(r))
    && (section === 'all' || r.section === section)
    && (!q || r.title.toLowerCase().includes(q) || r.id.toLowerCase().includes(q)
        || r.text.toLowerCase().includes(q)));

  const sel = cards[Math.min(selIdx, cards.length - 1)];

  // Clause panel: live citation lookup for the selected rule, else demo clause.
  // Query derivation, most specific anchor first:
  //   FL statutes  "Rule 627.351(6)(a) — …" → "627.351(6)"
  //   TX stat plan "Rule A.34 — …"           → "Rule 34" (regdocs label style)
  //   memo rules                              → the full name (reverse-containment
  //                                             matches its heading label)
  const statuteRef = sel?.title.match(/(\d{3}\.\d{3}(?:\(\d+\))?)/);
  const citNum = sel?.title.match(/([A-G])\.(\d{1,3})/);
  const citQ = useCitation(
    live && sel
      ? statuteRef ? statuteRef[1] : citNum ? `Rule ${citNum[2]}` : sel.title
      : null,
  );
  const match = citQ.data?.matches?.[0];
  const demoClause = CLAUSES[Math.min(selIdx, CLAUSES.length - 1)];
  const raw = sel?.raw;
  const jurName = raw?.jurisdiction_code ? (JUR[raw.jurisdiction_code] ?? raw.jurisdiction_code) : null;
  // Live with no match: a provenance card assembled from the rule node itself —
  // what it is, where it came from, who extracted it — never the demo clause.
  const clause = match
    ? { t: match.section_heading || match.citation_label, r: `${match.title} · ${match.citation_label}`,
        b: match.section_text, h: `${match.issuing_body} · ${match.document_type} · ${match.edition}` }
    : live && sel
    ? {
        t: raw?.short_title || sel.title,
        r: [raw?.clause_ref ? `§${raw.clause_ref}` : null, raw?.rule_kind, jurName]
          .filter(Boolean).join(' · ') || sel.cite,
        b: [
          `${raw?.rule_kind ?? 'Extracted'} rule${jurName ? ` for ${jurName}` : ''}, drawn from ` +
            (raw?.source_doc ? `“${raw.source_doc}”${raw.source_url ? ` (${raw.source_url})` : ''}.` : 'a source document that was not recorded.'),
          // Citation line only when it adds something beyond the doc name.
          ...(sel.hasCite && sel.text !== raw?.source_doc ? [`Citation: ${sel.text}`]
            : sel.hasCite ? [] : ['No citation was recorded during extraction.']),
          `Extracted by ${raw?.created_by ?? 'the parser'}${raw?.created_at ? ` on ${raw.created_at}` : ''}` +
            ` · version ${raw?.version ?? '1'} · ${raw?.status ?? 'draft'}.`,
        ].join('\n\n'),
        h: raw?.source_doc
          ? 'The full text of this document isn’t loaded in the document store yet — only the Texas stat-plan documents are. Load it to read the original wording here.'
          : 'To anchor this rule, load its source document and re-run extraction so the parser records the citation.',
      }
    : demoClause;

  const decideMut = useRuleDecision();
  const decide = (id: string, d: Decision) => {
    setDecided((s) => ({ ...s, [id]: d }));  // optimistic; refetch reconciles
    if (live) decideMut.mutate({ ruleId: id, decision: d });
  };

  // Executable-form authoring modal — opened from the expanded rule card.
  const [authorRule, setAuthorRule] = useState<KgRule | null>(null);

  // Canon diff panel — last 30 days of KG mutations, fetched on demand.
  const [showDiff, setShowDiff] = useState(false);
  const since = useMemo(
    () => new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 19),
    [],
  );
  const diffQ = useKgDiff(showDiff ? since : null);
  const diff = diffQ.data;

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
        <button className="btn btn-secondary" onClick={() => setShowDiff((v) => !v)}>
          {showDiff ? 'Hide diff' : 'View full diff'}
        </button>
      </Blueprint>

      {showDiff && (
        <Blueprint style={{ padding: '16px 18px', marginBottom: 22 }}>
          <div className="k" style={{ marginBottom: 10 }}>
            Canon changes — last 30 days
            {diff ? ` · ${diff.total_changes} changes` : diffQ.isLoading ? ' · loading…' : diffQ.isError ? ' · KG unreachable' : ''}
          </div>
          {diff && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
              {([['Added', diff.added_nodes], ['Modified', diff.modified_nodes], ['Superseded', diff.superseded_nodes]] as const)
                .filter(([, ns]) => ns.length > 0)
                .map(([label, ns]) => (
                  <div key={label}>
                    <div className="k" style={{ marginBottom: 6 }}>{label} · {ns.length}</div>
                    {ns.slice(0, 8).map((n) => (
                      <div key={n.id} style={{ fontSize: 12.5, padding: '4px 0', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)' }}>
                        <span className="mono" style={{ fontSize: 10.5, color: 'var(--color-accent-700)', marginRight: 8 }}>{n.type}</span>
                        {n.name.length > 64 ? n.name.slice(0, 63) + '…' : n.name}
                      </div>
                    ))}
                    {ns.length > 8 && <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>+{ns.length - 8} more</div>}
                  </div>
                ))}
              <div>
                <div className="k" style={{ marginBottom: 6 }}>Audit trail · {diff.audit_entries.length}</div>
                {diff.audit_entries.slice(0, 8).map((a) => (
                  <div key={a.id} style={{ fontSize: 12, padding: '4px 0', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)' }}>
                    <span className="mono" style={{ fontSize: 10.5, marginRight: 8 }}>{a.occurred_at?.slice(0, 16)}</span>
                    {a.actor} · {a.summary.length > 56 ? a.summary.slice(0, 55) + '…' : a.summary}
                  </div>
                ))}
                {diff.audit_entries.length > 8 && (
                  <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>+{diff.audit_entries.length - 8} more</div>
                )}
              </div>
            </div>
          )}
        </Blueprint>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.05fr', gap: 30, alignItems: 'start' }}>
        <section>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <h4>Source document</h4>
            <span className="k">
              {match ? `${match.title} · ${match.citation_label}`
                : live ? 'no source clause resolved'
                : `TDI-HO-STATPLAN-2026.pdf · p. ${page} of 214`}
            </span>
          </div>
          <Blueprint style={{ padding: '34px 38px', background: '#fff' }}>
            <div style={{
              fontSize: 10, letterSpacing: '.09em', textTransform: 'uppercase',
              color: 'color-mix(in srgb,var(--color-text) 45%,transparent)',
              borderBottom: '1px solid var(--color-divider)', paddingBottom: 8, marginBottom: 20,
              display: 'flex', justifyContent: 'space-between',
            }}>
              <span>
                {match ? match.issuing_body
                  : live && sel ? (jurName ? `${jurName} · ${raw?.jurisdiction_code}` : 'Jurisdiction not recorded')
                  : 'Texas Department of Insurance'}
              </span>
              <span>
                {match ? match.document_type
                  : live && sel ? (raw?.source_kind ?? 'extracted rule')
                  : 'Residential Property Statistical Plan'}
              </span>
            </div>
            <div style={{ fontFamily: 'var(--font-heading)', fontSize: 19, marginBottom: 4 }}>{clause.t}</div>
            <div className="mono" style={{ fontSize: 11, color: 'var(--color-accent-700)', marginBottom: 16 }}>{clause.r}</div>
            <div style={{ fontSize: 13.5, lineHeight: 1.75, textWrap: 'pretty', whiteSpace: 'pre-wrap', color: '#25282a', maxHeight: 420, overflow: 'auto' }}>
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
            <span className="k">{pending} awaiting review · showing {filtered.length} of {cards.length}</span>
            <div className="seg" style={{ marginLeft: 'auto' }}>
              {([['pending', 'Pending'], ['low', 'Low confidence'], ['all', 'All']] as Array<[Filter, string]>).map(([f, label]) => (
                <label key={f} className="seg-opt">
                  <input type="radio" name="rf" checked={filter === f} onChange={() => setFilter(f)} />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search rules…"
              style={{
                flex: 1, padding: '6px 10px', fontSize: 12.5, fontFamily: 'var(--font-body)',
                border: '1px solid var(--color-divider)', borderRadius: 0,
                background: 'transparent', color: 'var(--color-text)', outline: 'none',
              }}
            />
            <div className="seg">
              {[['all', `All ${cards.length}`] as [string, string],
                ...sections.map(([s, n]) => [s, `${s === 'Other' ? 'Other' : '§' + s} ${n}`] as [string, string])]
                .map(([s, label]) => (
                  <label key={s} className="seg-opt">
                    <input type="radio" name="rsec" checked={section === s} onChange={() => setSection(s)} />
                    <span>{label}</span>
                  </label>
                ))}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 900, overflow: 'auto' }}>
            {filtered.map((r) => {
              const i = cards.indexOf(r);
              const d = decisionOf(r);
              // Compact one-line row for everything but the selected rule —
              // 139 full cards is a wall; the detail lives on selection.
              if (i !== selIdx) {
                return (
                  <Blueprint
                    key={r.id}
                    className="rowlink"
                    style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 8 }}
                    onClick={() => { setSelIdx(i); if (r.page) setPage(r.page); }}
                  >
                    <span className="mono" style={{ fontSize: 10.5, color: 'var(--color-accent-700)', flex: 'none' }}>
                      {r.id.length > 14 ? r.id.slice(0, 8) : r.id}
                    </span>
                    {r.raw?.jurisdiction_code && (
                      <span className="mono" style={{ fontSize: 10, flex: 'none', color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>
                        {r.raw.jurisdiction_code.replace('US-', '')}
                      </span>
                    )}
                    <span style={{ fontSize: 13, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {r.title}
                    </span>
                    <span className={'tag ' + (r.kind === 'Amended' ? 'tag-outline' : 'tag-neutral')}>{r.kind}</span>
                    <span className={'tag ' + (d === 'approved' ? 'tag-accent' : d === 'rejected' ? 'tag-neutral' : 'tag-outline')}>
                      {d === 'approved' ? 'Approved' : d === 'rejected' ? 'Sent back' : 'Pending'}
                    </span>
                  </Blueprint>
                );
              }
              return (
                <Blueprint
                  key={r.id}
                  style={{
                    padding: '16px 18px', cursor: 'pointer',
                    borderColor: ACC,
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
                      {mayDecide ? (
                        <>
                          {r.raw && (
                            <button className="btn btn-secondary"
                              title="author the rule's edit-package fields — target table, violation SQL, severity"
                              onClick={(e) => { e.stopPropagation(); setAuthorRule(r.raw!); }}>
                              {r.raw.violation_sql ? 'Edit executable…' : 'Make executable…'}
                            </button>
                          )}
                          <button className="btn btn-secondary" onClick={(e) => { e.stopPropagation(); decide(r.id, 'rejected'); }}>Reject</button>
                          <button className="btn btn-primary" onClick={(e) => { e.stopPropagation(); decide(r.id, 'approved'); }}>Approve</button>
                        </>
                      ) : (
                        <span className="k" title={`sign in as ${whoCan('rule_decision')} to review`}>
                          review requires {whoCan('rule_decision')}
                        </span>
                      )}
                    </span>
                  </div>
                </Blueprint>
              );
            })}
          </div>
        </section>
      </div>

      {authorRule && (
        <ExecutableFormModal key={authorRule.id} rule={authorRule}
          onClose={() => setAuthorRule(null)} />
      )}
    </div>
  );
}
