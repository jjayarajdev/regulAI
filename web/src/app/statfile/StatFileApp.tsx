// RegAssure — the statistical filing platform (module heritage: STATFILE).
// Shell: antd Layout — dark Sider with grouped Menu, header with cycle
// actions and the session identity; each screen is its own component.
// Cross-screen navigation goes through `go`.
import { useState, type ReactNode } from 'react';
import {
  ApartmentOutlined, AuditOutlined, BookOutlined, DashboardOutlined,
  DiffOutlined, FileDoneOutlined, FileProtectOutlined, LoginOutlined,
  LogoutOutlined, NodeIndexOutlined, SettingOutlined,
} from '@ant-design/icons';
import { Avatar, Badge, Button, ConfigProvider, Dropdown, Layout, Menu, Segmented, Tag, Tooltip, Typography } from 'antd';
import { can, canSee, GUEST, useFilings, useLogout, useMe, useRunCycle, whoCan, type AppUser } from './api';
import { LoginPage } from './LoginPage';
import { BRAND, BRAND_TAG, REGASSURE_THEME } from './theme';
import { NAV_SECTIONS, TITLES, type ScreenId } from './data';
import { DashboardScreen } from './screens/Dashboard';
import { RulesScreen } from './screens/Rules';
import { GraphScreen } from './screens/Graph';
import { PipelineScreen } from './screens/Pipeline';
import { AgentsScreen } from './screens/Agents';
import { ValidationScreen } from './screens/Validation';
import { RecordScreen } from './screens/Record';
import { FilingScreen } from './screens/Filing';
import { AmendmentsScreen } from './screens/Amendments';
import { MappingReviewScreen } from './screens/MappingReview';
import { ExtractionReviewScreen } from './screens/ExtractionReview';
import { ErrorBoundary } from './ErrorBoundary';
import { IsoScreen } from './screens/Iso';
import { ConfigScreen } from './screens/Config';
import { UsersScreen } from './screens/Users';
import { Toaster } from 'sonner';
import './statfile.css';

// Screens whose data comes from the live API today; the rest still render the
// design's demo content until their endpoints land.
const LIVE_SCREENS: ScreenId[] = ['dash', 'rules', 'val', 'pipe', 'mapping', 'record', 'graph', 'agents', 'config', 'filing', 'amend', 'extract'];

// Drill-in screens highlight their parent nav item: the record inspector is
// reached from Validation, the knowledge graph is the Rulebook's second tab,
// the agent console lives under Operations, users under Administration.
const NAV_PARENT: Partial<Record<ScreenId, ScreenId>> = {
  record: 'val', graph: 'rules', extract: 'rules', agents: 'pipe', users: 'config',
};

const NAV_ICONS: Partial<Record<ScreenId, ReactNode>> = {
  dash: <DashboardOutlined />, val: <AuditOutlined />, filing: <FileDoneOutlined />,
  amend: <DiffOutlined />, rules: <BookOutlined />, mapping: <NodeIndexOutlined />,
  pipe: <ApartmentOutlined />, config: <SettingOutlined />,
};

// Segmented tab strip for screens that share a nav item. The tab state IS the
// screen id, so deep links and existing go('agents')-style calls keep working.
// Tabs the role can't see are hidden; a lone tab renders no control at all.
function ScreenTabs({ tabs, screen, go, user }: {
  tabs: Array<[ScreenId, string]>; screen: ScreenId;
  go: (s: ScreenId) => () => void; user: AppUser;
}) {
  const visible = tabs.filter(([id]) => canSee(user, id));
  if (visible.length < 2) return null;
  return (
    <Segmented
      style={{ marginBottom: 18 }}
      value={screen}
      onChange={(v) => go(v as ScreenId)()}
      options={visible.map(([id, label]) => ({ label, value: id }))}
    />
  );
}

export function StatFileApp() {
  const [screen, setScreen] = useState<ScreenId>('dash');
  const go = (s: ScreenId) => () => setScreen(s);
  const [crumb, title] = TITLES[screen];

  // "Trace to Guidewire" on the validation screen lands the record inspector
  // on that policy.
  const [tracePolicy, setTracePolicy] = useState<string | null>(null);
  const traceTo = (policy: string) => { setTracePolicy(policy); setScreen('record'); };

  const cycleMut = useRunCycle();

  // Session identity: /auth/me resolves the stored token; the LoginPage
  // gate signs in; gating flows from the resolved user's role.
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
  const logoutMut = useLogout();
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
    return <LoginPage onGuest={browseAsGuest} />;
  }

  // Sections filtered per role; a section with nothing visible renders no
  // group header.
  const menuItems = NAV_SECTIONS
    .map((s) => ({ title: s.title, items: s.items.filter(([id]) => canSee(user, id)) }))
    .filter((s) => s.items.length > 0)
    .map((s) => ({
      type: 'group' as const,
      label: s.title,
      children: s.items.map(([id, label]) => ({ key: id, icon: NAV_ICONS[id], label })),
    }));
  const navActive = NAV_PARENT[screen] ?? screen;

  const initials = user.name.split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase();
  const userMenu = {
    items: signedIn
      ? [
          { key: 'who', label: <span className="k">{user.title}</span>, disabled: true },
          { type: 'divider' as const },
          { key: 'out', icon: <LogoutOutlined />, label: 'Sign out' },
        ]
      : [{ key: 'out', icon: <LoginOutlined />, label: 'Sign in' }],
    onClick: ({ key }: { key: string }) => { if (key === 'out') doLogout(); },
  };

  return (
    <ConfigProvider theme={REGASSURE_THEME}>
      <div className="sf">
        <Toaster position="bottom-right" toastOptions={{
          style: { borderRadius: 0, fontFamily: 'var(--font-body)', fontSize: 13 },
        }} />
        <Layout style={{ minHeight: '100vh' }}>
          <Layout.Sider width={260} style={{ position: 'sticky', top: 0, height: '100vh' }}>
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              <div style={{ padding: '18px 20px 14px', borderBottom: '1px solid rgba(255,255,255,0.12)', color: '#fff' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                  <FileProtectOutlined style={{ fontSize: 19, color: '#85a5ff' }} />
                  <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 19, letterSpacing: '0.02em' }}>
                    {BRAND}
                  </span>
                </div>
                <div style={{ fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.45)', marginTop: 5 }}>
                  {BRAND_TAG}
                </div>
              </div>
              <Menu
                theme="dark" mode="inline" items={menuItems}
                selectedKeys={[navActive]}
                onClick={({ key }) => setScreen(key as ScreenId)}
                style={{ flex: 1, overflow: 'auto', background: 'transparent', borderInlineEnd: 0, paddingTop: 6 }}
              />
              <div style={{ padding: '14px 20px 18px', borderTop: '1px solid rgba(255,255,255,0.12)', color: '#fff' }}>
                <div style={{ fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.45)' }}>
                  Active cycle
                </div>
                <div style={{ fontFamily: 'var(--font-heading)', fontSize: 16, marginTop: 3 }}>
                  {active ? active.id : 'TX HO · 2026 ANNUAL'}
                </div>
                <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.55)' }}>
                  {active ? `Due ${active.due_date} · ${dueDays} days` : 'Due 15 Sep 2026 · 42 days'}
                </div>
              </div>
            </div>
          </Layout.Sider>

          <Layout>
            <Layout.Header style={{
              height: 'auto', lineHeight: 'normal', padding: '13px 28px',
              borderBottom: '1px solid var(--color-divider)',
              display: 'flex', alignItems: 'center', gap: 10,
            }}>
              <div style={{ minWidth: 0 }}>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>{crumb}</Typography.Text>
                <Typography.Title level={4} style={{ margin: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {title}
                </Typography.Title>
              </div>
              <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
                <Badge
                  status={!wired ? 'default' : filingsQ.isLoading ? 'processing' : live ? 'success' : 'warning'}
                  text={<Typography.Text type="secondary" style={{ fontSize: 13 }}>{pill}</Typography.Text>}
                />
                <Tag style={{ marginInlineEnd: 0 }}>TDI Stat Plan v2026.1</Tag>
                <Button>Export</Button>
                <Tooltip title={can(user, 'run_pipeline')
                  ? 'Bronze→Silver→Gold, then re-validate'
                  : `requires ${whoCan('run_pipeline')}`}>
                  <Button
                    type="primary" danger={cycleMut.isError}
                    disabled={!can(user, 'run_pipeline')}
                    loading={cycleMut.isPending}
                    onClick={() => cycleMut.mutate()}
                  >
                    {cycleMut.isPending ? 'Running cycle…'
                      : cycleMut.isError ? 'Run failed — retry'
                      : 'Run cycle'}
                  </Button>
                </Tooltip>
                <Dropdown menu={userMenu} trigger={['click']}>
                  <button style={{
                    background: 'none', border: 'none', padding: '4px 6px', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: 8, fontFamily: 'inherit', fontSize: 13,
                  }} title={user.title}>
                    <Avatar size={30} style={{ background: signedIn ? '#1677ff' : '#98989b' }}>
                      {initials}
                    </Avatar>
                    <span style={{ lineHeight: 1.2, textAlign: 'left' }}>
                      {user.name}
                      <span className="k" style={{ display: 'block' }}>{user.role}</span>
                    </span>
                  </button>
                </Dropdown>
              </div>
            </Layout.Header>

            <Layout.Content className="content" style={{ background: 'var(--color-bg)' }}>
              <ErrorBoundary screen={screen}>
              {screen === 'dash' && <DashboardScreen go={go} />}
              {(screen === 'rules' || screen === 'graph' || screen === 'extract') && (
                <>
                  <ScreenTabs tabs={[['rules', 'Rulebook'], ['extract', 'Extraction review'], ['graph', 'Knowledge graph']]}
                    screen={screen} go={go} user={user} />
                  {screen === 'rules' ? <RulesScreen user={user} />
                    : screen === 'extract' ? <ExtractionReviewScreen user={user} />
                    : <GraphScreen />}
                </>
              )}
              {(screen === 'pipe' || screen === 'agents') && (
                <>
                  <ScreenTabs tabs={[['pipe', 'Medallion pipeline'], ['agents', 'Agent console']]}
                    screen={screen} go={go} user={user} />
                  {screen === 'pipe' ? <PipelineScreen /> : <AgentsScreen />}
                </>
              )}
              {screen === 'val' && <ValidationScreen onTrace={traceTo} user={user} />}
              {screen === 'record' && <RecordScreen initialPolicy={tracePolicy} user={user} />}
              {screen === 'filing' && <FilingScreen user={user} go={go} />}
              {screen === 'amend' && <AmendmentsScreen user={user} />}
              {screen === 'mapping' && <MappingReviewScreen />}
              {screen === 'iso' && <IsoScreen />}
              {(screen === 'config' || screen === 'users') && (
                <>
                  <ScreenTabs tabs={[['config', 'Jurisdictions'], ['users', 'Users & access']]}
                    screen={screen} go={go} user={user} />
                  {screen === 'config' ? <ConfigScreen go={go} user={user} /> : <UsersScreen user={user} />}
                </>
              )}
              </ErrorBoundary>
            </Layout.Content>
          </Layout>
        </Layout>
      </div>
    </ConfigProvider>
  );
}
