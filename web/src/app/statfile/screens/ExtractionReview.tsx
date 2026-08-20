// Extraction review — "agent proposes, human governs" for the rule
// extraction itself. Sentinel proposed every node in the extraction; a
// reviewer triages the proposals and records a verdict per proposal: accept,
// reject with a reason, or override individual fields. Approve-to-canon then
// materializes only what survived review.
//
// Layout is a fixed-height workbench (no page scrolling): document picker →
// band-filter chips → master list (own scroll) beside a sticky detail pane
// (own scroll). Approve lives in the header so it's always reachable.
// Live: /regulations/{slug}/review (file-backed sidecar next to the
// extraction JSON).
import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Blueprint } from '../Blueprint';
import {
  approveRegulation, can, useExtractionReview, useExtractStatus, useRegulations,
  useSetProposalVerdict, whoCan,
  type AppUser, type ReviewProposal,
} from '../api';
import { ACC, ACC9, NEU } from '../data';

const fmt = (n: number) => n.toLocaleString('en-US');
const confDot = (c: number) => (c >= 0.9 ? NEU : c >= 0.7 ? ACC : ACC9);

const VERDICT_TAG: Record<ReviewProposal['verdict'], [string, string]> = {
  accepted: ['tag-neutral', 'Accepted'],
  overridden: ['tag-accent', 'Overridden'],
  rejected: ['tag-outline', 'Rejected'],
};

// The fields a reviewer can correct in place. Everything else the agent
// proposed is display-only — a wrong type/temp_id is a rejection, not an edit.
const EDITABLE: Array<[key: string, label: string, kind: 'text' | 'number' | 'area']> = [
  ['name', 'Name', 'text'],
  ['section', 'Section', 'text'],
  ['rule_number', 'Rule number', 'number'],
  ['heading', 'Heading', 'text'],
  ['description', 'Description', 'area'],
];

// Review order: the bands the reviewer must look at float — escalated,
// queued, auto — lowest confidence first within each.
const BAND_RANK = { escalated: 0, queued: 1, auto: 2 } as const;
const sortProposals = (ps: ReviewProposal[]): ReviewProposal[] =>
  [...ps].sort((a, b) =>
    BAND_RANK[a.band] - BAND_RANK[b.band] || a.confidence - b.confidence);

type Filter = 'all' | 'attention' | 'escalated' | 'queued' | 'auto' | 'decided';
const matches = (p: ReviewProposal, f: Filter): boolean =>
  f === 'all' ? true
  : f === 'attention' ? p.band !== 'auto' && p.verdict === 'accepted' && !p.reason
  : f === 'decided' ? p.verdict !== 'accepted' || !!p.reason
  : p.band === f;

// The workbench height: everything below the app header fits the viewport.
const PANE_H = 'max(420px, calc(100vh - 322px))';

function ConfidenceCell({ c }: { c: number }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>
      <span className="mono" style={{ fontSize: 11.5 }}>{c.toFixed(2)}</span>
      <span style={{ width: 8, height: 8, background: confDot(c), flex: 'none' }} />
    </span>
  );
}

const inputStyle: CSSProperties = {
  display: 'block', width: '100%', boxSizing: 'border-box', marginTop: 4,
  padding: '7px 9px', fontSize: 12.5, fontFamily: 'var(--font-body)',
  border: '1px solid var(--color-divider)', borderRadius: 0,
  background: 'color-mix(in srgb,var(--color-text) 4%,transparent)',
  color: 'var(--color-text)',
};

// The right pane: one proposal's evidence + the verdict editor.
function ProposalDetail({ slug, p, mayReview, actor }: {
  slug: string; p: ReviewProposal; mayReview: boolean; actor: string;
}) {
  const verdictMut = useSetProposalVerdict();
  const [mode, setMode] = useState<'view' | 'reject' | 'edit'>('view');
  const [reason, setReason] = useState('');
  const [draft, setDraft] = useState<Record<string, string>>({});

  // Current value per editable field: override (if any) wins over proposal.
  const current = (key: string): string => {
    const v = p.overrides?.[key] ?? (key === 'name' ? p.name : p.fields[key]);
    return v == null ? '' : String(v);
  };
  const open = (m: 'reject' | 'edit') => {
    setMode(m); setReason(p.reason ?? '');
    if (m === 'edit') {
      setDraft(Object.fromEntries(EDITABLE.map(([k]) => [k, current(k)])));
    }
  };
  const close = () => { setMode('view'); setReason(''); verdictMut.reset(); };

  const put = (body: Parameters<typeof verdictMut.mutate>[0]) =>
    verdictMut.mutate(body, { onSuccess: close });

  const doAccept = () => put({ slug, tempId: p.temp_id, verdict: 'accepted', actor });
  const doReject = () => put({ slug, tempId: p.temp_id, verdict: 'rejected', reason: reason.trim(), actor });
  const doOverride = () => {
    // Only ship the fields that actually changed vs the agent's proposal.
    const overrides: Record<string, unknown> = {};
    for (const [k, , kind] of EDITABLE) {
      const orig = p.overrides?.[k] !== undefined ? p.overrides[k]
        : (k === 'name' ? p.name : p.fields[k] ?? null);
      const raw = (draft[k] ?? '').trim();
      const next = raw === '' ? null : kind === 'number' ? Number(raw) : raw;
      if (next !== (orig ?? null)) overrides[k] = next;
    }
    if (!Object.keys(overrides).length) { close(); return; }
    put({ slug, tempId: p.temp_id, verdict: 'overridden', overrides, reason: reason.trim(), actor });
  };

  const [tagClass, tagLabel] = VERDICT_TAG[p.verdict];
  const rejected = p.verdict === 'rejected';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', opacity: rejected ? 0.85 : 1 }}>
      {/* header — proposal identity + verdict state */}
      <div style={{ padding: '14px 18px 10px', borderBottom: '1px solid var(--color-divider)', flex: 'none' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span className="mono" style={{ fontSize: 14, color: 'var(--color-accent-700)', textDecoration: rejected ? 'line-through' : undefined }}>
            {String(p.overrides?.name ?? p.name)}
          </span>
          <span className="tag tag-outline">{p.type}</span>
          <span className={'tag ' + tagClass}>{tagLabel}</span>
          <span style={{ marginLeft: 'auto' }}><ConfidenceCell c={p.confidence} /></span>
        </div>
        {p.actor && (
          <div className="mono muted" style={{ fontSize: 10.5, marginTop: 5 }}>
            reviewed by {p.actor} · {(p.at ?? '').replace('T', ' ')}
          </div>
        )}
      </div>

      {/* scrollable body — fields + evidence + reviewer note */}
      <div style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: '12px 18px' }}>
        {Object.keys(p.fields).length > 0 && (
          <div style={{ marginBottom: 12, display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', gap: '6px 18px' }}>
            {Object.entries(p.fields).map(([k, v]) => {
              const over = p.overrides?.[k] !== undefined;
              return (
                <div key={k} style={{ fontSize: 12, display: 'flex', gap: 8, alignItems: 'baseline' }}>
                  <span className="k" style={{ flex: 'none' }}>{k}</span>
                  <span className="mono" style={{ fontSize: 11.5, overflowWrap: 'anywhere' }}>
                    {over ? (
                      <>
                        <s style={{ opacity: 0.55 }}>{String(v)}</s>{' '}
                        <span style={{ color: 'var(--color-accent-700)' }}>{String(p.overrides![k])}</span>
                      </>
                    ) : String(v)}
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {p.citations.map((c, i) => (
          <div key={i} style={{ marginBottom: 10, paddingLeft: 12, borderLeft: `3px solid ${NEU}` }}>
            <div className="k" style={{ marginBottom: 4 }}>
              Cited · {c.kind} · chars {fmt(c.char_start)}–{fmt(c.char_end)}
            </div>
            <div style={{ fontSize: 12.5, lineHeight: 1.6, fontStyle: 'italic', opacity: 0.85 }}>
              “{c.excerpt}”
            </div>
          </div>
        ))}
        {p.citations.length === 0 && (
          <div className="mono muted" style={{ fontSize: 10.5, marginBottom: 10 }}>
            ⚑ no citation — the agent proposed this without a supporting span
          </div>
        )}

        {mode === 'view' && p.reason && (
          <div style={{
            margin: '4px 0 12px', padding: '11px 13px',
            borderLeft: '3px solid var(--color-accent)',
            background: 'color-mix(in srgb,var(--color-accent) 7%,transparent)',
          }}>
            <div className="k" style={{ marginBottom: 5 }}>Reviewer</div>
            <div style={{ fontSize: 12.5, lineHeight: 1.6 }}>{p.reason}</div>
          </div>
        )}
      </div>

      {/* action footer — always visible, no scrolling to reach a verdict */}
      <div style={{ padding: '12px 18px 14px', borderTop: '1px solid var(--color-divider)', flex: 'none' }}>
        {mode === 'view' && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {rejected || p.verdict === 'overridden' ? (
              <button className="btn btn-secondary" disabled={!mayReview || verdictMut.isPending}
                title={mayReview ? 'back to accepted-as-proposed' : `requires ${whoCan('bulletin')}`}
                onClick={doAccept}>
                Reset to accepted
              </button>
            ) : (
              <>
                <button className="btn btn-secondary" disabled={!mayReview}
                  title={mayReview ? undefined : `requires ${whoCan('bulletin')}`}
                  onClick={() => open('edit')}>
                  Edit fields…
                </button>
                <button className="btn btn-secondary" disabled={!mayReview}
                  title={mayReview ? undefined : `requires ${whoCan('bulletin')}`}
                  onClick={() => open('reject')}>
                  Reject…
                </button>
              </>
            )}
            {verdictMut.isPending && <span className="k">saving…</span>}
          </div>
        )}

        {mode === 'reject' && (
          <div>
            <label style={{ fontSize: 12, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>
              Why is this proposal wrong? (goes on the review record)
              <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2}
                style={{ ...inputStyle, resize: 'vertical' }} autoFocus />
            </label>
            <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
              <button className="btn btn-primary" disabled={!reason.trim() || verdictMut.isPending} onClick={doReject}>
                {verdictMut.isPending ? 'Saving…' : 'Reject proposal'}
              </button>
              <button className="btn btn-secondary" onClick={close}>Cancel</button>
            </div>
          </div>
        )}

        {mode === 'edit' && (
          <div style={{ maxHeight: 300, overflow: 'auto' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 16px', marginBottom: 10 }}>
              {EDITABLE.map(([k, label, kind]) => (
                <label key={k} style={{ fontSize: 12, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)', gridColumn: kind === 'area' ? '1 / -1' : undefined }}>
                  {label}
                  {kind === 'area' ? (
                    <textarea value={draft[k] ?? ''} rows={2}
                      onChange={(e) => setDraft((d) => ({ ...d, [k]: e.target.value }))}
                      style={{ ...inputStyle, resize: 'vertical' }} />
                  ) : (
                    <input value={draft[k] ?? ''} type={kind === 'number' ? 'number' : 'text'}
                      onChange={(e) => setDraft((d) => ({ ...d, [k]: e.target.value }))}
                      style={inputStyle} />
                  )}
                </label>
              ))}
            </div>
            <label style={{ fontSize: 12, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)', display: 'block', marginBottom: 10 }}>
              Reason for the correction
              <input value={reason} onChange={(e) => setReason(e.target.value)} style={inputStyle} />
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-primary" disabled={!reason.trim() || verdictMut.isPending} onClick={doOverride}>
                {verdictMut.isPending ? 'Saving…' : 'Save override'}
              </button>
              <button className="btn btn-secondary" onClick={close}>Cancel</button>
            </div>
          </div>
        )}

        {verdictMut.error != null && (
          <div style={{ fontSize: 12, color: '#a33', marginTop: 8 }}>{(verdictMut.error as Error).message}</div>
        )}
      </div>
    </div>
  );
}

export function ExtractionReviewScreen({ user }: { user: AppUser }) {
  const docsQ = useRegulations();
  const docs = (docsQ.data?.documents ?? []).filter((d) => d.has_extraction);

  const [selSlug, setSelSlug] = useState<string | null>(null);
  const doc = docs.find((d) => d.slug === selSlug) ?? docs[0];

  const reviewQ = useExtractionReview(doc?.slug ?? null);
  const d = reviewQ.data;
  const loading = docsQ.isPending || (!!doc && reviewQ.isPending);

  // If Sentinel is (re)extracting this document, the proposal set is being
  // rewritten — lock every verdict/approve action (the API 409s them too)
  // and refresh the review once the job lands.
  const statusQ = useExtractStatus(doc?.slug ?? null, true);
  const extracting = statusQ.data?.status === 'running';
  const mayReview = can(user, 'bulletin') && !extracting;
  useEffect(() => {
    if (!extracting && statusQ.data?.status === 'done') reviewQ.refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refetch on job completion only
  }, [extracting]);

  const [filter, setFilter] = useState<Filter>('all');
  const [selId, setSelId] = useState<string | null>(null);

  const sorted = useMemo(() => sortProposals(d?.proposals ?? []), [d]);
  const shown = useMemo(() => sorted.filter((p) => matches(p, filter)), [sorted, filter]);
  const active = shown.find((p) => p.temp_id === selId) ?? shown[0];

  // Approve → canon: materializes accepted + overridden, drops rejected.
  const qc = useQueryClient();
  const [approving, setApproving] = useState(false);
  const [approveMsg, setApproveMsg] = useState<string | null>(null);
  const doApprove = async () => {
    if (!doc) return;
    setApproving(true); setApproveMsg(null);
    try {
      const r = await approveRegulation(doc.slug) as {
        nodes_created?: unknown[]; review?: { nodes_rejected?: number };
      };
      const created = Array.isArray(r.nodes_created) ? r.nodes_created.length : 0;
      const dropped = r.review?.nodes_rejected ?? 0;
      setApproveMsg(`✓ Materialized ${created} nodes`
        + (dropped ? ` · ${dropped} rejected dropped` : ''));
      qc.invalidateQueries({ queryKey: ['sf', 'kg-rules'] });
      qc.invalidateQueries({ queryKey: ['sf', 'regulations'] });
    } catch (e) {
      setApproveMsg((e as Error).message);
    } finally { setApproving(false); }
  };

  const attention = sorted.filter((p) => matches(p, 'attention')).length;
  const decided = sorted.filter((p) => matches(p, 'decided')).length;
  const chips: Array<[Filter, string, number]> = d ? [
    ['all', 'All', d.totals.proposals],
    ['attention', 'Needs review', attention],
    ['escalated', 'Escalated <0.70', d.totals.escalated],
    ['queued', 'Queued 0.70–0.89', d.totals.queued],
    ['auto', 'Auto ≥0.90', d.totals.proposals - d.totals.queued - d.totals.escalated],
    ['decided', 'Decided', decided],
  ] : [];

  return (
    <div className="sc">
      {/* ── header: document picker + review stats + approve ───────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 12, flexWrap: 'wrap' }}>
        <select
          value={doc?.slug ?? ''}
          onChange={(e) => { setSelSlug(e.target.value); setSelId(null); setFilter('all'); setApproveMsg(null); }}
          style={{
            padding: '8px 10px', fontSize: 13, fontFamily: 'var(--font-body)',
            border: '1px solid var(--color-divider)', borderRadius: 0,
            background: 'var(--color-bg, transparent)', color: 'var(--color-text)',
            maxWidth: 420,
          }}
        >
          {docs.map((m) => <option key={m.slug} value={m.slug}>{m.label}</option>)}
          {docs.length === 0 && <option value="">no extractions on disk yet</option>}
        </select>

        {d && (
          <span className="mono muted" style={{ fontSize: 11 }} title={d.summary}>
            {fmt(d.totals.proposals)} proposals · avg {d.totals.avg_confidence?.toFixed(2) ?? '—'}
            {d.totals.overridden > 0 && <> · <span style={{ color: 'var(--color-accent-700)' }}>{d.totals.overridden} overridden</span></>}
            {d.totals.rejected > 0 && <> · <span style={{ color: 'var(--color-accent-700)' }}>{d.totals.rejected} rejected</span></>}
          </span>
        )}

        <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 10 }}>
          {approveMsg && <span style={{ fontSize: 12 }}>{approveMsg}</span>}
          {d && (
            <button className="btn btn-primary" disabled={!mayReview || approving}
              title={mayReview
                ? `Materializes ${fmt(d.totals.accepted)} proposals to the knowledge graph`
                  + (d.totals.rejected ? `, drops ${d.totals.rejected} rejected` : '')
                  + '. Re-approving is safe — materialization dedupes.'
                : `requires ${whoCan('bulletin')}`}
              onClick={doApprove}>
              {approving ? 'Materializing…' : `Approve ${fmt(d.totals.accepted)} to canon →`}
            </button>
          )}
        </span>
      </div>

      {/* ── band filter chips ───────────────────────────────────────────── */}
      {d && (
        <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
          {chips.map(([f, label, count]) => (
            <button key={f} onClick={() => { setFilter(f); setSelId(null); }}
              style={{
                padding: '4px 11px', fontSize: 11.5, cursor: 'pointer', borderRadius: 0,
                fontFamily: 'var(--font-body)',
                border: '1px solid ' + (filter === f ? 'var(--color-accent)' : 'var(--color-divider)'),
                background: filter === f ? 'color-mix(in srgb,var(--color-accent) 10%,transparent)' : 'transparent',
                color: 'var(--color-text)',
              }}>
              {label} <span className="mono" style={{ fontSize: 10.5, opacity: 0.7 }}>{count}</span>
            </button>
          ))}
        </div>
      )}

      {extracting && (
        <div style={{
          marginBottom: 12, padding: '10px 14px', fontSize: 12.5,
          borderLeft: '3px solid var(--color-accent)',
          background: 'color-mix(in srgb,var(--color-accent) 8%,transparent)',
        }}>
          <span className="mono" style={{ fontSize: 11.5 }}>Sentinel is re-extracting this document…</span>
          {' '}the proposal set is being rewritten, so review actions are locked until it finishes.
        </div>
      )}

      {loading && <div className="k">loading extraction…</div>}
      {!loading && !d && (
        <div className="muted" style={{ fontSize: 13, lineHeight: 1.6, maxWidth: 520 }}>
          No extraction on disk yet — upload and extract a document from
          Administration → Add a jurisdiction, then review the proposals here.
        </div>
      )}

      {/* ── the workbench: list (own scroll) beside detail (own scroll) ── */}
      {!loading && d && (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(340px,2fr) 3fr', gap: 18, alignItems: 'stretch', height: PANE_H }}>
          <Blueprint style={{ overflow: 'auto', padding: 0 }}>
            {shown.map((p) => {
              const on = p.temp_id === active?.temp_id;
              const [tagClass, tagLabel] = VERDICT_TAG[p.verdict];
              return (
                <div key={p.temp_id} className="rowlink" onClick={() => setSelId(p.temp_id)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 9, padding: '8px 12px',
                    borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)',
                    borderLeft: '3px solid ' + (on ? 'var(--color-accent)' : 'transparent'),
                    background: on ? 'color-mix(in srgb,#5980a6 10%,transparent)' : undefined,
                  }}>
                  <span title={`confidence ${p.confidence.toFixed(2)}`}
                    style={{ width: 8, height: 8, background: confDot(p.confidence), flex: 'none' }} />
                  <span style={{
                    flex: 1, minWidth: 0, fontSize: 12.5,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    textDecoration: p.verdict === 'rejected' ? 'line-through' : undefined,
                    opacity: p.verdict === 'rejected' ? 0.6 : 1,
                  }}>
                    {String(p.overrides?.name ?? p.name)}
                  </span>
                  <span className="mono muted" style={{ fontSize: 9.5, flex: 'none' }}>{p.type}</span>
                  <span className={'tag ' + tagClass} style={{ flex: 'none', fontSize: 9.5 }}>{tagLabel}</span>
                </div>
              );
            })}
            {shown.length === 0 && (
              <div className="k" style={{ padding: 16 }}>nothing in this band</div>
            )}
          </Blueprint>

          <Blueprint style={{ overflow: 'hidden', padding: 0 }}>
            {active && doc ? (
              <ProposalDetail key={active.temp_id} slug={doc.slug} p={active}
                mayReview={mayReview} actor={user.name} />
            ) : (
              <div className="k" style={{ padding: 16 }}>select a proposal</div>
            )}
          </Blueprint>
        </div>
      )}
    </div>
  );
}
