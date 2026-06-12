// RegulAI workstation shell — React port of ui/workstation.html's chrome:
// topbar (brand / context breadcrumb / user), 240px rail (nav + my filings +
// sources), page-header strip (eyebrow, live status dots, refresh).
// Screens render inside <main>; Overview is fully wired, the rest are stubs
// queued for porting.

import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useBackendState, useFilings, useValidate, useValidateAll } from '../../api/hooks';
import { Overview } from './Overview';
import { FilingWorkshop } from './FilingWorkshop';

export type WsScreen = 'dashboard' | 'filing' | 'regulations' | 'bulletins' | 'audit';

const SCREEN_TITLES: Record<WsScreen, string> = {
  dashboard: 'Overview',
  filing: 'Filing workshop',
  regulations: 'Regulations',
  bulletins: 'Bulletins',
  audit: 'Audit log',
};

export function WorkstationApp() {
  const [screen, setScreen] = useState<WsScreen>('dashboard');
  const [selectedFilingId, setSelectedFilingId] = useState<string | null>(null);

  const queryClient = useQueryClient();
  const filingsQ = useFilings();
  const stQ = useBackendState();

  const filings = filingsQ.data?.filings ?? [];
  const activeFilingId = selectedFilingId ?? filingsQ.data?.default ?? null;
  const activeFiling = filings.find((f) => f.id === activeFilingId) ?? null;

  const filingIds = filings.map((f) => f.id);
  const validations = useValidateAll(filingIds);
  const activeVal = useValidate(activeFilingId).data;

  const st = stQ.data;
  const countByFiling = Object.fromEntries(
    filingIds.map((id, i) => [id, validations[i]?.data?.summary.total_violations]),
  );

  // Cycle label like "Filing cycle Q4 2025", from the active filing id suffix.
  const cycleLabel = activeFilingId
    ? `Filing cycle ${activeFilingId.split('-').slice(1).join(' ')}`
    : 'Filing cycle';

  const sfState = stQ.isLoading ? '…' : st?.reference_loaded ? 'live' : 'offline';
  const kgState = stQ.isLoading ? '…' : st ? 'live' : 'offline';

  return (
    <div className="ws-root">
      <div className="app">
        {/* ── topbar ─────────────────────────────────── */}
        <header className="topbar">
          <div className="brand">RegulAI</div>
          <div className="filing-ctx">
            <b>Lone Star Mutual</b>
            <span className="dot">/</span>
            <span className="jur-pill" title="Active regulatory jurisdiction">
              {activeFiling?.jurisdiction_code ?? '—'}
            </span>
            <span className="dot">/</span>
            <span>
              {activeFiling
                ? `${activeFiling.plan_code} · ${activeFiling.id.split('-').slice(1).join('-')}`
                : 'loading…'}
            </span>
            <span className="dot">/</span>
            <span style={{ color: stQ.isLoading ? 'var(--ink-3)' : st && !st.reference_loaded ? 'var(--warn)' : 'var(--ink-3)' }}>
              {stQ.isLoading
                ? '… connecting'
                : !st || !st.reference_loaded
                  ? '⚠ Snowflake unreachable'
                  : st.bulletin_applied
                    ? `✓ bulletin ${st.bulletin_id} applied`
                    : '◯ canon v1 (baseline)'}
            </span>
          </div>
          <div className="top-right">
            <button className="icon-btn" title="Search">
              <svg className="ic" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg>
            </button>
            <button className="icon-btn" title="Notifications">
              <svg className="ic" viewBox="0 0 24 24"><path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 0 1-3.4 0" /></svg>
            </button>
            <div className="user">
              <div className="avatar">DR</div>
              <div className="user-meta">
                <div className="user-name">Diana Reyes</div>
                <div className="user-role">VP, Compliance</div>
              </div>
            </div>
          </div>
        </header>

        {/* ── rail ───────────────────────────────────── */}
        <nav className="rail">
          <div className="rail-group">
            <button className={`rail-link ${screen === 'dashboard' ? 'active' : ''}`} onClick={() => setScreen('dashboard')}>
              Overview
            </button>
            <button className={`rail-link ${screen === 'filing' ? 'active' : ''}`} onClick={() => setScreen('filing')}>
              Filing
              <span className="count num">
                {activeVal ? (activeVal.summary.total_violations > 0 ? activeVal.summary.total_violations : '✓') : '—'}
              </span>
            </button>
            <button className={`rail-link ${screen === 'regulations' ? 'active' : ''}`} onClick={() => setScreen('regulations')}>
              Regulations
              <span className="count num">{activeVal?.summary.rules_run ?? '—'}</span>
            </button>
            <button className={`rail-link ${screen === 'bulletins' ? 'active' : ''}`} onClick={() => setScreen('bulletins')}>
              Bulletins
              <span className="count">{st ? (st.bulletin_applied ? '✓' : 'new') : '—'}</span>
            </button>
            <button className={`rail-link ${screen === 'audit' ? 'active' : ''}`} onClick={() => setScreen('audit')}>
              Audit log
            </button>
          </div>

          <div className="rail-group">
            <div className="rail-label">My filings</div>
            {filingsQ.isLoading && <div className="rail-link" style={{ opacity: 0.5 }}>loading filings…</div>}
            {filings.map((f) => {
              const isActive = f.id === activeFilingId;
              const n = countByFiling[f.id];
              return (
                <button
                  key={f.id}
                  className={`rail-link ${isActive ? 'active-filing' : ''}`}
                  title={`${f.plan_name} · ${f.cadence} · due ${f.due_date}`}
                  onClick={() => { setSelectedFilingId(f.id); setScreen('filing'); }}
                >
                  {f.id}
                  <span className="count num" style={n !== undefined && n > 0 ? { color: isActive ? undefined : 'var(--bad)' } : undefined}>
                    {n === undefined ? '—' : n > 0 ? n : '✓'}
                  </span>
                </button>
              );
            })}
          </div>

          <div className="rail-group">
            <div className="rail-label">Sources</div>
            <a className="rail-link" href="http://localhost:7474" target="_blank" rel="noopener noreferrer">
              Knowledge graph<span className="count">↗</span>
            </a>
            <a className="rail-link" href="https://app.snowflake.com/" target="_blank" rel="noopener noreferrer">
              Snowflake<span className="count">↗</span>
            </a>
            <div className="rail-link">ShareFile<span className="count">preview</span></div>
          </div>
        </nav>

        {/* ── page header bar ────────────────────────── */}
        <div className="page-header">
          <span className="ph-eyebrow">{SCREEN_TITLES[screen]}</span>
          <span className="ph-sep">/</span>
          <span className="ph-title">{cycleLabel}</span>
          <div className="ph-meta">
            <span><span className={`live-dot ${sfState !== 'live' ? 'off' : ''}`} />Snowflake {sfState}</span>
            <span><span className={`live-dot ${kgState !== 'live' ? 'off' : ''}`} />Neo4j KG {kgState}</span>
            <button className="refresh" onClick={() => queryClient.invalidateQueries()}>⟲ Refresh</button>
          </div>
        </div>

        {/* ── main ───────────────────────────────────── */}
        <main>
          {screen === 'dashboard' && (
            <Overview
              activeFilingId={activeFilingId}
              onOpenFiling={(id) => { setSelectedFilingId(id); setScreen('filing'); }}
            />
          )}
          {screen === 'filing' && (
            <FilingWorkshop
              activeFilingId={activeFilingId}
              onBack={() => setScreen('dashboard')}
            />
          )}
          {screen !== 'dashboard' && screen !== 'filing' && (
            <div className="screen">
              <div className="stub-screen">
                <div className="eyebrow">{SCREEN_TITLES[screen]}</div>
                <div className="stub-card">
                  The <b>{SCREEN_TITLES[screen]}</b> screen is next in the React port.
                  The data hooks it needs are already wired (
                  {screen === 'regulations' && 'kg/rules, validate'}
                  {screen === 'bulletins' && 'state, bulletin text'}
                  {screen === 'audit' && 'audit trail, kg/audit'}) — only the
                  markup remains. Until then, the original is available in
                  ui/workstation.html.
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
