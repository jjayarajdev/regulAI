// Users & access — admin console over GOLD_AUDIT.APP_USER: role changes,
// activate/deactivate, password resets, new accounts. The nav item only
// renders for manage_users roles; this screen re-checks and explains itself
// to anyone who lands here without the grant.
import { useState } from 'react';
import { Blueprint } from '../Blueprint';
import { can, useAdminUsers, useSaveUser, whoCan, type AppUser, type Role } from '../api';

const ROLES: Role[] = ['viewer', 'analyst', 'actuary', 'admin', 'cco'];

// What each role means, shown beside the table so admins assign deliberately.
const ROLE_NOTES: Array<[Role, string]> = [
  ['viewer', 'Read-only — dashboards and screens, no actions'],
  ['analyst', 'Prepares the report: run cycle, fix/assign exceptions, analyst sign-off'],
  ['actuary', 'Reconciliation review and actuary sign-off'],
  ['admin', 'Spec onboarding: documents, extractions, rule approvals, suppressions, user management'],
  ['cco', 'Oversight: officer sign-off, seal & transmit, ack, user management'],
];

const inputStyle = {
  padding: '6px 9px', fontSize: 12.5, border: '1px solid var(--color-divider)',
  borderRadius: 0, background: 'transparent', color: 'var(--color-text)',
} as const;

export function UsersScreen({ user }: { user?: AppUser }) {
  const mayManage = can(user, 'manage_users');
  const adminUsersQ = useAdminUsers(mayManage);
  const saveUser = useSaveUser();
  const [nu, setNu] = useState({ name: '', email: '', role: 'analyst' as Role, password: '' });

  if (!mayManage) {
    return (
      <div className="sc">
        <Blueprint style={{ padding: '18px 20px' }}>
          <div className="k" style={{ marginBottom: 6 }}>Access control</div>
          <div style={{ fontSize: 13.5 }}>
            User management requires {whoCan('manage_users')} — you are signed in as{' '}
            {user?.name ?? 'Guest'} ({user?.role ?? 'viewer'}).
          </div>
        </Blueprint>
      </div>
    );
  }

  return (
    <div className="sc" style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 30, alignItems: 'start' }}>
      <section>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 10 }}>
          <h4>Users</h4>
          <span className="k">GOLD_AUDIT.APP_USER · role changes take effect immediately</span>
        </div>
        <table className="table">
          <thead>
            <tr><th>Name</th><th>Email</th><th>Role</th><th>Title</th><th>Status</th><th /></tr>
          </thead>
          <tbody>
            {(adminUsersQ.data?.users ?? []).map((u) => (
              <tr key={u.user_id} className="row">
                <td style={{ fontSize: 13, fontWeight: 500 }}>{u.name}</td>
                <td className="mono" style={{ fontSize: 12 }}>{u.email}</td>
                <td>
                  <select
                    value={u.role}
                    disabled={saveUser.update.isPending || u.user_id === user?.user_id}
                    onChange={(e) => saveUser.update.mutate({ userId: u.user_id, role: e.target.value as Role })}
                    style={{ ...inputStyle, padding: '4px 6px', fontSize: 12 }}
                  >
                    {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </td>
                <td style={{ fontSize: 12, color: 'color-mix(in srgb,var(--color-text) 60%,transparent)' }}>{u.title}</td>
                <td><span className={'tag ' + (u.active ? 'tag-neutral' : 'tag-outline')}>{u.active ? 'Active' : 'Deactivated'}</span></td>
                <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                  <button className="btn btn-secondary" disabled={saveUser.update.isPending}
                    onClick={() => saveUser.update.mutate({ userId: u.user_id, password: 'Regulai#2026' })}
                    title="Reset password to the default (Regulai#2026)">
                    Reset pw
                  </button>{' '}
                  <button className="btn btn-secondary"
                    disabled={saveUser.update.isPending || u.user_id === user?.user_id}
                    onClick={() => saveUser.update.mutate({ userId: u.user_id, active: !u.active })}>
                    {u.active ? 'Deactivate' : 'Reactivate'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <Blueprint style={{ marginTop: 20, padding: '16px 18px' }}>
          <div className="k" style={{ marginBottom: 10 }}>Add user</div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <input value={nu.name} onChange={(e) => setNu({ ...nu, name: e.target.value })}
              placeholder="Name" style={inputStyle} />
            <input value={nu.email} onChange={(e) => setNu({ ...nu, email: e.target.value })}
              placeholder="email@regulai.demo" style={{ ...inputStyle, width: 190 }} />
            <select value={nu.role} onChange={(e) => setNu({ ...nu, role: e.target.value as Role })}
              style={{ ...inputStyle, padding: '6px 8px' }}>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
            <input type="password" value={nu.password} onChange={(e) => setNu({ ...nu, password: e.target.value })}
              placeholder="password (blank = default)" style={{ ...inputStyle, width: 180 }} />
            <button className="btn btn-primary"
              disabled={saveUser.create.isPending || !nu.name.trim() || !nu.email.trim()}
              onClick={() => saveUser.create.mutate(
                { name: nu.name.trim(), email: nu.email.trim(), role: nu.role, password: nu.password || undefined },
                { onSuccess: () => setNu({ name: '', email: '', role: 'analyst', password: '' }) },
              )}>
              {saveUser.create.isPending ? 'Creating…' : 'Create'}
            </button>
          </div>
          {(saveUser.create.error != null || saveUser.update.error != null) && (
            <div className="k" style={{ marginTop: 8, color: 'var(--color-accent-700)' }}>
              {[(saveUser.create.error as Error | null)?.message,
                (saveUser.update.error as Error | null)?.message].filter(Boolean).join(' · ')}
            </div>
          )}
        </Blueprint>
      </section>

      <aside>
        <h4 style={{ marginBottom: 10 }}>Roles &amp; permissions</h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {ROLE_NOTES.map(([role, note]) => (
            <Blueprint key={role} style={{ padding: '12px 14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span className="mono" style={{ fontSize: 12, fontWeight: 600 }}>{role}</span>
                {user?.role === role && <span className="tag tag-accent">you</span>}
              </div>
              <div style={{ fontSize: 12.5, lineHeight: 1.55, color: 'color-mix(in srgb,var(--color-text) 70%,transparent)' }}>
                {note}
              </div>
            </Blueprint>
          ))}
        </div>
        <div className="k" style={{ marginTop: 14, lineHeight: 1.6 }}>
          Every user change is audited (USER_ACTION) under your name. Passwords
          are pbkdf2-hashed; sessions expire after 12h or on server restart.
        </div>
      </aside>
    </div>
  );
}
