import type { Filing, StateResponse } from '../../api/types';
import type { FilingAgg } from './ExperienceApp';
import type { ExpRecord } from './api';

type Dot = 'green' | 'red' | 'purple' | 'amber' | 'grey';
interface Card { n: number; dot: Dot; lbl: string }

function KpiRow({ title, sub, cards }: { title: string; sub: string; cards: Card[] }) {
  return (
    <>
      <div className="sect-h">{title}</div>
      <div className="sect-sub">{sub}</div>
      <div className="kpi-row">
        {cards.map((c, i) => (
          <div className="kpi" key={i}>
            <div className="n"><span className={`dot ${c.dot}`} />{c.n.toLocaleString()}</div>
            <div className="lbl">{c.lbl}</div>
          </div>
        ))}
      </div>
    </>
  );
}

export function Dashboard({ filings, records, byFiling, bulletin }: {
  filings: Filing[]; records: ExpRecord[]; byFiling: Record<string, FilingAgg>; bulletin?: StateResponse;
}) {
  const today = new Date();
  const overdue = filings.filter((f) => f.due_date && new Date(f.due_date) < today).length;
  const withExc = filings.filter((f) => (byFiling[f.id]?.count || 0) > 0).length;
  const active = filings.filter((f) => f.is_active !== false).length;
  const flagged = new Set(records.map((r) => r.id)).size;
  const errors = records.filter((r) => r.severity === 'ERROR').length;
  const warns = records.filter((r) => r.severity === 'WARNING').length;
  const rules = new Set(records.map((r) => r.ruleNumber).filter(Boolean)).size;

  const jurs = [...new Set(filings.map((f) => f.jurisdiction_code))];
  const bull = bulletin?.bulletin_applied
    ? `bulletin ${bulletin.bulletin_id} applied`
    : bulletin?.bulletin_id ? `${bulletin.bulletin_id} pending` : 'canon v1';

  const filingCards: Card[] = [
    { n: filings.length, dot: 'purple', lbl: 'Total filings' },
    { n: active, dot: 'green', lbl: 'Active this cycle' },
    { n: overdue, dot: overdue ? 'red' : 'grey', lbl: 'Overdue' },
    { n: withExc, dot: withExc ? 'red' : 'green', lbl: 'With open exceptions' },
    { n: filings.length - withExc, dot: 'green', lbl: 'Clean' },
  ];
  const valCards: Card[] = [
    { n: records.length, dot: records.length ? 'red' : 'green', lbl: 'Total violations' },
    { n: flagged, dot: flagged ? 'purple' : 'grey', lbl: 'Records flagged' },
    { n: errors, dot: errors ? 'red' : 'grey', lbl: 'Errors (blockers)' },
    { n: warns, dot: warns ? 'amber' : 'grey', lbl: 'Warnings' },
    { n: rules, dot: 'purple', lbl: 'Rules triggered' },
  ];

  return (
    <>
      <div className="pghead">
        <h1>Dashboard</h1>
        <span className="pill">Q4 2025 <span className="cv">cycle</span> <span className="cv">▾</span></span>
        <span className="pill">{jurs.join(' · ') || 'All jurisdictions'} <span className="cv">▾</span></span>
        <span className="pill">{bull} <span className="cv">▾</span></span>
      </div>
      <div className="content">
        <KpiRow title="Filing obligations" sub="Statutory filings for the current reporting cycle" cards={filingCards} />
        <KpiRow title="Validation" sub="Rule-engine results across the current filings" cards={valCards} />
      </div>
    </>
  );
}
