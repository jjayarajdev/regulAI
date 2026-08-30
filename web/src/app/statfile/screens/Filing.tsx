// Filing & submission — reimagined as a native Ant Design page: the journey
// as a Steps rail, approval chain / sealed package / transmission / archive
// as Cards, copyable hashes, and an email-style compose form. Live:
// /filing/{id}/submission (polled), /filing/{id}/file for the package
// read-out, /filing/{id}/send for transmission. Falls back to a demo journey
// when the warehouse is cold.
import { useState, type CSSProperties, type ReactNode } from 'react';
import { toast } from 'sonner';
import { PaperClipOutlined } from '@ant-design/icons';
import { Alert, Button, Card, Col, Input, Row, Segmented, Steps, Tag, Tooltip, Typography } from 'antd';
import {
  can, useAdvanceFiling, useFilingFile, useFilings, useSendFiling,
  useSubmissionState, whoCan, type AppUser,
} from '../api';
import type { Filing, SubmissionState } from '../../../api/types';
import type { ScreenId } from '../data';

const { Text } = Typography;

const fmt = (n: number | null | undefined) => (n == null ? '—' : n.toLocaleString('en-US'));
const kb = (bytes: number | null | undefined) => (bytes == null ? '—' : (bytes / 1024).toFixed(1) + ' KB');
const juris = (code?: string | null) => (code ?? '').replace(/^US-/, '') || '—';
const stamp = (s?: string | null) => (s ? s.replace('T', ' ').slice(0, 16) : null);

const MONO: CSSProperties = { fontFamily: "ui-monospace,'SFMono-Regular',Menlo,monospace" };

// Journey steps in order; a filing's status (plus email/ack/archive presence)
// tells how far along it is.
const STEPS: Array<[string, string]> = [
  ['validated', 'Validated'], ['analyst_signed', 'Analyst signed'],
  ['actuary_approved', 'Actuary approved'], ['officer_approved', 'Officer approved'],
  ['submitted', 'Sealed'], ['sent', 'Sent'], ['acked', 'Acknowledged'], ['archived', 'Archived'],
];
// status → number of completed steps.
const STATUS_DONE: Record<string, number> = {
  draft: 0, validating: 0, validated: 1, analyst_signed: 2, actuary_approved: 3,
  officer_approved: 4, submitted: 5, sent: 6, acked: 7,
};

// Design-demo journey (per filing) for a cold warehouse — the screen keeps
// working, actions stay disabled.
const demoSub = (filingId: string): SubmissionState => ({
  filing_id: filingId,
  status: 'officer_approved',
  approval: {
    filing_id: filingId, status: 'officer_approved', open_blockers: 0,
    next_role: null, can_seal: true, submitted_at: null, acked_at: null,
  },
  submission: null, email: null, ack: null, archive: null,
});

const DEMO_FILINGS: Filing[] = [
  {
    id: 'TPA-Q4-2025', plan_name: 'Texas Private Passenger Auto / Homeowners', plan_code: 'TPA',
    policy_id_ranges: [], cadence: 'Quarterly', period_start: '2025-10-01', period_end: '2025-12-31',
    due_date: '2026-07-15', channel: 'TICO ShareFile', is_active: true, jurisdiction_code: 'US-TX',
  },
  {
    id: 'FHCF-A-2026', plan_name: 'Florida Hurricane Catastrophe Fund — Annual Data Call', plan_code: 'FHCF',
    policy_id_ranges: [], cadence: 'Annual', period_start: '2025-01-01', period_end: '2025-12-31',
    due_date: '2026-09-01', channel: 'FHCF Email Submission', is_active: true, jurisdiction_code: 'US-FL',
  },
];

// Prefilled compose defaults, derived from the filing + sealed package.
const defaultTo = (f: Filing) =>
  f.jurisdiction_code === 'US-FL' ? 'datacall@fhcf.example' : 'stat.submissions@tico.example';
const defaultSubject = (f: Filing) =>
  `${f.plan_code} statistical submission — ${f.id} (${f.plan_name})`;
const defaultBody = (f: Filing, s: SubmissionState['submission']) =>
  `To the ${juris(f.jurisdiction_code)} statistical reporting desk,\n\n` +
  `Please find attached the sealed ${f.plan_code} submission for filing ${f.id}, ` +
  `covering ${f.period_start} through ${f.period_end}.\n\n` +
  (s
    ? `File: ${s.file_name}\nRecords: ${fmt(s.record_count)}\nSHA-256: ${s.sha256}\n\n`
    : '') +
  `The package was validated against the current edit reference and carries the\n` +
  `full sign-off chain in its audit trail.\n\nRegards,\nRegulAI filing desk`;

function MetaRow({ k, children }: { k: string; children: ReactNode }) {
  return (
    <div style={{ display: 'flex', gap: 10, padding: '5px 0', fontSize: 12.5, borderBottom: '1px solid rgba(5,5,5,0.06)' }}>
      <Text type="secondary" style={{ flex: 'none', width: 92, fontSize: 12 }}>{k}</Text>
      <span style={{ ...MONO, fontSize: 11.5, overflowWrap: 'anywhere' }}>{children}</span>
    </div>
  );
}

function ShaChip({ sha }: { sha: string }) {
  return (
    <Text copyable={{ text: sha, tooltips: ['copy SHA-256', 'copied'] }} style={{ ...MONO, fontSize: 11.5 }}>
      {sha.slice(0, 16)}…
    </Text>
  );
}

function AttachmentChip({ name, bytes }: { name: string; bytes: number }) {
  return (
    <Tag icon={<PaperClipOutlined />} style={{ ...MONO, fontSize: 10.5, marginInlineEnd: 0 }}>
      {name} · {kb(bytes)}
    </Tag>
  );
}

export function FilingScreen({ user, go }: { user?: AppUser; go?: (s: ScreenId) => () => void }) {
  const filingsQ = useFilings();
  const filings = (filingsQ.data?.filings ?? DEMO_FILINGS).filter((f) => f.is_active);
  const [selId, setSelId] = useState<string | null>(null);
  const filing = filings.find((f) => f.id === selId)
    ?? filings.find((f) => f.id === filingsQ.data?.default)
    ?? filings[0];

  const subQ = useSubmissionState(filing?.id ?? null);
  const live = !!subQ.data;
  const sub = subQ.data ?? demoSub(filing?.id ?? '—');
  const a = sub.approval;

  // Package read-out once sealed (before that the file doesn't exist yet).
  const fileQ = useFilingFile(sub.submission ? filing?.id ?? null : null);

  const adv = useAdvanceFiling();
  const sendMut = useSendFiling();
  const busy = adv.approve.isPending || adv.seal.isPending || adv.ack.isPending || sendMut.isPending;

  const done = sub.archive ? STEPS.length : STATUS_DONE[sub.status] ?? 0;
  const stepStamp: Record<string, string | null> = {
    submitted: stamp(sub.submission?.sealed_at ?? a.submitted_at),
    sent: stamp(sub.email?.sent_at),
    acked: stamp(sub.ack?.acked_at ?? a.acked_at),
    archived: stamp(sub.archive?.archived_at),
  };

  const mutErrors = [adv.approve.error, adv.seal.error, adv.ack.error]
    .filter((e): e is Error => e != null);

  if (!filing) return <Text type="secondary">no active filings</Text>;

  // ── sign-off chain rows ─────────────────────────────────────────────────
  const ROLES: Array<{ role: 'analyst' | 'actuary' | 'officer'; label: string; perm: string; doneAt: number }> = [
    { role: 'analyst', label: 'Analyst sign-off', perm: 'sign_analyst', doneAt: 2 },
    { role: 'actuary', label: 'Actuary approval', perm: 'sign_actuary', doneAt: 3 },
    { role: 'officer', label: 'Compliance officer approval', perm: 'sign_officer', doneAt: 4 },
  ];
  const maySeal = can(user, 'seal');
  const maySend = can(user, 'send');
  const mayAck = can(user, 'ack');

  const chainRow: CSSProperties = {
    display: 'flex', gap: 10, alignItems: 'center', padding: '8px 0', fontSize: 13,
    borderBottom: '1px solid rgba(5,5,5,0.06)',
  };

  return (
    <div>
      {/* ── filing selector ─────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <Segmented
          value={filing.id}
          onChange={(id) => { setSelId(id as string); sendMut.reset(); adv.approve.reset(); adv.seal.reset(); adv.ack.reset(); }}
          options={filings.map((f) => ({ label: <span style={{ ...MONO, fontSize: 12 }}>{f.id}</span>, value: f.id }))}
        />
        <Tag color="geekblue">{juris(filing.jurisdiction_code)}</Tag>
        {!live && <Tag color="orange" title="submission state unavailable — showing the design journey">demo data</Tag>}
        <Text type="secondary" style={{ fontSize: 13 }}>
          {filing.plan_name} · {filing.cadence} · due {filing.due_date}
        </Text>
        <Tag style={{ marginLeft: 'auto', marginInlineEnd: 0 }}>{filing.channel}</Tag>
      </div>

      {/* ── journey stepper ─────────────────────────────────────────────── */}
      <Card style={{ marginBottom: 16 }}>
        <Steps
          size="small" labelPlacement="vertical" current={done}
          items={STEPS.map(([key, label], i) => ({
            title: label,
            description: i < done && stepStamp[key]
              ? <span style={{ ...MONO, fontSize: 10 }}>{stepStamp[key]}</span>
              : undefined,
          }))}
        />
      </Card>

      <Row gutter={[16, 16]}>
        {/* ── left column: approvals + package ───────────────────────────── */}
        <Col xs={24} xl={11}>
          <Card
            title="Approval chain"
            extra={<Text type="secondary" style={{ ...MONO, fontSize: 11 }}>state {sub.status}</Text>}
          >
            {a.open_blockers > 0 && (
              <Alert
                type="warning" showIcon style={{ marginBottom: 12 }}
                message={<><Text strong>{a.open_blockers}</Text> blocking exception{a.open_blockers > 1 ? 's' : ''} hold the chain</>}
                action={<Button size="small" onClick={go ? go('val') : undefined}>Open validation triage</Button>}
              />
            )}

            {ROLES.map(({ role, label, perm, doneAt }) => {
              const isDone = (STATUS_DONE[sub.status] ?? 0) >= doneAt;
              const isNext = a.next_role === role;
              const allowed = can(user, perm);
              return (
                <div key={role} style={chainRow}>
                  <span style={{ flex: 1 }}>{label}</span>
                  {isDone ? (
                    <Tag color="green">Signed ✓</Tag>
                  ) : isNext ? (
                    <Tooltip title={!allowed ? `requires ${whoCan(perm)}`
                      : a.open_blockers > 0 ? 'blocked by open exceptions' : undefined}>
                      <Button size="small" type="primary" loading={adv.approve.isPending}
                        disabled={!live || busy || !allowed || a.open_blockers > 0}
                        onClick={() => adv.approve.mutate({ filingId: filing.id, role }, {
                          onSuccess: () => toast(`${label} recorded`),
                        })}>
                        Sign off
                      </Button>
                    </Tooltip>
                  ) : (
                    <Tag style={{ opacity: 0.6 }}>Waiting</Tag>
                  )}
                </div>
              );
            })}

            <div style={{ ...chainRow, borderBottom: 'none' }}>
              <span style={{ flex: 1 }}>Seal — render &amp; SHA-256 the package</span>
              {sub.submission ? (
                <Tag color="green">Sealed ✓</Tag>
              ) : (
                <Tooltip title={!maySeal ? `requires ${whoCan('seal')}`
                  : !a.can_seal ? 'officer approval with zero blockers required' : undefined}>
                  <Button size="small" type="primary" loading={adv.seal.isPending}
                    disabled={!live || busy || !a.can_seal || !maySeal}
                    onClick={() => adv.seal.mutate(filing.id, {
                      onSuccess: (r) => toast(`Package sealed — sha256:${(r.sha256 ?? '').slice(0, 12)}…`),
                    })}>
                    Seal package
                  </Button>
                </Tooltip>
              )}
            </div>

            {mutErrors.length > 0 && (
              <Text type="danger" style={{ display: 'block', marginTop: 8, fontSize: 12 }}>
                {mutErrors.map((e) => e.message).join(' · ')}
              </Text>
            )}
          </Card>

          <Card title="Sealed package" style={{ marginTop: 16 }}>
            {sub.submission ? (
              <>
                <MetaRow k="File">{sub.submission.file_name ?? fileQ.data?.file_name ?? '—'}</MetaRow>
                <MetaRow k="SHA-256"><ShaChip sha={sub.submission.sha256} /></MetaRow>
                <MetaRow k="Records">
                  {fileQ.data
                    ? `${fmt(fileQ.data.record_count)} — P ${fmt(fileQ.data.p_count)} · L ${fmt(fileQ.data.l_count)} · C ${fmt(fileQ.data.c_count)}`
                    : fmt(sub.submission.record_count)}
                </MetaRow>
                <MetaRow k="Size">{kb(sub.submission.file_size_bytes ?? fileQ.data?.byte_count)} · {fmt(sub.submission.file_size_bytes ?? fileQ.data?.byte_count)} bytes</MetaRow>
                <MetaRow k="Sealed">{stamp(sub.submission.sealed_at) ?? '—'}</MetaRow>
                {fileQ.data ? (
                  <pre style={{
                    ...MONO, margin: '12px 0 0', padding: '10px 12px', fontSize: 10.5, lineHeight: 1.6,
                    maxHeight: 210, overflow: 'auto', whiteSpace: 'pre',
                    background: 'rgba(5,5,5,0.04)', borderRadius: 6,
                  }}>
                    {fileQ.data.preview}
                    {'\n⋮\n'}
                    {fileQ.data.footer}
                  </pre>
                ) : fileQ.isLoading ? (
                  <Text type="secondary" style={{ display: 'block', fontSize: 12, marginTop: 10 }}>rendering package preview…</Text>
                ) : null}
              </>
            ) : (
              <Text type="secondary" style={{ fontSize: 12.5, lineHeight: 1.6 }}>
                The fixed-width package renders at seal — the sign-off chain must complete with
                zero open blockers first. Sealing computes the SHA-256 and writes the
                submission row to the audit chain.
              </Text>
            )}
          </Card>
        </Col>

        {/* ── right column: mail + ack/archive ───────────────────────────── */}
        <Col xs={24} xl={13}>
          <Card
            title={`Transmission — ${filing.channel}`}
            extra={sub.email && (
              <Tag color="green">{sub.email.transport === 'outbox' ? 'saved to outbox' : 'SMTP'}</Tag>
            )}
          >
            {sub.email ? (
              <>
                {/* sent-message view */}
                <div style={{ marginBottom: 10 }}>
                  <MetaRow k="From">{sub.email.from}</MetaRow>
                  <MetaRow k="To">{sub.email.to.join(', ')}</MetaRow>
                  <MetaRow k="Subject">{sub.email.subject}</MetaRow>
                  <MetaRow k="Date">{stamp(sub.email.sent_at)}</MetaRow>
                  <MetaRow k="Message-ID">{sub.email.message_id}</MetaRow>
                </div>
                <div style={{ fontSize: 12.5, lineHeight: 1.65, whiteSpace: 'pre-wrap', padding: '4px 0 10px' }}>
                  {sub.email.body}
                </div>
                {sub.email.attachment && (
                  <AttachmentChip name={sub.email.attachment.name} bytes={sub.email.attachment.bytes} />
                )}
                <div style={{ ...MONO, fontSize: 10.5, marginTop: 10, lineHeight: 1.7, color: 'rgba(0,0,0,0.45)' }}>
                  eml {sub.email.eml_path}
                  {(sub.sftp_path || sendMut.data?.sftp_path || sub.archive) && (
                    <><br />sftp {sub.sftp_path ?? sendMut.data?.sftp_path ?? sub.archive!.path}</>
                  )}
                </div>

                {/* inbound receipt as a threaded reply */}
                {sub.ack && (
                  <Card size="small" style={{ marginTop: 14, marginLeft: 18, borderLeft: '3px solid #1677ff', background: 'rgba(22,119,255,0.05)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Reply · regulator</Text>
                      <Tag color="blue">{sub.ack.receipt}</Tag>
                      <span style={{ ...MONO, marginLeft: 'auto', fontSize: 10.5, color: 'rgba(0,0,0,0.45)' }}>{stamp(sub.ack.acked_at)}</span>
                    </div>
                    <div style={{ fontSize: 12.5, lineHeight: 1.6 }}>
                      Receipt confirmed by {filing.channel}. The submission passed intake checks
                      and is registered under receipt {sub.ack.receipt}.
                    </div>
                    <div style={{ ...MONO, fontSize: 10.5, marginTop: 6, color: 'rgba(0,0,0,0.45)' }}>eml {sub.ack.eml_path}</div>
                  </Card>
                )}
              </>
            ) : (
              // compose card — keyed so drafts reset per filing / after seal
              <ComposeCard
                key={filing.id + (sub.submission?.sha256 ?? '')}
                filing={filing} sub={sub} live={live}
                maySend={maySend} busy={busy}
                onSend={(draft) => sendMut.mutate({ filingId: filing.id, ...draft }, {
                  onSuccess: (r) => toast(
                    r.email.transport === 'outbox'
                      ? 'Submission sent — message saved to outbox'
                      : 'Submission sent via SMTP',
                  ),
                })}
                sending={sendMut.isPending}
                error={sendMut.error as Error | null}
              />
            )}
          </Card>

          <Card title="Acknowledgment & archive" style={{ marginTop: 16 }}>
            {sub.ack ? (
              <div style={chainRow}>
                <span style={{ flex: 1 }}>Regulator acknowledgment</span>
                <Tag color="blue">{sub.ack.receipt}</Tag>
                <span style={{ ...MONO, fontSize: 10.5, color: 'rgba(0,0,0,0.45)' }}>{stamp(sub.ack.acked_at)}</span>
              </div>
            ) : (
              <div style={chainRow}>
                <span style={{ flex: 1 }}>Regulator acknowledgment</span>
                <Tooltip title={!mayAck ? `requires ${whoCan('ack')}`
                  : sub.status !== 'sent' ? 'the package must be sent first' : undefined}>
                  <Button size="small" loading={adv.ack.isPending}
                    disabled={!live || busy || sub.status !== 'sent' || !mayAck}
                    onClick={() => adv.ack.mutate(filing.id, {
                      onSuccess: (r) => toast(`Acknowledgment recorded${r.receipt_id ? ' · ' + r.receipt_id : ''}`),
                    })}>
                    Record acknowledgment
                  </Button>
                </Tooltip>
              </div>
            )}
            {sub.archive ? (
              <div style={{ marginTop: 4 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '8px 0 4px' }}>
                  <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Archive</Text>
                  <Tag color="purple">immutable</Tag>
                </div>
                <MetaRow k="Path">{sub.archive.path}</MetaRow>
                <MetaRow k="SHA-256"><ShaChip sha={sub.archive.sha256} /></MetaRow>
                <MetaRow k="Archived">{stamp(sub.archive.archived_at) ?? '—'}</MetaRow>
              </div>
            ) : (
              <Text type="secondary" style={{ display: 'block', fontSize: 12, marginTop: 6 }}>
                The package archives on transmission — path and hash land here.
              </Text>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

// Email-client style compose card, shown until the package is sent.
function ComposeCard({ filing, sub, live, maySend, busy, sending, error, onSend }: {
  filing: Filing;
  sub: SubmissionState;
  live: boolean;
  maySend: boolean;
  busy: boolean;
  sending: boolean;
  error: Error | null;
  onSend: (draft: { to: string[]; subject: string; body: string }) => void;
}) {
  const [to, setTo] = useState(defaultTo(filing));
  const [subject, setSubject] = useState(defaultSubject(filing));
  const [body, setBody] = useState(defaultBody(filing, sub.submission));
  const sealed = sub.status === 'submitted';
  const toList = to.split(',').map((s) => s.trim()).filter(Boolean);

  return (
    <div>
      <Input
        addonBefore="To" value={to} onChange={(e) => setTo(e.target.value)}
        style={{ marginBottom: 8 }} styles={{ input: { ...MONO, fontSize: 11.5 } }}
      />
      <Input
        addonBefore="Subject" value={subject} onChange={(e) => setSubject(e.target.value)}
        style={{ marginBottom: 8 }}
      />
      <Input.TextArea
        value={body} onChange={(e) => setBody(e.target.value)} rows={9}
        style={{ lineHeight: 1.6 }}
      />
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 10 }}>
        {sub.submission ? (
          <AttachmentChip name={sub.submission.file_name} bytes={sub.submission.file_size_bytes} />
        ) : (
          <Text type="secondary" style={{ fontSize: 11.5 }}>attachment appears at seal</Text>
        )}
        <Tooltip title={!maySend ? `requires ${whoCan('send')}`
          : !sealed ? 'seal the package before sending' : undefined}>
          <Button type="primary" style={{ marginLeft: 'auto' }} loading={sending}
            disabled={!live || busy || !sealed || !maySend || toList.length === 0}
            onClick={() => onSend({ to: toList, subject, body })}>
            Send submission
          </Button>
        </Tooltip>
      </div>
      {!maySend && (
        <Text type="secondary" style={{ display: 'block', marginTop: 6, fontSize: 12 }}>
          requires {whoCan('send')} — switch persona to transmit
        </Text>
      )}
      {error != null && (
        <Text type="danger" style={{ display: 'block', marginTop: 6, fontSize: 12 }}>{error.message}</Text>
      )}
    </div>
  );
}
