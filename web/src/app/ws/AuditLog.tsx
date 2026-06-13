// Audit log — chain-of-custody timeline from GOLD_AUDIT.USER_ACTION plus the
// knowledge-graph canon mutation log (KGAuditEntry), one .tl entry per event.

import { useAudit, useKgAudit } from '../../api/hooks';

interface AuditLogProps {
  activeFilingId: string | null;
}

const RHS_META: Record<string, { icon: string; color: string; label: string }> = {
  validation_run: { icon: 'V', color: 'var(--sf)', label: 'Validation run' },
  manual_fix: { icon: 'F', color: 'var(--accent)', label: 'Manual fix' },
  bulletin_apply: { icon: 'B', color: 'var(--kg)', label: 'Bulletin applied' },
  bulletin_reset: { icon: 'R', color: 'var(--ink-3)', label: 'Bulletin reset' },
  analyst_approved: { icon: '✓', color: 'var(--good)', label: 'Analyst sign-off' },
  actuary_approved: { icon: '✓', color: 'var(--good)', label: 'Actuary sign-off' },
  officer_approved: { icon: '✓', color: 'var(--good)', label: 'Officer sign-off' },
  regulator_ack: { icon: '↑', color: 'var(--good)', label: 'Regulator ACK' },
};

const KG_META: Record<string, { icon: string; color: string; label: string }> = {
  bulletin_apply: { icon: 'B', color: 'var(--kg)', label: 'Bulletin → KG' },
  bulletin_reset: { icon: 'R', color: 'var(--ink-3)', label: 'Bulletin reset' },
  rule_update: { icon: '↺', color: 'var(--warn)', label: 'Canon node superseded' },
  node_create: { icon: '+', color: 'var(--accent)', label: 'Canon node added' },
  extraction: { icon: 'X', color: 'var(--sf)', label: 'Sentinel extraction' },
};

export function AuditLog({ activeFilingId }: AuditLogProps) {
  const auditQ = useAudit(activeFilingId);
  const kgQ = useKgAudit();

  const audit = auditQ.data;
  const kgEntries = kgQ.data?.entries ?? [];
  const openCount = (audit?.exceptions ?? []).filter((e) => e.resolution_status === 'open').length;
  const fixedCount = (audit?.exceptions ?? []).filter((e) => e.resolution_status === 'fixed').length;

  return (
    <div className="screen">
      <div className="screen-audit-inner">
        <div className="audit-head">
          <span className="audit-eyebrow eyebrow">{activeFilingId ?? '—'} · chain of custody</span>
          <h1 className="audit-title">Every byte<br />has a <em>trail</em>.</h1>
          <p className="audit-sub">
            {auditQ.isLoading && 'Loading the audit trail…'}
            {auditQ.isError && <span style={{ color: 'var(--warn)' }}>Cannot reach the audit trail.</span>}
            {audit && (
              <>
                {audit.actions.length} RHS events + {kgEntries.length} KG events from
                GOLD_AUDIT.USER_ACTION + KGAuditEntry · {openCount} open exception{openCount !== 1 ? 's' : ''} · {fixedCount} resolved
                {audit.batch.last_validated_at && <> · last validation {audit.batch.last_validated_at}</>}
              </>
            )}
          </p>
        </div>

        <div className="timeline">
          {(audit?.actions ?? []).map((a, i) => {
            const meta = RHS_META[a.action_type] ?? { icon: '·', color: 'var(--ink-2)', label: a.action_type.replace(/_/g, ' ') };
            return (
              <div className={`tl ${i === 0 ? 'now' : 'done'}`} key={a.action_id}>
                <div className="tl-head">
                  <span className="tl-action" style={i === 0 ? undefined : { color: meta.color }}>{meta.label}</span>
                  <span className="tl-time">{a.acted_at}</span>
                </div>
                <div className="tl-card">
                  <div className="tl-actor">
                    <div className="avatar" style={{ background: meta.color }}>{meta.icon}</div>
                    <div className="meta">
                      <div className="nm">{a.actor}</div>
                      <div className="rl">{a.action_type.replace(/_/g, ' ')}</div>
                    </div>
                  </div>
                  <div className="tl-detail">
                    {a.summary}
                    {(a.target_record || a.target_rule) && (
                      <div className="tl-foot">
                        {a.target_record && <span>target <b>{a.target_record}</b></span>}
                        {a.target_rule && <span>rule/field <b>{a.target_rule}</b></span>}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}

          {audit && audit.actions.length === 0 && (
            <div className="tl done">
              <div className="tl-head"><span className="tl-action">No recorded actions</span></div>
              <div className="tl-card">
                <div className="tl-actor"><div className="avatar" style={{ background: 'var(--ink-3)' }}>·</div>
                  <div className="meta"><div className="nm">—</div></div>
                </div>
                <div className="tl-detail">This filing has no persisted user actions yet.</div>
              </div>
            </div>
          )}

          {kgEntries.length > 0 && (
            <div className="tl-divider">◆ Knowledge-graph audit · {kgEntries.length} canon event{kgEntries.length !== 1 ? 's' : ''}</div>
          )}
          {kgEntries.map((e) => {
            const meta = KG_META[e.action] ?? { icon: '·', color: 'var(--ink-2)', label: e.action.replace(/_/g, ' ') };
            return (
              <div className="tl done" key={e.id}>
                <div className="tl-head">
                  <span className="tl-action" style={{ color: meta.color }}>
                    {meta.label}<span className="kg-pill">KG</span>
                  </span>
                  <span className="tl-time">{e.occurred_at}</span>
                </div>
                <div className="tl-card">
                  <div className="tl-actor">
                    <div className="avatar" style={{ background: meta.color }}>{meta.icon}</div>
                    <div className="meta">
                      <div className="nm">{e.actor}</div>
                      <div className="rl">canon mutation</div>
                    </div>
                  </div>
                  <div className="tl-detail">
                    {e.summary}
                    <div className="tl-foot"><span>affected nodes <b>{e.affected_count}</b></span></div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
