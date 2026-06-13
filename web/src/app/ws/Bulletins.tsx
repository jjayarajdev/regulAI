// Bulletins screen — inbox list, bulletin detail with live impact numbers,
// the before/after verdict flip, raw bulletin text, and the Apply/Reset
// canon mutation (works in mock mode: violations actually close).

import { useState } from 'react';
import {
  useApplyBulletin, useBackendState, useBronzeCancellations, useBulletinText,
  useResetBulletin, useValidate,
} from '../../api/hooks';

interface BulletinsProps {
  activeFilingId: string | null;
}

export function Bulletins({ activeFilingId }: BulletinsProps) {
  const stQ = useBackendState();
  const valQ = useValidate(activeFilingId);
  const bronzeQ = useBronzeCancellations(activeFilingId);
  const textQ = useBulletinText();
  const apply = useApplyBulletin();
  const reset = useResetBulletin();
  const [lastDelta, setLastDelta] = useState<number | null>(null);

  const st = stQ.data;
  const v = valQ.data;
  const applied = st?.bulletin_applied ?? false;
  const busy = apply.isPending || reset.isPending;

  const title = (st?.bulletin_title ?? '').replace(/^Commissioner's Bulletin\s+\S+\s*—\s*/, '')
    || 'Credit Score Declination During Catastrophe Periods';

  // Impact: A.34 violations are the ones this bulletin affects.
  const affected = (v?.violations ?? []).filter((x) => x.rule_number === 'A.34');
  const recordsInScope = bronzeQ.data?.count ?? 0;

  const onToggle = async () => {
    if (applied) {
      await reset.mutateAsync();
      setLastDelta(null);
    } else {
      const res = await apply.mutateAsync();
      setLastDelta(Object.values(res.deltas).reduce((n, d) => n + d.closed_count, 0));
    }
  };

  return (
    <div className="screen screen-bulletins">
      <aside className="bul-side">
        <div className="bul-side-head">
          <span className="eyebrow">Bulletin inbox</span>
          <h3>
            {stQ.isLoading
              ? 'connecting…'
              : applied
                ? <>canon <em className="applied">amended</em></>
                : <><em>1 new</em> bulletin</>}
          </h3>
        </div>
        <div className="bul-item active">
          <div className="bul-meta">
            <span className="bul-src">TDI</span>
            <span className={`tag ${applied ? 'ok' : 'warn'}`}>{applied ? 'applied' : 'new'}</span>
            <span className="bul-date">{st?.bulletin_id ?? '—'}</span>
          </div>
          <div className="bul-title">{title}</div>
          <div className="bul-snippet">
            Reason code L submitted alone becomes a reporting violation during
            declared catastrophe periods — companion code required.
          </div>
        </div>
      </aside>

      <div className="bul-main">
        <div className="bul-detail-head">
          <div className="bul-detail-eyebrow">
            Commissioner's bulletin · {st?.bulletin_id ?? '—'} · affects rule A.34
          </div>
          <h1 className="bul-detail-title">
            Credit score declination,<br /><em>amended.</em>
          </h1>
          <div className="bul-detail-sub">
            <span>Source · TDI</span><span className="dot">·</span>
            <span>{st?.bulletin_id ?? '—'}</span><span className="dot">·</span>
            <span>{applied ? 'currently applied' : 'not yet applied'}</span>
          </div>
          <div className="bul-detail-actions">
            <button
              className={`btn ${applied ? '' : 'primary'}`}
              disabled={busy || stQ.isLoading || !st}
              onClick={onToggle}
            >
              {busy
                ? (applied ? 'Resetting…' : 'Applying… (rebuilds canon)')
                : applied ? 'Reset to baseline' : 'Apply to canon'}
            </button>
          </div>
          {(apply.isError || reset.isError) && (
            <div style={{ marginTop: 12, fontSize: 13, color: 'var(--bad)' }}>
              Bulletin step failed: {String((apply.error ?? reset.error as Error)?.message)}
            </div>
          )}
          {lastDelta !== null && !busy && (
            <div style={{ marginTop: 12, fontSize: 13, color: 'var(--good)' }}>
              ✓ Bulletin applied · {lastDelta} exception{lastDelta !== 1 ? 's' : ''} closed across filings ·
              FILING_EXCEPTION rows tagged <span className="mono">resolution_action='bulletin'</span>
            </div>
          )}
        </div>

        <div className="impact-row">
          <div className="impact-cell left">
            <span className="eyebrow">Records re-evaluated</span>
            <div className="impact-num num">{recordsInScope}<span className="unit">on {activeFilingId}</span></div>
            <div className="impact-sub">Every bronze notice record is re-checked against the amended canon.</div>
          </div>
          <div className="impact-cell">
            <span className="eyebrow">Net validation</span>
            <div className="impact-num num">
              {applied
                ? <em>{lastDelta !== null ? `+${lastDelta} cleared` : 'applied'}</em>
                : affected.length > 0 ? `${affected.length} would flip` : 'no effect'}
            </div>
            <div className="impact-sub">
              {applied
                ? 'A.34 L-companion violations resolved by the catastrophe-period override.'
                : affected.length > 0
                  ? `${affected.map((x) => x.policy_number).slice(0, 3).join(' · ')}${affected.length > 3 ? ' · …' : ''} flip VALID when applied.`
                  : 'No open A.34 violations on this filing.'}
            </div>
          </div>
        </div>

        <div className="flip">
          <div className="flip-cell before">
            <span className="eyebrow">Canon v1 (baseline)</span>
            <div className="flip-verdict">Verdict <em>INVALID</em></div>
            <div className="flip-reason">
              Reason code <span className="mono">L</span> submitted alone — credit
              score declination requires a companion code under rule A.34.
            </div>
          </div>
          <div className="flip-arrow">→</div>
          <div className="flip-cell after">
            <span className="eyebrow">After bulletin · canon v2</span>
            <div className="flip-verdict">Verdict <em>VALID</em></div>
            <div className="flip-reason">
              Catastrophe-period override: standalone <span className="mono">L</span>{' '}
              is accepted when the notice date falls inside a declared
              catastrophe window.
            </div>
          </div>
        </div>

        <div className="reg-h">Bulletin source text · markdown from regulator</div>
        <div className="card" style={{ overflow: 'hidden' }}>
          <pre className="bul-text-pre">
            {textQ.isLoading ? 'loading bulletin text…' : textQ.data ?? 'Bulletin text not available.'}
          </pre>
        </div>
      </div>
    </div>
  );
}
