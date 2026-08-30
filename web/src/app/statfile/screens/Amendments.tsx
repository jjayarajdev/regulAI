// Amendments & impact — reimagined as a native Ant Design page: bulletin
// master list as a selectable Card+List rail, impact totals as Statistic
// cards, per-rule before/after diffs as two-column Cards with Badge
// severities, and the RBAC-gated apply bar. Live: /bulletins +
// /bulletin/{name}/impact; when the knowledge graph is offline
// (503 / kg_offline) the screen degrades to the bundled demo impact.
import { useMemo, useState, type CSSProperties } from 'react';
import { toast } from 'sonner';
import {
  Alert, Badge, Button, Card, Col, Input, List, Row, Skeleton, Space, Tag,
  Tooltip, Typography,
} from 'antd';
import {
  can, useApplyBulletin, useBulletinImpact, useBulletins, whoCan, type AppUser,
} from '../api';
import { ApiError } from '../../../api/client';
import type { Bulletin, BulletinImpact, RuleChange, RuleChangeSide } from '../../../api/types';

const { Text, Title, Paragraph } = Typography;

const MONO: CSSProperties = { fontFamily: "ui-monospace,'SFMono-Regular',Menlo,monospace" };
const KICKER: CSSProperties = { fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em' };

const sevBadge = (s: string): 'error' | 'warning' | 'default' =>
  s === 'ERROR' ? 'error' : s === 'WARNING' ? 'warning' : 'default';
const juris = (code?: string | null) => (code ?? '').replace(/^US-/, '') || '—';
const fmt = (n: number) => n.toLocaleString('en-US');

// change_kind → [Tag color, label] mapped by meaning: added lands new canon
// (green), modified is active change (blue), retired reads neutral.
const KIND_TAG: Record<RuleChange['change_kind'], [string | undefined, string]> = {
  modified: ['blue', 'Modified'],
  added: ['green', 'Added'],
  retired: [undefined, 'Retired'],
};

// ── design-demo fixtures — fallback when the API/KG is unavailable ─────────
const DEMO_BULLETINS: Bulletin[] = [
  {
    name: 'B-2026-Q4-118',
    title: 'Credit Score Declination During Catastrophe Periods',
    effective_date: '2026-01-01',
    status: 'pending',
    targets: 3,
    summary: 'During a declared catastrophe period, reason code L submitted alone becomes a reporting violation — a companion catastrophe-related code is required on the notice record.',
    jurisdiction_code: 'US-TX',
  },
  {
    name: 'B-2026-Q3-104',
    title: 'Notice-Period Alignment for Renewal Declinations',
    effective_date: '2025-10-01',
    status: 'applied',
    targets: 2,
    summary: 'Aligned the minimum notice window for nonrenewals with §22 (30 days), retiring the 21-day transitional rule.',
    jurisdiction_code: 'US-TX',
  },
];

const DEMO_IMPACTS: Record<string, BulletinImpact> = {
  'B-2026-Q4-118': {
    bulletin: DEMO_BULLETINS[0],
    rule_changes: [
      {
        rule_number: 'A.34',
        name: 'Reason code L (credit score declination) requires companion',
        change_kind: 'modified',
        before: {
          violation_sql: "LENGTH(j.declinereason) = 1 AND j.declinereason = 'L'",
          severity: 'WARNING',
          violation_reason: 'L should carry a companion code',
        },
        after: {
          violation_sql: "LENGTH(j.declinereason) = 1 AND j.declinereason = 'L'\nAND EXISTS (SELECT 1 FROM REF.CAT_PERIOD cp\n  WHERE j.noticedate BETWEEN cp.start_date AND cp.end_date)",
          severity: 'ERROR',
          violation_reason: 'L alone during a declared catastrophe period',
        },
        records: {
          newly_failing: 12, newly_passing: 0,
          sample_newly_failing: ['POL-0011', 'POL-0050', 'POL-0410', 'POL-0412', 'POL-2107', 'POL-2151'],
          sample_newly_passing: [],
        },
      },
      {
        rule_number: 'A.22',
        name: 'Notice date must precede effective date by 30+ days',
        change_kind: 'modified',
        before: {
          violation_sql: 'DATEDIFF(day, j.noticedate, j.effectivedate) < 30',
          severity: 'ERROR',
          violation_reason: 'Insufficient notice period',
        },
        after: {
          violation_sql: 'DATEDIFF(day, j.noticedate, j.effectivedate) < 30\nAND j.action <> \'DECLINATION\'',
          severity: 'ERROR',
          violation_reason: 'Insufficient notice period (declinations carved out per bulletin)',
        },
        records: {
          newly_failing: 0, newly_passing: 2,
          sample_newly_failing: [],
          sample_newly_passing: ['POL-0007', 'POL-2103'],
        },
      },
      {
        rule_number: 'A.41',
        name: 'Catastrophe-period declination memo required',
        change_kind: 'added',
        before: null,
        after: {
          violation_sql: "j.declinereason LIKE 'L%' AND j.cat_memo IS NULL\nAND EXISTS (SELECT 1 FROM REF.CAT_PERIOD cp\n  WHERE j.noticedate BETWEEN cp.start_date AND cp.end_date)",
          severity: 'WARNING',
          violation_reason: 'Catastrophe-period declination lacks the underwriting memo',
        },
        records: null,
        sql_error: 'REF.CAT_PERIOD not yet loaded in the warehouse — dry-run skipped',
      },
    ],
    totals: { rules_affected: 3, newly_failing: 12, newly_passing: 2, filings_affected: ['TPA-Q4-2025', 'CL-Q4-2025'] },
  },
  'B-2026-Q3-104': {
    bulletin: DEMO_BULLETINS[1],
    rule_changes: [
      {
        rule_number: 'A.22',
        name: 'Notice date must precede effective date by 30+ days',
        change_kind: 'modified',
        before: {
          violation_sql: 'DATEDIFF(day, j.noticedate, j.effectivedate) < 21',
          severity: 'ERROR',
          violation_reason: 'Insufficient notice period (21-day transitional window)',
        },
        after: {
          violation_sql: 'DATEDIFF(day, j.noticedate, j.effectivedate) < 30',
          severity: 'ERROR',
          violation_reason: 'Insufficient notice period',
        },
        records: {
          newly_failing: 4, newly_passing: 0,
          sample_newly_failing: ['POL-0007', 'POL-0413', 'POL-2110', 'POL-2144'],
          sample_newly_passing: [],
        },
      },
      {
        rule_number: 'A.22-T',
        name: 'Transitional 21-day notice window (2025)',
        change_kind: 'retired',
        before: {
          violation_sql: 'DATEDIFF(day, j.noticedate, j.effectivedate) < 21\nAND j.effectivedate < \'2025-10-01\'',
          severity: 'WARNING',
          violation_reason: 'Below the transitional 21-day window',
        },
        after: null,
        records: {
          newly_failing: 0, newly_passing: 3,
          sample_newly_failing: [],
          sample_newly_passing: ['POL-0021', 'POL-0038', 'POL-2131'],
        },
      },
    ],
    totals: { rules_affected: 2, newly_failing: 4, newly_passing: 3, filings_affected: ['TPA-Q4-2025'] },
  },
};

// ── bulletin master rail — Card + selectable List, filterable at scale ─────
function BulletinRail({ bulletins, value, onChange }: {
  bulletins: Bulletin[];
  value: string | null;
  onChange: (name: string) => void;
}) {
  const [q, setQ] = useState('');
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return bulletins;
    return bulletins.filter((b) =>
      `${b.name} ${b.title} ${juris(b.jurisdiction_code)} ${b.status}`.toLowerCase().includes(needle));
  }, [bulletins, q]);

  return (
    <Card title="Commissioner's bulletins" size="small" styles={{ body: { padding: 0 } }}>
      {bulletins.length > 6 && (
        <div style={{ padding: '8px 12px 0' }}>
          <Input allowClear size="small" placeholder="filter…"
            value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      )}
      <List
        size="small"
        dataSource={filtered}
        locale={{ emptyText: 'no matches' }}
        style={{ maxHeight: 'max(360px, calc(100vh - 320px))', overflow: 'auto' }}
        renderItem={(b) => {
          const on = b.name === value;
          return (
            <List.Item
              onClick={() => onChange(b.name)}
              style={{
                cursor: 'pointer', paddingInline: 13,
                borderInlineStart: `3px solid ${on ? '#1677ff' : 'transparent'}`,
                background: on ? 'rgba(22,119,255,0.06)' : undefined,
              }}
            >
              <List.Item.Meta
                title={
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ ...MONO, flex: 1, minWidth: 0, fontSize: 12.5, fontWeight: on ? 600 : 400 }}>
                      {b.name}
                    </span>
                    <Tag color={b.status === 'applied' ? 'green' : 'blue'} style={{ marginInlineEnd: 0 }}>
                      {b.status === 'applied' ? 'Applied' : 'Pending'}
                    </Tag>
                  </div>
                }
                description={
                  <Text type="secondary" style={{ ...MONO, fontSize: 10.5 }}>
                    {juris(b.jurisdiction_code)} · eff {b.effective_date} · {b.targets} target{b.targets === 1 ? '' : 's'}
                  </Text>
                }
              />
            </List.Item>
          );
        }}
      />
    </Card>
  );
}

// One side of a before/after diff. `changed` gets the primary left-border;
// a null side renders as a dashed ghost.
function SideCol({ label, side, changed, ghostText }: {
  label: string;
  side: RuleChangeSide | null;
  changed?: boolean;
  ghostText: string;
}) {
  if (!side) {
    return (
      <div style={{
        border: '1px dashed rgba(5,5,5,0.25)', borderRadius: 6,
        minHeight: 130, display: 'grid', placeItems: 'center', padding: 12,
      }}>
        <Text type="secondary" style={{ fontSize: 11.5, textAlign: 'center' }}>{ghostText}</Text>
      </div>
    );
  }
  return (
    <div style={changed
      ? { borderLeft: '3px solid #1677ff', paddingLeft: 12 }
      : { paddingLeft: 0 }}>
      <Space size={8} style={{ marginBottom: 7 }}>
        <Text type="secondary" style={KICKER}>{label}</Text>
        <Badge status={sevBadge(side.severity)} />
        <span style={{ ...MONO, fontSize: 10.5 }}>{side.severity}</span>
      </Space>
      <div style={{ fontSize: 12.5, lineHeight: 1.55, marginBottom: 8 }}>{side.violation_reason}</div>
      <pre style={{
        ...MONO, fontSize: 11, lineHeight: 1.65, padding: '9px 11px', margin: 0,
        whiteSpace: 'pre-wrap', background: 'rgba(5,5,5,0.04)', borderRadius: 6,
      }}>
        {side.violation_sql}
      </pre>
    </div>
  );
}

function SampleChips({ ids }: { ids: string[] }) {
  return (
    <Space size={4} wrap>
      {ids.map((id) => (
        <Tag key={id} style={{ ...MONO, fontSize: 10, marginInlineEnd: 0 }}>{id}</Tag>
      ))}
    </Space>
  );
}

export function AmendmentsScreen({ user }: { user?: AppUser }) {
  const mayApply = can(user, 'bulletin');
  const bulQ = useBulletins();
  const live = !!bulQ.data;
  const bulletins = bulQ.data?.bulletins?.length ? bulQ.data.bulletins : DEMO_BULLETINS;

  const [selName, setSelName] = useState<string | null>(null);
  const B = bulletins.find((b) => b.name === selName)
    ?? bulletins.find((b) => b.status === 'pending')
    ?? bulletins[0];

  const impactQ = useBulletinImpact(live && B ? B.name : null);
  const kgOffline = !!bulQ.data?.kg_offline
    || (impactQ.error instanceof ApiError && impactQ.error.status === 503);
  // KG offline or warehouse cold → the bundled demo impact keeps the story alive.
  const impact: BulletinImpact | undefined =
    impactQ.data ?? ((!live || kgOffline || impactQ.isError) ? DEMO_IMPACTS[B?.name ?? ''] ?? DEMO_IMPACTS['B-2026-Q4-118'] : undefined);
  const loading = live && !kgOffline && impactQ.isPending;

  const applyMut = useApplyBulletin();

  const kpis: Array<{ label: string; value: string; note: string; tone?: 'red' | 'green' }> = impact ? [
    { label: 'Rules affected', value: String(impact.totals.rules_affected), note: 'in the executable canon' },
    { label: 'Newly failing', value: fmt(impact.totals.newly_failing), note: 'records caught by the amendment', tone: impact.totals.newly_failing > 0 ? 'red' : undefined },
    { label: 'Newly passing', value: fmt(impact.totals.newly_passing), note: 'exceptions the amendment clears', tone: impact.totals.newly_passing > 0 ? 'green' : undefined },
    { label: 'Filings affected', value: String(impact.totals.filings_affected.length), note: impact.totals.filings_affected.join(' · ') || '—' },
  ] : [];

  return (
    <Row gutter={[16, 16]} wrap={false} align="top">
      {/* ── bulletin master list — compact, searchable, scales to 50 states ── */}
      <Col flex="300px" style={{ minWidth: 0 }}>
        <BulletinRail bulletins={bulletins} value={B?.name ?? null} onChange={setSelName} />
      </Col>

      {/* ── impact analysis ────────────────────────────────────────────── */}
      <Col flex="auto" style={{ minWidth: 0 }}>
        {!live && !bulQ.isLoading && (
          <div style={{ marginBottom: 10 }}>
            <Tag color="orange" title="bulletins API empty or unreachable — showing design fixtures">demo data</Tag>
          </div>
        )}
        {!live && bulQ.isLoading && <Text type="secondary" style={KICKER}>loading bulletins…</Text>}
        {B && (
          <>
            <Space size={10} align="baseline" wrap style={{ marginBottom: 4 }}>
              <Title level={4} style={{ margin: 0 }}>{B.title}</Title>
              <Text type="secondary" style={KICKER}>impact on the executable canon</Text>
            </Space>
            <div style={{ ...MONO, fontSize: 11, margin: '4px 0 8px', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              <Text type="secondary" style={{ fontSize: 11 }}>eff. {B.effective_date}</Text>
              <Text type="secondary" style={{ fontSize: 11 }}>{juris(B.jurisdiction_code)}</Text>
              <Text type="secondary" style={{ fontSize: 11 }}>{B.targets} rule target{B.targets === 1 ? '' : 's'}</Text>
            </div>
            <Paragraph type="secondary" style={{ fontSize: 12.5, lineHeight: 1.65, maxWidth: '92ch', marginBottom: 16 }}>
              {B.summary}
            </Paragraph>
          </>
        )}

        {kgOffline && (
          <Alert
            type="warning" showIcon style={{ marginBottom: 16 }}
            message="Knowledge graph offline — start Neo4j to compute live impact. Showing the bundled demo analysis."
          />
        )}

        {loading && (
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            {[0, 1, 2, 3].map((i) => (
              <Col xs={12} xl={6} key={i}>
                <Card size="small">
                  <Skeleton active title={false} paragraph={{ rows: 2 }} />
                </Card>
              </Col>
            ))}
          </Row>
        )}

        {/* No resolved rule targets → nothing to diff or apply. Say so
            instead of rendering four zeros and a live Apply button. */}
        {!loading && impact && impact.totals.rules_affected === 0 && impact.rule_changes.length === 0 && (
          <Card style={{ maxWidth: 720 }}>
            <Title level={5} style={{ marginTop: 0 }}>No impact on the executable canon</Title>
            <Paragraph style={{ fontSize: 13, lineHeight: 1.7 }}>
              None of this bulletin's provisions resolve to an executable rule —
              its extracted rules are descriptive (no compiled <Text code>violation_sql</Text>),
              so there is nothing to diff against the validation reference and
              nothing for an amendment to materialize.
            </Paragraph>
            <Paragraph type="secondary" style={{ fontSize: 12, lineHeight: 1.65 }}>
              A bulletin gains impact here once its target rules are compiled into
              the edit package. Until then, review its extracted provisions on the
              Rulebook screen — apply is disabled because it would be a no-op.
            </Paragraph>
            <Tooltip title="no resolved rule targets — nothing to materialize">
              <Button disabled style={{ marginTop: 4 }}>Apply amendment</Button>
            </Tooltip>
          </Card>
        )}

        {!loading && impact && !(impact.totals.rules_affected === 0 && impact.rule_changes.length === 0) && (
          <>
            {/* KPI row — Statistic cards for the dry-run totals */}
            <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
              {kpis.map((k) => (
                <Col xs={12} xl={6} key={k.label}>
                  <Card size="small">
                    <Text type="secondary" style={KICKER}>{k.label}</Text>
                    <div style={{
                      fontSize: 28, lineHeight: 1.15, marginTop: 4,
                      color: k.tone === 'red' ? '#cf1322' : k.tone === 'green' ? '#3f8600' : undefined,
                    }}>
                      {k.value}
                    </div>
                    <Text type="secondary" ellipsis style={{ display: 'block', fontSize: 11, marginTop: 2 }}>
                      {k.note}
                    </Text>
                  </Card>
                </Col>
              ))}
            </Row>

            {/* per-rule diffs */}
            {impact.rule_changes.map((rc) => {
              const [kindColor, kindLabel] = KIND_TAG[rc.change_kind];
              return (
                <Card
                  key={rc.rule_number}
                  size="small"
                  style={{ marginBottom: 16 }}
                  title={
                    <Space size={10}>
                      <Text code>{rc.rule_number}</Text>
                      <span style={{ fontSize: 14 }}>{rc.name}</span>
                    </Space>
                  }
                  extra={<Tag color={kindColor} style={{ marginInlineEnd: 0 }}>{kindLabel}</Tag>}
                >
                  <Row gutter={[20, 16]}>
                    <Col xs={24} md={12}>
                      <SideCol label="Before" side={rc.before}
                        changed={rc.change_kind === 'retired'}
                        ghostText="no prior rule — introduced by this bulletin" />
                    </Col>
                    <Col xs={24} md={12}>
                      <SideCol label="After" side={rc.after}
                        changed={rc.change_kind !== 'retired'}
                        ghostText="retired — no successor rule" />
                    </Col>
                  </Row>

                  {rc.records ? (
                    <div style={{
                      display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 10,
                      marginTop: 14, paddingTop: 12, borderTop: '1px solid rgba(5,5,5,0.06)', fontSize: 12.5,
                    }}>
                      <span>
                        <Text strong>{fmt(rc.records.newly_failing)}</Text> record{rc.records.newly_failing === 1 ? '' : 's'} newly failing
                      </span>
                      {rc.records.sample_newly_failing.length > 0 && <SampleChips ids={rc.records.sample_newly_failing} />}
                      {rc.records.newly_passing > 0 && (
                        <>
                          <span style={{ marginLeft: 8 }}>
                            <Text strong>{fmt(rc.records.newly_passing)}</Text> newly passing
                          </span>
                          {rc.records.sample_newly_passing.length > 0 && <SampleChips ids={rc.records.sample_newly_passing} />}
                        </>
                      )}
                    </div>
                  ) : rc.sql_error ? (
                    <Text type="warning" style={{ display: 'block', marginTop: 12, fontSize: 11.5 }}>
                      record impact unavailable — {rc.sql_error}
                    </Text>
                  ) : null}
                </Card>
              );
            })}

            {/* apply bar */}
            {B?.status === 'pending' ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 6, flexWrap: 'wrap' }}>
                <Tooltip title={mayApply ? undefined : `requires ${whoCan('bulletin')}`}>
                  <Button
                    type="primary" loading={applyMut.isPending}
                    disabled={!live || !mayApply}
                    onClick={() => applyMut.mutate(undefined, {
                      onSuccess: () => toast(`${B.name} applied — canon rebuilt, validation re-running`),
                    })}>
                    Apply amendment
                  </Button>
                </Tooltip>
                <Text type="secondary" style={KICKER}>materializes the rule changes into the canon and re-runs validation</Text>
                {applyMut.error != null && (
                  <Text type="danger" style={{ marginLeft: 'auto', fontSize: 12 }}>
                    {applyMut.error instanceof ApiError ? applyMut.error.message : 'apply failed'}
                  </Text>
                )}
              </div>
            ) : (
              <Space size={10} style={{ marginTop: 6 }}>
                <Tag color="green">Applied — validation reference updated</Tag>
                <Text type="secondary" style={KICKER}>the executable canon carries these changes</Text>
              </Space>
            )}
          </>
        )}

        {!loading && !impact && !impactQ.isError && (
          <Text type="secondary" style={KICKER}>select a bulletin to compute its impact</Text>
        )}
      </Col>
    </Row>
  );
}
