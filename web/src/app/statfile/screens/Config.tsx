// States & standards — jurisdiction cards, standards registry, and the
// onboarding stepper. Live: jurisdictions merged from /filings (who files)
// and /kg/rules (whose canon exists — catches states mid-onboarding);
// standards registry from /reg/documents with jurisdiction inferred from the
// issuing body; the onboarding panel reflects the real state of the furthest
// in-progress jurisdiction (today: Florida) instead of the design's fiction.
import { useMemo } from 'react';
import { Blueprint } from '../Blueprint';
import { useFilings, useKgRules, useRegDocuments } from '../api';
import { ACC9, ONBOARD_STEPS, STANDARDS, STATES } from '../data';

const STATE_NAMES: Record<string, string> = {
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
};

export function ConfigScreen() {
  const filingsQ = useFilings();
  const docsQ = useRegDocuments();
  const rulesQ = useKgRules();

  const live = (filingsQ.data?.filings.length ?? 0) > 0;

  const states = useMemo(() => {
    const filings = filingsQ.data?.filings ?? [];
    const rules = rulesQ.data?.rules ?? [];
    if (!filings.length && !rules.length) {
      return STATES.map((s) => ({ ...s, filings: s.detail as string | null, canon: null as string | null }));
    }

    const byJur = new Map<string, typeof filings>();
    for (const f of filings) {
      const code = (f.jurisdiction_code || '').replace(/^US-/, '') || '—';
      if (!byJur.has(code)) byJur.set(code, []);
      byJur.get(code)!.push(f);
    }
    const ruleStats = new Map<string, { total: number; approved: number }>();
    for (const r of rules) {
      const code = (r.jurisdiction_code || '').replace(/^US-/, '') || '—';
      const s = ruleStats.get(code) ?? { total: 0, approved: 0 };
      s.total += 1;
      if (r.status === 'approved') s.approved += 1;
      ruleStats.set(code, s);
    }

    const codes = [...new Set([...byJur.keys(), ...ruleStats.keys()])]
      .sort((a, b) => Number(byJur.has(b)) - Number(byJur.has(a)) || a.localeCompare(b));
    return codes.map((code) => {
      const fs = byJur.get(code) ?? [];
      const rs = ruleStats.get(code);
      const filing = fs.length > 0;
      return {
        code,
        name: STATE_NAMES[code] ?? code,
        filings: fs.length ? fs.map((f) => `${f.plan_code} · due ${f.due_date}`).join('  ·  ') : null,
        canon: rs ? `${rs.total} rules in canon · ${rs.approved} approved` : 'no canon yet',
        status: filing ? (fs.some((f) => f.is_active) ? 'Live' : 'Filed')
          : code === 'US' ? 'Defaults' : 'Onboarding',
        tagClass: filing ? (fs.some((f) => f.is_active) ? 'tag-accent' : 'tag-neutral')
          : code === 'US' ? 'tag-neutral' : 'tag-outline',
        color: ACC9,
      };
    });
  }, [filingsQ.data, rulesQ.data]);

  const standards = useMemo(() => {
    const docs = docsQ.data?.documents ?? [];
    if (!docs.length) return STANDARDS.map((s) => ({ ...s, jur: '—' }));
    return [...docs]
      .map((d) => {
        // Bulletins carry their id in the title; a bare "1" says nothing.
        // Effective date is the meaningful "version" in those cases.
        const redundant = !d.edition || d.title.includes(d.edition) || /^\d$/.test(d.edition);
        return {
          name: d.title,
          ver: redundant ? `eff. ${d.effective_date}` : d.edition,
          rules: `${(d.word_count / 1000).toFixed(1)}K words`
            + (d.page_count > 2 ? ` · ${d.page_count} pp` : ''),
          owner: d.issuing_body,
          jur: ISSUER_JUR[d.issuing_body] ?? '—',
        };
      })
      .sort((a, b) => a.jur.localeCompare(b.jur) || a.name.localeCompare(b.name));
  }, [docsQ.data]);

  // The real onboarding pipeline state for the furthest non-filing
  // jurisdiction (FL): docs loaded → rules extracted → human approval →
  // executable edits → filing calendar.
  const onboard = useMemo(() => {
    const rules = (rulesQ.data?.rules ?? []).filter((r) => r.jurisdiction_code === 'US-FL');
    const docs = (docsQ.data?.documents ?? []).filter((d) => ISSUER_JUR[d.issuing_body] === 'FL');
    if (!rules.length) return null;
    const approved = rules.filter((r) => r.status === 'approved').length;
    const executable = rules.filter((r) => r.executable).length;
    const mk = (n: number, title: string, body: string, state: 'done' | 'now' | 'todo') => ({
      n, title, body,
      status: state === 'done' ? 'Done' : state === 'now' ? 'In progress' : 'Not started',
      tagClass: state === 'done' ? 'tag-neutral' : state === 'now' ? 'tag-accent' : 'tag-outline',
      ring: state === 'todo' ? 'var(--color-divider)' : 'var(--color-accent)',
      fill: state === 'done' ? 'var(--color-accent)' : 'transparent',
      num: state === 'done' ? '#f2f2f3' : 'var(--color-text)',
    });
    return {
      steps: [
        mk(1, 'Ingest regulator documents',
           `${docs.length} FL documents loaded into the regdocs store — statutes 627.062/627.351, OIR-22-04M, the FHCF data-call form.`,
           docs.length > 0 ? 'done' : 'todo'),
        mk(2, 'Extract rules to the canon',
           `${rules.length} FL rules in the knowledge graph, extracted by Sentinel with citations.`,
           'done'),
        mk(3, 'Human approval gate',
           `${approved} of ${rules.length} rules approved — review the drafts on the Rulebook screen.`,
           approved === rules.length ? 'done' : 'now'),
        mk(4, 'Compile executable edits',
           executable ? `${executable} executable edits compiled.` : 'No FL rules compiled to validation edits yet.',
           executable ? 'done' : 'todo'),
        mk(5, 'Configure the filing calendar',
           'No FL filings configured — the silver layer is already jurisdiction-agnostic.',
           'todo'),
      ],
    };
  }, [rulesQ.data, docsQ.data]);

  return (
    <div className="sc" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 34, alignItems: 'start' }}>
      <section>
        <h4 style={{ marginBottom: 10 }}>Jurisdictions {live && <span className="k">live · filings + canon</span>}</h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {states.map((s) => (
            <Blueprint key={s.code} style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 14 }}>
              <div style={{ fontFamily: 'var(--font-heading)', fontSize: 30, width: 52, color: s.color }}>{s.code}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 500 }}>{s.name}</div>
                {s.filings && (
                  <div style={{ fontSize: 11.5, color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>{s.filings}</div>
                )}
                {s.canon && (
                  <div className="mono" style={{ fontSize: 10.5, marginTop: 2, color: 'color-mix(in srgb,var(--color-text) 48%,transparent)' }}>{s.canon}</div>
                )}
              </div>
              <span className={'tag ' + s.tagClass}>{s.status}</span>
            </Blueprint>
          ))}
        </div>

        <h4 style={{ margin: '30px 0 10px' }}>
          Standards registry {live && docsQ.data?.documents.length ? <span className="k">live · loaded regulator documents</span> : null}
        </h4>
        <table className="table">
          <thead>
            <tr><th>Jur</th><th>Standard</th><th>Version</th><th>Size</th><th>Owner</th></tr>
          </thead>
          <tbody>
            {standards.map((s) => (
              <tr key={s.name} className="row">
                <td className="mono" style={{ fontSize: 12, fontWeight: 500 }}>{s.jur}</td>
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
        <div className="k">
          {onboard ? 'Onboard a jurisdiction · live — derived from the canon' : 'Onboard a jurisdiction · vision demo'}
        </div>
        <h4 style={{ margin: '4px 0', fontSize: 23 }}>
          {onboard ? 'Florida · Property' : 'California · Homeowners'}
        </h4>
        <div style={{ fontSize: 12.5, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)', marginBottom: 20 }}>
          {onboard
            ? 'Real pipeline state: documents and extracted rules are in the canon; approval, edit compilation and the filing calendar remain.'
            : 'Configuration only — no pipeline code is written. The silver layer is already jurisdiction-agnostic; a new state is a rulebook, a mapping and an edit package.'}
        </div>

        {(onboard?.steps ?? ONBOARD_STEPS).map((s) => (
          <div key={s.n} style={{ display: 'grid', gridTemplateColumns: '26px 1fr', gap: 13, paddingBottom: 18 }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <span className="mono" style={{
                fontSize: 11, width: 22, height: 22, display: 'grid', placeItems: 'center',
                border: '1px solid ' + s.ring, background: s.fill, color: s.num,
              }}>{s.n}</span>
              <span style={{ flex: 1, width: 1, background: 'var(--color-divider)', marginTop: 5 }} />
            </div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 8 }}>
                {s.title} <span className={'tag ' + s.tagClass}>{s.status}</span>
              </div>
              <div style={{ fontSize: 12.5, lineHeight: 1.6, color: 'color-mix(in srgb,var(--color-text) 64%,transparent)', marginTop: 2 }}>{s.body}</div>
            </div>
          </div>
        ))}

        <div style={{ display: 'flex', gap: 8, paddingTop: 6 }}>
          <button className="btn btn-secondary">Clone Texas config</button>
          <button className="btn btn-primary">Resume onboarding</button>
        </div>
      </Blueprint>
    </div>
  );
}
