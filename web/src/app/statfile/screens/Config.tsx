// Jurisdictions — the Administration screen, rebuilt on the claude.ai/design
// v2 "Jurisdictions" mock. Two underline tabs:
//   Registry          — jurisdiction cards (filings ∪ canon), the standards
//                       registry (loaded regulator documents) and the
//                       onboard-a-jurisdiction checklist, all live-derived.
//   Add a jurisdiction — the onboarding wizard. Steps 1–3 drive the real
//                       regulation-store endpoints (/api/regulations upload →
//                       extract/start + status poll → approve) and feed the
//                       designed panels from the live payloads where they
//                       exist (pages, slug, parser model, confidence bands).
//                       Steps 4–6 have no backend yet: they render the full
//                       claude.ai/design v2 content from the CA fixture story
//                       below, each panel tagged 'demo projection', with deep
//                       links into the real Mapping/Validation screens.
//                       Wizard state persists in localStorage so
//                       Save-and-exit ↔ Resume onboarding round-trip.
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Blueprint } from '../Blueprint';
import {
  approveRegulation, can, goLiveOnboarding, startExtraction, uploadRegulation,
  useExtractStatus, useFilings, useJurisdictions, useKgRules, useRegDocuments,
  useRegulations, useSaveJurisdiction, whoCan, type AppUser,
} from '../api';
import { ACC, ACC9, ONBOARD_STEPS, STANDARDS, STATES, type ScreenId } from '../data';

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

// The mock's six wizard steps — title + one-line description.
const WIZ_STEPS: Array<[string, string]> = [
  ['Upload the rulebook', 'Point at the PDF and name the jurisdiction'],
  ['Parse & segment', 'Structure the document into citable clauses'],
  ['Extract candidate rules', 'Derive rules with confidence and citations'],
  ['Map to the silver contract', 'Resolve every field to a conformed column'],
  ['Compile edits & dry run', "Shadow cycle against last year's data"],
  ['Certify', 'Compliance sign-off, then the jurisdiction goes live'],
];

// ── the CA Homeowners onboarding story ──────────────────────────────────────
// Every fixture number the wizard renders lives here (ported verbatim from the
// claude.ai/design v2 mock). Steps 2–3 prefer live values from the upload /
// extraction payloads and fall back to this; steps 4–6 have no backend today
// and render it in both modes under a 'demo projection' chip.
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
    { band: 'Auto-approved', range: 'confidence ≥ 0.90', count: 168, color: ACC },
    { band: 'Queued for review', range: '0.70 – 0.89', count: 38, color: '#94bce3' },
    { band: 'Escalated', range: 'below 0.70', count: 8, color: ACC9 },
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
    { field: 'territory_code', silver: 'risk_location.postal_code', how: 'Reuses the Texas derivation with a CDI territory table', state: 'Resolved', tagClass: 'tag-neutral' },
    { field: 'amount_of_insurance', silver: 'coverage_detail.cov_a_limit', how: 'Direct, width change only', state: 'Resolved', tagClass: 'tag-neutral' },
    { field: 'written_premium', silver: 'premium_transaction.amount', how: 'Direct, same sign convention', state: 'Resolved', tagClass: 'tag-neutral' },
    { field: 'wildfire_risk_score', silver: '—', how: 'No conformed column. Vendor score, needs a new silver derivation', state: 'New derivation', tagClass: 'tag-outline' },
    { field: 'brush_clearance_ind', silver: '—', how: 'Present in Guidewire as a HOPDwelling question, not yet conformed', state: 'New derivation', tagClass: 'tag-outline' },
    { field: 'moratorium_flag', silver: 'policy_exposure.nonrenew_reason', how: 'Derived from an existing column, new expression', state: 'New expression', tagClass: 'tag-outline' },
  ],
  dryCycle: 'CA-HO-2025S',
  dry: [
    { k: 'Records produced', v: '486,220', tag: '—', tagClass: 'tag-neutral' },
    { k: 'Passing all edits', v: '471,904', tag: '97.1%', tagClass: 'tag-neutral' },
    { k: 'Blocking exceptions', v: '9,118', tag: '1.9%', tagClass: 'tag-accent' },
    { k: 'Premium tie to GL', v: '$188,402,110', tag: '0.02%', tagClass: 'tag-neutral' },
    { k: 'Exposure tie', v: '486,004.2', tag: '0.00%', tagClass: 'tag-neutral' },
    { k: 'Runtime', v: '1 h 42m', tag: '—', tagClass: 'tag-neutral' },
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
        tagClass: isLive || fs.length || code === 'US' ? 'tag-neutral' : 'tag-outline',
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
      tagClass: state === 'done' ? 'tag-neutral' : 'tag-outline',
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
    tagClass: s.status === 'Onboarding' ? 'tag-outline' : 'tag-neutral',
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

  return (
    <div className="sc">
      <div className="tabs-underline">
        <button className={'tab-underline' + (tab === 'registry' ? ' on' : '')} onClick={() => setTab('registry')}>
          Registry
        </button>
        <button className={'tab-underline' + (tab === 'add' ? ' on' : '')} onClick={() => setTab('add')}>
          Add a jurisdiction
        </button>
      </div>

      {tab === 'registry' ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 34, alignItems: 'start' }}>
          <section>
            <h4 style={{ marginBottom: 14 }}>Jurisdictions {live && <span className="k">live · filings + canon</span>}</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {cards.map((s) => (
                <JurCard key={s.code} card={s} user={user}
                  editable={!!derived && mayOnboard} />
              ))}
            </div>

            <h4 style={{ margin: '32px 0 10px' }}>
              Standards registry {live && (docsQ.data?.documents.length ?? 0) > 0 && <span className="k">live · loaded regulator documents</span>}
            </h4>
            <table className="table">
              <thead>
                <tr><th>Standard</th><th>Version</th><th>Rules</th><th>Owner</th></tr>
              </thead>
              <tbody>
                {standards.map((s) => (
                  <tr key={s.name} className="row">
                    <td style={{ fontSize: 13 }}>{s.name}</td>
                    <td className="mono" style={{ fontSize: 12 }}>{s.ver}</td>
                    <td className="mono" style={{ fontSize: 12 }}>{s.rules}</td>
                    <td style={{ fontSize: 12, color: 'color-mix(in srgb,var(--color-text) 60%,transparent)' }}>{s.owner}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <Blueprint className="gridwash" style={{ padding: '22px 24px' }}>
            <div className="k">Onboard a jurisdiction{onboard ? ' · live — derived from the canon' : ' · vision demo'}</div>
            <h4 style={{ margin: '4px 0', fontSize: 23 }}>{onboard ? onboard.title : 'California · Homeowners'}</h4>
            <div style={{ fontSize: 12.5, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)', margin: '4px 0 18px' }}>
              Configuration only — no pipeline code is written. The silver layer is already
              jurisdiction-agnostic; a new state is a rulebook, a mapping and an edit package.
            </div>

            {(onboard?.steps ?? ONBOARD_STEPS.map((s) => ({
              n: Number(s.n), title: s.title, body: s.body, status: s.status,
              tagClass: s.status === 'Done' ? 'tag-neutral' : 'tag-outline',
            }))).map((s) => (
              <div key={s.n} style={{ display: 'flex', alignItems: 'baseline', gap: 12, padding: '9px 0', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)' }}>
                <span className="mono" style={{ fontSize: 11, width: 14, color: 'color-mix(in srgb,var(--color-text) 45%,transparent)' }}>{s.n}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 500 }}>{s.title}</div>
                  <div style={{ fontSize: 12, lineHeight: 1.55, color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>{s.body}</div>
                </div>
                <span className={'tag ' + s.tagClass}>{s.status}</span>
              </div>
            ))}

            <div style={{ fontSize: 12.5, lineHeight: 1.65, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)', margin: '16px 0 18px' }}>
              A jurisdiction is onboarded by uploading its rulebook. The agents parse it, derive
              rules, map them onto the existing silver contract and dry-run a shadow cycle —
              pipeline code is never written.
            </div>

            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <button className="btn btn-secondary" disabled title="coming soon">
                Clone {derived?.cloneFrom ? shortName(derived.cloneFrom) : 'Texas'} config
              </button>
              {onboard?.allDone ? (
                <button
                  onClick={go('mapping')}
                  style={{ background: 'none', border: 'none', padding: '0 4px', cursor: 'pointer', fontSize: 13, color: 'var(--color-accent-700)', textDecoration: 'underline', fontFamily: 'var(--font-body)' }}
                >
                  View mapping review →
                </button>
              ) : (
                <button className="btn btn-primary" onClick={resumeOnboarding}>Resume onboarding →</button>
              )}
            </div>
          </Blueprint>
        </div>
      ) : (
        <Wizard
          wizard={wizard} patch={patchWizard} go={go} user={user}
          mayOnboard={mayOnboard} onExit={() => setTab('registry')}
        />
      )}
    </div>
  );
}

// ── an editable jurisdiction card ───────────────────────────────────────────
// Display name + line of business persist on the KG Jurisdiction node
// (display_name / lob via PATCH /api/jurisdictions/{code}); pause/resume
// flips the jurisdiction's FilingObligations, which drives Live ↔ Filed.
interface JurCardData {
  code: string; name: string; lob: string; sub: string;
  hasFilings: boolean; status: string; tagClass: string;
}

function JurCard({ card: s, user, editable }: {
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

  const input = (val: string, set: (v: string) => void, ph: string): ReactNode => (
    <input value={val} placeholder={ph} onChange={(e) => set(e.target.value)}
      style={{
        display: 'block', width: '100%', boxSizing: 'border-box', marginTop: 3,
        padding: '7px 9px', fontSize: 12.5, fontFamily: 'var(--font-body)',
        border: '1px solid var(--color-divider)', borderRadius: 0,
        background: 'color-mix(in srgb,var(--color-text) 4%,transparent)',
        color: 'var(--color-text)',
      }} />
  );

  const clickable = editable && !editing;
  return (
    <Blueprint
      onClick={clickable ? open : undefined}
      title={clickable ? 'click to edit' : undefined}
      style={{
        padding: '16px 18px', display: 'flex',
        alignItems: editing ? 'flex-start' : 'center', gap: 18,
        cursor: clickable ? 'pointer' : undefined,
      }}>
      <div style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 34, width: 56, lineHeight: 1, color: 'var(--color-accent-900)' }}>
        {s.code}
      </div>
      {editing ? (
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12 }}>
            <label style={{ fontSize: 11, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>
              Display name{input(name, setName, 'Oklahoma — Insurance Department')}
            </label>
            <label style={{ fontSize: 11, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>
              Line of business{input(lob, setLob, 'Homeowners')}
            </label>
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <button className="btn btn-primary" disabled={!name.trim() || saveMut.isPending} onClick={doSave}>
              {saveMut.isPending ? 'Saving…' : 'Save'}
            </button>
            <button className="btn btn-secondary" onClick={() => setEditing(false)}>Cancel</button>
            {s.hasFilings && (
              <button className="btn btn-secondary" disabled={saveMut.isPending} onClick={doToggleFilings}
                title={s.status === 'Live' ? 'sets the filing obligations inactive — card reads Filed' : 'reactivates the filing obligations — card reads Live'}>
                {s.status === 'Live' ? 'Pause filings' : 'Resume filings'}
              </button>
            )}
            {saveMut.error != null && (
              <span style={{ fontSize: 11.5, color: '#a33' }}>{(saveMut.error as Error).message}</span>
            )}
          </div>
        </div>
      ) : (
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14.5, fontWeight: 500 }}>{s.name}</div>
          <div style={{ fontSize: 11.5, marginTop: 2, color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>
            {s.sub}
          </div>
        </div>
      )}
      {!editing && editable && (
        <button onClick={open}
          style={{
            background: 'none', border: 'none', padding: '0 2px', cursor: 'pointer',
            fontSize: 12, color: 'var(--color-accent-700)', textDecoration: 'underline',
            fontFamily: 'var(--font-body)', flex: 'none',
          }}>
          Edit
        </button>
      )}
      {!editing && <span className={'tag ' + s.tagClass}>{s.status}</span>}
    </Blueprint>
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
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState<'upload' | 'extract' | 'approve' | 'golive' | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Extraction status poll — live while steps 2–3 own the screen (step 2 only
  // reads it for the parser label; a finished/cached job also survives a
  // Back-jump from later steps).
  const statusQ = useExtractStatus(wizard.slug, wizard.step === 2 || wizard.step === 3);
  const status = statusQ.data;
  const extractRunning = wizard.step === 3 && status?.status === 'running';

  // A finished background extraction advances nothing by itself — approval is
  // the explicit human act — but the rail should say "Done running".
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

  const railStatus = (n: number): [string, string] => {
    if (n < wizard.step) return ['Done', 'tag-neutral'];
    if (n === wizard.step) {
      if (n === 3 && extractRunning) return ['Running', 'tag-accent'];
      return ['Active', 'tag-accent'];
    }
    return ['Queued', 'tag-outline'];
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
      { band: 'Auto-approved', range: 'confidence ≥ 0.90', count: proposedNodes!.filter((n) => (n.confidence ?? 0) >= 0.9).length, color: ACC },
      { band: 'Queued for review', range: '0.70 – 0.89', count: proposedNodes!.filter((n) => (n.confidence ?? 0) >= 0.7 && (n.confidence ?? 0) < 0.9).length, color: '#94bce3' },
      { band: 'Escalated', range: 'below 0.70', count: proposedNodes!.filter((n) => (n.confidence ?? 0) < 0.7).length, color: ACC9 },
    ]
    : story.extractBands;

  const projChip = (label = 'demo projection') => (
    <span className="tag tag-outline" style={{ marginLeft: 'auto', opacity: 0.75 }}>{label}</span>
  );
  const kickerRow = (kicker: string, chip?: boolean, chipLabel?: string) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 9 }}>
      <span className="k">{kicker}</span>
      {chip && projChip(chipLabel)}
    </div>
  );
  const deepLink = (label: string, onLink: () => void) => (
    <button
      onClick={onLink}
      style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontSize: 12.5, color: 'var(--color-accent-700)', textDecoration: 'underline', fontFamily: 'var(--font-body)' }}
    >
      {label}
    </button>
  );
  // The design footer: Back + Save-and-exit on the left, primary on the right.
  const footer = (primary: ReactNode) => (
    <div style={{ display: 'flex', gap: 8, marginTop: 22, borderTop: '1px solid var(--color-divider)', paddingTop: 16 }}>
      {wizard.step > 1 && (
        <button className="btn btn-secondary" onClick={back} disabled={navLocked}
          title={navLocked ? 'wait for the current step to finish' : undefined}>
          ← Back
        </button>
      )}
      <button className="btn btn-secondary" onClick={onExit} disabled={processing}
        title={extractRunning ? 'safe — the extraction keeps running server-side' : undefined}>
        Save and exit
      </button>
      <span style={{ marginLeft: 'auto' }}>{primary}</span>
    </div>
  );

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 34, alignItems: 'start' }}>
      {/* left rail — progress */}
      <section>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 12 }}>
          <span className="k">Progress</span>
          <span className="mono" style={{ fontSize: 12 }}>{progress}%</span>
        </div>
        {WIZ_STEPS.map(([title, desc], i) => {
          const n = i + 1;
          const [label, tagClass] = railStatus(n);
          const jumpable = n < wizard.step && !navLocked; // completed steps re-open on click
          return (
            <div
              key={title}
              onClick={jumpable ? () => patch({ step: n }) : undefined}
              title={jumpable ? `back to step ${n}` : undefined}
              style={{ display: 'grid', gridTemplateColumns: '24px 1fr auto', gap: 10, padding: '9px 0', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)', cursor: jumpable ? 'pointer' : 'default' }}
            >
              <span className="mono" style={{
                fontSize: 11, width: 21, height: 21, display: 'grid', placeItems: 'center',
                border: '1px solid ' + (n <= wizard.step ? 'var(--color-accent)' : 'var(--color-divider)'),
                background: n < wizard.step ? 'var(--color-accent)' : 'transparent',
                color: n < wizard.step ? 'var(--color-bg)' : 'var(--color-text)',
              }}>{n}</span>
              <div>
                <div style={{ fontSize: 13.5, fontWeight: n === wizard.step ? 500 : 400 }}>{title}</div>
                <div style={{ fontSize: 11.5, lineHeight: 1.5, color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>{desc}</div>
              </div>
              <span className={'tag ' + tagClass} style={{ alignSelf: 'start' }}>{label}</span>
            </div>
          );
        })}
      </section>

      {/* main — step content */}
      <section>
        {wizard.step === 1 && (
          <>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 14 }}>
              <h4>Upload the rulebook</h4>
              <span className="k">Point at the PDF and name the jurisdiction</span>
            </div>
            <Blueprint
              className="gridwash"
              style={{
                padding: '52px 40px', textAlign: 'center',
                background: dragOver ? 'var(--color-accent-100)' : undefined,
              }}
              onClick={() => inputRef.current?.click()}
            >
              <div
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => { e.preventDefault(); setDragOver(false); chooseFile(e.dataTransfer.files?.[0] ?? null); }}
              >
                <div style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 22 }}>
                  Drop the jurisdiction&rsquo;s statistical plan PDF
                </div>
                <div style={{ fontSize: 12.5, margin: '6px 0 18px', color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>
                  Or a bulletin, a circular, or a filing manual. Nothing else about the platform
                  changes — the rulebook is the input.
                </div>
                <button className="btn btn-secondary" onClick={(e) => { e.stopPropagation(); inputRef.current?.click(); }}>
                  Choose file
                </button>
                <input
                  ref={inputRef} type="file" accept=".pdf,application/pdf" style={{ display: 'none' }}
                  onChange={(e) => chooseFile(e.target.files?.[0] ?? null)}
                />
                {wizard.fileName && (
                  <div className="mono" style={{ marginTop: 16, fontSize: 12, color: 'var(--color-accent-700)' }}>
                    ✓ {wizard.fileName}{mb ? ` · ${mb} MB` : ''}{wizard.pages ? ` · ${wizard.pages} pp` : ''}
                    {!fileRef.current && !wizard.slug && '  (re-choose after reload)'}
                  </div>
                )}
              </div>
            </Blueprint>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20, margin: '22px 0' }}>
              {([
                ['Jurisdiction', 'California', wizard.jurisdiction, (v: string) => patch({ jurisdiction: v })],
                ['Line of business', 'Homeowners', wizard.lob, (v: string) => patch({ lob: v })],
                ['Standard code', 'CDI HO 2026', wizard.std, (v: string) => patch({ std: v })],
              ] as Array<[string, string, string, (v: string) => void]>).map(([label, ph, val, set]) => (
                <label key={label} style={{ fontSize: 12, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>
                  {label}
                  <input
                    value={val} placeholder={ph} onChange={(e) => set(e.target.value)}
                    style={{
                      display: 'block', width: '100%', marginTop: 5, padding: '9px 11px',
                      fontSize: 13, fontFamily: 'var(--font-body)', border: '1px solid var(--color-divider)',
                      borderRadius: 0, background: 'color-mix(in srgb,var(--color-text) 4%,transparent)',
                      color: 'var(--color-text)',
                    }}
                  />
                </label>
              ))}
            </div>

            {error && <div style={{ fontSize: 12.5, color: '#a33', marginBottom: 12 }}>{error}</div>}
            {footer(
              <button
                className="btn btn-primary"
                disabled={!mayOnboard || busy === 'upload' || !wizard.fileName || !wizard.jurisdiction.trim()}
                title={gate ?? (!wizard.fileName ? 'choose the rulebook PDF' : !wizard.jurisdiction.trim() ? 'name the jurisdiction' : undefined)}
                onClick={doUpload}
              >
                {busy === 'upload' ? 'Uploading…' : 'Parse document →'}
              </button>,
            )}
          </>
        )}

        {wizard.step === 2 && (
          <>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 14 }}>
              <h4>Parse &amp; segment</h4>
              <span className="k">Structure the document into citable clauses</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.25fr', gap: 24 }}>
              <Blueprint style={{ padding: '16px 18px' }}>
                {kickerRow('Parse result', parseRows.some((r) => !r.live),
                  parseRows.some((r) => r.live) ? 'counts projected' : 'demo projection')}
                {parseRows.map((r) => (
                  <div key={r.k} style={{ display: 'flex', gap: 10, padding: '5px 0', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)', fontSize: 12.5 }}>
                    <span style={{ flex: 1, color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>{r.k}</span>
                    <span className="mono" style={{ fontSize: 11.5, textAlign: 'right', opacity: r.live ? 1 : 0.75 }}>{r.v}</span>
                  </div>
                ))}
              </Blueprint>
              <Blueprint style={{ padding: '16px 18px' }}>
                {kickerRow('Document outline — highlighted sections carry reportable rules', true)}
                {story.outline.map((o) => (
                  <div key={o.s} className="row" style={{ display: 'flex', gap: 12, padding: '8px 6px', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)', alignItems: 'baseline' }}>
                    <span className="mono" style={{ fontSize: 11.5, width: 64, color: 'var(--color-accent-700)' }}>{o.s}</span>
                    <span style={{ flex: 1, fontSize: 13 }}>{o.t}</span>
                    <span className="mono" style={{ fontSize: 11, color: 'color-mix(in srgb,var(--color-text) 52%,transparent)' }}>{o.c}</span>
                  </div>
                ))}
              </Blueprint>
            </div>
            <div style={{ fontSize: 12.5, lineHeight: 1.65, margin: '16px 0 0', color: 'color-mix(in srgb,var(--color-text) 62%,transparent)', maxWidth: '78ch' }}>
              The document is registered in the regulation store as{' '}
              <span className="mono" style={{ fontSize: 11.5 }}>{wizard.slug ?? 'uploaded-cdi-ho-2026'}</span>{' '}
              and its text is staged as the Sentinel input. Extraction is an LLM pass that derives
              candidate rules with confidence scores and citations — it takes a couple of minutes
              and runs in the background.
            </div>
            {error && <div style={{ fontSize: 12.5, color: '#a33', margin: '12px 0 0' }}>{error}</div>}
            {footer(
              <button
                className="btn btn-primary" disabled={!mayOnboard || busy === 'extract'} title={gate}
                onClick={doExtract}
              >
                {busy === 'extract' ? 'Starting…' : 'Extract rules →'}
              </button>,
            )}
          </>
        )}

        {wizard.step === 3 && (
          <>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 14 }}>
              <h4>Extract candidate rules</h4>
              <span className="k">Derive rules with confidence and citations</span>
            </div>
            {status?.status === 'error' ? (
              <Blueprint style={{ padding: '22px 24px' }}>
                <div style={{ fontSize: 13, color: '#a33' }}>{status.error ?? 'Extraction failed.'}</div>
              </Blueprint>
            ) : extractRunning || (!wizard.approved && status?.status !== 'done') ? (
              <Blueprint style={{ padding: '22px 24px' }}>
                <div style={{ fontSize: 13, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>
                  <span className="mono" style={{ fontSize: 12 }}>Sentinel is reading the document…</span>
                  {' '}polling <span className="mono" style={{ fontSize: 11.5 }}>/extract/status</span> — this
                  is an LLM pass and can take a couple of minutes. Safe to Save and exit; the job keeps running.
                </div>
              </Blueprint>
            ) : (
              <>
                <Blueprint style={{ padding: '18px 20px', marginBottom: 20 }}>
                  {kickerRow(`${fmt(bandTotal)} candidate rules by confidence`, !bandsLive, 'projected')}
                  {bands.map((b) => (
                    <div key={b.band} style={{ display: 'grid', gridTemplateColumns: '150px 130px 1fr 70px', gap: 14, alignItems: 'center', padding: '7px 0' }}>
                      <span style={{ fontSize: 13 }}>{b.band}</span>
                      <span className="mono" style={{ fontSize: 11.5, color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>{b.range}</span>
                      <span style={{ height: 9, background: 'color-mix(in srgb,var(--color-text) 9%,transparent)', position: 'relative', display: 'block' }}>
                        <span style={{ position: 'absolute', inset: '0 auto 0 0', width: `${bandTotal ? Math.round((b.count / bandTotal) * 100) : 0}%`, background: b.color }} />
                      </span>
                      <span className="mono" style={{ fontSize: 13, textAlign: 'right' }}>{fmt(b.count)}</span>
                    </div>
                  ))}
                </Blueprint>
                <div style={{ fontSize: 13, lineHeight: 1.7, maxWidth: '78ch', marginBottom: 12 }}>
                  {bandsLive && status?.result?.summary ? status.result.summary : story.extractNote}
                </div>
                <div style={{ fontSize: 12.5, color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>
                  {wizard.approved
                    ? 'Approved — the extraction is materialized in the knowledge graph as draft rules.'
                    : 'Mapping the fields approves the extraction into the knowledge graph — the rules land as drafts and go through the human approval gate on the Rulebook screen.'}
                </div>
                <div style={{ marginTop: 10, display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap' }}>
                  {deepLink('Review the queued proposals first →', go('extract'))}
                  <button
                    className="btn btn-secondary"
                    style={reArm ? { borderColor: 'var(--color-accent)', color: 'var(--color-accent-700)' } : undefined}
                    disabled={!mayOnboard || busy === 'extract'}
                    title="extraction is non-deterministic — a re-run produces a different proposal set and orphans recorded verdicts"
                    onClick={doReExtract}
                    onBlur={() => setReArm(false)}
                  >
                    {reArm ? 'Replaces all proposals + verdicts — click again to confirm' : 'Re-extract…'}
                  </button>
                </div>
              </>
            )}
            {error && status?.status !== 'error' && <div style={{ fontSize: 12.5, color: '#a33', margin: '12px 0 0' }}>{error}</div>}
            {footer(
              status?.status === 'error' ? (
                <button className="btn btn-primary" disabled={!mayOnboard || busy === 'extract'} title={gate} onClick={doExtract}>
                  Retry extraction
                </button>
              ) : (
                <button
                  className="btn btn-primary"
                  disabled={!mayOnboard || busy === 'approve' || (!wizard.approved && status?.status !== 'done')}
                  title={gate ?? (!wizard.approved && status?.status !== 'done' ? 'waiting for the extraction to finish' : !wizard.approved ? 'approves the extraction into the canon' : undefined)}
                  onClick={doApprove}
                >
                  {busy === 'approve' ? 'Approving…' : 'Map fields →'}
                </button>
              ),
            )}
          </>
        )}

        {wizard.step >= 4 && (
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 14 }}>
            <h4>{WIZ_STEPS[wizard.step - 1][0]}</h4>
            <span className="k">{WIZ_STEPS[wizard.step - 1][1]}</span>
          </div>
        )}

        {/* Step 4 — Map to the silver contract. No live backend yet: the CA
            story renders under a demo-projection chip; the real work happens
            on the Mapping review screen (deep link below). */}
        {wizard.step === 4 && (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 18, marginBottom: 22 }}>
              {story.mapSummary.map((m) => (
                <Blueprint key={m.k} style={{ padding: '12px 14px' }}>
                  <div style={{ fontFamily: 'var(--font-heading)', fontSize: 30, lineHeight: 1 }}>{m.v}</div>
                  <div style={{ fontSize: 11, lineHeight: 1.4, color: 'color-mix(in srgb,var(--color-text) 58%,transparent)', marginTop: 4 }}>{m.k}</div>
                </Blueprint>
              ))}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 6 }}>{projChip()}</div>
            <table className="table">
              <thead>
                <tr><th>CDI field</th><th>Silver column</th><th>Resolution</th><th>Status</th></tr>
              </thead>
              <tbody>
                {story.map.map((m) => (
                  <tr key={m.field} className="row">
                    <td className="mono" style={{ fontSize: 12 }}>{m.field}</td>
                    <td className="mono" style={{ fontSize: 12, color: 'color-mix(in srgb,var(--color-text) 65%,transparent)' }}>{m.silver}</td>
                    <td style={{ fontSize: 12.5 }}>{m.how}</td>
                    <td><span className={'tag ' + m.tagClass}>{m.state}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ fontSize: 12.5, lineHeight: 1.6, marginTop: 14, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>
              Field mapping is operator-reviewed today: the schema-mapper agent proposes, a human
              accepts or overrides. {deepLink('Open mapping review →', go('mapping'))}
            </div>
            {footer(
              <button className="btn btn-primary" onClick={() => patch({ step: 5 })}>
                Compile &amp; dry run →
              </button>,
            )}
          </>
        )}

        {/* Step 5 — Compile edits & dry run. Fixture shadow cycle, honest chip,
            deep link to the real Validation workbench. */}
        {wizard.step === 5 && (
          <>
            <Blueprint style={{ padding: '18px 20px', marginBottom: 20 }}>
              {kickerRow(`Shadow cycle ${story.dryCycle}`, true)}
              {story.dry.map((d) => (
                <div key={d.k} style={{ display: 'flex', gap: 12, alignItems: 'center', padding: '7px 0', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)' }}>
                  <span style={{ flex: 1, fontSize: 13, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>{d.k}</span>
                  <span className="mono" style={{ fontSize: 13 }}>{d.v}</span>
                  <span className={'tag ' + d.tagClass} style={{ width: 64, justifyContent: 'center' }}>{d.tag}</span>
                </div>
              ))}
            </Blueprint>
            <div style={{ fontSize: 13, lineHeight: 1.7, maxWidth: '78ch' }}>{story.dryNote}</div>
            <div style={{ fontSize: 12.5, lineHeight: 1.6, marginTop: 12, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>
              Compiled validation edits run as a shadow cycle against last year&rsquo;s data.{' '}
              {deepLink('Open validation triage →', go('val'))}
            </div>
            {footer(
              <button className="btn btn-primary" onClick={() => patch({ step: 6 })}>
                Send to compliance →
              </button>,
            )}
          </>
        )}

        {/* Step 6 — Certify. Manifest + what-going-live-changes; Go live is
            mock-only until a real filing-obligation endpoint exists. */}
        {wizard.step === 6 && (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
              <Blueprint style={{ padding: '18px 20px' }}>
                {kickerRow('Certification manifest', true)}
                {story.cert.map((c) => (
                  <div key={c.k} style={{ display: 'flex', gap: 10, padding: '6px 0', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)', fontSize: 12.5 }}>
                    <span style={{ flex: 1, color: 'color-mix(in srgb,var(--color-text) 55%,transparent)' }}>{c.k}</span>
                    <span className="mono" style={{ fontSize: 11.5, textAlign: 'right' }}>{c.v}</span>
                  </div>
                ))}
              </Blueprint>
              <Blueprint className="gridwash" style={{ padding: '20px 22px' }}>
                <div style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 21, marginBottom: 8 }}>
                  What going live changes
                </div>
                <div style={{ fontSize: 13, lineHeight: 1.75 }}>{story.goLiveNote}</div>
              </Blueprint>
            </div>
            {error && <div style={{ fontSize: 12.5, color: '#a33', margin: '12px 0 0' }}>{error}</div>}
            {footer(
              <button
                className="btn btn-primary"
                disabled={!mayOnboard || busy === 'golive'}
                title={gate ?? 'creates the filing obligation — the jurisdiction goes live'}
                onClick={doGoLive}
              >
                {busy === 'golive' ? 'Going live…' : 'Go live →'}
              </button>,
            )}
          </>
        )}
      </section>
    </div>
  );
}
