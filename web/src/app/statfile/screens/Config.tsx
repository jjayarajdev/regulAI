// Jurisdictions — the Administration screen, rebuilt on the claude.ai/design
// v2 "Jurisdictions" mock. Two underline tabs:
//   Registry          — jurisdiction cards (filings ∪ canon), the standards
//                       registry (loaded regulator documents) and the
//                       onboard-a-jurisdiction checklist, all live-derived.
//   Add a jurisdiction — the onboarding wizard. Steps 1–3 drive the real
//                       regulation-store endpoints (/api/regulations upload →
//                       extract/start + status poll → approve); steps 4–6 are
//                       operator-driven today and render honestly as queued
//                       with deep links. Wizard state persists in localStorage
//                       so Save-and-exit ↔ Resume onboarding round-trip.
import { useEffect, useMemo, useRef, useState } from 'react';
import { Blueprint } from '../Blueprint';
import {
  approveRegulation, can, startExtraction, uploadRegulation, useExtractStatus,
  useFilings, useKgRules, useRegDocuments, whoCan, type AppUser,
} from '../api';
import { ONBOARD_STEPS, STANDARDS, STATES, type ScreenId } from '../data';

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

type Tab = 'registry' | 'add';

export function ConfigScreen({ go, user }: {
  go: (s: ScreenId) => () => void; user: AppUser;
}) {
  const filingsQ = useFilings();
  const docsQ = useRegDocuments();
  const rulesQ = useKgRules();

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

    const codes = [...new Set([...byJur.keys(), ...ruleStats.keys()])]
      .sort((a, b) => Number(byJur.has(b)) - Number(byJur.has(a)) || a.localeCompare(b));

    const cards = codes.map((code) => {
      const fs = byJur.get(code) ?? [];
      const rs = ruleStats.get(code);
      const isLive = fs.some((f) => f.is_active);
      const plans = [...new Set(fs.map((f) => f.plan_code))];
      const sub = [
        LOB[code],
        plans.length ? `${plans.join(', ')} plan${plans.length > 1 ? 's' : ''}` : 'no filing configured',
        rs
          ? `${fmt(rs.total)} rules` + (rs.executable ? ` · ${rs.executable} executable` : '')
          : 'no canon yet',
      ].filter(Boolean).join(' · ');
      return {
        code,
        name: STATE_NAMES[code] ?? code,
        sub,
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
        jd.length
          ? `${jd.length} regulator document${jd.length > 1 ? 's' : ''} loaded into the regdocs store — ${jd.map((d) => d.title).slice(0, 2).join('; ')}${jd.length > 2 ? '; …' : ''}.`
          : 'No regulator documents loaded yet.',
        st(jd.length ? 'done' : 'now')),
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
  }, [filingsQ.data, rulesQ.data, docsQ.data]);

  // Demo fallback (warehouse cold): the design fixtures, reshaped.
  const cards = derived?.cards ?? STATES.map((s) => ({
    code: s.code, name: s.name, sub: s.detail, status: s.status,
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
                <Blueprint key={s.code} style={{ padding: '16px 18px', display: 'flex', alignItems: 'center', gap: 18 }}>
                  <div style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 34, width: 56, lineHeight: 1, color: 'var(--color-accent-900)' }}>
                    {s.code}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14.5, fontWeight: 500 }}>{s.name}</div>
                    <div style={{ fontSize: 11.5, marginTop: 2, color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>
                      {s.sub}
                    </div>
                  </div>
                  <span className={'tag ' + s.tagClass}>{s.status}</span>
                </Blueprint>
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

// ── the Add-a-jurisdiction wizard ───────────────────────────────────────────
function Wizard({ wizard, patch, go, mayOnboard, onExit }: {
  wizard: WizardState; patch: (p: Partial<WizardState>) => void;
  go: (s: ScreenId) => () => void; user: AppUser;
  mayOnboard: boolean; onExit: () => void;
}) {
  const fileRef = useRef<File | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState<'upload' | 'extract' | 'approve' | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Extraction status poll — active while step 3 owns the screen.
  const statusQ = useExtractStatus(wizard.slug, wizard.step === 3 && !wizard.approved);
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
      const r = await uploadRegulation(f, label, wizard.jurisdiction ? `${wizard.jurisdiction} — uploaded rulebook` : undefined);
      patch({ slug: r.slug, pages: r.pages, chars: r.chars, step: 2 });
    } catch (e) {
      setError((e as Error).message);
    } finally { setBusy(null); }
  };

  const doExtract = async () => {
    if (!wizard.slug) return;
    setBusy('extract'); setError(null);
    try {
      await startExtraction(wizard.slug);
      patch({ step: 3 });
      statusQ.refetch();
    } catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  };

  const doApprove = async () => {
    if (!wizard.slug) return;
    setBusy('approve'); setError(null);
    try {
      await approveRegulation(wizard.slug);
      patch({ approved: true, step: 4 });
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
  const progress = Math.round(((wizard.step - 1) / WIZ_STEPS.length) * 100);

  const mb = wizard.fileSize != null ? (wizard.fileSize / 1048576).toFixed(1) : null;

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
          return (
            <div key={title} style={{ display: 'grid', gridTemplateColumns: '24px 1fr auto', gap: 10, padding: '9px 0', borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)' }}>
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
            <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid var(--color-divider)', paddingTop: 16 }}>
              <button className="btn btn-secondary" onClick={onExit}>Save and exit</button>
              <button
                className="btn btn-primary"
                disabled={!mayOnboard || busy === 'upload' || !wizard.fileName || !wizard.jurisdiction.trim()}
                title={gate ?? (!wizard.fileName ? 'choose the rulebook PDF' : !wizard.jurisdiction.trim() ? 'name the jurisdiction' : undefined)}
                onClick={doUpload}
              >
                {busy === 'upload' ? 'Uploading…' : 'Parse document →'}
              </button>
            </div>
          </>
        )}

        {wizard.step === 2 && (
          <>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 14 }}>
              <h4>Parse &amp; segment</h4>
              <span className="k">Structure the document into citable clauses</span>
            </div>
            <Blueprint style={{ padding: '22px 24px' }}>
              <div className="mono" style={{ fontSize: 12.5, color: 'var(--color-accent-700)', marginBottom: 10 }}>
                ✓ {wizard.fileName ?? wizard.slug} · {wizard.pages ?? '—'} pages · {wizard.chars != null ? fmt(wizard.chars) : '—'} chars of text extracted
              </div>
              <div style={{ fontSize: 13, lineHeight: 1.7, color: 'color-mix(in srgb,var(--color-text) 70%,transparent)' }}>
                The document is registered in the regulation store as{' '}
                <span className="mono" style={{ fontSize: 12 }}>{wizard.slug}</span> and its text is
                staged as the Sentinel input. The next step runs the extraction agent — an LLM pass
                that derives candidate rules with confidence scores and citations. It takes a couple
                of minutes and runs in the background.
              </div>
            </Blueprint>
            {error && <div style={{ fontSize: 12.5, color: '#a33', margin: '12px 0 0' }}>{error}</div>}
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 22, borderTop: '1px solid var(--color-divider)', paddingTop: 16 }}>
              <button className="btn btn-secondary" onClick={onExit}>Save and exit</button>
              <button
                className="btn btn-primary" disabled={!mayOnboard || busy === 'extract'} title={gate}
                onClick={doExtract}
              >
                {busy === 'extract' ? 'Starting…' : 'Extract candidate rules →'}
              </button>
            </div>
          </>
        )}

        {wizard.step === 3 && (
          <>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 14 }}>
              <h4>Extract candidate rules</h4>
              <span className="k">Derive rules with confidence and citations</span>
            </div>
            <Blueprint style={{ padding: '22px 24px' }}>
              {status?.status === 'done' && status.result ? (
                <>
                  <div className="mono" style={{ fontSize: 12.5, color: 'var(--color-accent-700)', marginBottom: 10 }}>
                    ✓ {status.result.n_nodes} candidate nodes · {status.result.n_relationships} relationships · {status.result.n_citations} citations · {status.result.model}
                  </div>
                  {status.result.summary && (
                    <div style={{ fontSize: 13, lineHeight: 1.7, color: 'color-mix(in srgb,var(--color-text) 70%,transparent)', marginBottom: 10 }}>
                      {status.result.summary}
                    </div>
                  )}
                  <div style={{ fontSize: 12.5, color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>
                    Approval materializes the extraction into the knowledge graph — the rules land as
                    drafts and go through the human approval gate on the Rulebook screen.
                  </div>
                </>
              ) : status?.status === 'error' ? (
                <div style={{ fontSize: 13, color: '#a33' }}>{status.error ?? 'Extraction failed.'}</div>
              ) : (
                <div style={{ fontSize: 13, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>
                  <span className="mono" style={{ fontSize: 12 }}>Sentinel is reading the document…</span>
                  {' '}polling <span className="mono" style={{ fontSize: 11.5 }}>/extract/status</span> — this
                  is an LLM pass and can take a couple of minutes. Safe to Save and exit; the job keeps running.
                </div>
              )}
            </Blueprint>
            {error && status?.status !== 'error' && <div style={{ fontSize: 12.5, color: '#a33', margin: '12px 0 0' }}>{error}</div>}
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 22, borderTop: '1px solid var(--color-divider)', paddingTop: 16 }}>
              <button className="btn btn-secondary" onClick={onExit}>Save and exit</button>
              {status?.status === 'error' ? (
                <button className="btn btn-primary" disabled={!mayOnboard || busy === 'extract'} title={gate} onClick={doExtract}>
                  Retry extraction
                </button>
              ) : (
                <button
                  className="btn btn-primary"
                  disabled={!mayOnboard || busy === 'approve' || status?.status !== 'done'}
                  title={gate ?? (status?.status !== 'done' ? 'waiting for the extraction to finish' : undefined)}
                  onClick={doApprove}
                >
                  {busy === 'approve' ? 'Approving…' : 'Approve into the canon →'}
                </button>
              )}
            </div>
          </>
        )}

        {wizard.step >= 4 && (
          <>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 14 }}>
              <h4>{WIZ_STEPS[wizard.step - 1][0]}</h4>
              <span className="k">{WIZ_STEPS[wizard.step - 1][1]}</span>
            </div>
            {/* Steps 4–6 are operator-driven today — no fake automation. */}
            {([
              [4, 'Map to the silver contract',
                'Field mapping is operator-reviewed today: the schema-mapper agent proposes, a human accepts or overrides on the Mapping review screen.',
                'Open mapping review →', go('mapping')],
              [5, 'Compile edits & dry run',
                'Compiled validation edits run as a shadow cycle on the Validation workbench against last year’s data.',
                'Open validation triage →', go('val')],
              [6, 'Certify',
                'Compliance sign-off is recorded on the filing screen when the jurisdiction’s first cycle seals — then it goes live in the registry.',
                null, undefined],
            ] as Array<[number, string, string, string | null, (() => void) | undefined]>).map(([n, title, note, linkLabel, onLink]) => (
              <Blueprint key={n} style={{ padding: '16px 18px', marginBottom: 12, opacity: n === wizard.step ? 1 : 0.75 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span className="mono" style={{ fontSize: 11, color: 'color-mix(in srgb,var(--color-text) 45%,transparent)' }}>{n}</span>
                  <span style={{ fontSize: 14, fontWeight: 500 }}>{title}</span>
                  <span className="tag tag-outline" style={{ marginLeft: 'auto' }}>Queued</span>
                </div>
                <div style={{ fontSize: 12.5, lineHeight: 1.6, margin: '6px 0 0 21px', color: 'color-mix(in srgb,var(--color-text) 62%,transparent)' }}>
                  {note}
                  {linkLabel && (
                    <>
                      {' '}
                      <button
                        onClick={onLink}
                        style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontSize: 12.5, color: 'var(--color-accent-700)', textDecoration: 'underline', fontFamily: 'var(--font-body)' }}
                      >
                        {linkLabel}
                      </button>
                    </>
                  )}
                </div>
              </Blueprint>
            ))}
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 22, borderTop: '1px solid var(--color-divider)', paddingTop: 16 }}>
              <button className="btn btn-secondary" onClick={onExit}>Save and exit</button>
              <span className="k" style={{ alignSelf: 'center' }}>
                steps 4–6 advance as the operators land mapping, dry-run and sign-off
              </span>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
