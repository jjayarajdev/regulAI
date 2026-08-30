// Jurisdictions — the Administration screen, redesigned as a native Ant
// Design page. Two Tabs:
//   Registry          — jurisdiction List with code Avatars and inline edit
//                       (PATCH /api/jurisdictions), the standards registry as
//                       a Table, and the onboard-a-jurisdiction checklist as
//                       vertical Steps, all live-derived.
//   Add a jurisdiction — the onboarding wizard: a vertical Steps rail beside
//                       per-step Cards. Steps 1–3 drive the real
//                       regulation-store endpoints (/api/regulations upload →
//                       extract/start + status poll → approve) with an
//                       Upload.Dragger front door; steps 4–6 have no backend
//                       yet and render the CA fixture story below under
//                       orange demo-data Tags, with deep links into the real
//                       Mapping/Validation screens. Wizard state persists in
//                       localStorage so Save-and-exit ↔ Resume onboarding
//                       round-trip.
import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { InboxOutlined, LoadingOutlined } from '@ant-design/icons';
import {
  Alert, Avatar, Button, Card, Col, Input, List, Progress, Row, Space,
  Statistic, Steps, Table, Tabs, Tag, Tooltip, Typography, Upload,
} from 'antd';
import {
  approveRegulation, can, goLiveOnboarding, startExtraction, uploadRegulation,
  useExtractStatus, useFilings, useJurisdictions, useKgRules, useRegDocuments,
  useRegulations, useSaveJurisdiction, whoCan, type AppUser,
} from '../api';
import { ONBOARD_STEPS, STANDARDS, STATES, type ScreenId } from '../data';

const { Text, Paragraph, Title } = Typography;

const MONO: CSSProperties = { fontFamily: "ui-monospace,'SFMono-Regular',Menlo,monospace" };
const K_LABEL: CSSProperties = { fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em' };

export const STATE_NAMES: Record<string, string> = {
  TX: 'Texas — Department of Insurance',
  FL: 'Florida — Office of Insurance Regulation',
  OK: 'Oklahoma — Insurance Department',
  LA: 'Louisiana — Department of Insurance',
  CA: 'California — Department of Insurance',
  US: 'Federal / NAIC defaults',
};

// Which state a regulator document belongs to, from its issuing body.
const ISSUER_JUR: Record<string, string> = {
  TICO: 'TX', TDI: 'TX', 'Texas Legislature': 'TX',
  'Florida Legislature': 'FL', 'FL OIR': 'FL', 'Florida SBA': 'FL',
  CDI: 'CA', 'CA DOI': 'CA', 'California Legislature': 'CA',
};

// Line-of-business labels per jurisdiction (display flavor only).
const LOB: Record<string, string> = {
  TX: 'Homeowners, dwelling fire', FL: 'Property', CA: 'Homeowners',
  OK: 'Homeowners', LA: 'Homeowners',
};

const shortName = (code: string) => (STATE_NAMES[code] ?? code).split(' — ')[0];
const fmt = (n: number) => n.toLocaleString('en-US');

// Registry status → antd Tag color.
const STATUS_COLOR: Record<string, string | undefined> = {
  Live: 'green', Filed: 'blue', Onboarding: 'orange', Defaults: undefined,
};
// Onboard-panel step status string → antd Steps status.
const STEP_STATUS: Record<string, 'finish' | 'process' | 'wait'> = {
  Done: 'finish', 'In progress': 'process', Active: 'process', Queued: 'wait',
};

// The demo-fallback marker: orange Tag with the reason in the title.
function DemoTag({ reason, children }: { reason: string; children?: ReactNode }) {
  return <Tag color="orange" title={reason}>{children ?? 'demo data'}</Tag>;
}

// Compact key/value row for parse results, manifests and dry-run read-outs.
function KV({ k, v, dim }: { k: string; v: ReactNode; dim?: boolean }) {
  return (
    <div style={{ display: 'flex', gap: 10, padding: '5px 0', fontSize: 12.5, borderBottom: '1px solid rgba(5,5,5,0.06)' }}>
      <Text type="secondary" style={{ flex: 1, fontSize: 12 }}>{k}</Text>
      <span style={{ ...MONO, fontSize: 11.5, textAlign: 'right', opacity: dim ? 0.65 : 1 }}>{v}</span>
    </div>
  );
}

// ── wizard state (persisted) ────────────────────────────────────────────────
const WIZARD_KEY = 'statfile-onboard-wizard';
interface WizardState {
  step: number; // 1..6
  jurisdiction: string; lob: string; std: string;
  slug: string | null;
  fileName: string | null; fileSize: number | null;
  pages: number | null; chars: number | null;
  approved: boolean;
}
const EMPTY_WIZARD: WizardState = {
  step: 1, jurisdiction: '', lob: '', std: '',
  slug: null, fileName: null, fileSize: null, pages: null, chars: null,
  approved: false,
};
const loadWizard = (): WizardState => {
  try {
    const raw = localStorage.getItem(WIZARD_KEY);
    if (raw) return { ...EMPTY_WIZARD, ...(JSON.parse(raw) as Partial<WizardState>) };
  } catch { /* private mode / corrupt state — start fresh */ }
  return EMPTY_WIZARD;
};
const saveWizard = (w: WizardState) => {
  try { localStorage.setItem(WIZARD_KEY, JSON.stringify(w)); } catch { /* fine */ }
};

// The wizard's six steps — title + one-line description.
const WIZ_STEPS: Array<[string, string]> = [
  ['Upload the rulebook', 'Point at the PDF and name the jurisdiction'],
  ['Parse & segment', 'Structure the document into citable clauses'],
  ['Extract candidate rules', 'Derive rules with confidence and citations'],
  ['Map to the silver contract', 'Resolve every field to a conformed column'],
  ['Compile edits & dry run', "Shadow cycle against last year's data"],
  ['Certify', 'Compliance sign-off, then the jurisdiction goes live'],
];

// ── the CA Homeowners onboarding story ──────────────────────────────────────
// Every fixture number the wizard renders lives here. Steps 2–3 prefer live
// values from the upload / extraction payloads and fall back to this; steps
// 4–6 have no backend today and render it in both modes under an orange
// demo-data Tag. Colors are antd semantics (green = settled, orange = needs
// work, red = escalated/blocking).
export const CA_ONBOARDING_STORY = {
  parse: [
    ['Pages', '188'], ['Sections detected', '9'], ['Citable clauses', '412'],
    ['Tables', '31'], ['Appendices', '6'], ['Record layouts found', '2'],
    ['Document hash', 'sha256:4a17…9de1'], ['Parser', 'opus-4 · 11m 04s'],
  ] as Array<[string, string]>,
  outline: [
    { s: '§1', t: 'Scope and reporting obligation', c: '18 clauses' },
    { s: '§2', t: 'Submission media and timing', c: '24 clauses' },
    { s: '§3', t: 'Record layout — residential property', c: '61 clauses' },
    { s: '§4', t: 'Code tables and territory definitions', c: '94 clauses' },
    { s: '§5', t: 'Loss reporting', c: '77 clauses' },
    { s: '§6', t: 'Edits and rejection criteria', c: '88 clauses' },
    { s: 'App. A–F', t: 'Territory, county and form appendices', c: '50 clauses' },
  ],
  extractTotal: 214,
  extractBands: [
    { band: 'Auto-approved', range: 'confidence ≥ 0.90', count: 168, color: '#52c41a' },
    { band: 'Queued for review', range: '0.70 – 0.89', count: 38, color: '#faad14' },
    { band: 'Escalated', range: 'below 0.70', count: 8, color: '#ff4d4f' },
  ],
  extractNote: 'Eight rules could not be resolved from the text alone — six are clause/appendix '
    + 'conflicts of the same shape Texas hit on roof age, and two reference a CDI bulletin the '
    + 'rulebook does not contain. They sit in the review queue with the conflicting passages side by side.',
  mapSummary: [
    { v: '47', k: 'Fields in the CDI layout' },
    { v: '39', k: 'Resolved from existing silver' },
    { v: '6', k: 'Need a new derivation' },
    { v: '2', k: 'Need a new Guidewire extract' },
    { v: '0', k: 'Need pipeline code' },
  ],
  map: [
    { field: 'territory_code', silver: 'risk_location.postal_code', how: 'Reuses the Texas derivation with a CDI territory table', state: 'Resolved', color: 'green' },
    { field: 'amount_of_insurance', silver: 'coverage_detail.cov_a_limit', how: 'Direct, width change only', state: 'Resolved', color: 'green' },
    { field: 'written_premium', silver: 'premium_transaction.amount', how: 'Direct, same sign convention', state: 'Resolved', color: 'green' },
    { field: 'wildfire_risk_score', silver: '—', how: 'No conformed column. Vendor score, needs a new silver derivation', state: 'New derivation', color: 'orange' },
    { field: 'brush_clearance_ind', silver: '—', how: 'Present in Guidewire as a HOPDwelling question, not yet conformed', state: 'New derivation', color: 'orange' },
    { field: 'moratorium_flag', silver: 'policy_exposure.nonrenew_reason', how: 'Derived from an existing column, new expression', state: 'New expression', color: 'orange' },
  ],
  dryCycle: 'CA-HO-2025S',
  dry: [
    { k: 'Records produced', v: '486,220', tag: '—', color: undefined as string | undefined },
    { k: 'Passing all edits', v: '471,904', tag: '97.1%', color: 'green' as string | undefined },
    { k: 'Blocking exceptions', v: '9,118', tag: '1.9%', color: 'red' as string | undefined },
    { k: 'Premium tie to GL', v: '$188,402,110', tag: '0.02%', color: undefined as string | undefined },
    { k: 'Exposure tie', v: '486,004.2', tag: '0.00%', color: undefined as string | undefined },
    { k: 'Runtime', v: '1 h 42m', tag: '—', color: undefined as string | undefined },
  ],
  dryNote: 'The dry run used 2025 California policies already in silver. No bronze ingestion '
    + 'changed and no Guidewire extract was added — the 9,118 exceptions are all wildfire-score '
    + 'nulls from the two unconformed fields.',
  cert: [
    { k: 'Rulebook', v: 'CDI-HO-2026.pdf · sha256:4a17…9de1' },
    { k: 'Rules approved', v: '206 / 214' },
    { k: 'Rules outstanding', v: '8 — escalated to compliance' },
    { k: 'Silver contract', v: 'v4 · unchanged' },
    { k: 'New derivations', v: '6 · reviewed by data engineering' },
    { k: 'Dry-run cycle', v: 'CA-HO-2025S · 97.1% clean' },
    { k: 'Sign-off', v: 'awaiting d.okafor' },
  ],
  goLiveNote: 'California appears in the filing dashboard with its own cycle and due date. It '
    + 'reads the same silver tables Texas reads, through its own approved rule set and its own '
    + 'edit package. No bronze ingestion, no pipeline code and no Guidewire extract was added — '
    + 'the six new derivations became columns every jurisdiction can now use.',
};

type Tab = 'registry' | 'add';

export function ConfigScreen({ go, user }: {
  go: (s: ScreenId) => () => void; user: AppUser;
}) {
  const filingsQ = useFilings();
  const docsQ = useRegDocuments();
  const rulesQ = useKgRules();
  const regsQ = useRegulations();
  const jursQ = useJurisdictions();

  // Server-backed display metadata (editable on the cards) — falls back to
  // the design maps when the KG has no value yet.
  const jurMeta = useMemo(() => {
    const m = new Map<string, { name: string | null; lob: string | null }>();
    for (const j of jursQ.data?.jurisdictions ?? []) {
      m.set(j.code.replace(/^US-/, '') || 'US', { name: j.name, lob: j.lob });
    }
    return m;
  }, [jursQ.data]);

  const [tab, setTab] = useState<Tab>('registry');
  const [wizard, setWizard] = useState<WizardState>(loadWizard);
  const patchWizard = (p: Partial<WizardState>) =>
    setWizard((w) => { const next = { ...w, ...p }; saveWizard(next); return next; });

  const mayOnboard = can(user, 'bulletin');
  const live = (filingsQ.data?.filings.length ?? 0) > 0;

  // ── registry derivation: filings (who files) ∪ KG rules (whose canon
  //    exists — catches states mid-onboarding). Real counts, no fiction. ─────
  const derived = useMemo(() => {
    const filings = filingsQ.data?.filings ?? [];
    const rules = rulesQ.data?.rules ?? [];
    const docs = docsQ.data?.documents ?? [];
    if (!filings.length && !rules.length) return null;

    const byJur = new Map<string, typeof filings>();
    for (const f of filings) {
      const code = (f.jurisdiction_code || '').replace(/^US-/, '') || '—';
      if (!byJur.has(code)) byJur.set(code, []);
      byJur.get(code)!.push(f);
    }
    const ruleStats = new Map<string, { total: number; approved: number; executable: number }>();
    for (const r of rules) {
      const code = (r.jurisdiction_code || '').replace(/^US-/, '') || '—';
      const s = ruleStats.get(code) ?? { total: 0, approved: 0, executable: 0 };
      s.total += 1;
      if (r.status === 'approved') s.approved += 1;
      if (r.executable) s.executable += 1;
      ruleStats.set(code, s);
    }
    const docsFor = (code: string) => docs.filter((d) => ISSUER_JUR[d.issuing_body] === code);
    // Uploaded rulebooks live in the regulation store (not the warehouse
    // regdocs table) and carry the jurisdiction from the wizard.
    const uploadsFor = (code: string) =>
      (regsQ.data?.documents ?? []).filter((d) => d.jurisdiction_code === `US-${code}`);

    const codes = [...new Set([...byJur.keys(), ...ruleStats.keys()])]
      .sort((a, b) => Number(byJur.has(b)) - Number(byJur.has(a)) || a.localeCompare(b));

    const cards = codes.map((code) => {
      const fs = byJur.get(code) ?? [];
      const rs = ruleStats.get(code);
      const isLive = fs.some((f) => f.is_active);
      const plans = [...new Set(fs.map((f) => f.plan_code))];
      const meta = jurMeta.get(code);
      const lob = meta?.lob || LOB[code];
      const sub = [
        lob,
        plans.length ? `${plans.join(', ')} plan${plans.length > 1 ? 's' : ''}` : 'no filing configured',
        rs
          ? `${fmt(rs.total)} rules` + (rs.executable ? ` · ${rs.executable} executable` : '')
          : 'no canon yet',
      ].filter(Boolean).join(' · ');
      return {
        code,
        name: meta?.name || STATE_NAMES[code] || code,
        lob: lob ?? '',
        sub,
        hasFilings: fs.length > 0,
        status: isLive ? 'Live' : fs.length ? 'Filed'
          : code === 'US' ? 'Defaults' : 'Onboarding',
      };
    });

    // Onboard panel target: the furthest-along jurisdiction that isn't filing
    // yet; when every known jurisdiction is live (today's real state), the
    // most recently onboarded live one — its story, all steps done.
    const liveCodes = new Set(codes.filter((c) => (byJur.get(c) ?? []).some((f) => f.is_active)));
    const onboarding = codes
      .filter((c) => !liveCodes.has(c) && c !== 'US' && ruleStats.has(c))
      .sort((a, b) => (ruleStats.get(b)?.total ?? 0) - (ruleStats.get(a)?.total ?? 0));
    let target: string | null = onboarding[0] ?? null;
    let targetLive = false;
    if (!target && liveCodes.size) {
      // Most recent regulator document per live jurisdiction = onboarded last.
      target = [...liveCodes].sort((a, b) => {
        const at = docsFor(a).map((d) => d.loaded_at).sort().at(-1) ?? '';
        const bt = docsFor(b).map((d) => d.loaded_at).sort().at(-1) ?? '';
        return bt.localeCompare(at);
      })[0];
      targetLive = true;
    }
    if (!target) return { cards, onboard: null, cloneFrom: null };

    const jr = rules.filter((r) => (r.jurisdiction_code || '').replace(/^US-/, '') === target);
    const jd = docsFor(target);
    const ju = uploadsFor(target);
    const approved = jr.filter((r) => r.status === 'approved').length;
    const executable = jr.filter((r) => r.executable).length;
    const jf = byJur.get(target) ?? [];

    type StepState = 'done' | 'now' | 'todo';
    const mk = (n: number, title: string, body: string, state: StepState) => ({
      n, title, body,
      status: state === 'done' ? 'Done' : state === 'now' ? 'In progress' : 'Queued',
    });
    // Every step of a live jurisdiction is done by definition — it files.
    const st = (real: StepState): StepState => (targetLive ? 'done' : real);
    const steps = [
      mk(1, 'Ingest rulebook',
        jd.length || ju.length
          ? `${jd.length + ju.length} regulator document${jd.length + ju.length > 1 ? 's' : ''} loaded — ${[...jd.map((d) => d.title), ...ju.map((d) => d.label)].slice(0, 2).join('; ')}${jd.length + ju.length > 2 ? '; …' : ''}.`
          : 'No regulator documents loaded yet.',
        st(jd.length || ju.length ? 'done' : 'now')),
      mk(2, 'Extract candidate rules',
        `${fmt(jr.length)} rules in the knowledge graph, extracted with citations.`,
        st(jr.length ? 'done' : 'todo')),
      mk(3, 'Map to the silver contract',
        targetLive
          ? `${fmt(jr.length)} rules resolved against the conformed silver columns.`
          : `${approved} of ${fmt(jr.length)} rules approved against the silver contract — review the drafts on the Rulebook screen.`,
        st(approved === jr.length && jr.length > 0 ? 'done' : 'now')),
      mk(4, 'Compile the edit package',
        executable
          ? `${executable} executable validation edits compiled.`
          : 'Validation edits compile once the mapping review lands.',
        st(executable ? 'done' : 'todo')),
      mk(5, 'Dry-run and certify',
        jf.length
          ? `${jf.length} filing${jf.length > 1 ? 's' : ''} configured — certified and filing.`
          : 'Shadow cycle against last year’s data, then compliance sign-off before the first live filing.',
        st(jf.length ? 'done' : 'todo')),
    ];
    const firstOpen = steps.findIndex((s) => s.status !== 'Done'); // -1 → all done

    // The clone template: the live jurisdiction with the deepest canon.
    const cloneFrom = [...liveCodes]
      .sort((a, b) => (ruleStats.get(b)?.total ?? 0) - (ruleStats.get(a)?.total ?? 0))[0] ?? null;

    return {
      cards,
      cloneFrom,
      onboard: {
        code: target,
        title: `${shortName(target)} · ${LOB[target] ?? 'Property'}`,
        allDone: targetLive || firstOpen === -1,
        steps,
        // Panel step n maps to wizard step n+1 (wizard splits ingest into
        // upload + parse); all-done lands on Certify.
        resumeStep: firstOpen === -1 ? 6 : Math.min(firstOpen + 2, 6),
      },
    };
  }, [filingsQ.data, rulesQ.data, docsQ.data, regsQ.data, jurMeta]);

  // Demo fallback (warehouse cold): the design fixtures, reshaped.
  const cards = derived?.cards ?? STATES.map((s) => ({
    code: s.code, name: s.name, lob: '', sub: s.detail, hasFilings: false,
    status: s.status,
  }));
  const onboard = derived?.onboard ?? null;

  // ── standards registry: loaded regulator documents; RULES = canon rules
  //    that cite the document when the KG records it, else document size. ────
  const standards = useMemo(() => {
    const docs = docsQ.data?.documents ?? [];
    const rules = rulesQ.data?.rules ?? [];
    if (!docs.length) return STANDARDS;
    return [...docs]
      .map((d) => {
        // Bulletins carry their id in the title; a bare "1" says nothing —
        // the effective date is the meaningful "version" there.
        const redundant = !d.edition || d.title.includes(d.edition) || /^\d$/.test(d.edition);
        const cited = rules.filter((r) => r.source_doc === d.title).length;
        return {
          name: d.title,
          ver: redundant ? `eff. ${d.effective_date}` : d.edition,
          rules: cited ? fmt(cited)
            : `${(d.word_count / 1000).toFixed(1)}K words` + (d.page_count > 2 ? ` · ${d.page_count} pp` : ''),
          owner: d.issuing_body,
          jur: ISSUER_JUR[d.issuing_body] ?? '—',
        };
      })
      .sort((a, b) => a.jur.localeCompare(b.jur) || a.name.localeCompare(b.name));
  }, [docsQ.data, rulesQ.data]);
  const standardsLive = (docsQ.data?.documents.length ?? 0) > 0;

  const resumeOnboarding = () => {
    // A saved wizard session wins; otherwise seed one from the panel's
    // real pipeline position so the wizard opens on the right step.
    if (!wizard.slug && wizard.step === 1 && onboard) {
      patchWizard({
        step: onboard.resumeStep,
        jurisdiction: shortName(onboard.code),
        lob: LOB[onboard.code] ?? '',
        approved: onboard.resumeStep > 3,
      });
    }
    setTab('add');
  };

  const standardsColumns = [
    { title: 'Standard', dataIndex: 'name', key: 'name', render: (v: string) => <span style={{ fontSize: 13 }}>{v}</span> },
    { title: 'Version', dataIndex: 'ver', key: 'ver', width: 140, render: (v: string) => <span style={{ ...MONO, fontSize: 12 }}>{v}</span> },
    { title: 'Rules', dataIndex: 'rules', key: 'rules', width: 160, render: (v: string) => <span style={{ ...MONO, fontSize: 12 }}>{v}</span> },
    { title: 'Owner', dataIndex: 'owner', key: 'owner', width: 150, render: (v: string) => <Text type="secondary" style={{ fontSize: 12 }}>{v}</Text> },
  ];

  const onboardStepItems = (onboard?.steps ?? ONBOARD_STEPS.map((s) => ({
    n: Number(s.n), title: s.title, body: s.body, status: s.status,
  }))).map((s) => ({
    title: <span style={{ fontSize: 14 }}>{s.title}</span>,
    status: STEP_STATUS[s.status] ?? 'wait',
    description: (
      <Text type="secondary" style={{ fontSize: 12, lineHeight: 1.55, display: 'block', paddingBottom: 6 }}>
        {s.body}
      </Text>
    ),
  }));

  const registry = (
    <Row gutter={[16, 16]} align="top">
      <Col xs={24} xl={12}>
        <Card
          title="Jurisdictions"
          extra={!derived
            ? <DemoTag reason="warehouse cold — showing design fixtures" />
            : live && <Text type="secondary" style={{ fontSize: 13 }}>live · filings + canon</Text>}
          styles={{ body: { padding: 0 } }}
        >
          <List
            dataSource={cards}
            rowKey={(s) => s.code}
            renderItem={(s) => (
              <JurItem card={s} user={user} editable={!!derived && mayOnboard} />
            )}
          />
        </Card>

        <Card
          title="Standards registry"
          extra={!standardsLive
            ? <DemoTag reason="no regulator documents loaded — showing design fixtures" />
            : live && <Text type="secondary" style={{ fontSize: 13 }}>live · loaded regulator documents</Text>}
          style={{ marginTop: 16 }}
          styles={{ body: { padding: 0 } }}
        >
          <Table
            rowKey="name"
            dataSource={standards}
            columns={standardsColumns}
            pagination={false} size="middle"
          />
        </Card>
      </Col>

      <Col xs={24} xl={12}>
        <Card
          title="Onboard a jurisdiction"
          extra={onboard
            ? <Tag color="green">live · derived from the canon</Tag>
            : <DemoTag reason="no canon yet — the CA design story">vision demo</DemoTag>}
        >
          <Title level={4} style={{ margin: '0 0 4px' }}>
            {onboard ? onboard.title : 'California · Homeowners'}
          </Title>
          <Paragraph type="secondary" style={{ fontSize: 12.5, marginBottom: 18 }}>
            Configuration only — no pipeline code is written. The silver layer is already
            jurisdiction-agnostic; a new state is a rulebook, a mapping and an edit package.
          </Paragraph>

          <Steps direction="vertical" size="small" items={onboardStepItems} />

          <Paragraph type="secondary" style={{ fontSize: 12.5, lineHeight: 1.65, margin: '14px 0 18px' }}>
            A jurisdiction is onboarded by uploading its rulebook. The agents parse it, derive
            rules, map them onto the existing silver contract and dry-run a shadow cycle —
            pipeline code is never written.
          </Paragraph>

          <Space>
            <Tooltip title="coming soon">
              <Button disabled>
                Clone {derived?.cloneFrom ? shortName(derived.cloneFrom) : 'Texas'} config
              </Button>
            </Tooltip>
            {onboard?.allDone ? (
              <Button type="link" onClick={go('mapping')} style={{ paddingInline: 4 }}>
                View mapping review →
              </Button>
            ) : (
              <Button type="primary" onClick={resumeOnboarding}>Resume onboarding →</Button>
            )}
          </Space>
        </Card>
      </Col>
    </Row>
  );

  return (
    <Tabs
      activeKey={tab}
      onChange={(k) => setTab(k as Tab)}
      destroyOnHidden

      items={[
        { key: 'registry', label: 'Registry', children: registry },
        {
          key: 'add',
          label: 'Add a jurisdiction',
          children: (
            <Wizard
              wizard={wizard} patch={patchWizard} go={go} user={user}
              mayOnboard={mayOnboard} onExit={() => setTab('registry')}
            />
          ),
        },
      ]}
    />
  );
}

// ── an editable jurisdiction row ────────────────────────────────────────────
// Display name + line of business persist on the KG Jurisdiction node
// (display_name / lob via PATCH /api/jurisdictions/{code}); pause/resume
// flips the jurisdiction's FilingObligations, which drives Live ↔ Filed.
interface JurCardData {
  code: string; name: string; lob: string; sub: string;
  hasFilings: boolean; status: string;
}

function JurItem({ card: s, user, editable }: {
  card: JurCardData; user: AppUser; editable: boolean;
}) {
  const saveMut = useSaveJurisdiction();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(s.name);
  const [lob, setLob] = useState(s.lob);
  const open = () => { setName(s.name); setLob(s.lob); setEditing(true); saveMut.reset(); };
  const patchCode = s.code === 'US' ? 'US' : `US-${s.code}`;

  const doSave = () => {
    if (!name.trim()) return;
    saveMut.mutate(
      { code: patchCode, display_name: name.trim(), lob: lob.trim(), actor: user.name },
      { onSuccess: () => setEditing(false) },
    );
  };
  const doToggleFilings = () =>
    saveMut.mutate(
      { code: patchCode, filing_active: s.status !== 'Live', actor: user.name },
      { onSuccess: () => setEditing(false) },
    );

  const clickable = editable && !editing;
  return (
    <List.Item
      onClick={clickable ? open : undefined}
      title={clickable ? 'click to edit' : undefined}
      style={{ padding: '14px 20px', cursor: clickable ? 'pointer' : undefined }}
    >
      <div style={{ display: 'flex', gap: 14, width: '100%', alignItems: editing ? 'flex-start' : 'center' }}>
        <Avatar
          shape="square" size={46}
          style={{ background: 'rgba(22,119,255,0.1)', color: '#1677ff', fontWeight: 600, fontSize: 16, flexShrink: 0 }}
        >
          {s.code}
        </Avatar>
        {editing ? (
          <div style={{ flex: 1, minWidth: 0 }} onClick={(e) => e.stopPropagation()}>
            <Row gutter={12}>
              <Col span={14}>
                <Text type="secondary" style={{ fontSize: 12 }}>Display name</Text>
                <Input
                  size="small" value={name} style={{ marginTop: 3 }}
                  placeholder="Oklahoma — Insurance Department"
                  onChange={(e) => setName(e.target.value)}
                />
              </Col>
              <Col span={10}>
                <Text type="secondary" style={{ fontSize: 12 }}>Line of business</Text>
                <Input
                  size="small" value={lob} style={{ marginTop: 3 }}
                  placeholder="Homeowners"
                  onChange={(e) => setLob(e.target.value)}
                />
              </Col>
            </Row>
            <Space wrap style={{ marginTop: 10 }}>
              <Button size="small" type="primary" loading={saveMut.isPending}
                disabled={!name.trim()} onClick={doSave}>
                Save
              </Button>
              <Button size="small" onClick={() => setEditing(false)}>Cancel</Button>
              {s.hasFilings && (
                <Tooltip title={s.status === 'Live'
                  ? 'sets the filing obligations inactive — card reads Filed'
                  : 'reactivates the filing obligations — card reads Live'}>
                  <Button size="small" disabled={saveMut.isPending} onClick={doToggleFilings}>
                    {s.status === 'Live' ? 'Pause filings' : 'Resume filings'}
                  </Button>
                </Tooltip>
              )}
              {saveMut.error != null && (
                <Text type="danger" style={{ fontSize: 11.5 }}>{(saveMut.error as Error).message}</Text>
              )}
            </Space>
          </div>
        ) : (
          <>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 14.5, fontWeight: 500 }}>{s.name}</div>
              <Text type="secondary" style={{ fontSize: 11.5 }}>{s.sub}</Text>
            </div>
            {editable && (
              <Button size="small" type="link" style={{ flex: 'none', paddingInline: 2 }}
                onClick={(e) => { e.stopPropagation(); open(); }}>
                Edit
              </Button>
            )}
            <Tag color={STATUS_COLOR[s.status]} style={{ marginInlineEnd: 0 }}>{s.status}</Tag>
          </>
        )}
      </div>
    </List.Item>
  );
}

// ── the Add-a-jurisdiction wizard ───────────────────────────────────────────
function Wizard({ wizard, patch, go, mayOnboard, onExit }: {
  wizard: WizardState; patch: (p: Partial<WizardState>) => void;
  go: (s: ScreenId) => () => void; user: AppUser;
  mayOnboard: boolean; onExit: () => void;
}) {
  const qc = useQueryClient();
  const fileRef = useRef<File | null>(null);
  const [busy, setBusy] = useState<'upload' | 'extract' | 'approve' | 'golive' | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Extraction status poll — live while steps 2–3 own the screen (step 2 only
  // reads it for the parser label; a finished/cached job also survives a
  // Back-jump from later steps).
  const statusQ = useExtractStatus(wizard.slug, wizard.step === 2 || wizard.step === 3);
  const status = statusQ.data;
  const extractRunning = wizard.step === 3 && status?.status === 'running';

  // A finished background extraction advances nothing by itself — approval is
  // the explicit human act — but the rail should say it's running/done.
  useEffect(() => { if (status?.status === 'error') setError(status.error ?? 'extraction failed'); }, [status]);

  const gate = mayOnboard ? undefined : `requires ${whoCan('bulletin')}`;

  const chooseFile = (f: File | null) => {
    if (!f) return;
    setError(null);
    fileRef.current = f;
    patch({ fileName: f.name, fileSize: f.size, pages: null, chars: null, slug: null, approved: false });
  };

  const doUpload = async () => {
    const f = fileRef.current;
    if (!f) { setError('Choose the rulebook PDF first (files don’t survive a reload — re-choose it).'); return; }
    setBusy('upload'); setError(null);
    try {
      const label = wizard.std || [wizard.jurisdiction, wizard.lob].filter(Boolean).join(' ') || undefined;
      const r = await uploadRegulation(
        f, label,
        wizard.jurisdiction ? `${wizard.jurisdiction} — uploaded rulebook` : undefined,
        wizard.jurisdiction || undefined,
      );
      patch({ slug: r.slug, pages: r.pages, chars: r.chars, step: 2 });
    } catch (e) {
      setError((e as Error).message);
    } finally { setBusy(null); }
  };

  const doExtract = async () => {
    if (!wizard.slug) return;
    // A cached extraction already exists → don't spend tokens or replace the
    // proposal set; step 3 renders it directly (Re-extract is the explicit,
    // armed action there).
    if (statusQ.data?.status === 'done') { patch({ step: 3 }); return; }
    setBusy('extract'); setError(null);
    try {
      await startExtraction(wizard.slug);
      patch({ step: 3 });
      statusQ.refetch();
    } catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  };

  // Two-step re-extract: first click arms, second click forces. Replacing a
  // reviewed proposal set must never be one accidental click.
  const [reArm, setReArm] = useState(false);
  const doReExtract = async () => {
    if (!wizard.slug) return;
    if (!reArm) { setReArm(true); return; }
    setReArm(false); setBusy('extract'); setError(null);
    try {
      await startExtraction(wizard.slug, true);
      patch({ approved: false });
      statusQ.refetch();
    } catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  };

  const doApprove = async () => {
    if (!wizard.slug) return;
    // Re-visiting an already-approved step 3 — nothing to re-approve.
    if (wizard.approved) { patch({ step: 4 }); return; }
    setBusy('approve'); setError(null);
    try {
      await approveRegulation(wizard.slug);
      patch({ approved: true, step: 4 });
    } catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  };

  // Certify → Go live. Mock mode materializes the filing obligation (the
  // registry card flips to Live, the dashboard gains a CA cycle) and closes
  // the wizard; live mode disables the button (see the render below).
  const doGoLive = async () => {
    setBusy('golive'); setError(null);
    try {
      await goLiveOnboarding(wizard.jurisdiction || 'California');
      qc.invalidateQueries({ queryKey: ['sf'] });
      patch({ ...EMPTY_WIZARD });
      onExit();
    } catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  };

  // 0 → 100 in 20% ticks across the six steps, matching the design mock.
  const progress = Math.round(((wizard.step - 1) / (WIZ_STEPS.length - 1)) * 100);
  const back = () => patch({ step: Math.max(1, wizard.step - 1) });

  // Processing lock: while a request is in flight, or Sentinel is rewriting
  // the extraction, block every other wizard action so nothing conflicting
  // can be triggered. Save-and-exit stays available during the (minutes-long)
  // extraction — the job runs server-side and the wizard resumes onto it —
  // but is blocked during short in-flight requests.
  const processing = busy !== null;
  const navLocked = processing || extractRunning;

  const mb = wizard.fileSize != null ? (wizard.fileSize / 1048576).toFixed(1) : null;

  // ── step 2: parse rows — live where the upload/extraction payloads carry
  //    the value, the CA story otherwise. No invented hashes: the upload
  //    response has no sha, so the live document row is slug + size. ────────
  const story = CA_ONBOARDING_STORY;
  const parserLive = status?.status === 'done' && status.result?.model && status.result.model !== 'cached'
    ? status.result.model : null;
  const parseRows: Array<{ k: string; v: string; live: boolean }> = wizard.slug
    ? [
      { k: 'Pages', v: wizard.pages != null ? String(wizard.pages) : '—', live: wizard.pages != null },
      { k: 'Characters extracted', v: wizard.chars != null ? fmt(wizard.chars) : '—', live: wizard.chars != null },
      ...story.parse.slice(1, 6).map(([k, v]) => ({ k, v, live: false })),
      { k: 'Registered as', v: `${wizard.slug}${mb ? ` · ${mb} MB` : ''}`, live: true },
      { k: 'Parser', v: parserLive ?? story.parse[7][1], live: !!parserLive },
    ]
    : story.parse.map(([k, v]) => ({ k, v, live: false }));

  // ── step 3: confidence bands — real when the extraction payload exposes
  //    proposed_nodes[].confidence (api/main.py does), CA story otherwise. ──
  const proposedNodes = status?.status === 'done' ? status.result?.extraction?.proposed_nodes : undefined;
  const bandsLive = !!proposedNodes?.length && proposedNodes.some((n) => typeof n.confidence === 'number');
  const bandTotal = bandsLive ? proposedNodes!.length : story.extractTotal;
  const bands = bandsLive
    ? [
      { band: 'Auto-approved', range: 'confidence ≥ 0.90', count: proposedNodes!.filter((n) => (n.confidence ?? 0) >= 0.9).length, color: '#52c41a' },
      { band: 'Queued for review', range: '0.70 – 0.89', count: proposedNodes!.filter((n) => (n.confidence ?? 0) >= 0.7 && (n.confidence ?? 0) < 0.9).length, color: '#faad14' },
      { band: 'Escalated', range: 'below 0.70', count: proposedNodes!.filter((n) => (n.confidence ?? 0) < 0.7).length, color: '#ff4d4f' },
    ]
    : story.extractBands;

  const stepHeader = (n: number) => (
    <Space align="baseline" size={12} style={{ marginBottom: 14 }}>
      <Title level={4} style={{ margin: 0 }}>{WIZ_STEPS[n - 1][0]}</Title>
      <Text type="secondary" style={{ fontSize: 13 }}>{WIZ_STEPS[n - 1][1]}</Text>
    </Space>
  );
  const deepLink = (label: string, onLink: () => void) => (
    <Button type="link" size="small" style={{ padding: 0, fontSize: 12.5 }} onClick={onLink}>
      {label}
    </Button>
  );
  // The design footer: Back + Save-and-exit on the left, primary on the right.
  const footer = (primary: ReactNode) => (
    <div style={{ display: 'flex', gap: 8, marginTop: 22, borderTop: '1px solid rgba(5,5,5,0.06)', paddingTop: 16 }}>
      {wizard.step > 1 && (
        <Tooltip title={navLocked ? 'wait for the current step to finish' : undefined}>
          <Button onClick={back} disabled={navLocked}>← Back</Button>
        </Tooltip>
      )}
      <Tooltip title={extractRunning ? 'safe — the extraction keeps running server-side' : undefined}>
        <Button onClick={onExit} disabled={processing}>Save and exit</Button>
      </Tooltip>
      <span style={{ marginLeft: 'auto' }}>{primary}</span>
    </div>
  );

  return (
    <Row gutter={[16, 16]} align="top">
      {/* left rail — progress */}
      <Col xs={24} xl={7}>
        <Card
          title="Progress"
          extra={<span style={{ ...MONO, fontSize: 12 }}>{progress}%</span>}
        >
          <Progress percent={progress} size="small" showInfo={false} style={{ marginBottom: 16 }} />
          <Steps
            direction="vertical" size="small"
            current={wizard.step - 1}
            onChange={(i) => {
              const n = i + 1;
              if (n < wizard.step && !navLocked) patch({ step: n });
            }}
            items={WIZ_STEPS.map(([title, desc], i) => {
              const n = i + 1;
              return {
                title,
                description: (
                  <Text type="secondary" style={{ fontSize: 11.5, lineHeight: 1.5, display: 'block', paddingBottom: 6 }}>
                    {desc}
                  </Text>
                ),
                status: (n < wizard.step ? 'finish' : n === wizard.step ? 'process' : 'wait') as 'finish' | 'process' | 'wait',
                icon: n === wizard.step && extractRunning ? <LoadingOutlined /> : undefined,
                disabled: !(n < wizard.step) || navLocked,
              };
            })}
          />
        </Card>
      </Col>

      {/* main — step content */}
      <Col xs={24} xl={17}>
        {wizard.step === 1 && (
          <>
            {stepHeader(1)}
            <Upload.Dragger
              accept=".pdf,application/pdf"
              maxCount={1}
              showUploadList={false}
              beforeUpload={(f) => { chooseFile(f); return false; }}
              disabled={busy === 'upload'}
            >
              <p className="ant-upload-drag-icon"><InboxOutlined /></p>
              <p className="ant-upload-text">Drop the jurisdiction&rsquo;s statistical plan PDF</p>
              <p className="ant-upload-hint">
                Or a bulletin, a circular, or a filing manual. Nothing else about the platform
                changes — the rulebook is the input.
              </p>
            </Upload.Dragger>
            {wizard.fileName && (
              <Text type="success" style={{ ...MONO, display: 'block', marginTop: 12, fontSize: 12 }}>
                ✓ {wizard.fileName}{mb ? ` · ${mb} MB` : ''}{wizard.pages ? ` · ${wizard.pages} pp` : ''}
                {!fileRef.current && !wizard.slug && '  (re-choose after reload)'}
              </Text>
            )}

            <Row gutter={[16, 16]} style={{ margin: '20px 0 0' }}>
              {([
                ['Jurisdiction', 'California', wizard.jurisdiction, (v: string) => patch({ jurisdiction: v })],
                ['Line of business', 'Homeowners', wizard.lob, (v: string) => patch({ lob: v })],
                ['Standard code', 'CDI HO 2026', wizard.std, (v: string) => patch({ std: v })],
              ] as Array<[string, string, string, (v: string) => void]>).map(([label, ph, val, set]) => (
                <Col key={label} xs={24} md={8}>
                  <Text type="secondary" style={{ fontSize: 12 }}>{label}</Text>
                  <Input
                    value={val} placeholder={ph} style={{ marginTop: 4 }}
                    onChange={(e) => set(e.target.value)}
                  />
                </Col>
              ))}
            </Row>

            {error && <Alert type="error" showIcon message={error} style={{ marginTop: 14 }} />}
            {footer(
              <Tooltip title={gate ?? (!wizard.fileName ? 'choose the rulebook PDF'
                : !wizard.jurisdiction.trim() ? 'name the jurisdiction' : undefined)}>
                <Button
                  type="primary" loading={busy === 'upload'}
                  disabled={!mayOnboard || busy === 'upload' || !wizard.fileName || !wizard.jurisdiction.trim()}
                  onClick={doUpload}
                >
                  Parse document →
                </Button>
              </Tooltip>,
            )}
          </>
        )}

        {wizard.step === 2 && (
          <>
            {stepHeader(2)}
            <Row gutter={[16, 16]}>
              <Col xs={24} lg={11}>
                <Card
                  size="small"
                  title={<Text type="secondary" style={K_LABEL}>Parse result</Text>}
                  extra={parseRows.some((r) => !r.live) && (
                    <DemoTag reason="rows without a live payload value come from the CA design story">
                      {parseRows.some((r) => r.live) ? 'counts projected' : 'demo projection'}
                    </DemoTag>
                  )}
                >
                  {parseRows.map((r) => <KV key={r.k} k={r.k} v={r.v} dim={!r.live} />)}
                </Card>
              </Col>
              <Col xs={24} lg={13}>
                <Card
                  size="small"
                  title={<Text type="secondary" style={K_LABEL}>Document outline — reportable sections</Text>}
                  extra={<DemoTag reason="no live outline endpoint yet — the CA design story">demo projection</DemoTag>}
                >
                  {story.outline.map((o) => (
                    <div key={o.s} style={{ display: 'flex', gap: 12, padding: '7px 0', alignItems: 'baseline', borderBottom: '1px solid rgba(5,5,5,0.06)' }}>
                      <span style={{ ...MONO, fontSize: 11.5, width: 64, flex: 'none', color: '#1677ff' }}>{o.s}</span>
                      <span style={{ flex: 1, fontSize: 13 }}>{o.t}</span>
                      <Text type="secondary" style={{ ...MONO, fontSize: 11 }}>{o.c}</Text>
                    </div>
                  ))}
                </Card>
              </Col>
            </Row>
            <Paragraph type="secondary" style={{ fontSize: 12.5, lineHeight: 1.65, margin: '16px 0 0', maxWidth: '78ch' }}>
              The document is registered in the regulation store as{' '}
              <Text code style={{ fontSize: 11.5 }}>{wizard.slug ?? 'uploaded-cdi-ho-2026'}</Text>{' '}
              and its text is staged as the Sentinel input. Extraction is an LLM pass that derives
              candidate rules with confidence scores and citations — it takes a couple of minutes
              and runs in the background.
            </Paragraph>
            {error && <Alert type="error" showIcon message={error} style={{ marginTop: 12 }} />}
            {footer(
              <Tooltip title={gate}>
                <Button
                  type="primary" loading={busy === 'extract'}
                  disabled={!mayOnboard || busy === 'extract'}
                  onClick={doExtract}
                >
                  Extract rules →
                </Button>
              </Tooltip>,
            )}
          </>
        )}

        {wizard.step === 3 && (
          <>
            {stepHeader(3)}
            {status?.status === 'error' ? (
              <Alert type="error" showIcon message={status.error ?? 'Extraction failed.'} />
            ) : extractRunning || (!wizard.approved && status?.status !== 'done') ? (
              <Alert
                type="info"
                icon={<LoadingOutlined />} showIcon
                message="Sentinel is reading the document…"
                description={(
                  <>
                    polling <Text code style={{ fontSize: 11.5 }}>/extract/status</Text> — this is an LLM pass
                    and can take a couple of minutes. Safe to Save and exit; the job keeps running.
                  </>
                )}
              />
            ) : (
              <>
                <Card
                  size="small"
                  title={<Text type="secondary" style={K_LABEL}>{fmt(bandTotal)} candidate rules by confidence</Text>}
                  extra={!bandsLive && <DemoTag reason="extraction payload carries no confidence values — the CA design story">projected</DemoTag>}
                  style={{ marginBottom: 16 }}
                >
                  {bands.map((b) => (
                    <Row key={b.band} gutter={12} align="middle" style={{ padding: '5px 0' }}>
                      <Col flex="150px" style={{ fontSize: 13 }}>{b.band}</Col>
                      <Col flex="130px">
                        <Text type="secondary" style={{ ...MONO, fontSize: 11.5 }}>{b.range}</Text>
                      </Col>
                      <Col flex="auto">
                        <Progress
                          percent={bandTotal ? Math.round((b.count / bandTotal) * 100) : 0}
                          showInfo={false} size="small" strokeColor={b.color}
                        />
                      </Col>
                      <Col flex="70px" style={{ ...MONO, fontSize: 13, textAlign: 'right' }}>{fmt(b.count)}</Col>
                    </Row>
                  ))}
                </Card>
                <Paragraph style={{ fontSize: 13, lineHeight: 1.7, maxWidth: '78ch', marginBottom: 10 }}>
                  {bandsLive && status?.result?.summary ? status.result.summary : story.extractNote}
                </Paragraph>
                <Text type="secondary" style={{ fontSize: 12.5, display: 'block' }}>
                  {wizard.approved
                    ? 'Approved — the extraction is materialized in the knowledge graph as draft rules.'
                    : 'Mapping the fields approves the extraction into the knowledge graph — the rules land as drafts and go through the human approval gate on the Rulebook screen.'}
                </Text>
                <Space size={14} wrap style={{ marginTop: 10 }}>
                  {deepLink('Review the queued proposals first →', go('extract'))}
                  <Tooltip title="extraction is non-deterministic — a re-run produces a different proposal set and orphans recorded verdicts">
                    <Button
                      danger={reArm}
                      disabled={!mayOnboard || busy === 'extract'}
                      onClick={doReExtract}
                      onBlur={() => setReArm(false)}
                    >
                      {reArm ? 'Replaces all proposals + verdicts — click again to confirm' : 'Re-extract…'}
                    </Button>
                  </Tooltip>
                </Space>
              </>
            )}
            {error && status?.status !== 'error' && (
              <Alert type="error" showIcon message={error} style={{ marginTop: 12 }} />
            )}
            {footer(
              status?.status === 'error' ? (
                <Tooltip title={gate}>
                  <Button type="primary" loading={busy === 'extract'}
                    disabled={!mayOnboard || busy === 'extract'} onClick={doExtract}>
                    Retry extraction
                  </Button>
                </Tooltip>
              ) : (
                <Tooltip title={gate ?? (!wizard.approved && status?.status !== 'done'
                  ? 'waiting for the extraction to finish'
                  : !wizard.approved ? 'approves the extraction into the canon' : undefined)}>
                  <Button
                    type="primary" loading={busy === 'approve'}
                    disabled={!mayOnboard || busy === 'approve' || (!wizard.approved && status?.status !== 'done')}
                    onClick={doApprove}
                  >
                    Map fields →
                  </Button>
                </Tooltip>
              ),
            )}
          </>
        )}

        {/* Step 4 — Map to the silver contract. No live backend yet: the CA
            story renders under a demo-data Tag; the real work happens on the
            Mapping review screen (deep link below). */}
        {wizard.step === 4 && (
          <>
            {stepHeader(4)}
            <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
              {story.mapSummary.map((m) => (
                <Col key={m.k} flex="1 1 120px">
                  <Card size="small">
                    <Statistic value={m.v} title={<span style={{ fontSize: 11, lineHeight: 1.4 }}>{m.k}</span>} valueStyle={{ fontSize: 28 }} />
                  </Card>
                </Col>
              ))}
            </Row>
            <Card
              size="small"
              title={<Text type="secondary" style={K_LABEL}>Field mapping</Text>}
              extra={<DemoTag reason="no live mapping backend yet — the CA design story">demo projection</DemoTag>}
              styles={{ body: { padding: 0 } }}
            >
              <Table
                rowKey="field"
                dataSource={story.map}
                pagination={false} size="middle"
                columns={[
                  { title: 'CDI field', dataIndex: 'field', key: 'field', width: 180, render: (v: string) => <span style={{ ...MONO, fontSize: 12 }}>{v}</span> },
                  { title: 'Silver column', dataIndex: 'silver', key: 'silver', width: 240, render: (v: string) => <Text type="secondary" style={{ ...MONO, fontSize: 12 }}>{v}</Text> },
                  { title: 'Resolution', dataIndex: 'how', key: 'how', render: (v: string) => <span style={{ fontSize: 12.5 }}>{v}</span> },
                  { title: 'Status', dataIndex: 'state', key: 'state', width: 140, render: (v: string, m) => <Tag color={m.color}>{v}</Tag> },
                ]}
              />
            </Card>
            <Paragraph type="secondary" style={{ fontSize: 12.5, lineHeight: 1.6, marginTop: 14 }}>
              Field mapping is operator-reviewed today: the schema-mapper agent proposes, a human
              accepts or overrides. {deepLink('Open mapping review →', go('mapping'))}
            </Paragraph>
            {footer(
              <Button type="primary" onClick={() => patch({ step: 5 })}>
                Compile & dry run →
              </Button>,
            )}
          </>
        )}

        {/* Step 5 — Compile edits & dry run. Fixture shadow cycle, honest demo
            Tag, deep link to the real Validation workbench. */}
        {wizard.step === 5 && (
          <>
            {stepHeader(5)}
            <Card
              size="small"
              title={<Text type="secondary" style={K_LABEL}>Shadow cycle {story.dryCycle}</Text>}
              extra={<DemoTag reason="no dry-run backend yet — the CA design story">demo projection</DemoTag>}
              style={{ marginBottom: 16 }}
            >
              {story.dry.map((d) => (
                <div key={d.k} style={{ display: 'flex', gap: 12, alignItems: 'center', padding: '7px 0', borderBottom: '1px solid rgba(5,5,5,0.06)' }}>
                  <Text type="secondary" style={{ flex: 1, fontSize: 13 }}>{d.k}</Text>
                  <span style={{ ...MONO, fontSize: 13 }}>{d.v}</span>
                  <Tag color={d.color} style={{ width: 64, textAlign: 'center', marginInlineEnd: 0 }}>{d.tag}</Tag>
                </div>
              ))}
            </Card>
            <Paragraph style={{ fontSize: 13, lineHeight: 1.7, maxWidth: '78ch' }}>{story.dryNote}</Paragraph>
            <Paragraph type="secondary" style={{ fontSize: 12.5, lineHeight: 1.6, marginTop: 12 }}>
              Compiled validation edits run as a shadow cycle against last year&rsquo;s data.{' '}
              {deepLink('Open validation triage →', go('val'))}
            </Paragraph>
            {footer(
              <Button type="primary" onClick={() => patch({ step: 6 })}>
                Send to compliance →
              </Button>,
            )}
          </>
        )}

        {/* Step 6 — Certify. Manifest + what-going-live-changes; Go live is
            mock-only until a real filing-obligation endpoint exists. */}
        {wizard.step === 6 && (
          <>
            {stepHeader(6)}
            <Row gutter={[16, 16]}>
              <Col xs={24} lg={12}>
                <Card
                  size="small"
                  title={<Text type="secondary" style={K_LABEL}>Certification manifest</Text>}
                  extra={<DemoTag reason="no certification backend yet — the CA design story">demo projection</DemoTag>}
                >
                  {story.cert.map((c) => <KV key={c.k} k={c.k} v={c.v} />)}
                </Card>
              </Col>
              <Col xs={24} lg={12}>
                <Card size="small" title="What going live changes">
                  <Paragraph style={{ fontSize: 13, lineHeight: 1.75, marginBottom: 0 }}>
                    {story.goLiveNote}
                  </Paragraph>
                </Card>
              </Col>
            </Row>
            {error && <Alert type="error" showIcon message={error} style={{ marginTop: 12 }} />}
            {footer(
              <Tooltip title={gate ?? 'creates the filing obligation — the jurisdiction goes live'}>
                <Button
                  type="primary" loading={busy === 'golive'}
                  disabled={!mayOnboard || busy === 'golive'}
                  onClick={doGoLive}
                >
                  Go live →
                </Button>
              </Tooltip>,
            )}
          </>
        )}
      </Col>
    </Row>
  );
}
