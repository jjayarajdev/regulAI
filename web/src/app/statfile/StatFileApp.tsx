// STATFILE — the Statistical Filing Platform experience, ported from the
// claude.ai/design mock. Shell: sidebar nav + header; each screen is its own
// component. Cross-screen navigation goes through `go`.
import { useState } from 'react';
import { getActor, setActor } from '../../api/client';
import { can, GUEST, useFilings, useRunCycle, useUsers, whoCan, type AppUser } from './api';
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
const LIVE_SCREENS: ScreenId[] = ['dash', 'rules', 'val', 'pipe', 'record', 'graph', 'agents', 'config'];

export function StatFileApp() {
  const [screen, setScreen] = useState<ScreenId>('dash');
  const go = (s: ScreenId) => () => setScreen(s);
  const [crumb, title] = TITLES[screen];

  // "Trace to Guidewire" on the validation screen lands the record inspector
  // on that policy.
  const [tracePolicy, setTracePolicy] = useState<string | null>(null);
  const traceTo = (policy: string) => { setTracePolicy(policy); setScreen('record'); };

  const cycleMut = useRunCycle();

  // Persona (Phase 1 RBAC): pick who you are; the id rides every request as
  // X-Actor and gates which actions the screens offer.
  const usersQ = useUsers();
  const [actorId, setActorId] = useState<string | null>(getActor());
  const user: AppUser = usersQ.data?.users.find((u) => u.user_id === actorId) ?? GUEST;
  const pickUser = (id: string) => {
    const next = id === 'guest' ? null : id;
    setActor(next);
    setActorId(next);
  };

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
              <select
                value={user.user_id}
                onChange={(e) => pickUser(e.target.value)}
                title={`${user.title} — role ${user.role}`}
                style={{
                  padding: '5px 8px', fontSize: 12, fontFamily: 'var(--font-body)',
                  border: '1px solid var(--color-divider)', borderRadius: 0,
                  background: 'transparent', color: 'var(--color-text)', maxWidth: 190,
                }}
              >
                <option value="guest">Guest · read-only</option>
                {(usersQ.data?.users ?? []).map((u) => (
                  <option key={u.user_id} value={u.user_id}>{u.name} · {u.role}</option>
                ))}
              </select>
              <span className={'tag ' + (live ? 'tag-accent' : 'tag-neutral')}>
                <span style={{
                  width: 7, height: 7, borderRadius: '50%', marginRight: 6,
                  background: live ? 'var(--color-accent)' : 'var(--color-neutral-500)',
                }} />
                {pill}
              </span>
              <span className="tag tag-outline">TDI Stat Plan v2026.1</span>
              <button className="btn btn-secondary">Export</button>
              <button
                className="btn btn-primary"
                disabled={cycleMut.isPending || !can(user, 'run_pipeline')}
                onClick={() => cycleMut.mutate()}
                title={can(user, 'run_pipeline')
                  ? 'Bronze→Silver→Gold, then re-validate'
                  : `requires ${whoCan('run_pipeline')}`}
              >
                {cycleMut.isPending ? 'Running cycle…'
                  : cycleMut.isError ? 'Run failed — retry'
                  : 'Run cycle'}
              </button>
            </div>
          </header>

          <div className="content">
            {screen === 'dash' && <DashboardScreen go={go} />}
            {screen === 'rules' && <RulesScreen user={user} />}
            {screen === 'graph' && <GraphScreen />}
            {screen === 'pipe' && <PipelineScreen />}
            {screen === 'agents' && <AgentsScreen />}
            {screen === 'val' && <ValidationScreen onTrace={traceTo} user={user} />}
            {screen === 'record' && <RecordScreen initialPolicy={tracePolicy} user={user} />}
            {screen === 'iso' && <IsoScreen />}
            {screen === 'config' && <ConfigScreen />}
          </div>
        </main>
      </div>
    </div>
  );
}
