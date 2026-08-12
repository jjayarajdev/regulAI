// STATFILE — the Statistical Filing Platform experience, ported from the
// claude.ai/design mock. Shell: sidebar nav + header; each screen is its own
// component. Cross-screen navigation goes through `go`.
import { useState } from 'react';
import { can, canSee, GUEST, useFilings, useLogin, useLogout, useMe, useRunCycle, whoCan, type AppUser } from './api';
import { NAV, TITLES, type ScreenId } from './data';
import { DashboardScreen } from './screens/Dashboard';
import { RulesScreen } from './screens/Rules';
import { GraphScreen } from './screens/Graph';
import { PipelineScreen } from './screens/Pipeline';
import { AgentsScreen } from './screens/Agents';
import { ValidationScreen } from './screens/Validation';
import { RecordScreen } from './screens/Record';
import { FilingScreen } from './screens/Filing';
import { AmendmentsScreen } from './screens/Amendments';
import { IsoScreen } from './screens/Iso';
import { ConfigScreen } from './screens/Config';
import { UsersScreen } from './screens/Users';
import { Toaster } from 'sonner';
import './statfile.css';

// Screens whose data comes from the live API today; the rest still render the
// design's demo content until their endpoints land.
const LIVE_SCREENS: ScreenId[] = ['dash', 'rules', 'val', 'pipe', 'record', 'graph', 'agents', 'config', 'filing', 'amend'];

export function StatFileApp() {
  const [screen, setScreen] = useState<ScreenId>('dash');
  const go = (s: ScreenId) => () => setScreen(s);
  const [crumb, title] = TITLES[screen];

  // "Trace to Guidewire" on the validation screen lands the record inspector
  // on that policy.
  const [tracePolicy, setTracePolicy] = useState<string | null>(null);
  const traceTo = (policy: string) => { setTracePolicy(policy); setScreen('record'); };

  const cycleMut = useRunCycle();

  // Session identity: /auth/me resolves the stored token; the login card
  // below the header signs in; gating flows from the resolved user's role.
  const meQ = useMe();
  const user: AppUser = meQ.data?.user ?? GUEST;
  const signedIn = user.user_id !== 'guest';
  const [guest, setGuest] = useState(() => {
    try { return sessionStorage.getItem('regulai-guest') === '1'; } catch { return false; }
  });
  const browseAsGuest = () => {
    try { sessionStorage.setItem('regulai-guest', '1'); } catch { /* fine */ }
    setGuest(true);
  };
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const loginMut = useLogin();
  const logoutMut = useLogout();
  const doLogin = () =>
    loginMut.mutate({ email: email.trim(), password }, {
      onSuccess: () => { setEmail(''); setPassword(''); },
    });
  const doLogout = () => {
    try { sessionStorage.removeItem('regulai-guest'); } catch { /* fine */ }
    setGuest(false);
    logoutMut.mutate();
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

  // If the open screen isn't visible to this role (sign-out, role change),
  // fall back to the dashboard.
  if (!canSee(user, screen) && !meQ.isLoading) {
    setScreen('dash');
  }

  // Login gate: the app renders only for a signed-in user or an explicit
  // guest (read-only) session. While the token resolves, render nothing to
  // avoid flashing the gate at signed-in users.
  if (meQ.isLoading) return <div className="sf" />;
  if (!signedIn && !guest) {
    return (
      <div className="sf" style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}>
        <div style={{ width: 340, border: '1px solid var(--color-divider)', padding: '30px 32px', background: 'var(--color-bg, #fff)' }}>
          <div className="wordmark" style={{ fontSize: 26 }}>STATFILE</div>
          <div className="k" style={{ margin: '4px 0 22px' }}>Regulatory reporting fabric · sign in</div>
          <input
            value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email" autoFocus
            style={{ width: '100%', boxSizing: 'border-box', padding: '9px 11px', fontSize: 13, marginBottom: 10, border: '1px solid var(--color-divider)', borderRadius: 0, background: 'transparent', color: 'var(--color-text)' }}
          />
          <input
            type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password"
            onKeyDown={(e) => { if (e.key === 'Enter') doLogin(); }}
            style={{ width: '100%', boxSizing: 'border-box', padding: '9px 11px', fontSize: 13, marginBottom: 14, border: '1px solid var(--color-divider)', borderRadius: 0, background: 'transparent', color: 'var(--color-text)' }}
          />
          <button className="btn btn-primary btn-block" disabled={loginMut.isPending || !email.trim() || !password}
            onClick={doLogin}>
            {loginMut.isPending ? 'Signing in…' : 'Sign in'}
          </button>
          {loginMut.error != null && (
            <div className="k" style={{ marginTop: 10, color: 'var(--color-accent-700)' }}>
              {(loginMut.error as Error).message}
            </div>
          )}
          <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px solid var(--color-divider)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="k">no account? ask your admin</span>
            <button
              onClick={browseAsGuest}
              style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontSize: 12, color: 'var(--color-accent-700)', textDecoration: 'underline' }}
            >
              browse as guest
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="sf">
      <Toaster position="bottom-right" toastOptions={{
        style: { borderRadius: 0, fontFamily: 'var(--font-body)', fontSize: 13 },
      }} />
      <div className="shell">
        <aside className="side">
          <div className="side-brand">
            <div className="wordmark">STATFILE</div>
            <div className="k" style={{ marginTop: 4 }}>Regulatory reporting fabric</div>
          </div>
          <nav className="side-nav">
            {NAV.filter(([id]) => canSee(user, id)).map(([id, label], i) => (
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
              <span className="tag tag-outline" title={user.title}>{user.name} · {user.role}</span>
              <button className="btn btn-secondary" onClick={doLogout}>
                {signedIn ? 'Sign out' : 'Sign in'}
              </button>
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
            {screen === 'filing' && <FilingScreen user={user} go={go} />}
            {screen === 'amend' && <AmendmentsScreen user={user} />}
            {screen === 'iso' && <IsoScreen />}
            {screen === 'config' && <ConfigScreen />}
            {screen === 'users' && <UsersScreen user={user} />}
          </div>
        </main>
      </div>
    </div>
  );
}
