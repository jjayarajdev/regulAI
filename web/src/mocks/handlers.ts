// MSW request handlers — intercept /api/rhs/* in the browser and answer from
// the mutable mock db (filing-state mutations work end-to-end; see db.ts).
// Active only when VITE_API_MODE !== 'live' (see src/main.tsx).
// Unknown filing ids fall back to the TPA fixture so ad-hoc testing never 404s.

import { http, HttpResponse } from 'msw';
import { API_BASE } from '../api/client';
import * as fx from './fixtures';
import { ack, applyBulletin, approve, db, fixBronze, neighborhood, resetBulletin } from './db';
import type { ApprovalRole } from '../api/types';

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
    return HttpResponse.json(db.state);
  }),

  http.get(`${API_BASE}/validate`, async ({ request }) => {
    await delay(600); // validation is the slow endpoint in real life too
    const filing = new URL(request.url).searchParams.get('filing');
    return HttpResponse.json(byFiling(db.validate, filing));
  }),

  http.get(`${API_BASE}/validation`, async () => {
    await delay();
    return HttpResponse.json(fx.flatValidation);
  }),

  http.get(`${API_BASE}/bronze/cancellations`, async ({ request }) => {
    await delay();
    const filing = new URL(request.url).searchParams.get('filing');
    return HttpResponse.json(byFiling(db.bronze, filing));
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
    return HttpResponse.json(db.kgRules);
  }),

  http.get(`${API_BASE}/kg/neighborhood/:ruleId`, async ({ params }) => {
    await delay(350);
    return HttpResponse.json(neighborhood(String(params.ruleId)));
  }),

  http.get(`${API_BASE}/bulletin`, async () => {
    await delay();
    return new HttpResponse(fx.bulletinText, {
      headers: { 'Content-Type': 'text/plain' },
    });
  }),

  http.get(`${API_BASE}/audit/:filingId`, async ({ params }) => {
    await delay();
    return HttpResponse.json(byFiling(db.audit, String(params.filingId)));
  }),

  http.get(`${API_BASE}/filing/:filingId/approval-state`, async ({ params }) => {
    await delay();
    return HttpResponse.json(byFiling(db.approval, String(params.filingId)));
  }),

  http.get(`${API_BASE}/anomalies`, async ({ request }) => {
    await delay();
    const filing = new URL(request.url).searchParams.get('filing');
    return HttpResponse.json(byFiling(fx.anomaliesByFiling, filing));
  }),

  http.get(`${API_BASE}/kg/audit`, async () => {
    await delay();
    return HttpResponse.json(db.kgAudit);
  }),

  // ── mutations ───────────────────────────────────────────────────
  http.post(`${API_BASE}/bulletin/apply`, async () => {
    await delay(1200); // the real apply rebuilds the canon — let it feel weighty
    return HttpResponse.json(applyBulletin());
  }),

  http.post(`${API_BASE}/bulletin/reset`, async () => {
    await delay(800);
    return HttpResponse.json(resetBulletin());
  }),

  http.post(`${API_BASE}/filing/:filingId/approve`, async ({ params, request }) => {
    await delay(400);
    const body = (await request.json()) as { role?: string };
    const { status, body: payload } = approve(String(params.filingId), (body.role ?? '') as ApprovalRole);
    return HttpResponse.json(payload, { status });
  }),

  http.post(`${API_BASE}/filing/:filingId/ack`, async ({ params }) => {
    await delay(400);
    const { status, body: payload } = ack(String(params.filingId));
    return HttpResponse.json(payload, { status });
  }),

  http.post(`${API_BASE}/bronze/fix`, async ({ request }) => {
    await delay(500);
    const body = (await request.json()) as { policy_number?: string; field?: string; new_value?: string };
    const { status, body: payload } = fixBronze(
      body.policy_number ?? '', body.field ?? 'reason_code', body.new_value ?? '');
    return HttpResponse.json(payload, { status });
  }),
];
