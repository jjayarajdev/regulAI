// TanStack Query hooks — one per RHS endpoint. Components consume these and
// never call fetch directly, so swapping mock/live data or changing caching
// policy happens here (and in client.ts), nowhere else.

import { useQueries, useQuery } from '@tanstack/react-query';
import { getJson, getText } from './client';
import type {
  AnomaliesResponse,
  ApprovalStateResponse,
  AuditResponse,
  BronzeCancellationsResponse,
  ClaimsResponse,
  FilingsResponse,
  FlatValidationResponse,
  KgAuditResponse,
  KgRulesResponse,
  PipelineStateResponse,
  StateResponse,
  ValidateResponse,
} from './types';

const fq = (filingId: string) => `?filing=${encodeURIComponent(filingId)}`;

export function useFilings() {
  return useQuery({
    queryKey: ['filings'],
    queryFn: () => getJson<FilingsResponse>('/filings'),
  });
}

export function useBackendState() {
  return useQuery({
    queryKey: ['state'],
    queryFn: () => getJson<StateResponse>('/state'),
  });
}

export function useValidate(filingId: string | null) {
  return useQuery({
    queryKey: ['validate', filingId],
    queryFn: () => getJson<ValidateResponse>('/validate' + fq(filingId!)),
    enabled: !!filingId,
  });
}

/** Validation summaries for many filings at once (rail badges, overview rows). */
export function useValidateAll(filingIds: string[]) {
  return useQueries({
    queries: filingIds.map((id) => ({
      queryKey: ['validate', id],
      queryFn: () => getJson<ValidateResponse>('/validate' + fq(id)),
    })),
  });
}

export function useFlatValidation() {
  return useQuery({
    queryKey: ['validation'],
    queryFn: () => getJson<FlatValidationResponse>('/validation'),
  });
}

export function useBronzeCancellations(filingId: string | null) {
  return useQuery({
    queryKey: ['bronze', filingId],
    queryFn: () => getJson<BronzeCancellationsResponse>('/bronze/cancellations' + fq(filingId!)),
    enabled: !!filingId,
  });
}

export function useClaims(filingId: string | null) {
  return useQuery({
    queryKey: ['claims', filingId],
    queryFn: () => getJson<ClaimsResponse>('/bronze/claims' + fq(filingId!)),
    enabled: !!filingId,
  });
}

export function usePipelineState() {
  return useQuery({
    queryKey: ['pipeline'],
    queryFn: () => getJson<PipelineStateResponse>('/pipeline/state'),
  });
}

export function useKgRules() {
  return useQuery({
    queryKey: ['kgRules'],
    queryFn: () => getJson<KgRulesResponse>('/kg/rules'),
  });
}

export function useBulletinText() {
  return useQuery({
    queryKey: ['bulletinText'],
    queryFn: () => getText('/bulletin'),
  });
}

export function useAudit(filingId: string | null) {
  return useQuery({
    queryKey: ['audit', filingId],
    queryFn: () => getJson<AuditResponse>('/audit/' + encodeURIComponent(filingId!)),
    enabled: !!filingId,
  });
}

export function useApprovalState(filingId: string | null) {
  return useQuery({
    queryKey: ['approval', filingId],
    queryFn: () =>
      getJson<ApprovalStateResponse>('/filing/' + encodeURIComponent(filingId!) + '/approval-state'),
    enabled: !!filingId,
  });
}

export function useApprovalStates(filingIds: string[]) {
  return useQueries({
    queries: filingIds.map((id) => ({
      queryKey: ['approval', id],
      queryFn: () =>
        getJson<ApprovalStateResponse>('/filing/' + encodeURIComponent(id) + '/approval-state'),
    })),
  });
}

export function useAnomalies(filingId: string | null) {
  return useQuery({
    queryKey: ['anomalies', filingId],
    queryFn: () => getJson<AnomaliesResponse>('/anomalies' + fq(filingId!)),
    enabled: !!filingId,
  });
}

export function useKgAudit(limit = 20) {
  return useQuery({
    queryKey: ['kgAudit', limit],
    queryFn: () => getJson<KgAuditResponse>(`/kg/audit?limit=${limit}`),
  });
}
