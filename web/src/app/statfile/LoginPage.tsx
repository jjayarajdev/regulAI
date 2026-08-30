// RegAssure sign-in — split-panel login built with Ant Design: brand
// narrative on the left, form on the right, themed to the "Industry" design
// tokens (steel-blue accent, square corners, Barlow type).
import { FileProtectOutlined, LockOutlined, UserOutlined } from '@ant-design/icons';
import { Alert, Button, ConfigProvider, Form, Input } from 'antd';
import { useLogin } from './api';
import { BRAND, BRAND_TAG, REGASSURE_THEME } from './theme';
import './statfile.css';
import './LoginPage.css';

export function LoginPage({ onGuest }: { onGuest: () => void }) {
  const loginMut = useLogin();
  const onFinish = (v: { email: string; password: string }) =>
    loginMut.mutate({ email: v.email.trim(), password: v.password });

  return (
    <ConfigProvider theme={REGASSURE_THEME}>
      <div className="sf lp">
        <aside className="lp-brand">
          <div className="lp-logo">
            <FileProtectOutlined className="lp-mark" />
            <span className="lp-name">{BRAND}</span>
          </div>
          <div className="lp-hero">
            <h1>The system of record for every statistical filing.</h1>
            <p>
              Validation, lineage and sign-off share a single inspection path.
              Every exception is attributed to a person and written to the
              filing record before anything leaves the building.
            </p>
            <div className="lp-words">
              Dashboard · Validation · Records · Filing · Amendments
              <br />
              Rulebook · Mapping · Pipeline · Agents · Knowledge graph
            </div>
          </div>
          <div className="lp-foot">
            {BRAND_TAG} · TX HO · 2026 annual · due 15 Sep 2026
          </div>
        </aside>

        <main className="lp-form">
          <div className="lp-form-col">
            <h2>Sign in</h2>
            <p className="lp-sub">
              Sign in with your directory identity. Actions are attributed and
              recorded; what you can see and sign follows your role.
            </p>

            <Form layout="vertical" requiredMark={false} onFinish={onFinish} disabled={loginMut.isPending}>
              <Form.Item name="email" label="Email" rules={[{ required: true, message: 'Email is required' }]}>
                <Input size="large" prefix={<UserOutlined />} placeholder="you@company.com" autoFocus autoComplete="username" />
              </Form.Item>
              <Form.Item name="password" label="Password" rules={[{ required: true, message: 'Password is required' }]}>
                <Input.Password size="large" prefix={<LockOutlined />} placeholder="password" autoComplete="current-password" />
              </Form.Item>
              <Button type="primary" htmlType="submit" size="large" block loading={loginMut.isPending}>
                Sign in
              </Button>
            </Form>

            {loginMut.error != null && (
              <Alert
                type="error" showIcon style={{ marginTop: 14 }}
                message={(loginMut.error as Error).message}
              />
            )}

            <div className="lp-caps">Session attributed · Actions role-gated</div>
            <div className="lp-alt">
              <span className="k">no account? ask your admin</span>
              <Button type="link" size="small" style={{ padding: 0 }} onClick={onGuest}>
                browse as guest
              </Button>
            </div>
          </div>
        </main>
      </div>
    </ConfigProvider>
  );
}
