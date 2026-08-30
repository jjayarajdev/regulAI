// TX record inspector — reimagined as a native Ant Design page: Segmented
// record-set picker, pager and policy search in the toolbar, the encoded TSPR
// record as a highlighted mono block (click a field row to light its slice),
// the field-by-field breakdown as a dense Table, and the submission package /
// open edits / GL reconciliation as Cards on a side rail. Live: navigates the
// policies with open edits (/validate/all), renders each one's
// SILVER.TSPR_PREMIUM_STAGING row (/submission/{policy}); the record image and
// positions are assembled from the encoded field values. Demo record when the
// warehouse is cold.
import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from 'react';
import { LeftOutlined, RightOutlined } from '@ant-design/icons';
import { Button, Card, Col, Input, Row, Segmented, Table, Tag, Tooltip, Typography } from 'antd';
import {
  can, policiesFrom, useAdvanceFiling, useApprovalState, useFilings, usePipelineContract,
  useReconciliation, useSubmission, useSubmissionPolicies, useValidateAll, whoCan, type AppUser,
} from '../api';
import { PKG, REC_FIELDS, RECON, RECORD_IMAGE } from '../data';

const { Text } = Typography;

const MONO: CSSProperties = { fontFamily: "ui-monospace,'SFMono-Regular',Menlo,monospace" };
const K: CSSProperties = { fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em' };

// Provenance for the staging columns the contract endpoint doesn't carry
// (system-populated ones the mapping agent must not touch).
const SRC: Record<string, string> = {
  record_type: 'transform (fixed)',
  stat_plan: 'transform (fixed)',
  validation_status: 'rule engine',
};

// Decode the TSPR-encoded value back to something a human can read. Only the
// deterministic encodings — dates (Rule 8), $1000s amounts, ZIP+4, constants.
const fmtUsd = (v: unknown) => '$' + Number(v).toLocaleString('en-US');
function decode(name: string, v: string | number | null): string {
  if (v == null) return '∅ null';
  const s = String(v);
  switch (name) {
    case 'effective_date':
      return s.length === 5 ? `MMDDY → ${s.slice(0, 2)}/${s.slice(2, 4)} · yr …${s[4]}` : '';
    case 'expiry_date':
      return s.length === 3 ? `MMY → ${s.slice(0, 2)} · yr …${s[2]}` : '';
    case 'amt_insurance_dw': return `Dwelling ${fmtUsd(Number(v) * 1000)}`;
    case 'amt_insurance_pp': return `Contents ${fmtUsd(Number(v) * 1000)}`;
    case 'amt_insurance_alu': return `ALE ${fmtUsd(Number(v) * 1000)}`;
    case 'fire_premium': return `Fire ${fmtUsd(v)}`;
    case 'ec_premium': return `Ext. coverage ${fmtUsd(v)}`;
    case 'deductible_1_amt': return fmtUsd(v);
    case 'zip9': return s.length >= 9 ? `${s.slice(0, 5)}-${s.slice(5)}` : s;
    case 'line_of_business': return s === '1' ? 'Homeowners' : '';
    case 'record_type': return s === '01' ? 'Premium record' : '';
    case 'stat_plan': return s === '4' ? 'TX stat plan' : '';
    case 'number_of_families': return `${s}-family`;
    default: return '';
  }
}

interface FieldRow { pos: string; name: string; val: string; dec: string; src: string; rule: string }

type RecordSet = 'edits' | 'clean' | 'all';

function MetaRow({ k, children }: { k: string; children: ReactNode }) {
  return (
    <div style={{ display: 'flex', gap: 10, padding: '5px 0', fontSize: 12.5, borderBottom: '1px solid rgba(5,5,5,0.06)' }}>
      <Text type="secondary" style={{ flex: 1, fontSize: 12 }}>{k}</Text>
      <span style={{ ...MONO, fontSize: 11.5, overflowWrap: 'anywhere' }}>{children}</span>
    </div>
  );
}

export function RecordScreen({ initialPolicy, user }: { initialPolicy?: string | null; user?: AppUser }) {
  const valQ = useValidateAll();
  const filingsQ = useFilings();
  const withEdits = useMemo(() => policiesFrom(valQ.data), [valQ.data]);

  // Full staged set (scoped to the active filing) → clean = staged − edits.
  const activeFiling = filingsQ.data?.filings.find((f) => f.is_active);
  const allQ = useSubmissionPolicies(activeFiling?.id ?? null);
  const allPolicies = allQ.data?.policies ?? [];
  const editSet = useMemo(() => new Set(withEdits), [withEdits]);
  const clean = useMemo(() => allPolicies.filter((p) => !editSet.has(p)), [allPolicies, editSet]);

  const [mode, setMode] = useState<RecordSet | null>(null);
  // Default: walk the problem records if any exist, else the clean set.
  const effMode: RecordSet = mode ?? (withEdits.length ? 'edits' : 'clean');
  const policies = effMode === 'edits' ? withEdits : effMode === 'clean' ? clean : allPolicies;
  const SET_LABEL: Record<RecordSet, string> = {
    edits: 'with edits', clean: 'clean — ready to submit', all: 'staged',
  };

  const [idx, setIdx] = useState(0);
  // Search overrides the failing-policy picker — any policy is inspectable.
  const [override, setOverride] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  // Deep link from the validation screen's "Trace to Guidewire".
  useEffect(() => {
    if (!initialPolicy) return;
    const i = withEdits.indexOf(initialPolicy);
    if (i >= 0) { setMode('edits'); setIdx(i); setOverride(null); }
    else setOverride(initialPolicy);
  }, [initialPolicy, withEdits]);
  const policy = override ?? (policies.length ? policies[Math.min(idx, policies.length - 1)] : null);
  const subQ = useSubmission(policy);

  const live = !!(policy && subQ.data?.found && subQ.data.fields);

  // Real Bronze→Silver provenance per column, from the same contract endpoint
  // the pipeline screen renders.
  const conQ = usePipelineContract();
  const contractBy = useMemo(() => {
    const m = new Map<string, { source: string | null; rule: string | null }>();
    for (const c of conQ.data?.columns ?? []) {
      m.set(c.name.toLowerCase(), { source: c.source, rule: c.rule });
    }
    return m;
  }, [conQ.data]);

  // Assemble the encoded record image + per-field character positions from
  // the staging row (the SDF layout metadata isn't served yet, so positions
  // are within this assembled image).
  const { image, fields } = useMemo((): { image: string; fields: FieldRow[] } => {
    if (!live) return { image: RECORD_IMAGE, fields: REC_FIELDS };
    const entries = Object.entries(subQ.data!.fields!);
    let cursor = 1;
    const rows: FieldRow[] = entries.map(([name, v]) => {
      const val = v == null ? '·' : String(v).replace(/\s+/g, '');
      const pos = `${cursor}–${cursor + val.length - 1}`;
      cursor += val.length;
      const con = contractBy.get(name);
      return {
        pos, name, val,
        dec: decode(name, v),
        src: con?.source ?? SRC[name] ?? 'SILVER.TSPR_PREMIUM_STAGING',
        rule: con?.rule ?? (name === 'validation_status' ? 'all edits' : '—'),
      };
    });
    return { image: rows.map((r) => r.val).join(''), fields: rows };
  }, [live, subQ.data, contractBy]);

  // Click a field row → highlight its slice of the record image.
  const [selKey, setSelKey] = useState<string | null>(null);
  useEffect(() => { setSelKey(null); }, [policy]);
  const selField = fields.find((f) => f.pos + f.name === selKey) ?? null;
  let preBody: ReactNode = image;
  if (selField) {
    const [a, b] = selField.pos.split('–').map((n) => parseInt(n, 10));
    if (Number.isFinite(a) && Number.isFinite(b) && a >= 1 && b >= a && b <= image.length) {
      preBody = (
        <>
          {image.slice(0, a - 1)}
          <span style={{ background: 'rgba(22,119,255,0.18)', outline: '1px solid #1677ff', borderRadius: 2 }}>
            {image.slice(a - 1, b)}
          </span>
          {image.slice(b)}
        </>
      );
    }
  }

  const violations = useMemo(() => {
    if (!policy || !valQ.data) return [];
    return Object.values(valQ.data.by_filing).flatMap((f) => f.violations)
      .filter((v) => v.policy_number === policy);
  }, [policy, valQ.data]);

  const active = filingsQ.data?.filings.find((f) => f.is_active);
  const approvalQ = useApprovalState(live && active ? active.id : null);
  const adv = useAdvanceFiling();
  const reconQ = useReconciliation(live && active ? active.id : null);
  const pkg = live
    ? [
        { k: 'Cycle', v: active?.id ?? '—' },
        { k: 'Policy', v: policy! },
        { k: 'Open edits', v: String(violations.length) },
        { k: 'Records with edits', v: String(policies.length) },
        { k: 'Staging table', v: 'TSPR_PREMIUM_STAGING' },
        { k: 'Channel', v: active?.channel ?? '—' },
      ]
    : PKG;

  const rulesTotal = valQ.data
    ? Object.values(valQ.data.by_filing)[0]?.summary.rules_run ?? 0
    : 0;
  const passTag = live
    ? violations.length === 0
      ? `Passes ${rulesTotal} of ${rulesTotal} edits`
      : `${violations.length} open edit${violations.length > 1 ? 's' : ''}`
    : 'Passes 214 of 214 edits';

  const fieldColumns = [
    {
      title: 'Pos', dataIndex: 'pos', key: 'pos', width: 74,
      render: (v: string) => <Text type="secondary" style={{ ...MONO, fontSize: 11 }}>{v}</Text>,
    },
    {
      title: 'Field', dataIndex: 'name', key: 'name', width: 170,
      render: (v: string) => <span style={{ fontSize: 12.5 }}>{v}</span>,
    },
    {
      title: 'Value', dataIndex: 'val', key: 'val', width: 140,
      render: (v: string) => <span style={{ ...MONO, fontSize: 12 }}>{v}</span>,
    },
    {
      title: 'Decoded', dataIndex: 'dec', key: 'dec',
      render: (v: string) => <Text type="secondary" style={{ fontSize: 12 }}>{v}</Text>,
    },
    {
      title: 'Source', dataIndex: 'src', key: 'src', ellipsis: true,
      render: (v: string) => <Text type="secondary" style={{ ...MONO, fontSize: 10.5 }}>{v}</Text>,
    },
    {
      title: 'Rule', dataIndex: 'rule', key: 'rule', width: 96,
      render: (v: string) => <Text code style={{ fontSize: 11 }}>{v}</Text>,
    },
  ];

  return (
    <div>
      {/* ── toolbar: set picker, pager, search, pass state ───────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <Text type="secondary" style={K}>Record</Text>
        <span style={{ ...MONO, fontSize: 13 }}>
          {override ? `${override} · via search`
            : policy ? `${policy} · ${idx + 1} of ${policies.length} ${SET_LABEL[effMode]}`
            : 'HO-TX-0048817-02 · seq 000418,229'}
        </span>
        <Segmented
          value={effMode}
          onChange={(m) => { setMode(m as RecordSet); setIdx(0); setOverride(null); }}
          options={[
            { label: `Edits ${withEdits.length}`, value: 'edits' },
            { label: `Clean ${clean.length}`, value: 'clean' },
            { label: `All ${allPolicies.length}`, value: 'all' },
          ]}
        />
        <Button icon={<LeftOutlined />} disabled={!policies.length || (!override && idx === 0)}
          onClick={() => { setOverride(null); setIdx((i) => Math.max(0, i - 1)); }}>Prev</Button>
        <Button disabled={!policies.length || (!override && idx >= policies.length - 1)}
          onClick={() => { setOverride(null); setIdx((i) => Math.min(policies.length - 1, i + 1)); }}>
          Next <RightOutlined />
        </Button>
        <Input.Search
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onSearch={(v) => { if (v.trim()) { setOverride(v.trim().toUpperCase()); setSearch(''); } }}
          placeholder="POL-…"
          style={{ width: 150 }}
          styles={{ input: { ...MONO, fontSize: 12 } }}
        />
        <Tag
          color={live && violations.length ? 'orange' : 'green'}
          style={{ marginLeft: 'auto', marginInlineEnd: 0 }}
        >
          {passTag}
        </Tag>
      </div>

      {/* ── encoded record image ─────────────────────────────────────────── */}
      <Card
        size="small"
        title={
          <Text type="secondary" style={{ ...K, fontWeight: 400 }}>
            {live ? `Encoded TSPR record — ${image.length} chars · SILVER.TSPR_PREMIUM_STAGING` : 'Fixed-length record image — 80 bytes'}
          </Text>
        }
        extra={!live && !subQ.isLoading && (
          <Tag color="orange" title="staging row unavailable — showing the design record">demo data</Tag>
        )}
        style={{ marginBottom: 16 }}
      >
        <pre style={{
          ...MONO, margin: 0, padding: '10px 12px', fontSize: 14, letterSpacing: '.12em',
          whiteSpace: 'nowrap', overflowX: 'auto', background: 'rgba(5,5,5,0.04)', borderRadius: 6,
        }}>
          {subQ.isLoading ? 'loading…' : preBody}
        </pre>
        {policy && subQ.data && !subQ.data.found && (
          <Text type="secondary" style={{ display: 'block', fontSize: 12, marginTop: 6 }}>{subQ.data.note}</Text>
        )}
      </Card>

      <Row gutter={[16, 16]}>
        {/* ── field-by-field table ───────────────────────────────────────── */}
        <Col xs={24} xl={14}>
          <Card
            title="Field-by-field with provenance"
            extra={selField && <Text type="secondary" style={{ fontSize: 12 }}>highlighting {selField.name} · pos {selField.pos}</Text>}
            styles={{ body: { padding: 0 } }}
          >
            <Table<FieldRow>
              rowKey={(f) => f.pos + f.name}
              dataSource={fields}
              columns={fieldColumns}
              pagination={false}
              size="small"
              onRow={(f) => ({
                onClick: () => setSelKey((k) => (k === f.pos + f.name ? null : f.pos + f.name)),
                style: {
                  cursor: 'pointer',
                  ...(selKey === f.pos + f.name ? { background: 'rgba(22,119,255,0.08)' } : {}),
                },
              })}
            />
          </Card>
        </Col>

        {/* ── side rail: package, open edits, reconciliation ─────────────── */}
        <Col xs={24} xl={10}>
          <Card title="Submission package">
            {pkg.map((p) => <MetaRow key={p.k} k={p.k}>{p.v}</MetaRow>)}
            <div style={{ marginTop: 12 }}>
              {(() => {
                const a = approvalQ.data;
                if (!live || !active || !a) {
                  return <Button type="primary" block disabled={live}>Seal & transmit to statistical agent</Button>;
                }
                const busy = adv.approve.isPending || adv.seal.isPending || adv.ack.isPending;
                const roleLabel: Record<string, string> = {
                  analyst: 'Sign off — Analyst', actuary: 'Sign off — Actuary', officer: 'Sign off — Compliance Officer',
                };
                // Which permission the next action needs, so the button can say
                // exactly who is allowed when the current persona isn't.
                const perm =
                  a.status === 'submitted' ? 'ack'
                  : a.can_seal ? 'seal'
                  : a.next_role ? `sign_${a.next_role === 'officer' ? 'officer' : a.next_role}` : null;
                const allowed = perm == null || can(user, perm);
                const [label, action, disabled]: [string, (() => void) | null, boolean] =
                  a.status === 'acked' ? ['Acknowledged by TICO ✓', null, true]
                  : a.status === 'submitted' ? ['Record TICO acknowledgment', () => adv.ack.mutate(active.id), busy || !allowed]
                  : a.can_seal ? ['Seal & transmit to statistical agent', () => adv.seal.mutate(active.id), busy || !allowed]
                  : a.next_role ? [roleLabel[a.next_role], () => adv.approve.mutate({ filingId: active.id, role: a.next_role! }), busy || a.open_blockers > 0 || !allowed]
                  : [`Blocked — state '${a.status}'`, null, true];
                return (
                  <>
                    <Tooltip title={perm != null && !allowed ? `requires ${whoCan(perm)} — you are ${user?.name ?? 'Guest'}` : undefined}>
                      <Button type="primary" block loading={busy} disabled={disabled} onClick={() => action?.()}>
                        {label}
                      </Button>
                    </Tooltip>
                    {perm != null && !allowed && (
                      <Text type="secondary" style={{ display: 'block', marginTop: 6, fontSize: 12 }}>
                        requires {whoCan(perm)} — switch persona to act
                      </Text>
                    )}
                    <Text type="secondary" style={{ ...MONO, display: 'block', fontSize: 10.5, marginTop: 7 }}>
                      state {a.status}
                      {a.open_blockers > 0 ? ` · ${a.open_blockers} blocker${a.open_blockers > 1 ? 's' : ''} hold the chain` : ''}
                      {a.acked_at ? ` · acked ${a.acked_at.slice(0, 16)}` : a.submitted_at ? ` · submitted ${a.submitted_at.slice(0, 16)}` : ''}
                    </Text>
                    {(adv.approve.error != null || adv.seal.error != null || adv.ack.error != null) && (
                      <Text type="danger" style={{ display: 'block', marginTop: 6, fontSize: 12 }}>
                        {[adv.approve.error, adv.seal.error, adv.ack.error]
                          .filter((e): e is Error => e != null).map((e) => e.message).join(' · ')}
                      </Text>
                    )}
                  </>
                );
              })()}
            </div>
            <Text type="secondary" style={{ display: 'block', fontSize: 11.5, marginTop: 8, lineHeight: 1.55 }}>
              Sign-off chain: analyst → actuary → compliance officer, each gated on zero open
              blockers. Sealing renders the fixed-width TSPR file and writes the SHA-256-sealed
              submission row to the audit chain.
            </Text>
          </Card>

          {live && violations.length > 0 && (
            <Card title="Open edits on this record" style={{ marginTop: 16 }}>
              {violations.map((v, i) => (
                <div key={i} style={{ padding: '7px 0', borderBottom: '1px solid rgba(5,5,5,0.06)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Text code style={{ fontSize: 11.5 }}>{v.rule_number}</Text>
                    <Tag color={String(v.severity).toLowerCase().includes('error') ? 'red' : 'orange'} style={{ marginInlineEnd: 0 }}>
                      {v.severity}
                    </Tag>
                  </div>
                  <div style={{ fontSize: 12.5, lineHeight: 1.5, marginTop: 2 }}>{v.violation_reason}</div>
                </div>
              ))}
            </Card>
          )}

          <Card
            title="Reconciliation to financials"
            extra={
              <Text type="secondary" style={{ fontSize: 12 }}>
                {live && reconQ.data ? 'GL tie-out' : reconQ.isLoading ? 'loading…' : !live ? '' : 'unavailable'}
              </Text>
            }
            style={{ marginTop: 16 }}
          >
            {live && reconQ.data ? reconQ.data.lines.map((l) => (
              <div key={l.label} style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '6px 0', fontSize: 12.5, borderBottom: '1px solid rgba(5,5,5,0.06)' }}>
                <Text type="secondary" style={{ flex: 1, fontSize: 12 }}>{l.label}</Text>
                <span style={{ ...MONO, fontSize: 12 }}>
                  {l.money ? '$' + Math.round(l.stat).toLocaleString('en-US') : l.stat.toLocaleString('en-US')}
                  {' / '}
                  {l.money ? '$' + Math.round(l.gl).toLocaleString('en-US') : l.gl.toLocaleString('en-US')}
                </span>
                <Tag color={l.status === 'Tie' ? 'green' : 'orange'} style={{ marginInlineEnd: 0 }}>
                  {l.status === 'Tie' ? 'Tie' : `Δ ${l.money ? '$' : ''}${Math.round(l.delta).toLocaleString('en-US')}`}
                </Tag>
              </div>
            )) : RECON.map((r) => (
              <div key={r.k} style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '6px 0', fontSize: 12.5, borderBottom: '1px solid rgba(5,5,5,0.06)' }}>
                <Text type="secondary" style={{ flex: 1, fontSize: 12 }}>{r.k}</Text>
                <span style={{ ...MONO, fontSize: 12 }}>{r.v}</span>
                <Tag color={r.tagClass === 'tag-neutral' ? 'green' : 'orange'} style={{ marginInlineEnd: 0 }}>{r.d}</Tag>
              </div>
            ))}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
