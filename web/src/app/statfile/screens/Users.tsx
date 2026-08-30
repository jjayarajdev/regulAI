// Users & access — reimagined as a native Ant Design admin console over
// GOLD_AUDIT.APP_USER: Table with inline role Select, Popconfirm-guarded
// resets/deactivation, a Modal form for new accounts, and the role legend as
// a side Card. The nav item only renders for manage_users roles; this screen
// re-checks and explains itself to anyone who lands here without the grant.
import { useState } from 'react';
import { UserAddOutlined } from '@ant-design/icons';
import {
  Badge, Button, Card, Col, Form, Input, List, Modal, Popconfirm, Result, Row,
  Select, Space, Table, Tag, Typography,
} from 'antd';
import { can, useAdminUsers, useSaveUser, whoCan, type AppUser, type Role } from '../api';

const { Text } = Typography;

const ROLES: Role[] = ['viewer', 'analyst', 'actuary', 'admin', 'cco'];

// What each role means, shown beside the table so admins assign deliberately.
const ROLE_NOTES: Array<[Role, string]> = [
  ['viewer', 'Read-only — dashboards and screens, no actions'],
  ['analyst', 'Prepares the report: run cycle, fix/assign exceptions, analyst sign-off'],
  ['actuary', 'Reconciliation review and actuary sign-off'],
  ['admin', 'Spec onboarding: documents, extractions, rule approvals, suppressions, user management'],
  ['cco', 'Oversight: officer sign-off, seal & transmit, ack, user management'],
];

export function UsersScreen({ user }: { user?: AppUser }) {
  const mayManage = can(user, 'manage_users');
  const adminUsersQ = useAdminUsers(mayManage);
  const saveUser = useSaveUser();
  const [addOpen, setAddOpen] = useState(false);
  const [form] = Form.useForm<{ name: string; email: string; role: Role; password?: string }>();

  if (!mayManage) {
    return (
      <Result
        status="403"
        title="Access control"
        subTitle={`User management requires ${whoCan('manage_users')} — you are signed in as ${user?.name ?? 'Guest'} (${user?.role ?? 'viewer'}).`}
      />
    );
  }

  const columns = [
    {
      title: 'Name', dataIndex: 'name', key: 'name',
      render: (v: string) => <Text strong>{v}</Text>,
    },
    {
      title: 'Email', dataIndex: 'email', key: 'email',
      render: (v: string) => <Text style={{ fontFamily: "ui-monospace,'SFMono-Regular',Menlo,monospace", fontSize: 12 }}>{v}</Text>,
    },
    {
      title: 'Role', dataIndex: 'role', key: 'role', width: 130,
      render: (v: Role, u: AppUser) => (
        <Select
          size="small" value={v} style={{ width: 110 }}
          disabled={saveUser.update.isPending || u.user_id === user?.user_id}
          onChange={(role) => saveUser.update.mutate({ userId: u.user_id, role })}
          options={ROLES.map((r) => ({ label: r, value: r }))}
        />
      ),
    },
    {
      title: 'Title', dataIndex: 'title', key: 'title',
      render: (v: string) => <Text type="secondary" style={{ fontSize: 12 }}>{v}</Text>,
    },
    {
      title: 'Status', dataIndex: 'active', key: 'active', width: 120,
      render: (active: boolean) => (
        <Badge status={active ? 'success' : 'default'} text={active ? 'Active' : 'Deactivated'} />
      ),
    },
    {
      title: '', key: 'actions', align: 'right' as const, width: 210,
      render: (_: unknown, u: AppUser) => (
        <Space size={4}>
          <Popconfirm
            title="Reset password?"
            description="Resets to the default (Regulai#2026)."
            onConfirm={() => saveUser.update.mutate({ userId: u.user_id, password: 'Regulai#2026' })}
          >
            <Button size="small" disabled={saveUser.update.isPending}>Reset pw</Button>
          </Popconfirm>
          <Popconfirm
            title={u.active ? 'Deactivate this user?' : 'Reactivate this user?'}
            description={u.active ? 'They lose access immediately.' : 'They regain access immediately.'}
            onConfirm={() => saveUser.update.mutate({ userId: u.user_id, active: !u.active })}
          >
            <Button size="small" danger={!!u.active}
              disabled={saveUser.update.isPending || u.user_id === user?.user_id}>
              {u.active ? 'Deactivate' : 'Reactivate'}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const mutError = [(saveUser.create.error as Error | null)?.message,
    (saveUser.update.error as Error | null)?.message].filter(Boolean).join(' · ');

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} xl={15}>
        <Card
          title="Users"
          extra={
            <Space>
              <Text type="secondary" style={{ fontSize: 12 }}>
                GOLD_AUDIT.APP_USER · role changes take effect immediately
              </Text>
              <Button type="primary" icon={<UserAddOutlined />} onClick={() => setAddOpen(true)}>
                Add user
              </Button>
            </Space>
          }
          styles={{ body: { padding: 0 } }}
        >
          <Table
            rowKey="user_id"
            dataSource={adminUsersQ.data?.users ?? []}
            columns={columns}
            loading={adminUsersQ.isLoading}
            pagination={false} size="middle"
          />
          {mutError !== '' && (
            <Text type="danger" style={{ display: 'block', padding: '10px 16px', fontSize: 12 }}>{mutError}</Text>
          )}
        </Card>
      </Col>

      <Col xs={24} xl={9}>
        <Card title="Roles & permissions" styles={{ body: { padding: 0 } }}>
          <List
            dataSource={ROLE_NOTES}
            renderItem={([role, note]) => (
              <List.Item style={{ padding: '12px 20px' }}>
                <List.Item.Meta
                  title={
                    <Space size={6}>
                      <Text code>{role}</Text>
                      {user?.role === role && <Tag color="blue">you</Tag>}
                    </Space>
                  }
                  description={<span style={{ fontSize: 12.5 }}>{note}</span>}
                />
              </List.Item>
            )}
          />
        </Card>
        <Text type="secondary" style={{ display: 'block', marginTop: 12, fontSize: 12, lineHeight: 1.6 }}>
          Every user change is audited (USER_ACTION) under your name. Passwords
          are pbkdf2-hashed; sessions expire after 12h or on server restart.
        </Text>
      </Col>

      <Modal
        title="Add user"
        open={addOpen}
        onCancel={() => setAddOpen(false)}
        confirmLoading={saveUser.create.isPending}
        okText="Create"
        onOk={() => form.validateFields().then((v) => {
          saveUser.create.mutate(
            { name: v.name.trim(), email: v.email.trim(), role: v.role, password: v.password || undefined },
            { onSuccess: () => { setAddOpen(false); form.resetFields(); } },
          );
        })}
      >
        <Form form={form} layout="vertical" initialValues={{ role: 'analyst' }} requiredMark={false}>
          <Form.Item name="name" label="Name" rules={[{ required: true, message: 'Name is required' }]}>
            <Input placeholder="Full name" />
          </Form.Item>
          <Form.Item name="email" label="Email" rules={[{ required: true, message: 'Email is required' }]}>
            <Input placeholder="email@regulai.demo" />
          </Form.Item>
          <Form.Item name="role" label="Role">
            <Select options={ROLES.map((r) => ({ label: r, value: r }))} />
          </Form.Item>
          <Form.Item name="password" label="Password" extra="Leave blank for the default (Regulai#2026)">
            <Input.Password placeholder="password" autoComplete="new-password" />
          </Form.Item>
        </Form>
      </Modal>
    </Row>
  );
}
