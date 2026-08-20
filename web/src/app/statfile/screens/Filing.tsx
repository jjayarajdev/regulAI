// Filing & submission — the end-to-end journey for one filing: sign-off
// chain → seal (fixed-width TSPR render, SHA-256) → email transmission to the
// regulator → inbound acknowledgment → immutable archive. Live:
// /filing/{id}/submission (polled), /filing/{id}/file for the package
// read-out, /filing/{id}/send for transmission. Falls back to a demo journey
// when the warehouse is cold.
import { useState, type CSSProperties, type ReactNode } from 'react';
import { toast } from 'sonner';
import { Blueprint } from '../Blueprint';
import {
  can, useAdvanceFiling, useFilingFile, useFilings, useSendFiling,
  useSubmissionState, whoCan, type AppUser,
} from '../api';
import type { Filing, SubmissionState } from '../../../api/types';
import type { ScreenId } from '../data';

const fmt = (n: number | null | undefined) => (n == null ? '—' : n.toLocaleString('en-US'));
const kb = (bytes: number | null | undefined) => (bytes == null ? '—' : (bytes / 1024).toFixed(1) + ' KB');
const juris = (code?: string | null) => (code ?? '').replace(/^US-/, '') || '—';
const stamp = (s?: string | null) => (s ? s.replace('T', ' ').slice(0, 16) : null);

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

const rowStyle: CSSProperties = {
  display: 'flex', gap: 10, padding: '6px 0', fontSize: 12.5,
  borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)',
};

function MetaRow({ k, children }: { k: string; children: ReactNode }) {
  return (
    <div style={rowStyle}>
      <span className="muted" style={{ flex: 'none', width: 92 }}>{k}</span>
      <span className="mono" style={{ fontSize: 11.5, overflowWrap: 'anywhere' }}>{children}</span>
    </div>
  );
}

function AttachmentChip({ name, bytes }: { name: string; bytes: number }) {
  return (
    <span className="tag tag-outline mono" style={{ fontSize: 10.5 }}>
      ⎘ {name} · {kb(bytes)}
    </span>
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

  const copySha = (sha: string) => {
    navigator.clipboard?.writeText(sha)
      .then(() => toast('SHA-256 copied to clipboard'))
      .catch(() => { /* clipboard blocked — no-op */ });
  };

  const mutErrors = [adv.approve.error, adv.seal.error, adv.ack.error]
    .filter((e): e is Error => e != null);

  if (!filing) return <div className="sc"><span className="k">no active filings</span></div>;

  // ── sign-off chain rows ─────────────────────────────────────────────────
  const ROLES: Array<{ role: 'analyst' | 'actuary' | 'officer'; label: string; perm: string; doneAt: number }> = [
    { role: 'analyst', label: 'Analyst sign-off', perm: 'sign_analyst', doneAt: 2 },
    { role: 'actuary', label: 'Actuary approval', perm: 'sign_actuary', doneAt: 3 },
    { role: 'officer', label: 'Compliance officer approval', perm: 'sign_officer', doneAt: 4 },
  ];
  const maySeal = can(user, 'seal');
  const maySend = can(user, 'send');
  const mayAck = can(user, 'ack');

  return (
    <div className="sc">
      {/* ── filing selector ─────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18, flexWrap: 'wrap' }}>
        <span className="k">Filing</span>
        <div className="seg">
          {filings.map((f) => (
            <label key={f.id} className="seg-opt">
              <input type="radio" name="filing-sel" checked={filing.id === f.id}
                onChange={() => { setSelId(f.id); sendMut.reset(); adv.approve.reset(); adv.seal.reset(); adv.ack.reset(); }} />
              <span className="mono" style={{ fontSize: 11.5 }}>{f.id}</span>
            </label>
          ))}
        </div>
        <span className="tag tag-outline">{juris(filing.jurisdiction_code)}</span>
        <span style={{ fontSize: 12.5, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>
          {filing.plan_name} · {filing.cadence} · due {filing.due_date}
        </span>
        <span className="tag tag-neutral" style={{ marginLeft: 'auto' }}>{filing.channel}</span>
      </div>

      {/* ── journey stepper ─────────────────────────────────────────────── */}
      <Blueprint style={{ padding: '16px 18px', marginBottom: 26 }}>
        <div className="k" style={{ marginBottom: 12 }}>Submission journey</div>
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${STEPS.length},1fr)`, gap: 10 }}>
          {STEPS.map(([key, label], i) => {
            const state = i < done ? 'done' : i === done ? 'current' : 'future';
            return (
              <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'flex-start' }}>
                <div style={{
                  alignSelf: 'stretch', height: 3,
                  background: state === 'done' ? 'var(--color-accent)'
                    : state === 'current' ? 'color-mix(in srgb,var(--color-accent) 40%,transparent)'
                    : 'color-mix(in srgb,var(--color-text) 10%,transparent)',
                }} />
                <span className={'tag ' + (state === 'done' ? 'tag-accent' : state === 'current' ? 'tag-outline' : 'tag-neutral')}
                  style={state === 'future' ? { opacity: 0.6 } : undefined}>
                  {label}
                </span>
                {state === 'done' && stepStamp[key] && (
                  <span className="mono muted" style={{ fontSize: 10 }}>{stepStamp[key]}</span>
                )}
              </div>
            );
          })}
        </div>
      </Blueprint>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.15fr', gap: 30, alignItems: 'start' }}>
        {/* ── left column: approvals + package ───────────────────────────── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
          <Blueprint style={{ padding: '16px 18px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
              <div className="k">Approval chain</div>
              <span className="mono" style={{ marginLeft: 'auto', fontSize: 10.5, color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>
                state {sub.status}
              </span>
            </div>

            {a.open_blockers > 0 && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px', marginBottom: 12,
                fontSize: 12.5, background: 'color-mix(in srgb,var(--color-accent) 9%,transparent)',
                borderLeft: '3px solid var(--color-accent-900, #1d2d3d)',
              }}>
                <span>
                  <strong>{a.open_blockers}</strong> blocking exception{a.open_blockers > 1 ? 's' : ''} hold the chain
                </span>
                <button className="btn btn-secondary" style={{ marginLeft: 'auto', padding: '3px 10px', fontSize: 11 }}
                  onClick={go ? go('val') : undefined}>
                  Open validation triage
                </button>
              </div>
            )}

            {ROLES.map(({ role, label, perm, doneAt }) => {
              const isDone = (STATUS_DONE[sub.status] ?? 0) >= doneAt;
              const isNext = a.next_role === role;
              const allowed = can(user, perm);
              return (
                <div key={role} style={{ ...rowStyle, alignItems: 'center' }}>
                  <span style={{ flex: 1 }}>{label}</span>
                  {isDone ? (
                    <span className="tag tag-neutral">Signed ✓</span>
                  ) : isNext ? (
                    <button className="btn btn-primary" style={{ padding: '3px 12px', fontSize: 11.5 }}
                      disabled={!live || busy || !allowed || a.open_blockers > 0}
                      title={!allowed ? `requires ${whoCan(perm)}`
                        : a.open_blockers > 0 ? 'blocked by open exceptions' : undefined}
                      onClick={() => adv.approve.mutate({ filingId: filing.id, role }, {
                        onSuccess: () => toast(`${label} recorded`),
                      })}>
                      {adv.approve.isPending ? 'Signing…' : 'Sign off'}
                    </button>
                  ) : (
                    <span className="tag tag-outline" style={{ opacity: 0.6 }}>Waiting</span>
                  )}
                </div>
              );
            })}

            <div style={{ ...rowStyle, alignItems: 'center', borderBottom: 'none' }}>
              <span style={{ flex: 1 }}>Seal — render &amp; SHA-256 the package</span>
              {sub.submission ? (
                <span className="tag tag-neutral">Sealed ✓</span>
              ) : (
                <button className="btn btn-primary" style={{ padding: '3px 12px', fontSize: 11.5 }}
                  disabled={!live || busy || !a.can_seal || !maySeal}
                  title={!maySeal ? `requires ${whoCan('seal')}`
                    : !a.can_seal ? 'officer approval with zero blockers required' : undefined}
                  onClick={() => adv.seal.mutate(filing.id, {
                    onSuccess: (r) => toast(`Package sealed — sha256:${(r.sha256 ?? '').slice(0, 12)}…`),
                  })}>
                  {adv.seal.isPending ? 'Sealing…' : 'Seal package'}
                </button>
              )}
            </div>

            {mutErrors.length > 0 && (
              <div className="k" style={{ marginTop: 8, color: 'var(--color-accent-700)' }}>
                {mutErrors.map((e) => e.message).join(' · ')}
              </div>
            )}
          </Blueprint>

          <Blueprint style={{ padding: '16px 18px' }}>
            <div className="k" style={{ marginBottom: 10 }}>Sealed package</div>
            {sub.submission ? (
              <>
                <MetaRow k="File">{sub.submission.file_name ?? fileQ.data?.file_name ?? '—'}</MetaRow>
                <MetaRow k="SHA-256">
                  <span onClick={() => copySha(sub.submission!.sha256)} title={sub.submission.sha256 + ' — click to copy'}
                    style={{ cursor: 'pointer', color: 'var(--color-accent-700)' }}>
                    {sub.submission.sha256.slice(0, 16)}… ⧉
                  </span>
                </MetaRow>
                <MetaRow k="Records">
                  {fileQ.data
                    ? `${fmt(fileQ.data.record_count)} — P ${fmt(fileQ.data.p_count)} · L ${fmt(fileQ.data.l_count)} · C ${fmt(fileQ.data.c_count)}`
                    : fmt(sub.submission.record_count)}
                </MetaRow>
                <MetaRow k="Size">{kb(sub.submission.file_size_bytes ?? fileQ.data?.byte_count)} · {fmt(sub.submission.file_size_bytes ?? fileQ.data?.byte_count)} bytes</MetaRow>
                <MetaRow k="Sealed">{stamp(sub.submission.sealed_at) ?? '—'}</MetaRow>
                {fileQ.data ? (
                  <pre className="mono" style={{
                    margin: '12px 0 0', padding: '10px 12px', fontSize: 10.5, lineHeight: 1.6,
                    maxHeight: 210, overflow: 'auto', whiteSpace: 'pre',
                    border: '1px solid var(--color-divider)',
                    background: 'color-mix(in srgb,var(--color-text) 4%,transparent)',
                    color: 'var(--color-accent-900)',
                  }}>
                    {fileQ.data.preview}
                    {'\n⋮\n'}
                    {fileQ.data.footer}
                  </pre>
                ) : fileQ.isLoading ? (
                  <div className="muted" style={{ fontSize: 12, marginTop: 10 }}>rendering package preview…</div>
                ) : null}
              </>
            ) : (
              <div className="muted" style={{ fontSize: 12.5, lineHeight: 1.6 }}>
                The fixed-width package renders at seal — the sign-off chain must complete with
                zero open blockers first. Sealing computes the SHA-256 and writes the
                submission row to the audit chain.
              </div>
            )}
          </Blueprint>
        </div>

        {/* ── right column: mail + ack/archive ───────────────────────────── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
          <Blueprint style={{ padding: '16px 18px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
              <div className="k">Transmission — {filing.channel}</div>
              {sub.email && (
                <span className="tag tag-neutral" style={{ marginLeft: 'auto' }}>
                  {sub.email.transport === 'outbox' ? 'saved to outbox' : 'SMTP'}
                </span>
              )}
            </div>

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
                <div className="mono muted" style={{ fontSize: 10.5, marginTop: 10, lineHeight: 1.7 }}>
                  eml {sub.email.eml_path}
                  {(sub.sftp_path || sendMut.data?.sftp_path || sub.archive) && (
                    <><br />sftp {sub.sftp_path ?? sendMut.data?.sftp_path ?? sub.archive!.path}</>
                  )}
                </div>

                {/* inbound receipt as a threaded reply */}
                {sub.ack && (
                  <div style={{
                    marginTop: 14, marginLeft: 18, padding: '12px 14px',
                    borderLeft: '3px solid var(--color-accent)',
                    background: 'color-mix(in srgb,var(--color-accent) 7%,transparent)',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <span className="k">Reply · regulator</span>
                      <span className="tag tag-accent">{sub.ack.receipt}</span>
                      <span className="mono muted" style={{ marginLeft: 'auto', fontSize: 10.5 }}>{stamp(sub.ack.acked_at)}</span>
                    </div>
                    <div style={{ fontSize: 12.5, lineHeight: 1.6 }}>
                      Receipt confirmed by {filing.channel}. The submission passed intake checks
                      and is registered under receipt {sub.ack.receipt}.
                    </div>
                    <div className="mono muted" style={{ fontSize: 10.5, marginTop: 6 }}>eml {sub.ack.eml_path}</div>
                  </div>
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
          </Blueprint>

          <Blueprint style={{ padding: '16px 18px' }}>
            <div className="k" style={{ marginBottom: 10 }}>Acknowledgment &amp; archive</div>
            {sub.ack ? (
              <div style={{ ...rowStyle, alignItems: 'center' }}>
                <span style={{ flex: 1 }}>Regulator acknowledgment</span>
                <span className="tag tag-accent">{sub.ack.receipt}</span>
                <span className="mono muted" style={{ fontSize: 10.5 }}>{stamp(sub.ack.acked_at)}</span>
              </div>
            ) : (
              <div style={{ ...rowStyle, alignItems: 'center' }}>
                <span style={{ flex: 1 }}>Regulator acknowledgment</span>
                <button className="btn btn-secondary" style={{ padding: '3px 12px', fontSize: 11.5 }}
                  disabled={!live || busy || sub.status !== 'sent' || !mayAck}
                  title={!mayAck ? `requires ${whoCan('ack')}`
                    : sub.status !== 'sent' ? 'the package must be sent first' : undefined}
                  onClick={() => adv.ack.mutate(filing.id, {
                    onSuccess: (r) => toast(`Acknowledgment recorded${r.receipt_id ? ' · ' + r.receipt_id : ''}`),
                  })}>
                  {adv.ack.isPending ? 'Recording…' : 'Record acknowledgment'}
                </button>
              </div>
            )}
            {sub.archive ? (
              <div style={{ marginTop: 4 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '8px 0 4px' }}>
                  <span className="k">Archive</span>
                  <span className="tag tag-outline">immutable</span>
                </div>
                <MetaRow k="Path">{sub.archive.path}</MetaRow>
                <MetaRow k="SHA-256">
                  <span onClick={() => copySha(sub.archive!.sha256)} title={sub.archive.sha256 + ' — click to copy'}
                    style={{ cursor: 'pointer', color: 'var(--color-accent-700)' }}>
                    {sub.archive.sha256.slice(0, 16)}… ⧉
                  </span>
                </MetaRow>
                <MetaRow k="Archived">{stamp(sub.archive.archived_at) ?? '—'}</MetaRow>
              </div>
            ) : (
              <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
                The package archives on transmission — path and hash land here.
              </div>
            )}
          </Blueprint>
        </div>
      </div>
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

  const inputStyle: CSSProperties = {
    flex: 1, padding: '6px 9px', fontSize: 12.5, fontFamily: 'var(--font-body)',
    border: '1px solid var(--color-divider)', borderRadius: 0,
    background: 'transparent', color: 'var(--color-text)',
  };

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 8 }}>
        <span className="k" style={{ width: 60, flex: 'none' }}>To</span>
        <input value={to} onChange={(e) => setTo(e.target.value)} style={{ ...inputStyle, fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 11.5 }} />
      </div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 8 }}>
        <span className="k" style={{ width: 60, flex: 'none' }}>Subject</span>
        <input value={subject} onChange={(e) => setSubject(e.target.value)} style={inputStyle} />
      </div>
      <textarea
        value={body} onChange={(e) => setBody(e.target.value)} rows={9}
        style={{
          width: '100%', boxSizing: 'border-box', padding: '9px 11px', fontSize: 12.5,
          fontFamily: 'var(--font-body)', lineHeight: 1.6, border: '1px solid var(--color-divider)',
          borderRadius: 0, background: 'transparent', color: 'var(--color-text)', resize: 'vertical',
        }}
      />
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 10 }}>
        {sub.submission ? (
          <AttachmentChip name={sub.submission.file_name} bytes={sub.submission.file_size_bytes} />
        ) : (
          <span className="muted" style={{ fontSize: 11.5 }}>attachment appears at seal</span>
        )}
        <button className="btn btn-primary" style={{ marginLeft: 'auto' }}
          disabled={!live || busy || sending || !sealed || !maySend || toList.length === 0}
          title={!maySend ? `requires ${whoCan('send')}`
            : !sealed ? 'seal the package before sending' : undefined}
          onClick={() => onSend({ to: toList, subject, body })}>
          {sending ? 'Sending…' : 'Send submission'}
        </button>
      </div>
      {!maySend && (
        <div className="k" style={{ marginTop: 6 }}>requires {whoCan('send')} — switch persona to transmit</div>
      )}
      {error != null && (
        <div className="k" style={{ marginTop: 6, color: 'var(--color-accent-700)' }}>{error.message}</div>
      )}
    </div>
  );
}
