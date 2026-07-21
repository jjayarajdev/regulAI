import { useState } from 'react';
import { ChevronRight, Download, SlidersHorizontal, Users } from 'lucide-react';
import type { Filing } from '../../api/types';
import type { FilingAgg } from './ExperienceApp';
import type { ExpRecord, RecStatus } from './api';

const STATUS: Record<RecStatus, { dot: string; label: string }> = {
  clean: { dot: 'green', label: 'Clean' },
  blocked: { dot: 'red', label: 'Blocked' },
  warning: { dot: 'amber', label: 'Warning' },
  review: { dot: 'purple', label: 'In Review' },
};

export function Records({ filings, records, byFiling, onOpen, onLookup }: {
  filings: Filing[]; records: ExpRecord[]; byFiling: Record<string, FilingAgg>;
  onOpen: (r: ExpRecord) => void; onLookup: (policy: string) => void;
}) {
  const [filter, setFilter] = useState<string>('all');
  const [lookup, setLookup] = useState('');

  const rows = records.filter((r) => (filter === 'all' ? true : r.filingId === filter));
  const errors = records.filter((r) => r.severity === 'ERROR').length;
  const warns = records.filter((r) => r.severity === 'WARNING').length;
  const flagged = new Set(records.map((r) => r.id)).size;
  const tabs = [{ k: 'all', label: 'All records', n: records.length },
    ...filings.map((f) => ({ k: f.id, label: f.id, n: byFiling[f.id]?.count || 0 }))];

  const doLookup = () => { const v = lookup.trim().toUpperCase(); if (v.startsWith('POL-')) onLookup(v); };

  return (
    <>
      <div className="pghead">
        <h1>Records</h1>
        <span className="pill">Q4 2025 <span className="cv">▾</span></span>
        <span className="pill">All jurisdictions <span className="cv">▾</span></span>
        <span className="pill">All carriers <span className="cv">▾</span></span>
      </div>
      <div className="content">
        <div className="stagebar">
          <span className="lead">Filter by filing</span>
          {tabs.map((t) => (
            <button key={t.k} className={`stage ${filter === t.k ? 'active' : ''}`} onClick={() => setFilter(t.k)}>
              {t.label}<span className="count">{t.n.toLocaleString()}</span>
            </button>
          ))}
        </div>
        <div className="filtbar">
          <span className="lead">Filter by status</span>
          <span className="statf sel"><span className="dot red" /><span className="num">{errors}</span> Errors</span>
          <span className="statf"><span className="dot amber" /><span className="num">{warns}</span> Warnings</span>
          <span className="statf"><span className="dot purple" /><span className="num">{flagged}</span> Records flagged</span>
          <span style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
            <span className="lead">View any record</span>
            <input value={lookup} onChange={(e) => setLookup(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && doLookup()} placeholder="POL-0001"
              style={{ font: 'inherit', fontSize: 12.5, border: '1px solid var(--exp-border)', borderRadius: 7, padding: '6px 9px', width: 150 }} />
            <button className="btn plain" onClick={doLookup} style={{ padding: '6px 11px', fontSize: 12.5 }}>Open →</button>
          </span>
        </div>

        <div className="tbl-wrap">
          <div className="tbl-tools">
            <button className="btn plain"><Users className="ic" size={15} />Assign</button>
            <button className="btn plain"><Download className="ic" size={15} />Download .csv</button>
            <button className="btn primary"><SlidersHorizontal className="ic" size={15} />Filters</button>
          </div>
          {rows.length ? (
            <>
              <table>
                <thead><tr>
                  <th style={{ width: 34 }}><input type="checkbox" className="cb" /></th>
                  <th style={{ width: 80 }}>Jur.</th><th style={{ width: 70 }}>Plan</th><th>Record ID</th>
                  <th style={{ width: 80 }}>Rule</th><th style={{ width: 120 }}>Status</th>
                  <th>Reason</th><th>Carrier</th><th style={{ width: 40 }}></th>
                </tr></thead>
                <tbody>
                  {rows.map((r) => {
                    const st = STATUS[r.status];
                    return (
                      <tr key={r.key} className="clickable" onClick={() => onOpen(r)}>
                        <td><input type="checkbox" className="cb" onClick={(e) => e.stopPropagation()} /></td>
                        <td><span className="tag">{r.jur}</span></td>
                        <td>{r.plan}</td>
                        <td className="mono"><b>{r.id}</b></td>
                        <td className="mono">{r.ruleNumber || '—'}</td>
                        <td><span className="st"><span className={`dot ${st.dot}`} />{st.label}</span></td>
                        <td style={{ color: 'var(--exp-muted)' }}>{r.reason}</td>
                        <td>{r.carrier}</td>
                        <td><span className="chev"><ChevronRight size={15} /></span></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div className="tbl-foot">Records <b style={{ color: 'var(--exp-ink)' }}>1–{rows.length}</b> of {rows.length} · Per page 25</div>
            </>
          ) : (
            <div className="empty-note">No exceptions for this filing — all records passing. ✓</div>
          )}
        </div>
      </div>
    </>
  );
}
