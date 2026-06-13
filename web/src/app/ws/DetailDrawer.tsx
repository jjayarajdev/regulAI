// Right-side detail drawer, ported from workstation.html's .detail-panel.
// PolicyDetail shows the bronze record, every rule's pass/fail verdict for
// that policy, an inline manual-fix editor per failing rule, and the
// quick-action bulletin shortcut for bare-L violations.

import { useState, type ReactNode } from 'react';
import { useApplyBulletin, useBronzeCancellations, useValidate } from '../../api/hooks';
import { FixEditor } from './FixEditor';

export function DetailDrawer({ open, eyebrow, title, onClose, children }: {
  open: boolean;
  eyebrow: string;
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <>
      <div className={`detail-backdrop ${open ? 'open' : ''}`} onClick={onClose} />
      <aside className={`detail-panel ${open ? 'open' : ''}`} aria-hidden={!open}>
        <div className="detail-header">
          <div>
            <div className="detail-eyebrow">{eyebrow}</div>
            <div className="detail-title">{title}</div>
          </div>
          <button className="detail-close" onClick={onClose}>×</button>
        </div>
        <div className="detail-body">{children}</div>
      </aside>
    </>
  );
}

export function PolicyDetail({ policy, filingId }: { policy: string; filingId: string | null }) {
  const valQ = useValidate(filingId);
  const bronzeQ = useBronzeCancellations(filingId);
  const applyBulletin = useApplyBulletin();
  const [fixingRule, setFixingRule] = useState<string | null>(null);

  const bronze = (bronzeQ.data?.rows ?? []).find((r) => r.policy === policy);
  const violations = (valQ.data?.violations ?? []).filter((x) => x.policy_number === policy);
  const rules = valQ.data?.rules ?? [];

  if (!bronze) {
    return <div style={{ color: 'var(--ink-3)' }}>{bronzeQ.isLoading ? 'Loading record…' : 'No record found.'}</div>;
  }

  const code = bronze.reason_code || '—';
  const failCount = rules.filter((r) => violations.some((x) => x.rule_id === r.rule_id)).length;

  return (
    <>
      <div className="detail-kv">
        <div className="k">Reason code</div>
        <div className="mono"><b>{code}</b></div>
        <div className="k">Action</div>
        <div>{bronze.action || '—'}</div>
        <div className="k">Notice date</div>
        <div className="mono">{bronze.noticedate || '—'}</div>
        <div className="k">Effective date</div>
        <div className="mono">{bronze.effectivedate || '—'}</div>
        <div className="k">Source</div>
        <div><code className="mono" style={{ fontSize: 12 }}>BRONZE.GW_PC_JOB ⋈ GW_PC_POLICY</code></div>
      </div>

      <h4 className="detail-h4">Validation results · {failCount} fail / {rules.length - failCount} pass</h4>
      <div style={{ border: '1px solid var(--line)', borderRadius: 6, overflow: 'hidden', marginBottom: 18 }}>
        {rules.map((r) => {
          const vio = violations.find((x) => x.rule_id === r.rule_id);
          return (
            <div key={r.rule_id}>
              <div className={`rule-result-row ${vio ? 'fail' : ''}`}>
                <span className="rr-num">{r.rule_number}</span>
                <span style={{ fontSize: 13 }}>
                  {r.rule_name}
                  {vio && <><br /><span className="rr-reason">{vio.violation_reason}</span></>}
                </span>
                <span className="rr-verdict">{vio ? '✗ fail' : '✓ pass'}</span>
                {vio
                  ? (
                    <button
                      className="vio-action"
                      onClick={() => setFixingRule(fixingRule === r.rule_number ? null : r.rule_number)}
                    >
                      Fix →
                    </button>
                  )
                  : <span />}
              </div>
              {fixingRule === r.rule_number && (
                <FixEditor
                  policy={policy}
                  currentCode={code === '—' ? '' : code}
                  ruleNum={r.rule_number}
                  onDone={() => setFixingRule(null)}
                  onCancel={() => setFixingRule(null)}
                />
              )}
            </div>
          );
        })}
      </div>

      {violations.length > 0 && code === 'L' && (
        <>
          <h4 className="detail-h4">Quick action</h4>
          <button className="btn primary" disabled={applyBulletin.isPending} onClick={() => applyBulletin.mutate()}>
            {applyBulletin.isPending ? 'Applying…' : 'Apply bulletin B-2026-Q4-118 (clears L-companion violation)'}
          </button>
        </>
      )}
      {violations.length === 0 && (
        <div style={{ fontSize: 13, color: 'var(--good)' }}>✓ Policy passes all executable rules.</div>
      )}
    </>
  );
}
