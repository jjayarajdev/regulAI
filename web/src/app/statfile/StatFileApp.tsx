// STATFILE — the Statistical Filing Platform experience, ported from the
// claude.ai/design mock. Shell: sidebar nav + header; each screen is its own
// component. Cross-screen navigation goes through `go`.
import { useState } from 'react';
import { useFilings } from './api';
import { NAV, TITLES, type ScreenId } from './data';
import { DashboardScreen } from './screens/Dashboard';
import { RulesScreen } from './screens/Rules';
import { GraphScreen } from './screens/Graph';
import { PipelineScreen } from './screens/Pipeline';
import { AgentsScreen } from './screens/Agents';
import { ValidationScreen } from './screens/Validation';
import { RecordScreen } from './screens/Record';
import { IsoScreen } from './screens/Iso';
import { ConfigScreen } from './screens/Config';
import './statfile.css';

// Screens whose data comes from the live API today; the rest still render the
// design's demo content until their endpoints land.
const LIVE_SCREENS: ScreenId[] = ['dash', 'rules', 'val'];

export function StatFileApp() {
  const [screen, setScreen] = useState<ScreenId>('dash');
  const go = (s: ScreenId) => () => setScreen(s);
  const [crumb, title] = TITLES[screen];

  // Data-source pill: connecting… → live data / demo data. Live means the
  // warehouse answered; a cold/failed warehouse degrades to demo fixtures.
  const filingsQ = useFilings();
  const wired = LIVE_SCREENS.includes(screen);
  const live = wired && !!filingsQ.data?.filings.length;
  const pill = !wired ? 'demo screen'
    : filingsQ.isLoading ? 'connecting…'
    : live ? 'live data' : 'demo data (warehouse offline)';

  // Sidebar cycle: first active live filing, else the design's fiction.
  const active = filingsQ.data?.filings.find((f) => f.is_active);
  const dueDays = active ? Math.max(0, Math.round((+new Date(active.due_date) - Date.now()) / 86400000)) : null;

  return (
    <div className="sf">
      <div className="shell">
        <aside className="side">
          <div className="side-brand">
            <div className="wordmark">STATFILE</div>
            <div className="k" style={{ marginTop: 4 }}>Regulatory reporting fabric</div>
          </div>
          <nav className="side-nav">
            {NAV.map(([id, label], i) => (
              <button key={id} className={'navbtn' + (screen === id ? ' on' : '')} onClick={go(id)}>
                <span className="num">{String(i + 1).padStart(2, '0')}</span>
                <span>{label}</span>
              </button>
            ))}
          </nav>
          <div className="side-cycle">
            <div className="k">Active cycle</div>
            <div className="cycle-name">{active ? active.id : 'TX HO · 2026 ANNUAL'}</div>
            <div className="cycle-due">
              {active ? `Due ${active.due_date} · ${dueDays} days` : 'Due 15 Sep 2026 · 42 days'}
            </div>
          </div>
        </aside>

        <main className="work">
          <header className="tophead">
            <div>
              <div className="k">{crumb}</div>
              <h3>{title}</h3>
            </div>
            <div className="actions">
              <span className={'tag ' + (live ? 'tag-accent' : 'tag-neutral')}>
                <span style={{
                  width: 7, height: 7, borderRadius: '50%', marginRight: 6,
                  background: live ? 'var(--color-accent)' : 'var(--color-neutral-500)',
                }} />
                {pill}
              </span>
              <span className="tag tag-outline">TDI Stat Plan v2026.1</span>
              <button className="btn btn-secondary">Export</button>
              <button className="btn btn-primary">Run cycle</button>
            </div>
          </header>

          <div className="content">
            {screen === 'dash' && <DashboardScreen go={go} />}
            {screen === 'rules' && <RulesScreen />}
            {screen === 'graph' && <GraphScreen />}
            {screen === 'pipe' && <PipelineScreen />}
            {screen === 'agents' && <AgentsScreen />}
            {screen === 'val' && <ValidationScreen />}
            {screen === 'record' && <RecordScreen />}
            {screen === 'iso' && <IsoScreen />}
            {screen === 'config' && <ConfigScreen />}
          </div>
        </main>
      </div>
    </div>
  );
}
