// Data layer for the CBRE experience — React Query hooks over /api/rhs, plus
// pure helpers that shape validation violations into the records/KPIs the UI
// renders. Self-contained (own query keys) so mutations can invalidate cleanly.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getJson, postJson } from '../../api/client';
import type { Filing, FilingsResponse, StateResponse, ValidateResponse, Violation } from '../../api/types';

// One-call validation for every filing (collapses N per-filing validates).
export interface FilingValidation { summary: ValidateResponse['summary']; violations: Violation[]; run_id: string | null }
export interface ValidateAllResponse { by_filing: Record<string, FilingValidation> }

// ── extra response shapes (not in api/types) ──────────────────────────────
export interface SubmissionResponse {
  policy_number: string;
  found: boolean;
  note?: string;
  fields?: Record<string, string | number | null>;
}
export interface PolicyFieldsResponse {
  policy_number: string;
  fields: Record<string, string | number | null>;
}
export interface AuditAction {
  action_id: string; action_type: string; actor: string;
  target_record: string | null; summary: string; acted_at: string;
}
export interface AuditResponse { actions: AuditAction[] }

// ── derived record ────────────────────────────────────────────────────────
export type RecStatus = 'blocked' | 'warning' | 'review' | 'clean';
export interface ExpRecord {
  key: string; id: string; jur: string; plan: string; filingId: string; carrier: string;
  ruleNumber: string; ruleName: string; severity: string; status: RecStatus; stage: string;
  reason: string; reasonFull: string; citation: string; recordId: string;
  resolved?: boolean; resolvedBy?: string;
}

const CARRIER: Record<string, string> = { 'US-TX': 'Lone Star Mutual', 'US-FL': 'Gulf Coast Insurance' };
export const carrierFor = (j: string) => CARRIER[j] || j || '—';

export function mapViolation(f: Filing, v: Violation): ExpRecord {
  const sev = (v.severity || 'ERROR').toUpperCase();
  return {
    key: `${f.id}/${v.policy_number}`, id: v.policy_number,
    jur: f.jurisdiction_code, plan: f.plan_code, filingId: f.id, carrier: carrierFor(f.jurisdiction_code),
    ruleNumber: v.rule_number, ruleName: v.rule_name, severity: sev,
    status: sev === 'ERROR' ? 'blocked' : sev === 'WARNING' ? 'warning' : 'review', stage: 'In Review',
    reason: (v.rule_number ? v.rule_number + ' — ' : '') + v.violation_reason,
    reasonFull: v.violation_reason + (v.citation ? ` (${v.citation})` : ''),
    citation: v.citation, recordId: v.record_id,
  };
}

// ── hooks ──────────────────────────────────────────────────────────────────
export const useFilings = () =>
  useQuery({ queryKey: ['exp', 'filings'], queryFn: () => getJson<FilingsResponse>('/filings') });

export const useBackendState = () =>
  useQuery({ queryKey: ['exp', 'state'], queryFn: () => getJson<StateResponse>('/state') });

export const useValidateAll = () =>
  useQuery({ queryKey: ['exp', 'validate-all'], queryFn: () => getJson<ValidateAllResponse>('/validate/all') });

export const useSubmission = (policy: string | null) =>
  useQuery({
    queryKey: ['exp', 'submission', policy],
    queryFn: () => getJson<SubmissionResponse>('/submission/' + encodeURIComponent(policy!)),
    enabled: !!policy,
  });

export const usePolicyFields = (policy: string | null) =>
  useQuery({
    queryKey: ['exp', 'policy', policy],
    queryFn: () => getJson<PolicyFieldsResponse>('/bronze/policy/' + encodeURIComponent(policy!)),
    enabled: !!policy,
  });

export const useAudit = (filingId: string | null) =>
  useQuery({
    queryKey: ['exp', 'audit', filingId],
    queryFn: () => getJson<AuditResponse>('/audit/' + encodeURIComponent(filingId!)),
    enabled: !!filingId,
  });

export function useBronzeFix() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { policy_number: string; field: string; new_value: string }) =>
      postJson('/bronze/fix', v),
    onSuccess: (_d, v) => {
      qc.invalidateQueries({ queryKey: ['exp', 'validate-all'] });
      qc.invalidateQueries({ queryKey: ['exp', 'submission', v.policy_number] });
      qc.invalidateQueries({ queryKey: ['exp', 'policy', v.policy_number] });
    },
  });
}

export function useApplyBulletin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => postJson('/bulletin/apply'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['exp', 'validate-all'] });
      qc.invalidateQueries({ queryKey: ['exp', 'state'] });
    },
  });
}
