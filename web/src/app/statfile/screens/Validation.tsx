// Validation triage — reimagined as a native Ant Design page: blocking-count
// Alert, severity facets as Card tabs over a Badge-severity Table, and the
// selected edit's why/rule/sample detail (with inline bronze fixes, suppress,
// assign, agent fix) in a right-side Drawer. Live: /validate/all grouped by
// rule; the sample panel pulls the first failing policy's bronze fields.
import { useMemo, useState } from 'react';
import { CloseOutlined, EditOutlined } from '@ant-design/icons';
import {
  Alert, Badge, Button, Card, Col, Drawer, Input, Row, Space, Table, Tag,
  Tooltip, Typography,
} from 'antd';
import {
  can, groupViolations, useApplyFix, useAssign, useBronzeFix, useClaims,
  useFilings, usePolicyFields, useReasonCodes, useSuppress, useUnsuppress,
  useValidateAll, whoCan, type AppUser, type GroupedError,
} from '../api';
import { ApiError } from '../../../api/client';
import { ERR_DETAIL } from '../data';

const { Text, Paragraph } = Typography;
const fmt = (n: number) => n.toLocaleString('en-US');

const MONO: React.CSSProperties = { fontFamily: "ui-monospace,'SFMono-Regular',Menlo,monospace" };

const sevBadge = (sev: number, suppressed?: boolean): 'error' | 'warning' | 'default' =>
  suppressed ? 'default' : sev === 2 ? 'error' : sev === 1 ? 'warning' : 'default';
const sevTagColor = (sev: number, suppressed?: boolean) =>
  suppressed ? undefined : sev === 2 ? 'red' : sev === 1 ? 'orange' : undefined;

export function ValidationScreen({ onTrace, user }: { onTrace?: (policy: string) => void; user?: AppUser }) {
  const maySuppress = can(user, 'suppress');
  const mayFix = can(user, 'fix');
  const mayAssign = can(user, 'assign');
  const valQ = useValidateAll();
  const errors = useMemo(() => groupViolations(valQ.data), [valQ.data]);
  const live = errors.some((e) => e.violations.length > 0);

  const [sev, setSev] = useState('all');
  const [errCode, setErrCode] = useState<string | null>(null);
  const fixMut = useApplyFix();
  const suppressMut = useSuppress();
  const unsuppressMut = useUnsuppress();
  const assignMut = useAssign();
  // Inline forms for suppress-memo / assignee entry.
  const [form, setForm] = useState<'suppress' | 'assign' | null>(null);
  const [memo, setMemo] = useState('');
  const [assignee, setAssignee] = useState('');
  const pickError = (code: string) => {
    setErrCode(code); setForm(null);
    fixMut.reset(); suppressMut.reset(); unsuppressMut.reset(); assignMut.reset();
  };

  const shown = errors.filter((e) =>
    sev === 'all' ? true : sev === 'sup' ? !!e.suppressed : String(e.sev) === sev && !e.suppressed);
  const E: GroupedError = errors.find((e) => e.code === errCode) ?? errors[0];
  const demo = !live ? ERR_DETAIL[E?.code] ?? ERR_DETAIL['TX-E118'] : null;

  const firstViolation = E?.violations[0];
  const policyQ = usePolicyFields(firstViolation?.policy_number ?? null);

  // Claim context when the rule targets claims (record_id CLM-…).
  const filingsQ = useFilings();
  const activeF = filingsQ.data?.filings.find((f) => f.is_active);
  const isClaimRule = !!firstViolation?.record_id?.startsWith('CLM-');
  const claimsQ = useClaims(isClaimRule ? activeF?.id ?? null : null);
  const claim = isClaimRule
    ? (claimsQ.data?.rows ?? []).find((c) => c.claim_number === firstViolation!.record_id)
    : undefined;

  // Inline record editor: which field is being edited + its draft value.
  const bronzeFix = useBronzeFix();
  // Legal companion pairings for the reason-code editor, from the canon-derived
  // reference map (e.g. LD = 'Credit score + claims history').
  const reasonCodesQ = useReasonCodes();
  const currentReason = String(policyQ.data?.fields?.reason_code ?? '');
  const reasonRecs = (reasonCodesQ.data?.rows ?? [])
    .filter((r) => currentReason
      && r.tspr_reason_code !== currentReason
      && r.tspr_reason_code.startsWith(currentReason)
      && !r.credit_score_companion_required)
    .slice(0, 4);
  const [editField, setEditField] = useState<string | null>(null);
  const [editVal, setEditVal] = useState('');
  const EDITABLE = new Set(['reason_code', 'naic_number', 'writtenpremium', 'termtype', 'noticedate', 'reporteddate', 'lossdate']);
  // Which field each rule actually fires on — the one to edit.
  const CULPRIT: Record<string, string[]> = {
    'A.34': ['reason_code'], 'A.10': ['writtenpremium'], 'A.22': ['noticedate'], 'B.10': ['reporteddate'],
  };
  const culprits = new Set(CULPRIT[E?.code ?? ''] ?? []);
  // Prefill a sensible correction when opening the editor on the culprit.
  const suggest = (field: string, current: string): string => {
    if (field === 'reason_code' && current === 'L') return 'LD';
    if (field === 'writtenpremium' && Number(current) <= 0) return String(Math.abs(Number(current)) || 1500);
    if (field === 'reporteddate' && claim?.loss_date) {
      const d = new Date(claim.loss_date); d.setDate(d.getDate() + 45);
      return d.toISOString().slice(0, 10);
    }
    return current;
  };
  const CLAIM_FIELDS = new Set(['reporteddate', 'lossdate']);
  const saveEdit = (field: string) => {
    const body = CLAIM_FIELDS.has(field)
      ? { record_id: firstViolation!.record_id, field, new_value: editVal.trim() }
      : { policy_number: firstViolation!.policy_number, field, new_value: editVal.trim() };
    bronzeFix.mutate(body, { onSuccess: () => setEditField(null) });
  };

  const size = (e: GroupedError) => e.violations.length || parseInt(e.count.replace(/,/g, '')) || 0;
  const activeErrors = errors.filter((e) => !e.suppressed);
  const counts = {
    all: activeErrors.reduce((n, e) => n + size(e), 0),
    2: activeErrors.filter((e) => e.sev === 2).reduce((n, e) => n + size(e), 0),
    1: activeErrors.filter((e) => e.sev === 1).reduce((n, e) => n + size(e), 0),
    0: activeErrors.filter((e) => e.sev === 0).reduce((n, e) => n + size(e), 0),
    sup: errors.filter((e) => e.suppressed).reduce((n, e) => n + size(e), 0),
  };
  const facetTabs = [
    { key: 'all', label: <>All <Text type="secondary">{fmt(counts.all)}</Text></> },
    { key: '2', label: <><Badge status="error" /> Blocking <Text type="secondary">{fmt(counts[2])}</Text></> },
    { key: '1', label: <><Badge status="warning" /> Warn <Text type="secondary">{fmt(counts[1])}</Text></> },
    { key: '0', label: <>Info <Text type="secondary">{fmt(counts[0])}</Text></> },
    ...(counts.sup > 0 ? [{ key: 'sup', label: <>Suppressed <Text type="secondary">{fmt(counts.sup)}</Text></> }] : []),
  ];

  // Sample failing record: live bronze fields when we have them, else the
  // design's demo sample for the selected code.
  const sample: Array<[string, string, 0 | 1]> = firstViolation
    ? [
        ['policy_number', firstViolation.policy_number, 0],
        ['record_id', firstViolation.record_id, 0],
        ...Object.entries(policyQ.data?.fields ?? {})
          .slice(0, 5)
          .map(([k, v]) => [k, String(v ?? '∅'), 0] as [string, string, 0 | 1]),
        ...(claim ? [
          ['lossdate', claim.loss_date ?? '∅', 0],
          ['reporteddate', claim.reported_date ?? '∅', 1],
          ['reporting_lag_days', String(claim.reporting_lag_days ?? '—'), 1],
        ] as Array<[string, string, 0 | 1]> : []),
      ]
    : demo?.sample ?? [];

  const columns = [
    {
      title: '', dataIndex: 'sev', key: 'sev', width: 36,
      render: (_: number, e: GroupedError) => <Badge status={sevBadge(e.sev, !!e.suppressed)} />,
    },
    {
      title: 'Edit', dataIndex: 'code', key: 'code', width: 100,
      render: (v: string) => <Text code>{v}</Text>,
    },
    {
      title: 'Field', dataIndex: 'field', key: 'field', width: 190,
      render: (v: string) => <span style={{ ...MONO, fontSize: 12 }}>{v}</span>,
    },
    { title: 'Description', dataIndex: 'desc', key: 'desc' },
    {
      title: 'Records', dataIndex: 'count', key: 'count', align: 'right' as const, width: 100,
      render: (v: string) => <Text strong>{v}</Text>,
    },
    {
      title: 'Origin', dataIndex: 'origin', key: 'origin', width: 180,
      render: (v: string) => <Text type="secondary" style={{ fontSize: 12 }}>{v}</Text>,
    },
    {
      title: 'Status', key: 'status', width: 190, align: 'right' as const,
      render: (_: unknown, e: GroupedError) => (
        <Space size={4} wrap style={{ justifyContent: 'flex-end' }}>
          {e.assignee && <Tag color="blue">{e.assignee}</Tag>}
          <Tag color={sevTagColor(e.sev, !!e.suppressed)} style={e.suppressed ? { opacity: 0.65 } : undefined}>
            {e.status}
          </Tag>
        </Space>
      ),
    },
  ];

  const mutErrors = [suppressMut.error, assignMut.error, unsuppressMut.error]
    .filter((e): e is ApiError => e instanceof ApiError).map((e) => e.message).join(' · ');

  return (
    <div>
      {counts[2] > 0 && (
        <Alert
          type="error" showIcon style={{ marginBottom: 16 }}
          message={<><Text strong>{fmt(counts[2])}</Text> records are held from the package until blocking edits clear.</>}
        />
      )}

      <Card
        tabList={facetTabs}
        activeTabKey={sev}
        onTabChange={setSev}
        tabBarExtraContent={!live
          ? <Tag color="orange" title="no live violations — showing design fixtures">demo data</Tag>
          : <Text type="secondary" style={{ fontSize: 13 }}>live · edit-package exceptions</Text>}
        styles={{ body: { padding: 0 } }}
      >
        <Table
          rowKey="code"
          dataSource={shown}
          columns={columns}
          pagination={false} size="middle"
          onRow={(e) => ({ onClick: () => pickError(e.code), style: { cursor: 'pointer' } })}
        />
      </Card>

      {/* Row click → the edit's full detail + actions in a right-side drawer. */}
      <Drawer
        open={!!E && errCode !== null}
        onClose={() => setErrCode(null)}
        width={920}
        title={E && (
          <div>
            <Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>edit {E.code} · {E.origin}</Text>
            <div style={{ ...MONO, fontSize: 16 }}>{E.field}</div>
          </div>
        )}
        extra={E && (
          <Space size={4}>
            {E.assignee && <Tag color="blue">assigned · {E.assignee}</Tag>}
            <Tag>{E.count} records</Tag>
            <Tag color={sevTagColor(E.sev, !!E.suppressed)}>{E.status}</Tag>
          </Space>
        )}
      >
        {E && (
        <>
          {E.suppressed && E.memo && (
            <Alert type="info" showIcon style={{ marginBottom: 16 }} message="Suppressed" description={E.memo} />
          )}
          <Row gutter={24}>
            <Col span={12}>
              <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Why it fired</Text>
              <Paragraph style={{ marginTop: 6, fontSize: 13, lineHeight: 1.65 }}>{demo ? demo.why : E.desc}</Paragraph>
              <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Rule &amp; citation</Text>
              <pre style={{
                ...MONO, fontSize: 11.5, lineHeight: 1.65, whiteSpace: 'pre-wrap', margin: '6px 0 0',
                padding: '9px 11px', background: 'rgba(5,5,5,0.04)', borderRadius: 6,
              }}>
                {demo ? demo.rule : `${E.code} · ${E.field}\n${E.origin}`}
              </pre>
            </Col>
            <Col span={12}>
              <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Sample failing record</Text>
              <div style={{ ...MONO, fontSize: 11.5, lineHeight: 1.9, marginTop: 6 }}>
                {sample.map(([k, v, bad]) => {
                  const hot = culprits.has(k);
                  return (
                  <div key={k} style={{
                    display: 'flex', gap: 10, alignItems: 'center',
                    borderBottom: '1px solid rgba(5,5,5,0.06)', padding: '2px 0',
                    ...(hot ? {
                      background: 'rgba(22,119,255,0.08)',
                      borderLeft: '3px solid #1677ff', paddingLeft: 7, marginLeft: -10,
                    } : {}),
                  }}>
                    <Text type="secondary" style={{ width: 150, flex: 'none', fontSize: 11.5, fontWeight: hot ? 600 : undefined }}>{k}</Text>
                    {editField === k ? (
                      <>
                        {k === 'reason_code' && reasonRecs.length > 0 && (
                          <span style={{ display: 'flex', gap: 5, flex: 'none' }}>
                            {reasonRecs.map((r) => (
                              <Tag.CheckableTag
                                key={r.tspr_reason_code}
                                checked={editVal === r.tspr_reason_code}
                                onChange={() => setEditVal(r.tspr_reason_code)}
                              >
                                <span title={r.description}>{r.tspr_reason_code}</span>
                              </Tag.CheckableTag>
                            ))}
                          </span>
                        )}
                        <Input
                          size="small" value={editVal} autoFocus
                          onChange={(e) => setEditVal(e.target.value)}
                          onPressEnter={() => saveEdit(k)}
                          onKeyDown={(e) => { if (e.key === 'Escape') setEditField(null); }}
                          style={{ flex: 1, fontSize: 11.5 }}
                        />
                        <Button size="small" type="primary" loading={bronzeFix.isPending} onClick={() => saveEdit(k)}>
                          Save
                        </Button>
                        <Button size="small" icon={<CloseOutlined />} onClick={() => setEditField(null)} />
                      </>
                    ) : (
                      <>
                        <Text type={bad ? 'danger' : undefined} style={{ fontSize: 11.5, overflowWrap: 'anywhere', flex: 1 }}>{v}</Text>
                        {hot && live && mayFix && (
                          <Tooltip title={`this is the field ${E.code} fires on — suggested correction prefilled`}>
                            <Button size="small" type="primary"
                              onClick={() => { setEditField(k); setEditVal(suggest(k, v === '∅' ? '' : v)); }}>
                              fix here
                            </Button>
                          </Tooltip>
                        )}
                        {!hot && live && mayFix && EDITABLE.has(k) && (
                          <Tooltip title={`edit ${k} in Bronze (CDC correction)`}>
                            <Button size="small" type="text" icon={<EditOutlined />}
                              onClick={() => { setEditField(k); setEditVal(v === '∅' ? '' : v); }} />
                          </Tooltip>
                        )}
                      </>
                    )}
                  </div>
                ); })}
              </div>
              {bronzeFix.isSuccess && (
                <Text type="success" style={{ display: 'block', marginTop: 6, fontSize: 12 }}>
                  saved to Bronze ✓ — revalidating (the group updates when the edit engine finishes, ~30s)
                </Text>
              )}
              {bronzeFix.error != null && (
                <Text type="danger" style={{ display: 'block', marginTop: 6, fontSize: 12 }}>
                  {(bronzeFix.error as Error).message}
                </Text>
              )}
              {firstViolation && policyQ.isLoading && (
                <Text type="secondary" style={{ display: 'block', marginTop: 6, fontSize: 12 }}>loading bronze fields…</Text>
              )}
            </Col>
          </Row>

          <div style={{ display: 'flex', gap: 8, marginTop: 20, paddingTop: 14, borderTop: '1px solid rgba(5,5,5,0.06)', alignItems: 'center', flexWrap: 'wrap' }}>
            <Button disabled={!firstViolation} onClick={() => firstViolation && onTrace?.(firstViolation.policy_number)}>
              Trace to Guidewire
            </Button>
            {E.suppressed ? (
              <Tooltip title={maySuppress ? undefined : `requires ${whoCan('suppress')}`}>
                <Button disabled={!live || !maySuppress} loading={unsuppressMut.isPending}
                  onClick={() => unsuppressMut.mutate(E.code)}>
                  Unsuppress
                </Button>
              </Tooltip>
            ) : (
              <Tooltip title={maySuppress ? undefined : `requires ${whoCan('suppress')}`}>
                <Button disabled={!live || !maySuppress}
                  onClick={() => { setForm(form === 'suppress' ? null : 'suppress'); setMemo(''); }}>
                  Suppress with memo
                </Button>
              </Tooltip>
            )}
            <Tooltip title={mayAssign ? undefined : `requires ${whoCan('assign')}`}>
              <Button disabled={!live || !mayAssign}
                onClick={() => { setForm(form === 'assign' ? null : 'assign'); setAssignee(E.assignee ?? ''); }}>
                {E.assignee ? 'Reassign' : 'Assign'}
              </Button>
            </Tooltip>
            <span style={{ marginLeft: 'auto', display: 'inline-flex', gap: 8, alignItems: 'center' }}>
              {fixMut.data && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {fixMut.data.fixed.length} fixed · {fixMut.data.skipped.length} skipped — revalidating
                </Text>
              )}
              {fixMut.error != null && (
                <Text type="danger" style={{ fontSize: 12 }}>
                  {fixMut.error instanceof ApiError ? fixMut.error.message : 'fix failed'}
                </Text>
              )}
              {/* Remedies are authored per rule (fix_expr on the KG rule, via
                  the Rulebook executable form) — the button enables only where
                  one exists; everything else would be the agent inventing
                  data. */}
              <Tooltip title={!mayFix ? `requires ${whoCan('fix')}`
                : !E.violations[0]?.fix_available
                  ? 'no remedy authored for this edit — the correct value lives in the source policy; use the record editor above, suppress with a memo, or author a remedy on the Rulebook screen'
                  : (E.violations[0]?.fix_description ?? 'bulk-applies the rule-authored remedy to every violating record')}>
                <Button
                  type="primary" loading={fixMut.isPending}
                  disabled={!live || !mayFix || !E.violations[0]?.fix_available}
                  onClick={() => fixMut.mutate(E.code)}
                >
                  {E.violations[0]?.fix_available ? `Apply agent fix to ${E.count}` : 'No automated remedy'}
                </Button>
              </Tooltip>
            </span>
          </div>

          {form === 'suppress' && (
            <div style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'flex-start' }}>
              <Input.TextArea
                value={memo}
                onChange={(e) => setMemo(e.target.value)}
                placeholder={`Why is ${E.code} being suppressed? (required — lands in the audit trail)`}
                rows={2} style={{ flex: 1 }}
              />
              <Button type="primary" disabled={memo.trim().length < 5} loading={suppressMut.isPending}
                onClick={() => suppressMut.mutate({ ruleNumber: E.code, memo: memo.trim() }, { onSuccess: () => setForm(null) })}>
                Suppress
              </Button>
            </div>
          )}
          {form === 'assign' && (
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <Input
                value={assignee}
                onChange={(e) => setAssignee(e.target.value)}
                placeholder="Assignee (empty to unassign)"
                style={{ flex: 1 }}
              />
              <Button type="primary" loading={assignMut.isPending}
                onClick={() => assignMut.mutate({ ruleNumber: E.code, assignee: assignee.trim() }, { onSuccess: () => setForm(null) })}>
                {assignee.trim() ? 'Assign' : 'Unassign'}
              </Button>
            </div>
          )}
          {mutErrors !== '' && (
            <Text type="danger" style={{ display: 'block', marginTop: 8, fontSize: 12 }}>{mutErrors}</Text>
          )}
        </>
        )}
      </Drawer>
    </div>
  );
}
