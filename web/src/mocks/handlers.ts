// MSW request handlers — intercept /api/rhs/* in the browser and answer with
// fixtures. Active only when VITE_API_MODE !== 'live' (see src/main.tsx).
// Unknown filing ids fall back to the TPA fixture so ad-hoc testing never 404s.

import { http, HttpResponse } from 'msw';
import { API_BASE } from '../api/client';
import * as fx from './fixtures';

// Small artificial latency so loading states are visible in mock mode.
const delay = (ms = 250) => new Promise((r) => setTimeout(r, ms));

const byFiling = <T,>(table: Record<string, T>, id: string | null): T =>
  table[id ?? ''] ?? table['TPA-Q4-2025'];

export const handlers = [
  http.get(`${API_BASE}/filings`, async () => {
    await delay();
    return HttpResponse.json(fx.filings);
  }),

  http.get(`${API_BASE}/state`, async () => {
    await delay();
    return HttpResponse.json(fx.state);
  }),

  http.get(`${API_BASE}/validate`, async ({ request }) => {
    await delay(600); // validation is the slow endpoint in real life too
    const filing = new URL(request.url).searchParams.get('filing');
    return HttpResponse.json(byFiling(fx.validateByFiling, filing));
  }),

  http.get(`${API_BASE}/validation`, async () => {
    await delay();
    return HttpResponse.json(fx.flatValidation);
  }),

  http.get(`${API_BASE}/bronze/cancellations`, async ({ request }) => {
    await delay();
    const filing = new URL(request.url).searchParams.get('filing');
    return HttpResponse.json(byFiling(fx.bronzeByFiling, filing));
  }),

  http.get(`${API_BASE}/bronze/claims`, async ({ request }) => {
    await delay();
    const filing = new URL(request.url).searchParams.get('filing');
    return HttpResponse.json(byFiling(fx.claimsByFiling, filing));
  }),

  http.get(`${API_BASE}/pipeline/state`, async () => {
    await delay();
    return HttpResponse.json(fx.pipelineState);
  }),

  http.get(`${API_BASE}/kg/rules`, async () => {
    await delay();
    return HttpResponse.json(fx.kgRules);
  }),

  http.get(`${API_BASE}/bulletin`, async () => {
    await delay();
    return new HttpResponse(fx.bulletinText, {
      headers: { 'Content-Type': 'text/plain' },
    });
  }),

  http.get(`${API_BASE}/audit/:filingId`, async ({ params }) => {
    await delay();
    return HttpResponse.json(byFiling(fx.auditByFiling, String(params.filingId)));
  }),

  http.get(`${API_BASE}/filing/:filingId/approval-state`, async ({ params }) => {
    await delay();
    return HttpResponse.json(byFiling(fx.approvalByFiling, String(params.filingId)));
  }),

  http.get(`${API_BASE}/anomalies`, async ({ request }) => {
    await delay();
    const filing = new URL(request.url).searchParams.get('filing');
    return HttpResponse.json(byFiling(fx.anomaliesByFiling, filing));
  }),

  http.get(`${API_BASE}/kg/audit`, async () => {
    await delay();
    return HttpResponse.json(fx.kgAudit);
  }),
];
