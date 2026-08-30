// Rulebook & rules — reimagined as a native Ant Design page: canon status as
// an Alert banner, the 30-day canon diff as a Card grid, the extraction queue
// as a searchable/filterable Table with confidence Progress bars, and the
// selected rule's source clause + logic + approve/reject actions in a
// right-side Drawer. Executable-form authoring is an antd Modal form.
// Live: /kg/rules for the queue, /reg/citation resolves the selected rule's
// citation to real regulator text. Demo fixtures when the canon is empty.
import { useMemo, useState, type CSSProperties, type ReactNode } from 'react';
import {
  Alert, Button, Card, Col, Divider, Drawer, Input, Modal, Progress, Row,
  Segmented, Select, Space, Table, Tag, Tooltip, Typography,
} from 'antd';
import {
  can, useAuthorExecutable, useCitation, useKgDiff, useKgRules, useRuleDecision,
  whoCan, type AppUser,
} from '../api';
import { CLAUSES, RULES } from '../data';
import type { KgRule } from '../../../api/types';

const { Text, Paragraph } = Typography;
const MONO: CSSProperties = { fontFamily: "ui-monospace,'SFMono-Regular',Menlo,monospace" };

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
      {children}
    </Text>
  );
}

function Field({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <label style={{ display: 'block' }}>
      <Text type="secondary" style={{ fontSize: 12 }}>{label}</Text>
      <div style={{ marginTop: 4 }}>{children}</div>
    </label>
  );
}

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
    fix_target_field: rule.fix_target_field ?? '',
    fix_expr: rule.fix_expr ?? '',
    fix_description: rule.fix_description ?? '',
  });
  const set = (k: keyof typeof f) => (v: string) => setF((s) => ({ ...s, [k]: v }));
  const valid = f.target_table.trim().length > 5 && f.target_id_expr.trim()
    && f.violation_sql.trim() && f.violation_reason.trim();

  const monoInput: CSSProperties = { ...MONO, fontSize: 12 };

  return (
    <Modal
      open
      onCancel={onClose}
      width={720}
      title={
        <div>
          <Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>
            executable form · {rule.jurisdiction_code ?? '—'} · runs in /validate once saved
          </Text>
          <div>
            {rule.name}{' '}
            <Tag color={rule.violation_sql ? 'geekblue' : undefined}>
              {rule.violation_sql ? 'editing' : 'not yet executable'}
            </Tag>
          </div>
        </div>
      }
      footer={
        <Space>
          {mut.error != null && (
            <Text type="danger" style={{ fontSize: 12 }}>{(mut.error as Error).message}</Text>
          )}
          <Button onClick={onClose}>Cancel</Button>
          <Button
            type="primary" disabled={!valid} loading={mut.isPending}
            onClick={() => mut.mutate(
              { ruleId: rule.id, ...f, citation: f.citation || undefined },
              { onSuccess: onClose },
            )}
          >
            Save — compile into the edit package
          </Button>
        </Space>
      }
    >
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '12px 16px', marginBottom: 12 }}>
        <Field label="Target table">
          <Input value={f.target_table} style={monoInput} onChange={(e) => set('target_table')(e.target.value)} />
        </Field>
        <Field label="Record id expression">
          <Input value={f.target_id_expr} style={monoInput} onChange={(e) => set('target_id_expr')(e.target.value)} />
        </Field>
      </div>
      <div style={{ marginBottom: 12 }}>
        <Field label={<>Violation SQL — predicate over alias <Text code>j</Text>; TRUE means the record violates the rule</>}>
          <Input.TextArea
            value={f.violation_sql} rows={5} style={monoInput}
            onChange={(e) => set('violation_sql')(e.target.value)}
          />
        </Field>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '12px 16px', marginBottom: 12 }}>
        <Field label="Violation reason (analyst-facing)">
          <Input value={f.violation_reason} onChange={(e) => set('violation_reason')(e.target.value)} />
        </Field>
        <Field label="Severity">
          <Select
            value={f.severity} style={{ width: '100%' }}
            onChange={(severity) => setF((s) => ({ ...s, severity }))}
            options={[
              { value: 'ERROR', label: 'ERROR — blocks sealing' },
              { value: 'WARNING', label: 'WARNING — flagged only' },
            ]}
          />
        </Field>
      </div>
      <Field label="Citation">
        <Input value={f.citation} onChange={(e) => set('citation')(e.target.value)} />
      </Field>

      <Divider style={{ margin: '16px 0 12px' }} />
      <div style={{ marginBottom: 8 }}>
        <SectionLabel>Automated remedy · optional — only where the rule text dictates the correction</SectionLabel>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px 16px', marginBottom: 12 }}>
        <Field label="Field to correct">
          <Input value={f.fix_target_field} style={monoInput} onChange={(e) => set('fix_target_field')(e.target.value)} />
        </Field>
        <Field label={<>Corrected value (SQL over <Text code>j</Text>)</>}>
          <Input value={f.fix_expr} style={monoInput} onChange={(e) => set('fix_expr')(e.target.value)} />
        </Field>
      </div>
      <Field label="Remedy description (shown on the Apply-fix button)">
        <Input value={f.fix_description} onChange={(e) => set('fix_description')(e.target.value)} />
      </Field>
      <Paragraph type="secondary" style={{ fontSize: 12, lineHeight: 1.6, marginTop: 14, marginBottom: 0 }}>
        Saving writes the executable properties onto the KG rule (audited as a manual edit),
        bumps its validation version, and refreshes the jurisdiction's validation reference —
        the edit runs on the next validation pass. No scripts, no JSON files.
      </Paragraph>
    </Modal>
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

const kindColor = (kind: string): string | undefined =>
  kind === 'Amended' ? 'orange' : kind === 'Validation edit' ? 'purple' : undefined;

const decisionTag = (d?: Decision) =>
  d === 'approved' ? <Tag color="green">Approved</Tag>
  : d === 'rejected' ? <Tag color="red">Sent back</Tag>
  : <Tag color="orange">Pending</Tag>;

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
  const [open, setOpen] = useState(false);
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

  // Executable-form authoring modal — opened from the drawer's action footer.
  const [authorRule, setAuthorRule] = useState<KgRule | null>(null);

  // Canon diff panel — last 30 days of KG mutations, fetched on demand.
  const [showDiff, setShowDiff] = useState(false);
  const since = useMemo(
    () => new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 19),
    [],
  );
  const diffQ = useKgDiff(showDiff ? since : null);
  const diff = diffQ.data;

  const pick = (r: RuleCard) => {
    const i = cards.indexOf(r);
    setSelIdx(i);
    if (r.page) setPage(r.page);
    setOpen(true);
  };

  const columns = [
    {
      title: 'Rule', dataIndex: 'id', key: 'id', width: 120,
      render: (v: string) => <Text code title={v}>{v.length > 14 ? v.slice(0, 8) + '…' : v}</Text>,
    },
    {
      title: '', key: 'jur', width: 56,
      render: (_: unknown, r: RuleCard) => r.raw?.jurisdiction_code
        ? <Tag color="geekblue" style={{ marginInlineEnd: 0 }}>{r.raw.jurisdiction_code.replace('US-', '')}</Tag>
        : null,
    },
    { title: 'Title', dataIndex: 'title', key: 'title', ellipsis: true },
    {
      title: 'Kind', dataIndex: 'kind', key: 'kind', width: 130,
      render: (v: string) => <Tag color={kindColor(v)}>{v}</Tag>,
    },
    {
      title: 'Confidence', dataIndex: 'conf', key: 'conf', width: 150,
      render: (v: number | null) => v == null
        ? <Text type="secondary">—</Text>
        : <Progress percent={v} size="small" status={v < 70 ? 'exception' : 'normal'} />,
    },
    {
      title: 'Status', key: 'status', width: 110, align: 'right' as const,
      render: (_: unknown, r: RuleCard) => decisionTag(decisionOf(r)),
    },
  ];

  return (
    <div>
      <Alert
        type="info" showIcon style={{ marginBottom: 16 }}
        message={live
          ? <>Canon loaded — <Text strong>{rulesQ.data!.counts.total}</Text> rules ({rulesQ.data!.counts.executable} executable, {rulesQ.data!.counts.descriptive} descriptive)</>
          : <>Rulebook version change detected — <Text strong>v2025.2 → v2026.1</Text></>}
        description={live
          ? `${pending} rules are not currently active — superseded versions or drafts awaiting approval.`
          : 'Parser found 9 amended clauses and 2 new clauses. 17 derived rules require re-approval before the cycle can close.'}
        action={
          <Button size="small" onClick={() => setShowDiff((v) => !v)}>
            {showDiff ? 'Hide diff' : 'View full diff'}
          </Button>
        }
      />

      {showDiff && (
        <Card
          title="Canon changes — last 30 days"
          extra={
            <Text type="secondary" style={{ fontSize: 12 }}>
              {diff ? `${diff.total_changes} changes`
                : diffQ.isLoading ? 'loading…'
                : diffQ.isError ? 'KG unreachable' : ''}
            </Text>
          }
          style={{ marginBottom: 16 }}
        >
          {diff && (
            <Row gutter={[16, 16]}>
              {([['Added', diff.added_nodes], ['Modified', diff.modified_nodes], ['Superseded', diff.superseded_nodes]] as const)
                .filter(([, ns]) => ns.length > 0)
                .map(([label, ns]) => (
                  <Col xs={24} md={12} key={label}>
                    <SectionLabel>{label} · {ns.length}</SectionLabel>
                    {ns.slice(0, 8).map((n) => (
                      <div key={n.id} style={{ fontSize: 12.5, padding: '4px 0', borderBottom: '1px solid rgba(5,5,5,0.06)' }}>
                        <Text type="secondary" style={{ ...MONO, fontSize: 10.5, marginRight: 8 }}>{n.type}</Text>
                        {n.name.length > 64 ? n.name.slice(0, 63) + '…' : n.name}
                      </div>
                    ))}
                    {ns.length > 8 && (
                      <Text type="secondary" style={{ display: 'block', fontSize: 11, marginTop: 4 }}>+{ns.length - 8} more</Text>
                    )}
                  </Col>
                ))}
              <Col xs={24} md={12}>
                <SectionLabel>Audit trail · {diff.audit_entries.length}</SectionLabel>
                {diff.audit_entries.slice(0, 8).map((a) => (
                  <div key={a.id} style={{ fontSize: 12, padding: '4px 0', borderBottom: '1px solid rgba(5,5,5,0.06)' }}>
                    <Text type="secondary" style={{ ...MONO, fontSize: 10.5, marginRight: 8 }}>{a.occurred_at?.slice(0, 16)}</Text>
                    {a.actor} · {a.summary.length > 56 ? a.summary.slice(0, 55) + '…' : a.summary}
                  </div>
                ))}
                {diff.audit_entries.length > 8 && (
                  <Text type="secondary" style={{ display: 'block', fontSize: 11, marginTop: 4 }}>+{diff.audit_entries.length - 8} more</Text>
                )}
              </Col>
            </Row>
          )}
        </Card>
      )}

      <Card
        title="Extracted rules"
        extra={
          <Space>
            {!live && (
              <Tag color="orange" title="the canon is empty or unreachable — showing design fixtures">demo data</Tag>
            )}
            <Text type="secondary" style={{ fontSize: 12 }}>
              {pending} awaiting review · showing {filtered.length} of {cards.length}
            </Text>
          </Space>
        }
        styles={{ body: { padding: 0 } }}
      >
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', padding: '12px 16px', borderBottom: '1px solid rgba(5,5,5,0.06)' }}>
          <Input
            allowClear placeholder="Search rules…" value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ flex: 1, minWidth: 200, maxWidth: 320 }}
          />
          <Segmented
            value={filter}
            onChange={(f) => setFilter(f as Filter)}
            options={[
              { value: 'pending', label: 'Pending' },
              { value: 'low', label: 'Low confidence' },
              { value: 'all', label: 'All' },
            ]}
          />
          <Select
            value={section}
            onChange={setSection}
            style={{ width: 170, marginLeft: 'auto' }}
            options={[
              { value: 'all', label: `All sections · ${cards.length}` },
              ...sections.map(([s, n]) => ({
                value: s, label: `${s === 'Other' ? 'Other' : '§' + s} · ${n}`,
              })),
            ]}
          />
        </div>
        <Table
          rowKey="id"
          dataSource={filtered}
          columns={columns}
          pagination={false} size="middle"
          onRow={(r) => ({ onClick: () => pick(r), style: { cursor: 'pointer' } })}
        />
      </Card>

      {/* Row click → clause text, rule logic and the decision footer in a drawer. */}
      <Drawer
        open={open && !!sel}
        onClose={() => setOpen(false)}
        width={920}
        title={sel && (
          <div>
            <Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>{sel.cite} · {sel.agent}</Text>
            <div style={{ fontSize: 16 }}>{sel.title}</div>
          </div>
        )}
        extra={sel && (
          <Space size={4}>
            {sel.raw?.jurisdiction_code && (
              <Tag color="geekblue">{sel.raw.jurisdiction_code.replace('US-', '')}</Tag>
            )}
            <Tag color={kindColor(sel.kind)}>{sel.kind}</Tag>
            {decisionTag(decisionOf(sel))}
          </Space>
        )}
      >
        {sel && (
        <>
          <Row gutter={24}>
            <Col span={12}>
              <SectionLabel>Source clause</SectionLabel>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, margin: '6px 0 12px' }}>
                <Text type="secondary" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  {match ? match.issuing_body
                    : live ? (jurName ? `${jurName} · ${raw?.jurisdiction_code}` : 'Jurisdiction not recorded')
                    : 'Texas Department of Insurance'}
                </Text>
                <Text type="secondary" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  {match ? match.document_type
                    : live ? (raw?.source_kind ?? 'extracted rule')
                    : 'Residential Property Statistical Plan'}
                </Text>
              </div>
              <Text strong style={{ display: 'block', fontSize: 16 }}>{clause.t}</Text>
              <div style={{ ...MONO, fontSize: 11, color: '#1677ff', margin: '2px 0 12px' }}>{clause.r}</div>
              <Paragraph style={{ fontSize: 13, lineHeight: 1.7, whiteSpace: 'pre-wrap', maxHeight: 360, overflow: 'auto' }}>
                {citQ.isLoading ? 'Resolving citation…' : clause.b}
              </Paragraph>
              <Alert type="info" message={<span style={{ fontSize: 12.5, lineHeight: 1.6 }}>{clause.h}</span>} />
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 14 }}>
                <Button size="small" onClick={() => setPage((p) => Math.max(1, p - 1))}>← Prev</Button>
                <Button size="small" onClick={() => setPage((p) => Math.min(214, p + 1))}>Next →</Button>
                <Text type="secondary" style={{ marginLeft: 'auto', fontSize: 11 }}>
                  {match ? `${match.title} · ${match.citation_label}`
                    : live ? 'no source clause resolved'
                    : `TDI-HO-STATPLAN-2026.pdf · p. ${page} of 214`}
                </Text>
              </div>
            </Col>
            <Col span={12}>
              <SectionLabel>What the rule says</SectionLabel>
              <Paragraph style={{ marginTop: 6, fontSize: 13, lineHeight: 1.65 }}>{sel.text}</Paragraph>
              <SectionLabel>Logic</SectionLabel>
              <pre style={{
                ...MONO, fontSize: 11.5, lineHeight: 1.65, whiteSpace: 'pre-wrap', margin: '6px 0 12px',
                padding: '9px 11px', background: 'rgba(5,5,5,0.04)', borderRadius: 6,
              }}>
                {sel.logic}
              </pre>
              <SectionLabel>Citation</SectionLabel>
              <div style={{ margin: '6px 0 12px' }}><Text code>{sel.cite}</Text></div>
              {sel.conf != null && (
                <>
                  <SectionLabel>Extraction confidence</SectionLabel>
                  <Progress
                    percent={sel.conf} size="small"
                    status={sel.conf < 70 ? 'exception' : 'normal'}
                    style={{ maxWidth: 220, display: 'block', margin: '6px 0 12px' }}
                  />
                </>
              )}
              <Text type="secondary" style={{ ...MONO, fontSize: 11 }}>{sel.agent}</Text>
            </Col>
          </Row>

          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 20, paddingTop: 14, borderTop: '1px solid rgba(5,5,5,0.06)' }}>
            {decisionTag(decisionOf(sel))}
            <span style={{ marginLeft: 'auto', display: 'inline-flex', gap: 8 }}>
              {sel.raw && (
                <Tooltip title={mayDecide
                  ? "author the rule's edit-package fields — target table, violation SQL, severity"
                  : `requires ${whoCan('rule_decision')}`}>
                  <Button disabled={!mayDecide} onClick={() => setAuthorRule(sel.raw!)}>
                    {sel.raw.violation_sql ? 'Edit executable…' : 'Make executable…'}
                  </Button>
                </Tooltip>
              )}
              <Tooltip title={mayDecide ? undefined : `requires ${whoCan('rule_decision')}`}>
                <Button danger disabled={!mayDecide} onClick={() => decide(sel.id, 'rejected')}>Reject</Button>
              </Tooltip>
              <Tooltip title={mayDecide ? undefined : `requires ${whoCan('rule_decision')}`}>
                <Button type="primary" disabled={!mayDecide} loading={decideMut.isPending}
                  onClick={() => decide(sel.id, 'approved')}>
                  Approve
                </Button>
              </Tooltip>
            </span>
          </div>
        </>
        )}
      </Drawer>

      {authorRule && (
        <ExecutableFormModal key={authorRule.id} rule={authorRule}
          onClose={() => setAuthorRule(null)} />
      )}
    </div>
  );
}
