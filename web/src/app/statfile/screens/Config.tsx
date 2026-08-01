// States & standards — jurisdiction cards, standards registry, and the
// California onboarding stepper.
import { Blueprint } from '../Blueprint';
import { ONBOARD_STEPS, STANDARDS, STATES } from '../data';

export function ConfigScreen() {
  return (
    <div className="sc" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 34, alignItems: 'start' }}>
      <section>
        <h4 style={{ marginBottom: 10 }}>Jurisdictions</h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {STATES.map((s) => (
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

        <h4 style={{ margin: '30px 0 10px' }}>Standards registry</h4>
        <table className="table">
          <thead>
            <tr><th>Standard</th><th>Version</th><th>Rules</th><th>Owner</th></tr>
          </thead>
          <tbody>
            {STANDARDS.map((s) => (
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
        <div className="k">Onboard a jurisdiction</div>
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
