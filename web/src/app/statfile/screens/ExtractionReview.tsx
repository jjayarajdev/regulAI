// Extraction review — "agent proposes, human governs" for the rule
// extraction itself, reimagined as a native Ant Design workbench. Sentinel
// proposed every node in the extraction; a reviewer triages the proposals and
// records a verdict per proposal: accept, reject with a reason, or override
// individual fields. Approve-to-canon then materializes only what survived
// review.
//
// Layout is a fixed-height workbench (no page scrolling): Select document
// picker → Segmented band filter → master List (own scroll) beside a sticky
// detail Card with an always-visible verdict footer (own scroll). Approve
// lives in the header so it's always reachable. Live:
// /regulations/{slug}/review (file-backed sidecar next to the extraction
// JSON).
import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  Alert, Badge, Button, Card, Empty, Input, List, Segmented, Select, Space,
  Tag, Tooltip, Typography,
} from 'antd';
import {
  approveRegulation, can, useExtractionReview, useExtractStatus, useRegulations,
  useSetProposalVerdict, whoCan,
  type AppUser, type ReviewProposal,
} from '../api';

const { Text } = Typography;
const MONO: CSSProperties = { fontFamily: "ui-monospace,'SFMono-Regular',Menlo,monospace" };

const fmt = (n: number) => n.toLocaleString('en-US');
// Confidence bands by meaning: auto ≥0.90 green, queued 0.70–0.89 orange,
// escalated <0.70 red.
const confColor = (c: number) => (c >= 0.9 ? 'green' : c >= 0.7 ? 'orange' : 'red');

const VERDICT_TAG: Record<ReviewProposal['verdict'], [string | undefined, string]> = {
  accepted: ['green', 'Accepted'],
  overridden: ['purple', 'Overridden'],
  rejected: ['red', 'Rejected'],
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

const fieldLabel: CSSProperties = { fontSize: 12, display: 'block' };

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

  const [tagColor, tagLabel] = VERDICT_TAG[p.verdict];
  const rejected = p.verdict === 'rejected';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', opacity: rejected ? 0.85 : 1 }}>
      {/* header — proposal identity + verdict state */}
      <div style={{ padding: '14px 18px 10px', borderBottom: '1px solid rgba(5,5,5,0.06)', flex: 'none' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <Text strong delete={rejected} style={{ ...MONO, fontSize: 14 }}>
            {String(p.overrides?.name ?? p.name)}
          </Text>
          <Tag>{p.type}</Tag>
          <Tag color={tagColor}>{tagLabel}</Tag>
          <Tag color={confColor(p.confidence)} style={{ marginLeft: 'auto', marginInlineEnd: 0 }}
            title={`confidence ${p.confidence.toFixed(2)}`}>
            conf {p.confidence.toFixed(2)}
          </Tag>
        </div>
        {p.actor && (
          <Text type="secondary" style={{ ...MONO, display: 'block', fontSize: 10.5, marginTop: 5 }}>
            reviewed by {p.actor} · {(p.at ?? '').replace('T', ' ')}
          </Text>
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
                  <Text type="secondary" style={{ flex: 'none', fontSize: 12 }}>{k}</Text>
                  <span style={{ ...MONO, fontSize: 11.5, overflowWrap: 'anywhere' }}>
                    {over ? (
                      <>
                        <Text delete type="secondary" style={{ fontSize: 11.5 }}>{String(v)}</Text>{' '}
                        <span style={{ color: '#1677ff' }}>{String(p.overrides![k])}</span>
                      </>
                    ) : String(v)}
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {p.citations.map((c, i) => (
          <div key={i} style={{ marginBottom: 10, paddingLeft: 12, borderLeft: '3px solid #d9d9d9' }}>
            <Text type="secondary" style={{ display: 'block', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
              Cited · {c.kind} · chars {fmt(c.char_start)}–{fmt(c.char_end)}
            </Text>
            <Text italic style={{ fontSize: 12.5, lineHeight: 1.6, opacity: 0.85 }}>
              “{c.excerpt}”
            </Text>
          </div>
        ))}
        {p.citations.length === 0 && (
          <Text type="warning" style={{ display: 'block', fontSize: 12, marginBottom: 10 }}>
            ⚑ no citation — the agent proposed this without a supporting span
          </Text>
        )}

        {mode === 'view' && p.reason && (
          <Alert type="info" showIcon message="Reviewer" description={p.reason}
            style={{ margin: '4px 0 12px' }} />
        )}
      </div>

      {/* action footer — always visible, no scrolling to reach a verdict */}
      <div style={{ padding: '12px 18px 14px', borderTop: '1px solid rgba(5,5,5,0.06)', flex: 'none' }}>
        {mode === 'view' && (
          <Space size={8}>
            {rejected || p.verdict === 'overridden' ? (
              <Tooltip title={mayReview ? 'back to accepted-as-proposed' : `requires ${whoCan('bulletin')}`}>
                <Button disabled={!mayReview} loading={verdictMut.isPending} onClick={doAccept}>
                  Reset to accepted
                </Button>
              </Tooltip>
            ) : (
              <>
                <Tooltip title={mayReview ? undefined : `requires ${whoCan('bulletin')}`}>
                  <Button disabled={!mayReview} onClick={() => open('edit')}>Edit fields…</Button>
                </Tooltip>
                <Tooltip title={mayReview ? undefined : `requires ${whoCan('bulletin')}`}>
                  <Button disabled={!mayReview} onClick={() => open('reject')}>Reject…</Button>
                </Tooltip>
              </>
            )}
            {verdictMut.isPending && <Text type="secondary" style={{ fontSize: 12 }}>saving…</Text>}
          </Space>
        )}

        {mode === 'reject' && (
          <div>
            <label style={fieldLabel}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Why is this proposal wrong? (goes on the review record)
              </Text>
              <Input.TextArea
                value={reason} rows={2} autoFocus style={{ marginTop: 4 }}
                onChange={(e) => setReason(e.target.value)}
              />
            </label>
            <Space size={8} style={{ marginTop: 10 }}>
              <Button type="primary" danger disabled={!reason.trim()} loading={verdictMut.isPending} onClick={doReject}>
                Reject proposal
              </Button>
              <Button onClick={close}>Cancel</Button>
            </Space>
          </div>
        )}

        {mode === 'edit' && (
          <div style={{ maxHeight: 300, overflow: 'auto' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 16px', marginBottom: 10 }}>
              {EDITABLE.map(([k, label, kind]) => (
                <label key={k} style={{ ...fieldLabel, gridColumn: kind === 'area' ? '1 / -1' : undefined }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>{label}</Text>
                  {kind === 'area' ? (
                    <Input.TextArea
                      value={draft[k] ?? ''} rows={2} style={{ marginTop: 4 }}
                      onChange={(e) => setDraft((d) => ({ ...d, [k]: e.target.value }))}
                    />
                  ) : (
                    <Input
                      value={draft[k] ?? ''} type={kind === 'number' ? 'number' : 'text'}
                      style={{ marginTop: 4 }}
                      onChange={(e) => setDraft((d) => ({ ...d, [k]: e.target.value }))}
                    />
                  )}
                </label>
              ))}
            </div>
            <label style={{ ...fieldLabel, marginBottom: 10 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>Reason for the correction</Text>
              <Input value={reason} style={{ marginTop: 4 }} onChange={(e) => setReason(e.target.value)} />
            </label>
            <Space size={8}>
              <Button type="primary" disabled={!reason.trim()} loading={verdictMut.isPending} onClick={doOverride}>
                Save override
              </Button>
              <Button onClick={close}>Cancel</Button>
            </Space>
          </div>
        )}

        {verdictMut.error != null && (
          <Text type="danger" style={{ display: 'block', fontSize: 12, marginTop: 8 }}>
            {(verdictMut.error as Error).message}
          </Text>
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
    <div>
      {/* ── header: document picker + review stats + approve ───────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 12, flexWrap: 'wrap' }}>
        <Select
          value={doc?.slug ?? ''}
          onChange={(slug) => { setSelSlug(slug); setSelId(null); setFilter('all'); setApproveMsg(null); }}
          style={{ minWidth: 260, maxWidth: 420 }}
          options={docs.length > 0
            ? docs.map((m) => ({ value: m.slug, label: m.label }))
            : [{ value: '', label: 'no extractions on disk yet' }]}
        />

        {d && (
          <Text type="secondary" title={d.summary} style={{ ...MONO, fontSize: 11 }}>
            {fmt(d.totals.proposals)} proposals · avg {d.totals.avg_confidence?.toFixed(2) ?? '—'}
            {d.totals.overridden > 0 && <> · <span style={{ color: '#1677ff' }}>{d.totals.overridden} overridden</span></>}
            {d.totals.rejected > 0 && <> · <span style={{ color: '#1677ff' }}>{d.totals.rejected} rejected</span></>}
          </Text>
        )}

        <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 10 }}>
          {approveMsg && <Text style={{ fontSize: 12 }}>{approveMsg}</Text>}
          {d && (
            <Tooltip title={mayReview
              ? `Materializes ${fmt(d.totals.accepted)} proposals to the knowledge graph`
                + (d.totals.rejected ? `, drops ${d.totals.rejected} rejected` : '')
                + '. Re-approving is safe — materialization dedupes.'
              : `requires ${whoCan('bulletin')}`}>
              <Button type="primary" disabled={!mayReview} loading={approving} onClick={doApprove}>
                Approve {fmt(d.totals.accepted)} to canon →
              </Button>
            </Tooltip>
          )}
        </span>
      </div>

      {/* ── band filter ─────────────────────────────────────────────────── */}
      {d && (
        <Segmented
          value={filter}
          onChange={(f) => { setFilter(f as Filter); setSelId(null); }}
          style={{ marginBottom: 12 }}
          options={chips.map(([f, label, count]) => ({
            value: f,
            label: <span>{label} <Text type="secondary" style={{ fontSize: 11 }}>{count}</Text></span>,
          }))}
        />
      )}

      {extracting && (
        <Alert
          type="warning" showIcon style={{ marginBottom: 12 }}
          message="Sentinel is re-extracting this document…"
          description="The proposal set is being rewritten, so review actions are locked until it finishes."
        />
      )}

      {loading && <Card loading />}
      {!loading && !d && (
        <Empty
          style={{ marginTop: 48 }}
          description={
            <Text type="secondary" style={{ fontSize: 13 }}>
              No extraction on disk yet — upload and extract a document from
              Administration → Add a jurisdiction, then review the proposals here.
            </Text>
          }
        />
      )}

      {/* ── the workbench: list (own scroll) beside detail (own scroll) ── */}
      {!loading && d && (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(340px,2fr) 3fr', gap: 16, alignItems: 'stretch', height: PANE_H }}>
          <Card style={{ height: '100%' }} styles={{ body: { padding: 0, height: '100%', overflow: 'auto' } }}>
            <List
              size="small"
              dataSource={shown}
              locale={{ emptyText: 'nothing in this band' }}
              renderItem={(p) => {
                const on = p.temp_id === active?.temp_id;
                const [tagColor, tagLabel] = VERDICT_TAG[p.verdict];
                return (
                  <List.Item
                    onClick={() => setSelId(p.temp_id)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 9, padding: '8px 12px',
                      cursor: 'pointer',
                      borderLeft: '3px solid ' + (on ? '#1677ff' : 'transparent'),
                      background: on ? 'rgba(22,119,255,0.08)' : undefined,
                    }}
                  >
                    <span title={`confidence ${p.confidence.toFixed(2)}`} style={{ flex: 'none', lineHeight: 1 }}>
                      <Badge color={confColor(p.confidence)} />
                    </span>
                    <span style={{
                      flex: 1, minWidth: 0, fontSize: 12.5,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      textDecoration: p.verdict === 'rejected' ? 'line-through' : undefined,
                      opacity: p.verdict === 'rejected' ? 0.6 : 1,
                    }}>
                      {String(p.overrides?.name ?? p.name)}
                    </span>
                    <Text type="secondary" style={{ ...MONO, fontSize: 9.5, flex: 'none' }}>{p.type}</Text>
                    <Tag color={tagColor} style={{ flex: 'none', fontSize: 9.5, lineHeight: '16px', marginInlineEnd: 0 }}>
                      {tagLabel}
                    </Tag>
                  </List.Item>
                );
              }}
            />
          </Card>

          <Card style={{ height: '100%' }} styles={{ body: { padding: 0, height: '100%', overflow: 'hidden' } }}>
            {active && doc ? (
              <ProposalDetail key={active.temp_id} slug={doc.slug} p={active}
                mayReview={mayReview} actor={user.name} />
            ) : (
              <Text type="secondary" style={{ display: 'block', padding: 16 }}>select a proposal</Text>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
