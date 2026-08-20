// Amendments & impact — commissioner's bulletins on the left, and for the
// selected one the KG-computed impact on the executable canon: per-rule
// before/after diffs, dry-run record impact, and the gated apply. Live:
// /bulletins + /bulletin/{name}/impact; when the knowledge graph is offline
// (503 / kg_offline) the screen degrades to the bundled demo impact.
import { useState, type CSSProperties } from 'react';
import { toast } from 'sonner';
import { Blueprint } from '../Blueprint';
import {
  can, useApplyBulletin, useBulletinImpact, useBulletins, whoCan, type AppUser,
} from '../api';
import { ApiError } from '../../../api/client';
import type { Bulletin, BulletinImpact, RuleChange, RuleChangeSide } from '../../../api/types';
import { ACC, ACC9, NEU } from '../data';

const sevDot = (s: string) => (s === 'ERROR' ? ACC9 : s === 'WARNING' ? ACC : NEU);
const juris = (code?: string | null) => (code ?? '').replace(/^US-/, '') || '—';
const fmt = (n: number) => n.toLocaleString('en-US');

const KIND_TAG: Record<RuleChange['change_kind'], [string, string]> = {
  modified: ['tag-outline', 'Modified'],
  added: ['tag-accent', 'Added'],
  retired: ['tag-neutral', 'Retired'],
};

// ── design-demo fixtures — fallback when the API/KG is unavailable ─────────
const DEMO_BULLETINS: Bulletin[] = [
  {
    name: 'B-2026-Q4-118',
    title: 'Credit Score Declination During Catastrophe Periods',
    effective_date: '2026-01-01',
    status: 'pending',
    targets: 3,
    summary: 'During a declared catastrophe period, reason code L submitted alone becomes a reporting violation — a companion catastrophe-related code is required on the notice record.',
    jurisdiction_code: 'US-TX',
  },
  {
    name: 'B-2026-Q3-104',
    title: 'Notice-Period Alignment for Renewal Declinations',
    effective_date: '2025-10-01',
    status: 'applied',
    targets: 2,
    summary: 'Aligned the minimum notice window for nonrenewals with §22 (30 days), retiring the 21-day transitional rule.',
    jurisdiction_code: 'US-TX',
  },
];

const DEMO_IMPACTS: Record<string, BulletinImpact> = {
  'B-2026-Q4-118': {
    bulletin: DEMO_BULLETINS[0],
    rule_changes: [
      {
        rule_number: 'A.34',
        name: 'Reason code L (credit score declination) requires companion',
        change_kind: 'modified',
        before: {
          violation_sql: "LENGTH(j.declinereason) = 1 AND j.declinereason = 'L'",
          severity: 'WARNING',
          violation_reason: 'L should carry a companion code',
        },
        after: {
          violation_sql: "LENGTH(j.declinereason) = 1 AND j.declinereason = 'L'\nAND EXISTS (SELECT 1 FROM REF.CAT_PERIOD cp\n  WHERE j.noticedate BETWEEN cp.start_date AND cp.end_date)",
          severity: 'ERROR',
          violation_reason: 'L alone during a declared catastrophe period',
        },
        records: {
          newly_failing: 12, newly_passing: 0,
          sample_newly_failing: ['POL-0011', 'POL-0050', 'POL-0410', 'POL-0412', 'POL-2107', 'POL-2151'],
          sample_newly_passing: [],
        },
      },
      {
        rule_number: 'A.22',
        name: 'Notice date must precede effective date by 30+ days',
        change_kind: 'modified',
        before: {
          violation_sql: 'DATEDIFF(day, j.noticedate, j.effectivedate) < 30',
          severity: 'ERROR',
          violation_reason: 'Insufficient notice period',
        },
        after: {
          violation_sql: 'DATEDIFF(day, j.noticedate, j.effectivedate) < 30\nAND j.action <> \'DECLINATION\'',
          severity: 'ERROR',
          violation_reason: 'Insufficient notice period (declinations carved out per bulletin)',
        },
        records: {
          newly_failing: 0, newly_passing: 2,
          sample_newly_failing: [],
          sample_newly_passing: ['POL-0007', 'POL-2103'],
        },
      },
      {
        rule_number: 'A.41',
        name: 'Catastrophe-period declination memo required',
        change_kind: 'added',
        before: null,
        after: {
          violation_sql: "j.declinereason LIKE 'L%' AND j.cat_memo IS NULL\nAND EXISTS (SELECT 1 FROM REF.CAT_PERIOD cp\n  WHERE j.noticedate BETWEEN cp.start_date AND cp.end_date)",
          severity: 'WARNING',
          violation_reason: 'Catastrophe-period declination lacks the underwriting memo',
        },
        records: null,
        sql_error: 'REF.CAT_PERIOD not yet loaded in the warehouse — dry-run skipped',
      },
    ],
    totals: { rules_affected: 3, newly_failing: 12, newly_passing: 2, filings_affected: ['TPA-Q4-2025', 'CL-Q4-2025'] },
  },
  'B-2026-Q3-104': {
    bulletin: DEMO_BULLETINS[1],
    rule_changes: [
      {
        rule_number: 'A.22',
        name: 'Notice date must precede effective date by 30+ days',
        change_kind: 'modified',
        before: {
          violation_sql: 'DATEDIFF(day, j.noticedate, j.effectivedate) < 21',
          severity: 'ERROR',
          violation_reason: 'Insufficient notice period (21-day transitional window)',
        },
        after: {
          violation_sql: 'DATEDIFF(day, j.noticedate, j.effectivedate) < 30',
          severity: 'ERROR',
          violation_reason: 'Insufficient notice period',
        },
        records: {
          newly_failing: 4, newly_passing: 0,
          sample_newly_failing: ['POL-0007', 'POL-0413', 'POL-2110', 'POL-2144'],
          sample_newly_passing: [],
        },
      },
      {
        rule_number: 'A.22-T',
        name: 'Transitional 21-day notice window (2025)',
        change_kind: 'retired',
        before: {
          violation_sql: 'DATEDIFF(day, j.noticedate, j.effectivedate) < 21\nAND j.effectivedate < \'2025-10-01\'',
          severity: 'WARNING',
          violation_reason: 'Below the transitional 21-day window',
        },
        after: null,
        records: {
          newly_failing: 0, newly_passing: 3,
          sample_newly_failing: [],
          sample_newly_passing: ['POL-0021', 'POL-0038', 'POL-2131'],
        },
      },
    ],
    totals: { rules_affected: 2, newly_failing: 4, newly_passing: 3, filings_affected: ['TPA-Q4-2025'] },
  },
};

// One side of a before/after diff. `changed` gets the accent left-border;
// a null side renders as a dashed ghost.
function SideCol({ label, side, changed, ghostText }: {
  label: string;
  side: RuleChangeSide | null;
  changed?: boolean;
  ghostText: string;
}) {
  if (!side) {
    return (
      <div style={{
        border: '1px dashed color-mix(in srgb,var(--color-text) 25%,transparent)',
        minHeight: 130, display: 'grid', placeItems: 'center', padding: 12,
      }}>
        <span className="muted" style={{ fontSize: 11.5, textAlign: 'center' }}>{ghostText}</span>
      </div>
    );
  }
  return (
    <div style={changed
      ? { borderLeft: '3px solid var(--color-accent)', paddingLeft: 12 }
      : { paddingLeft: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 7 }}>
        <span className="k">{label}</span>
        <span style={{ width: 8, height: 8, background: sevDot(side.severity), flex: 'none' }} />
        <span className="mono" style={{ fontSize: 10.5 }}>{side.severity}</span>
      </div>
      <div style={{ fontSize: 12.5, lineHeight: 1.55, marginBottom: 8 }}>{side.violation_reason}</div>
      <div className="mono" style={{
        fontSize: 11, lineHeight: 1.65, padding: '9px 11px', whiteSpace: 'pre-wrap',
        background: 'color-mix(in srgb,var(--color-text) 5%,transparent)',
      }}>
        {side.violation_sql}
      </div>
    </div>
  );
}

function SampleChips({ ids }: { ids: string[] }) {
  return (
    <span style={{ display: 'inline-flex', gap: 5, flexWrap: 'wrap' }}>
      {ids.map((id) => (
        <span key={id} className="tag tag-outline mono" style={{ fontSize: 10 }}>{id}</span>
      ))}
    </span>
  );
}

export function AmendmentsScreen({ user }: { user?: AppUser }) {
  const mayApply = can(user, 'bulletin');
  const bulQ = useBulletins();
  const live = !!bulQ.data;
  const bulletins = bulQ.data?.bulletins?.length ? bulQ.data.bulletins : DEMO_BULLETINS;

  const [selName, setSelName] = useState<string | null>(null);
  const B = bulletins.find((b) => b.name === selName)
    ?? bulletins.find((b) => b.status === 'pending')
    ?? bulletins[0];

  const impactQ = useBulletinImpact(live && B ? B.name : null);
  const kgOffline = !!bulQ.data?.kg_offline
    || (impactQ.error instanceof ApiError && impactQ.error.status === 503);
  // KG offline or warehouse cold → the bundled demo impact keeps the story alive.
  const impact: BulletinImpact | undefined =
    impactQ.data ?? ((!live || kgOffline || impactQ.isError) ? DEMO_IMPACTS[B?.name ?? ''] ?? DEMO_IMPACTS['B-2026-Q4-118'] : undefined);
  const loading = live && !kgOffline && impactQ.isPending;

  const applyMut = useApplyBulletin();

  const cardStyle = (selected: boolean): CSSProperties => ({
    padding: '13px 15px', cursor: 'pointer',
    background: selected ? 'color-mix(in srgb,#5980a6 10%,transparent)' : undefined,
  });

  const kpis = impact ? [
    { label: 'Rules affected', value: String(impact.totals.rules_affected), note: 'in the executable canon' },
    { label: 'Newly failing', value: fmt(impact.totals.newly_failing), note: 'records caught by the amendment' },
    { label: 'Newly passing', value: fmt(impact.totals.newly_passing), note: 'exceptions the amendment clears' },
    { label: 'Filings affected', value: String(impact.totals.filings_affected.length), note: impact.totals.filings_affected.join(' · ') || '—' },
  ] : [];

  return (
    <div className="sc" style={{ display: 'grid', gridTemplateColumns: '262px 1fr', gap: 28, alignItems: 'start' }}>
      {/* ── left rail: bulletin list — uniform cards, own scroll ─────────── */}
      <aside style={{
        display: 'flex', flexDirection: 'column', gap: 14,
        maxHeight: 'max(420px, calc(100vh - 230px))', overflow: 'auto',
      }}>
        <div className="k">Commissioner's bulletins</div>
        {bulletins.map((b) => (
          <Blueprint key={b.name} className="card" style={cardStyle(b.name === B?.name)}
            onClick={() => setSelName(b.name)}>
            <div className="card-kicker" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span>eff. {b.effective_date}</span>
              <span className="tag tag-outline" style={{ marginLeft: 'auto' }}>{juris(b.jurisdiction_code)}</span>
            </div>
            <div className="card-title" style={{ marginTop: 4 }}>{b.name}</div>
            {/* Clamped — the full summary reads in the main pane; the rail is
                for scanning, and unclamped blurbs made card heights wild. */}
            <p className="card-body" style={{
              margin: '5px 0 8px', display: '-webkit-box', WebkitLineClamp: 3,
              WebkitBoxOrient: 'vertical', overflow: 'hidden',
            }}>
              {b.summary}
            </p>
            <div className="card-meta" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className={'tag ' + (b.status === 'applied' ? 'tag-neutral' : 'tag-accent')}>
                {b.status === 'applied' ? 'Applied' : 'Pending review'}
              </span>
              <span className="mono muted" style={{ fontSize: 10.5 }}>{b.targets} rule target{b.targets === 1 ? '' : 's'}</span>
            </div>
          </Blueprint>
        ))}
        {!live && bulQ.isLoading && <span className="k">loading bulletins…</span>}
      </aside>

      {/* ── main: impact analysis ──────────────────────────────────────── */}
      <section>
        {B && (
          <>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 8 }}>
              <h4>{B.name} — {B.title}</h4>
              <span className="k">impact on the executable canon</span>
            </div>
            {/* The full bulletin summary lives here (the rail clamps it). */}
            <p style={{ fontSize: 12.5, lineHeight: 1.65, maxWidth: '92ch', margin: '0 0 16px', color: 'color-mix(in srgb,var(--color-text) 72%,transparent)' }}>
              {B.summary}
            </p>
          </>
        )}

        {kgOffline && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px', marginBottom: 16,
            fontSize: 12.5, background: 'color-mix(in srgb,var(--color-text) 5%,transparent)',
            borderLeft: '3px solid var(--color-neutral-500, #98989b)',
          }}>
            Knowledge graph offline — start Neo4j to compute live impact. Showing the bundled demo analysis.
          </div>
        )}

        {loading && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 22, marginBottom: 24 }}>
            {[0, 1, 2, 3].map((i) => (
              <Blueprint key={i} style={{ padding: '14px 16px 12px', minHeight: 74 }}>
                <div className="k">computing…</div>
                <div style={{ height: 30, marginTop: 8, background: 'color-mix(in srgb,var(--color-text) 7%,transparent)' }} />
              </Blueprint>
            ))}
          </div>
        )}

        {/* No resolved rule targets → nothing to diff or apply. Say so
            instead of rendering four zeros and a live Apply button. */}
        {!loading && impact && impact.totals.rules_affected === 0 && impact.rule_changes.length === 0 && (
          <Blueprint className="gridwash" style={{ padding: '26px 30px', maxWidth: 720 }}>
            <div style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 18, marginBottom: 8 }}>
              No impact on the executable canon
            </div>
            <div style={{ fontSize: 13, lineHeight: 1.7 }}>
              None of this bulletin's provisions resolve to an executable rule —
              its extracted rules are descriptive (no compiled <span className="mono" style={{ fontSize: 12 }}>violation_sql</span>),
              so there is nothing to diff against the validation reference and
              nothing for an amendment to materialize.
            </div>
            <div className="muted" style={{ fontSize: 12, lineHeight: 1.65, marginTop: 12 }}>
              A bulletin gains impact here once its target rules are compiled into
              the edit package. Until then, review its extracted provisions on the
              Rulebook screen — apply is disabled because it would be a no-op.
            </div>
            <button className="btn btn-secondary" disabled style={{ marginTop: 16 }}
              title="no resolved rule targets — nothing to materialize">
              Apply amendment
            </button>
          </Blueprint>
        )}

        {!loading && impact && !(impact.totals.rules_affected === 0 && impact.rule_changes.length === 0) && (
          <>
            {/* KPI row */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 22, marginBottom: 24 }}>
              {kpis.map((k) => (
                <Blueprint key={k.label} style={{ padding: '14px 16px 12px' }}>
                  <div className="k">{k.label}</div>
                  <div style={{ fontFamily: 'var(--font-heading)', fontSize: 32, lineHeight: 1.05, marginTop: 6 }}>{k.value}</div>
                  <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>{k.note}</div>
                </Blueprint>
              ))}
            </div>

            {/* per-rule diffs */}
            {impact.rule_changes.map((rc) => {
              const [kindTag, kindLabel] = KIND_TAG[rc.change_kind];
              return (
                <Blueprint key={rc.rule_number} style={{ padding: '16px 18px', marginBottom: 18 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                    <span className="mono" style={{ fontSize: 12, color: 'var(--color-accent-700)' }}>{rc.rule_number}</span>
                    <h4 style={{ fontSize: 15 }}>{rc.name}</h4>
                    <span className={'tag ' + kindTag} style={{ marginLeft: 'auto' }}>{kindLabel}</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                    <SideCol label="Before" side={rc.before}
                      changed={rc.change_kind === 'retired'}
                      ghostText="no prior rule — introduced by this bulletin" />
                    <SideCol label="After" side={rc.after}
                      changed={rc.change_kind !== 'retired'}
                      ghostText="retired — no successor rule" />
                  </div>

                  {rc.records ? (
                    <div style={{
                      display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 10,
                      marginTop: 14, paddingTop: 12, borderTop: '1px solid var(--color-divider)', fontSize: 12.5,
                    }}>
                      <span>
                        <strong>{fmt(rc.records.newly_failing)}</strong> record{rc.records.newly_failing === 1 ? '' : 's'} newly failing
                      </span>
                      {rc.records.sample_newly_failing.length > 0 && <SampleChips ids={rc.records.sample_newly_failing} />}
                      {rc.records.newly_passing > 0 && (
                        <>
                          <span style={{ marginLeft: 8 }}>
                            <strong>{fmt(rc.records.newly_passing)}</strong> newly passing
                          </span>
                          {rc.records.sample_newly_passing.length > 0 && <SampleChips ids={rc.records.sample_newly_passing} />}
                        </>
                      )}
                    </div>
                  ) : rc.sql_error ? (
                    <div className="muted" style={{ marginTop: 12, fontSize: 11.5 }}>
                      ⚠ record impact unavailable — {rc.sql_error}
                    </div>
                  ) : null}
                </Blueprint>
              );
            })}

            {/* apply bar */}
            {B?.status === 'pending' ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 6 }}>
                <button className="btn btn-primary"
                  disabled={!live || !mayApply || applyMut.isPending}
                  title={mayApply ? undefined : `requires ${whoCan('bulletin')}`}
                  onClick={() => applyMut.mutate(undefined, {
                    onSuccess: () => toast(`${B.name} applied — canon rebuilt, validation re-running`),
                  })}>
                  {applyMut.isPending ? 'Applying amendment…' : 'Apply amendment'}
                </button>
                <span className="k">materializes the rule changes into the canon and re-runs validation</span>
                {applyMut.error != null && (
                  <span className="k" style={{ marginLeft: 'auto', color: 'var(--color-accent-700)' }}>
                    {applyMut.error instanceof ApiError ? applyMut.error.message : 'apply failed'}
                  </span>
                )}
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 6 }}>
                <span className="tag tag-neutral">Applied — validation reference updated</span>
                <span className="k">the executable canon carries these changes</span>
              </div>
            )}
          </>
        )}

        {!loading && !impact && !impactQ.isError && (
          <span className="k">select a bulletin to compute its impact</span>
        )}
      </section>
    </div>
  );
}
