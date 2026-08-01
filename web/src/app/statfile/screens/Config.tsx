// States & standards — jurisdiction cards, standards registry, and the
// onboarding stepper. Live: jurisdictions derived from /filings, standards
// registry from /reg/documents; the California onboarding flow is the design's
// vision content (no onboarding pipeline exists yet).
import { useMemo } from 'react';
import { Blueprint } from '../Blueprint';
import { useFilings, useRegDocuments } from '../api';
import { ACC9, ONBOARD_STEPS, STANDARDS, STATES } from '../data';

const STATE_NAMES: Record<string, string> = {
  TX: 'Texas — Department of Insurance',
  OK: 'Oklahoma — Insurance Department',
  LA: 'Louisiana — Department of Insurance',
  CA: 'California — Department of Insurance',
};

export function ConfigScreen() {
  const filingsQ = useFilings();
  const docsQ = useRegDocuments();

  const live = (filingsQ.data?.filings.length ?? 0) > 0;

  const states = useMemo(() => {
    const filings = filingsQ.data?.filings ?? [];
    if (!filings.length) return STATES;
    const byJur = new Map<string, typeof filings>();
    for (const f of filings) {
      const code = (f.jurisdiction_code || '').replace(/^US-/, '') || '—';
      if (!byJur.has(code)) byJur.set(code, []);
      byJur.get(code)!.push(f);
    }
    return [...byJur.entries()].map(([code, fs]) => ({
      code,
      name: STATE_NAMES[code] ?? code,
      detail: fs.map((f) => `${f.plan_code} · due ${f.due_date}`).join('  ·  '),
      status: fs.some((f) => f.is_active) ? 'Live' : 'Filed',
      tagClass: fs.some((f) => f.is_active) ? 'tag-accent' : 'tag-neutral',
      color: ACC9,
    }));
  }, [filingsQ.data]);

  const standards = useMemo(() => {
    const docs = docsQ.data?.documents ?? [];
    if (!docs.length) return STANDARDS;
    return docs.map((d) => ({
      name: d.title,
      ver: d.edition || d.effective_date,
      rules: `${d.page_count} pp · ${(d.word_count / 1000).toFixed(1)}K words`,
      owner: d.issuing_body,
    }));
  }, [docsQ.data]);

  return (
    <div className="sc" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 34, alignItems: 'start' }}>
      <section>
        <h4 style={{ marginBottom: 10 }}>Jurisdictions {live && <span className="k">live · from filings</span>}</h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {states.map((s) => (
            <Blueprint key={s.code} style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 14 }}>
              <div style={{ fontFamily: 'var(--font-heading)', fontSize: 30, width: 52, color: s.color }}>{s.code}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 500 }}>{s.name}</div>
                <div style={{ fontSize: 11.5, color: 'color-mix(in srgb,var(--color-text) 58%,transparent)' }}>{s.detail}</div>
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
            <tr><th>Standard</th><th>Version</th><th>Size</th><th>Owner</th></tr>
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
        <div className="k">Onboard a jurisdiction · vision demo</div>
        <h4 style={{ margin: '4px 0', fontSize: 23 }}>California · Homeowners</h4>
        <div style={{ fontSize: 12.5, color: 'color-mix(in srgb,var(--color-text) 62%,transparent)', marginBottom: 20 }}>
          Configuration only — no pipeline code is written. The silver layer is already jurisdiction-agnostic; a new state is a rulebook, a mapping and an edit package.
        </div>

        {ONBOARD_STEPS.map((s) => (
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
