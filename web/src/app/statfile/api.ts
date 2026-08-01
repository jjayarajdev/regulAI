// STATFILE data layer — React Query hooks over /api/rhs plus pure mappers
// that shape API responses into the structures the screens render. Every
// screen keeps the design fixtures as fallback: when the warehouse is cold or
// a query fails, the UI degrades to demo content instead of breaking.
import { useQuery } from '@tanstack/react-query';
import { getJson } from '../../api/client';
import type {
  Filing, FilingsResponse, KgNeighborhoodResponse, KgRulesResponse,
  PipelineStateResponse, Violation,
} from '../../api/types';
import type { ValidateAllResponse } from '../experience/api';
import {
  CYCLES, ERRORS, LAYERS, MEDALLION, QUEUE,
  type Cycle, type EditError, type MedallionLayer, type QueueItem,
} from './data';

// ── hooks ──────────────────────────────────────────────────────────────────
export const useFilings = () =>
  useQuery({ queryKey: ['sf', 'filings'], queryFn: () => getJson<FilingsResponse>('/filings') });

export const useValidateAll = () =>
  useQuery({ queryKey: ['sf', 'validate-all'], queryFn: () => getJson<ValidateAllResponse>('/validate/all') });

export const usePipelineState = () =>
  useQuery({
    queryKey: ['sf', 'pipeline-state'],
    queryFn: () => getJson<PipelineStateResponse>('/pipeline/state'),
  });

export const useKgRules = () =>
  useQuery({ queryKey: ['sf', 'kg-rules'], queryFn: () => getJson<KgRulesResponse>('/kg/rules') });

export interface CitationMatch {
  section_id: string; document_id: string; citation_label: string;
  section_heading: string; section_text: string;
  title: string; document_type: string; issuing_body: string; edition: string;
}
export const useCitation = (q: string | null) =>
  useQuery({
    queryKey: ['sf', 'citation', q],
    queryFn: () => getJson<{ matches: CitationMatch[] }>('/reg/citation?q=' + encodeURIComponent(q!)),
    enabled: !!q,
  });

export interface PolicyFieldsResponse { policy_number: string; fields: Record<string, string | number | null> }
export const usePolicyFields = (policy: string | null) =>
  useQuery({
    queryKey: ['sf', 'policy', policy],
    queryFn: () => getJson<PolicyFieldsResponse>('/bronze/policy/' + encodeURIComponent(policy!)),
    enabled: !!policy,
  });

export interface SubmissionResponse {
  policy_number: string; found: boolean; note?: string;
  fields?: Record<string, string | number | null>;
}
export const useSubmission = (policy: string | null) =>
  useQuery({
    queryKey: ['sf', 'submission', policy],
    queryFn: () => getJson<SubmissionResponse>('/submission/' + encodeURIComponent(policy!)),
    enabled: !!policy,
  });

export interface CatalogTable { table_name: string; row_count: number; comment: string; last_altered: string | null }
export interface CatalogSchema {
  schema: string; description: string; table_count: number;
  populated_count: number; total_rows: number; tables: CatalogTable[];
}
export const useCatalog = () =>
  useQuery({
    queryKey: ['sf', 'catalog'],
    queryFn: () => getJson<{ schemas: CatalogSchema[] }>('/catalog'),
  });

export const useNeighborhood = (ruleId: string | null) =>
  useQuery({
    queryKey: ['sf', 'kg-neighborhood', ruleId],
    queryFn: () => getJson<KgNeighborhoodResponse>('/kg/neighborhood/' + encodeURIComponent(ruleId!)),
    enabled: !!ruleId,
  });

export interface AgentRunRow {
  run_id: string; agent: string; task: string; model: string | null;
  tokens: number | null; duration_ms: number | null; confidence: number | null;
  result: string; status: string; ran_at: string;
}
export interface AgentRunsResponse {
  runs: AgentRunRow[];
  stats: { runs: number; tokens: number; mean_confidence: number | null; escalated: number };
}
export const useAgentRuns = () =>
  useQuery({ queryKey: ['sf', 'agent-runs'], queryFn: () => getJson<AgentRunsResponse>('/agents/runs') });

export interface RegDocument {
  document_id: string; document_type: string; title: string; issuing_body: string;
  edition: string; effective_date: string; word_count: number; page_count: number; loaded_at: string;
}
export const useRegDocuments = () =>
  useQuery({
    queryKey: ['sf', 'reg-documents'],
    queryFn: () => getJson<{ documents: RegDocument[] }>('/reg/documents'),
  });

// ── mappers ────────────────────────────────────────────────────────────────
const fmt = (n: number) => n.toLocaleString('en-US');

const STATUS_TAG: Record<string, string> = {
  'In validation': 'tag-accent', Filed: 'tag-neutral', Onboarding: 'tag-outline',
};

export function cyclesFromFilings(filings: Filing[], val?: ValidateAllResponse): Cycle[] {
  if (!filings.length) return CYCLES;
  return filings.map((f) => {
    const v = val?.by_filing[f.id];
    const status = !f.is_active ? 'Filed' : v && v.summary.total_violations > 0 ? 'In validation' : 'Validated';
    return {
      state: (f.jurisdiction_code || '').replace(/^US-/, '') || '—',
      line: f.plan_name,
      std: f.plan_code,
      period: `${f.period_start} → ${f.period_end}`.slice(0, 17),
      due: f.due_date,
      records: v ? fmt(v.summary.total_violations) : '—',
      status,
      tagClass: STATUS_TAG[status] ?? 'tag-outline',
      goTo: 'val',
    };
  });
}

export interface Kpi { label: string; value: string; note: string }
export function kpisFrom(
  filings: Filing[], val?: ValidateAllResponse, pipe?: PipelineStateResponse, rulesPending?: number,
): Kpi[] {
  const gold = pipe?.layers.find((l) => l.layer === 'GOLD');
  const violations = val ? Object.values(val.by_filing).flatMap((f) => f.violations) : [];
  const blocking = violations.filter((v) => v.severity === 'ERROR').length;
  const due = filings.filter((f) => f.is_active).map((f) => f.due_date).sort()[0];
  const days = due ? Math.max(0, Math.round((+new Date(due) - Date.now()) / 86400000)) : null;
  return [
    { label: 'Records staged', value: gold ? fmt(gold.row_total) : '—', note: 'gold · all filings' },
    { label: 'Open exceptions', value: val ? fmt(violations.length) : '—', note: `${fmt(blocking)} blocking the package` },
    { label: 'Rules pending', value: rulesPending != null ? String(rulesPending) : '—', note: 'human approval gate' },
    { label: 'Days to due', value: days != null ? String(days) : '—', note: due ? `TDI · ${due}` : '—' },
  ];
}

export function layersFrom(pipe?: PipelineStateResponse) {
  if (!pipe?.layers.length) return LAYERS;
  const max = Math.max(...pipe.layers.map((l) => l.row_total || 0), 1);
  const order = ['BRONZE', 'SILVER', 'GOLD'];
  return [...pipe.layers]
    .sort((a, b) => order.indexOf(a.layer) - order.indexOf(b.layer))
    .map((l) => ({
      name: l.layer.charAt(0) + l.layer.slice(1).toLowerCase(),
      pct: Math.max(4, Math.round(((l.row_total || 0) / max) * 100)) + '%',
      meta: `${l.table_count} tables · ${fmt(l.row_total || 0)} rows`,
    }));
}

// Group violations by rule → the triage table rows.
export interface GroupedError extends EditError { violations: Violation[] }
export function groupViolations(val?: ValidateAllResponse): GroupedError[] {
  if (!val) return ERRORS.map((e) => ({ ...e, violations: [] }));
  const all = Object.values(val.by_filing).flatMap((f) => f.violations);
  if (!all.length) return ERRORS.map((e) => ({ ...e, violations: [] }));
  const by = new Map<string, Violation[]>();
  for (const v of all) {
    const k = v.rule_number || v.rule_id;
    if (!by.has(k)) by.set(k, []);
    by.get(k)!.push(v);
  }
  return [...by.entries()]
    .map(([code, vs]) => {
      const v = vs[0];
      const sev = v.severity === 'ERROR' ? 2 : v.severity === 'WARNING' ? 1 : 0;
      return {
        code,
        field: v.rule_name,
        desc: v.violation_reason,
        count: fmt(vs.length),
        origin: v.citation || 'Rule engine',
        sev: sev as 0 | 1 | 2,
        status: sev === 2 ? 'Blocking' : sev === 1 ? 'Warn' : 'Info',
        violations: vs,
      };
    })
    .sort((a, b) => b.sev - a.sev || b.violations.length - a.violations.length);
}

// Catalog schemas → the three medallion layer cards. Keeps the design's layer
// descriptions (they describe the architecture, not the data) but swaps in
// real tables, row counts and last-run times.
const abbrev = (n: number) =>
  n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? (n / 1e3).toFixed(1) + 'K' : String(n);

export function medallionFrom(schemas?: CatalogSchema[]): MedallionLayer[] {
  const bySchema = new Map((schemas ?? []).map((s) => [s.schema, s]));
  if (!['BRONZE', 'SILVER', 'GOLD'].some((n) => bySchema.get(n)?.tables.length)) return MEDALLION;
  return MEDALLION.map((demo) => {
    const s = bySchema.get(demo.name);
    if (!s || !s.tables.length) return demo;
    const last = s.tables.map((t) => t.last_altered).filter(Boolean).sort().at(-1);
    return {
      ...demo,
      status: s.populated_count > 0 ? 'Fresh' : 'Empty',
      tagClass: s.populated_count > 0 ? 'tag-neutral' : 'tag-outline',
      latency: `${s.populated_count}/${s.table_count} populated`,
      last: last ? last.slice(11, 16) || last.slice(0, 10) : '—',
      tables: [...s.tables]
        .sort((a, b) => b.row_count - a.row_count)
        .slice(0, 7)
        .map((t) => [`${demo.name.toLowerCase()}.${t.table_name.toLowerCase()}`, abbrev(t.row_count)] as [string, string]),
    };
  });
}

// Unique failing policies across every filing — the record inspector's
// navigable set (the interesting records are the ones with open edits).
export function policiesFrom(val?: ValidateAllResponse): string[] {
  if (!val) return [];
  const seen = new Set<string>();
  for (const f of Object.values(val.by_filing)) {
    for (const v of f.violations) seen.add(v.policy_number);
  }
  return [...seen].sort();
}

export function queueFrom(errors: GroupedError[], rulesPending?: number): QueueItem[] {
  if (!errors.some((e) => e.violations.length)) return QUEUE;
  const items: QueueItem[] = errors
    .filter((e) => e.sev === 2)
    .slice(0, 3)
    .map((e) => ({
      kicker: 'Exception',
      title: `${e.count} × ${e.field}`,
      body: e.desc,
      meta: e.code,
      goTo: 'val' as const,
    }));
  if (rulesPending) {
    items.unshift({
      kicker: 'Approval gate',
      title: `${rulesPending} rules await sign-off`,
      body: 'Draft or amended rules require human approval before the cycle can close.',
      meta: 'Blocks seal',
      goTo: 'rules',
    });
  }
  return items.slice(0, 4);
}
