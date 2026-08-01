import { useMemo, useState } from 'react';
import { Database, LayoutDashboard, Rows3, Settings } from 'lucide-react';
import type { Filing, ValidateResponse } from '../../api/types';
import { ExpRecord, mapViolation, useBackendState, useFilings, useValidateAll } from './api';
import { Dashboard } from './Dashboard';
import { Records } from './Records';
import { RecordDetail } from './RecordDetail';
import './experience.css';

export type FilingAgg = { filing: Filing; summary: Partial<ValidateResponse['summary']>; count: number; runId?: string | null };
export type Screen = 'dashboard' | 'records' | 'sources';

export function ExperienceApp() {
  const filingsQ = useFilings();
  const stateQ = useBackendState();
  const filings = filingsQ.data?.filings ?? [];
  const valQ = useValidateAll();

  const { records, byFiling } = useMemo(() => {
    const recs: ExpRecord[] = [];
    const bf: Record<string, FilingAgg> = {};
    const byId = valQ.data?.by_filing ?? {};
    filings.forEach((f) => {
      const v = byId[f.id];
      const viol = v?.violations ?? [];
      bf[f.id] = { filing: f, summary: v?.summary ?? {}, count: viol.length, runId: v?.run_id };
      viol.forEach((x) => recs.push(mapViolation(f, x)));
    });
    return { records: recs, byFiling: bf };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filings, valQ.dataUpdatedAt]);

  const live = !filingsQ.isError && filings.length > 0;
  const loading = filingsQ.isLoading || valQ.isLoading;
  const dataError = valQ.isError && !valQ.isLoading;
  const dataErrorMsg = (valQ.error as Error | undefined)?.message;

  const [screen, setScreen] = useState<Screen>('dashboard');
  const [current, setCurrent] = useState<ExpRecord | null>(null);

  const bulletin = stateQ.data;
  const stillFailing = current
    ? records.some((r) => r.id === current.id && r.ruleNumber === current.ruleNumber && r.filingId === current.filingId)
    : false;

  const openRecord = (r: ExpRecord) => setCurrent(r);
  const openLookup = (policy: string) => {
    const hit = records.find((r) => r.id === policy);
    setCurrent(hit ?? {
      key: 'lookup/' + policy, id: policy, jur: '—', plan: '—', filingId: '', carrier: '—',
      ruleNumber: '', ruleName: '—', severity: '', status: 'clean', stage: 'Validated',
      reason: '', reasonFull: 'No violations — clean record, ready for submission.', citation: '—', recordId: '',
    });
  };

  const RailBtn = ({ id, Icon, title }: { id: Screen; Icon: typeof Database; title: string }) => (
    <button className={screen === id && !current ? 'active' : ''} title={title}
      onClick={() => { setCurrent(null); setScreen(id); }}>
      <Icon className="ic" size={20} strokeWidth={1.8} />
    </button>
  );

  return (
    <div className="exp">
      <div className="head">
        <div className="brand">Regul<span>AI</span></div>
        <div className="right">
          <span className="env">
            <span className={'lv' + (dataError || !live ? ' mock' : '')} />
            {loading ? 'connecting…' : dataError ? 'warehouse offline' : live ? 'live data' : 'offline'} · Lone Star Mutual · Q4 2025
          </span>
          <div className="avatar">DR</div>
        </div>
      </div>

      <div className="shell">
        <nav className="rail">
          <RailBtn id="dashboard" Icon={LayoutDashboard} title="Dashboard" />
          <RailBtn id="records" Icon={Rows3} title="Records" />
          <RailBtn id="sources" Icon={Database} title="Sources" />
          <div className="grow" />
          <button title="Settings"><Settings className="ic" size={20} strokeWidth={1.8} /></button>
        </nav>

        <main className="main">
          {dataError && (
            <div className="databanner">
              <b>Data unavailable</b> — {dataErrorMsg && !/→ \d+$/.test(dataErrorMsg)
                ? dataErrorMsg
                : "the Databricks warehouse isn't responding."}{' '}
              Filings load, but records &amp; validation counts need the warehouse — they show 0 until it recovers.
            </div>
          )}
          {current ? (
            <RecordDetail
              key={current.key}
              record={current}
              agg={byFiling[current.filingId]}
              stillFailing={stillFailing}
              bulletinApplied={!!bulletin?.bulletin_applied}
              bulletinId={bulletin?.bulletin_id}
              onBack={() => setCurrent(null)}
            />
          ) : screen === 'dashboard' ? (
            <Dashboard filings={filings} records={records} byFiling={byFiling} bulletin={bulletin} />
          ) : screen === 'records' ? (
            <Records filings={filings} records={records} byFiling={byFiling}
              onOpen={openRecord} onLookup={openLookup} />
          ) : (
            <Sources />
          )}
        </main>
      </div>
    </div>
  );
}

function Sources() {
  return (
    <>
      <div className="pghead"><h1>Sources</h1><span className="pill">Databricks</span></div>
      <div className="content">
        <div className="sect-h">Data onboarding</div>
        <div className="sect-sub">Get carrier data into the canonical model.</div>
        <div className="kpi-row" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
          <a href="/admin/crawler" className="kpi" style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="n"><span className="dot green" />DB Crawler</div>
            <div className="lbl">Introspect a source DB → agent crawl plan → transform</div></a>
          <a href="/admin/mapping" className="kpi" style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="n"><span className="dot purple" />File onboarding</div>
            <div className="lbl">Profile a file → propose mapping → review → validate</div></a>
          <a href="/admin/regulations" className="kpi" style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="n"><span className="dot green" />Regulations</div>
            <div className="lbl">Upload a bulletin/regulation PDF → Sentinel (LLM) → KG</div></a>
        </div>
      </div>
    </>
  );
}
