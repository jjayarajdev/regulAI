// STATFILE data layer — React Query hooks over /api/rhs plus pure mappers
// that shape API responses into the structures the screens render. Every
// screen keeps the design fixtures as fallback: when the warehouse is cold or
// a query fails, the UI degrades to demo content instead of breaking.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getJson, patchJson, postJson, setToken } from '../../api/client';
import type {
  BulletinApplyResponse, BulletinImpact, BulletinsResponse,
  Filing, FilingFileResponse, FilingsResponse, KgNeighborhoodResponse, KgRulesResponse,
  PipelineStateResponse, SendFilingResponse, SubmissionState, Violation,
} from '../../api/types';
import type { ValidateAllResponse } from '../experience/api';
import {
  CYCLES, ERRORS, LAYERS, MEDALLION, QUEUE,
  type Cycle, type EditError, type MedallionLayer, type QueueItem,
} from './data';

// ── identity & RBAC ────────────────────────────────────────────────────────
export type Role = 'viewer' | 'analyst' | 'actuary' | 'admin' | 'cco';
export interface AppUser {
  user_id: string; name: string; role: Role; title: string;
  email?: string | null; active?: boolean;
}
export const GUEST: AppUser = { user_id: 'guest', name: 'Guest', role: 'viewer', title: 'Read-only' };

// Mirror of the server's ROLE_GRANTS — the server check is authoritative;
// this only decides what the UI offers.
const GRANTS: Record<string, Role[]> = {
  rule_decision: ['admin', 'cco'],
  suppress:      ['admin', 'cco'],
  assign:        ['analyst', 'actuary', 'admin', 'cco'],
  fix:           ['analyst', 'actuary', 'admin', 'cco'],
  run_pipeline:  ['analyst', 'actuary', 'admin', 'cco'],
  sign_analyst:  ['analyst'],
  sign_actuary:  ['actuary'],
  sign_officer:  ['cco'],
  seal:          ['cco'],
  ack:           ['cco'],
  send:          ['cco'],
  mapping:       ['admin', 'cco'],
  bulletin:      ['admin', 'cco'],
  manage_users:  ['admin', 'cco'],
};
export const can = (user: AppUser | undefined, perm: string): boolean =>
  !!user && (GRANTS[perm] ?? []).includes(user.role);
export const whoCan = (perm: string): string => (GRANTS[perm] ?? []).join(' / ');

// Which nav screens each role sees. Spec/canon management (rulebook, KG,
// standards, ISO) is the admin's world; the agent console is oversight;
// validation + record are the preparer/reviewer workbenches; the dashboard
// is the shared status board.
import type { ScreenId } from './data';
export const SCREEN_ACCESS: Record<ScreenId, Role[]> = {
  dash:   ['viewer', 'analyst', 'actuary', 'admin', 'cco'],
  val:    ['analyst', 'actuary', 'admin', 'cco'],
  record: ['analyst', 'actuary', 'admin', 'cco'],
  filing: ['analyst', 'actuary', 'admin', 'cco'],
  amend:  ['analyst', 'actuary', 'admin', 'cco'],
  pipe:   ['analyst', 'admin', 'cco'],
  agents: ['admin', 'cco'],
  rules:  ['admin', 'cco'],
  graph:  ['admin', 'cco'],
  iso:    ['admin', 'cco'],
  config: ['admin', 'cco'],
  users:  ['admin', 'cco'],
};
export const canSee = (user: AppUser | undefined, screen: ScreenId): boolean =>
  (SCREEN_ACCESS[screen] ?? []).includes(user?.role ?? 'viewer');

export const useUsers = () =>
  useQuery({
    queryKey: ['sf', 'users'],
    queryFn: () => getJson<{ users: AppUser[] }>('/auth/users'),
    staleTime: Infinity,
  });

// Session: who am I (resolved from the stored token server-side).
export const useMe = () =>
  useQuery({
    queryKey: ['sf', 'me'],
    queryFn: () => getJson<{ user: AppUser }>('/auth/me'),
    staleTime: 60_000,
  });
export const useLogin = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (creds: { email: string; password: string }) =>
      postJson<{ token: string; user: AppUser }>('/auth/login', creds),
    // Store the token BEFORE invalidating — /auth/me must refetch with it.
    onSuccess: (r) => { setToken(r.token); qc.invalidateQueries(); },
  });
};
export const useLogout = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => postJson<{ ok: boolean }>('/auth/logout'),
    onSettled: () => { setToken(null); qc.invalidateQueries(); },
  });
};

// Admin user management.
export const useAdminUsers = (enabled: boolean) =>
  useQuery({
    queryKey: ['sf', 'admin-users'],
    queryFn: () => getJson<{ users: AppUser[] }>('/auth/admin/users'),
    enabled,
  });
export const useSaveUser = () => {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['sf', 'admin-users'] });
    qc.invalidateQueries({ queryKey: ['sf', 'users'] });
  };
  return {
    create: useMutation({
      mutationFn: (u: { name: string; email: string; role: Role; title?: string; password?: string }) =>
        postJson<{ ok: boolean; user: AppUser }>('/auth/admin/users', u),
      onSettled: invalidate,
    }),
    update: useMutation({
      mutationFn: ({ userId, ...patch }: { userId: string; role?: Role; active?: boolean; password?: string; name?: string; title?: string }) =>
        patchJson<{ ok: boolean; user: AppUser }>(`/auth/admin/users/${encodeURIComponent(userId)}`, patch),
      onSettled: invalidate,
    }),
  };
};

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
export interface ContractColumn {
  name: string; dtype: string; description: string; required: boolean;
  domain_encoded: boolean; source: string | null; transform: string | null;
  rule: string | null; coverage_pct: number | null;
}
export interface PipelineContractResponse { target: string; row_count: number; columns: ContractColumn[] }
export const usePipelineContract = () =>
  useQuery({
    queryKey: ['sf', 'pipeline-contract'],
    queryFn: () => getJson<PipelineContractResponse>('/pipeline/contract'),
  });

export const useCatalog = () =>
  useQuery({
    queryKey: ['sf', 'catalog'],
    queryFn: () => getJson<{ schemas: CatalogSchema[] }>('/catalog'),
  });

// Persist an approve/reject decision on a canon rule, then refetch the queue
// (and the dashboard's rules-pending KPI, which reads the same query).
export const useRuleDecision = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ruleId, decision }: { ruleId: string; decision: 'approved' | 'rejected' }) =>
      postJson<{ ok: boolean; rule: { id: string; status: string } }>(
        `/kg/rules/${encodeURIComponent(ruleId)}/decision`, { decision },
      ),
    onSettled: () => qc.invalidateQueries({ queryKey: ['sf', 'kg-rules'] }),
  });
};

// Run the full cycle: Bronze→Silver, Silver→Gold, then let every query
// refetch (validation re-runs on the fresh gold). Long-running — Databricks.
export const useRunCycle = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const silver = await postJson<{ ok: boolean }>('/pipeline/silver');
      const gold = await postJson<{ ok: boolean }>('/pipeline/gold');
      return { ok: silver.ok && gold.ok };
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['sf'] }),
  });
};

// Canon diff — every node mutated since the given ISO time.
export interface KgDiffNode { id: string; type: string; name: string; created_at?: string; change_summary?: string; effective_until?: string }
export interface KgDiffResponse {
  scope: string; from: string; total_changes: number;
  added_nodes: KgDiffNode[]; modified_nodes: KgDiffNode[]; superseded_nodes: KgDiffNode[];
  added_edges: Array<{ src_name: string; dst_name: string; type: string }>;
  audit_entries: Array<{ id: string; action: string; actor: string; summary: string; occurred_at: string; affected_count: number }>;
}
export const useKgDiff = (since: string | null) =>
  useQuery({
    queryKey: ['sf', 'kg-diff', since],
    queryFn: () => getJson<KgDiffResponse>('/kg/diff?since=' + encodeURIComponent(since!)),
    enabled: !!since,
  });

// Every staged policy — the inspector's full navigable set (clean included).
export const useSubmissionPolicies = (filing: string | null) =>
  useQuery({
    queryKey: ['sf', 'submission-policies', filing],
    queryFn: () => getJson<{ policies: string[]; total: number }>(
      '/submission/policies/list' + (filing ? '?filing=' + encodeURIComponent(filing) : '')),
    staleTime: 300_000,
  });

// Reconciliation: stat-side gold records tied to the BillingCenter GL ledger.
export interface ReconLine {
  label: string; stat: number; gl: number; delta: number; money: boolean;
  status: 'Tie' | 'Variance';
}
export const useReconciliation = (filingId: string | null) =>
  useQuery({
    queryKey: ['sf', 'recon', filingId],
    queryFn: () => getJson<{ filing_id: string; lines: ReconLine[] }>(
      '/reconciliation/' + encodeURIComponent(filingId!)),
    enabled: !!filingId,
  });

// Sign-off chain: approval state + advancing actions for the active filing.
export interface ApprovalState {
  filing_id: string; status: string; open_blockers: number;
  next_role: 'analyst' | 'actuary' | 'officer' | null; can_seal: boolean;
  submitted_at: string | null; acked_at: string | null;
}
export const useApprovalState = (filingId: string | null) =>
  useQuery({
    queryKey: ['sf', 'approval', filingId],
    queryFn: () => getJson<ApprovalState>('/filing/' + encodeURIComponent(filingId!) + '/approval-state'),
    enabled: !!filingId,
  });
export const useAdvanceFiling = () => {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['sf', 'approval'] });
    qc.invalidateQueries({ queryKey: ['sf', 'filings'] });
    qc.invalidateQueries({ queryKey: ['sf', 'submission-state'] });
    qc.invalidateQueries({ queryKey: ['sf', 'filing-file'] });
  };
  return {
    approve: useMutation({
      mutationFn: ({ filingId, role }: { filingId: string; role: string }) =>
        postJson<{ ok: boolean }>(`/filing/${encodeURIComponent(filingId)}/approve`, { role }),
      onSettled: invalidate,
    }),
    // Sealing renders + persists the submission file (state → submitted).
    seal: useMutation({
      mutationFn: (filingId: string) =>
        getJson<{ sha256?: string }>(`/filing/${encodeURIComponent(filingId)}/file?persist=true`),
      onSettled: invalidate,
    }),
    ack: useMutation({
      mutationFn: (filingId: string) =>
        postJson<{ receipt_id?: string }>(`/filing/${encodeURIComponent(filingId)}/ack`),
      onSettled: invalidate,
    }),
  };
};

// Submission journey: the whole seal → send → ack → archive story for one
// filing. Polled at the default refetchInterval so a regulator ACK landing
// server-side shows up without a reload.
export const useSubmissionState = (filingId: string | null) =>
  useQuery({
    queryKey: ['sf', 'submission-state', filingId],
    queryFn: () => getJson<SubmissionState>('/filing/' + encodeURIComponent(filingId!) + '/submission'),
    enabled: !!filingId,
  });

// Rendered fixed-width package (read-only; sealing goes through
// useAdvanceFiling().seal which hits the same endpoint with persist=true).
export const useFilingFile = (filingId: string | null) =>
  useQuery({
    queryKey: ['sf', 'filing-file', filingId],
    queryFn: () => getJson<FilingFileResponse>('/filing/' + encodeURIComponent(filingId!) + '/file'),
    enabled: !!filingId,
    staleTime: 60_000,
  });

// Transmit the sealed package to the regulator (email + SFTP drop + archive).
export const useSendFiling = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ filingId, subject, body, to }: { filingId: string; subject?: string; body?: string; to?: string[] }) =>
      postJson<SendFilingResponse>(`/filing/${encodeURIComponent(filingId)}/send`, { subject, body, to }),
    onSettled: () => qc.invalidateQueries({ queryKey: ['sf'] }),
  });
};

// Regulatory bulletins + per-bulletin impact analysis (KG-computed diff of
// the executable canon plus a dry-run against the warehouse).
export const useBulletins = () =>
  useQuery({ queryKey: ['sf', 'bulletins'], queryFn: () => getJson<BulletinsResponse>('/bulletins') });

export const useBulletinImpact = (name: string | null) =>
  useQuery({
    queryKey: ['sf', 'bulletin-impact', name],
    queryFn: () => getJson<BulletinImpact>('/bulletin/' + encodeURIComponent(name!) + '/impact'),
    enabled: !!name,
    retry: false, // 503 = knowledge graph offline — don't hammer it
  });

export const useApplyBulletin = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => postJson<BulletinApplyResponse>('/bulletin/apply'),
    // The apply reruns validation and rewrites the canon — refetch everything.
    onSettled: () => qc.invalidateQueries({ queryKey: ['sf'] }),
  });
};

// Reason-code reference — what the regulation currently allows, canon-derived.
export interface ReasonCode {
  tspr_reason_code: string; description: string;
  must_appear_alone: boolean | null; credit_score_companion_required: boolean | null;
}
export const useReasonCodes = () =>
  useQuery({
    queryKey: ['sf', 'reason-codes'],
    queryFn: () => getJson<{ rows: ReasonCode[] }>('/reference/reason-codes'),
    staleTime: 300_000,
  });

// Manual Bronze correction — the record editor in the validation panel.
// Policy fields key on policy_number; claim fields (reporteddate/lossdate)
// key on the claim record_id.
export const useBronzeFix = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: { policy_number?: string; record_id?: string; field: string; new_value: string }) =>
      postJson<{ ok?: boolean }>('/bronze/fix', p),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['sf', 'validate-all'] });
      qc.invalidateQueries({ queryKey: ['sf', 'policy'] });
      qc.invalidateQueries({ queryKey: ['sf', 'claims'] });
      qc.invalidateQueries({ queryKey: ['sf', 'submission'] });
    },
  });
};

// Claims list (for claim-rule context in the validation panel).
export interface ClaimRow {
  claim_number: string; policy: string; loss_cause: string | null;
  loss_date: string | null; reported_date: string | null; reporting_lag_days: number | null;
}
export const useClaims = (filing: string | null) =>
  useQuery({
    queryKey: ['sf', 'claims', filing],
    queryFn: () => getJson<{ claims?: ClaimRow[]; rows?: ClaimRow[] }>(
      '/bronze/claims' + (filing ? '?filing=' + encodeURIComponent(filing) : '')),
    staleTime: 120_000,
  });

// Analyst triage: suppress (with memo) / release / assign a rule's exceptions.
export const useSuppress = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ruleNumber, memo }: { ruleNumber: string; memo: string }) =>
      postJson<{ ok: boolean }>('/validate/suppress', { rule_number: ruleNumber, memo }),
    onSettled: () => qc.invalidateQueries({ queryKey: ['sf', 'validate-all'] }),
  });
};
export const useUnsuppress = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ruleNumber: string) =>
      postJson<{ ok: boolean }>('/validate/unsuppress', { rule_number: ruleNumber }),
    onSettled: () => qc.invalidateQueries({ queryKey: ['sf', 'validate-all'] }),
  });
};
export const useAssign = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ruleNumber, assignee }: { ruleNumber: string; assignee: string }) =>
      postJson<{ ok: boolean }>('/validate/assign', { rule_number: ruleNumber, assignee }),
    onSettled: () => qc.invalidateQueries({ queryKey: ['sf', 'validate-all'] }),
  });
};

// Bulk-apply the server's deterministic remedy for one rule's violations.
// 400 when the rule has no automated fix — the UI surfaces the detail.
export interface FixResult {
  ok: boolean; rule_number: string;
  fixed: Array<{ policy_number: string; old: string; new: string }>;
  skipped: Array<{ policy_number: string; reason: string }>;
}
export const useApplyFix = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ruleNumber: string) => postJson<FixResult>('/validate/fix', { rule_number: ruleNumber }),
    onSettled: () => qc.invalidateQueries({ queryKey: ['sf', 'validate-all'] }),
  });
};

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
  useQuery({
    queryKey: ['sf', 'agent-runs'],
    queryFn: () => getJson<AgentRunsResponse>('/agents/runs'),
    // A transient warehouse hiccup must not swap real telemetry for the demo
    // fixture mid-session — keep showing the last good data.
    placeholderData: (prev) => prev,
    staleTime: 30_000,
  });

// One run + its correlated evidence: warehouse audit actions in the run's
// time window, KG audit entries matched by the run's task content.
export interface AgentRunAction {
  action_id: string; filing_batch_id: string; action_type: string; actor: string;
  target_record: string | null; target_rule: string | null; summary: string | null; acted_at: string;
}
export interface AgentRunKgEntry {
  id: string; action: string; actor: string; occurred_at: string;
  summary: string; affected_count: number | null;
}
export interface AgentRunStep {
  seq: number; step: string; detail: string; status: string; duration_ms: number | null;
}
export interface AgentRunDetail {
  run: AgentRunRow; steps: AgentRunStep[];
  actions: AgentRunAction[]; kg_entries: AgentRunKgEntry[];
}
export const useAgentRunDetail = (runId: string | null) =>
  useQuery({
    queryKey: ['sf', 'agent-run', runId],
    queryFn: () => getJson<AgentRunDetail>('/agents/runs/' + encodeURIComponent(runId!)),
    enabled: !!runId,
  });

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
  const violations = val
    ? Object.values(val.by_filing).flatMap((f) => f.violations).filter((v) => !v.suppressed)
    : [];
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
export interface GroupedError extends EditError {
  violations: Violation[];
  suppressed?: boolean;
  memo?: string;
  assignee?: string;
}
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
      const suppressed = !!val.suppressions?.[code];
      return {
        code,
        field: v.rule_name,
        desc: v.violation_reason,
        count: fmt(vs.length),
        origin: v.citation || 'Rule engine',
        sev: sev as 0 | 1 | 2,
        status: suppressed ? 'Suppressed' : sev === 2 ? 'Blocking' : sev === 1 ? 'Warn' : 'Info',
        violations: vs,
        suppressed,
        memo: val.suppressions?.[code]?.memo,
        assignee: val.assignments?.[code]?.assignee,
      };
    })
    .sort((a, b) => Number(!!a.suppressed) - Number(!!b.suppressed)
      || b.sev - a.sev || b.violations.length - a.violations.length);
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
    .filter((e) => e.sev === 2 && !e.suppressed)
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
