// MSW request handlers — intercept /api/rhs/* in the browser and answer from
// the mutable mock db (filing-state mutations work end-to-end; see db.ts).
// Active only when VITE_API_MODE !== 'live' (see src/main.tsx).
// Unknown filing ids fall back to the TPA fixture so ad-hoc testing never 404s.

import { http, HttpResponse } from 'msw';
import { API_BASE } from '../api/client';
import * as fx from './fixtures';
import { mappingDetail, mappingsList } from './mappings';
import {
  ack, applyBulletin, approve, approveRegulationMock, bulletinImpact, db,
  extractionReviewMock, extractionStatusMock, fixBronze, goLiveJurisdictionMock,
  neighborhood, putVerdictMock, renderFile, resetBulletin, sendFiling,
  startExtractionMock, submissionState, uploadRegulationMock,
} from './db';
import type { ApprovalRole } from '../api/types';

// Small artificial latency so loading states are visible in mock mode.
const delay = (ms = 250) => new Promise((r) => setTimeout(r, ms));

const byFiling = <T,>(table: Record<string, T>, id: string | null): T =>
  table[id ?? ''] ?? table['TPA-Q4-2025'];

// Mock identity — mirrors _SEED_USERS in api/rhs_demo.py so the RBAC-gated
// screens are reachable in mock mode. Any password signs in.
const MOCK_USERS = [
  { user_id: 'u-okonkwo', name: 'M. Okonkwo', email: 'm.okonkwo@regulai.demo', role: 'analyst', title: 'Compliance Analyst', active: true },
  { user_id: 'u-reyes', name: 'D. Reyes', email: 'd.reyes@regulai.demo', role: 'actuary', title: 'Actuary', active: true },
  { user_id: 'u-iyer', name: 'S. Iyer', email: 's.iyer@regulai.demo', role: 'admin', title: 'Compliance Officer · Specs & Onboarding', active: true },
  { user_id: 'u-park', name: 'J. Park', email: 'j.park@regulai.demo', role: 'cco', title: 'Chief Compliance Officer', active: true },
];
const MOCK_GUEST = { user_id: 'guest', name: 'Guest', role: 'viewer', title: 'Read-only' };

export const handlers = [
  // ── identity (mock sessions: token encodes the user id) ─────────
  http.get(`${API_BASE}/auth/users`, async () => {
    await delay(120);
    return HttpResponse.json({ users: MOCK_USERS });
  }),

  http.get(`${API_BASE}/auth/me`, async ({ request }) => {
    await delay(120);
    const token = request.headers.get('X-Auth-Token');
    const uid = token?.startsWith('mock-') ? token.slice(5) : null;
    const user = MOCK_USERS.find((u) => u.user_id === uid) ?? MOCK_GUEST;
    return HttpResponse.json({ user });
  }),

  http.post(`${API_BASE}/auth/login`, async ({ request }) => {
    await delay(300);
    const body = (await request.json().catch(() => ({}))) as { email?: string } | null;
    const user = MOCK_USERS.find((u) => u.email.toLowerCase() === (body?.email ?? '').toLowerCase());
    if (!user) return HttpResponse.json({ detail: 'unknown user (mock accepts the four seed personas)' }, { status: 401 });
    return HttpResponse.json({ token: 'mock-' + user.user_id, user });
  }),

  http.post(`${API_BASE}/auth/logout`, async () => {
    await delay(120);
    return HttpResponse.json({ ok: true });
  }),

  http.get(`${API_BASE}/filings`, async () => {
    await delay();
    return HttpResponse.json(db.filings);
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

  // Full submission journey: approval + sealed package + email + ack + archive.
  http.get(`${API_BASE}/filing/:filingId/submission`, async ({ params }) => {
    await delay();
    return HttpResponse.json(submissionState(String(params.filingId)));
  }),

  // Fixed-width package render; ?persist=true seals (gated on the chain).
  http.get(`${API_BASE}/filing/:filingId/file`, async ({ params, request }) => {
    const persist = new URL(request.url).searchParams.get('persist') === 'true';
    await delay(persist ? 1100 : 500); // sealing renders + hashes — let it feel real
    const { status, body } = renderFile(String(params.filingId), persist);
    return HttpResponse.json(body, { status });
  }),

  // Mapping review — the schema-mapper proposals + human review verdicts.
  http.get(`${API_BASE}/mappings`, async () => {
    await delay();
    return HttpResponse.json(mappingsList);
  }),

  http.get(`${API_BASE}/mapping/:name`, async ({ params }) => {
    await delay(400);
    if (String(params.name) !== mappingDetail.name) {
      return HttpResponse.json({ detail: `unknown mapping '${String(params.name)}'` }, { status: 404 });
    }
    return HttpResponse.json(mappingDetail);
  }),

  http.get(`${API_BASE}/bulletins`, async () => {
    await delay();
    return HttpResponse.json(db.bulletins);
  }),

  http.get(`${API_BASE}/bulletin/:name/impact`, async ({ params }) => {
    await delay(700); // the real impact runs KG diff + warehouse dry-run
    const imp = bulletinImpact(String(params.name));
    if (!imp) return HttpResponse.json({ detail: `unknown bulletin ${String(params.name)}` }, { status: 404 });
    return HttpResponse.json(imp);
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

  // Regulator document store — backs the standards registry.
  http.get(`${API_BASE}/reg/documents`, async () => {
    await delay();
    return HttpResponse.json(db.regDocuments);
  }),

  // ── regulation store (/api/regulations — NOT under /api/rhs) ─────
  // The jurisdiction-onboarding wizard: upload → background extract
  // (start + status poll) → approve-to-canon, mirroring api/main.py.
  http.get('/api/regulations', async () => {
    await delay();
    return HttpResponse.json(db.regulations);
  }),

  http.post('/api/regulations/upload', async ({ request }) => {
    await delay(900); // PDF parse feels like work
    const fd = await request.formData().catch(() => null);
    const file = fd?.get('file');
    if (!(file instanceof File)) {
      return HttpResponse.json({ detail: 'Only PDF uploads are supported.' }, { status: 400 });
    }
    if (!/\.pdf$/i.test(file.name)) {
      return HttpResponse.json({ detail: 'Only PDF uploads are supported.' }, { status: 400 });
    }
    const label = fd?.get('label');
    const category = fd?.get('category');
    const jurisdiction = fd?.get('jurisdiction');
    return HttpResponse.json(uploadRegulationMock(
      file.name,
      typeof label === 'string' ? label : null,
      typeof category === 'string' ? category : null,
      typeof jurisdiction === 'string' ? jurisdiction : null,
    ));
  }),

  http.post('/api/regulations/:slug/extract/start', async ({ params }) => {
    await delay(200);
    return HttpResponse.json(startExtractionMock(String(params.slug)));
  }),

  http.get('/api/regulations/:slug/extract/status', async ({ params }) => {
    await delay(150);
    return HttpResponse.json(extractionStatusMock(String(params.slug)));
  }),

  http.post('/api/regulations/:slug/approve', async ({ params }) => {
    await delay(700); // materializing to the KG is a real write
    const { status, body } = approveRegulationMock(String(params.slug));
    return HttpResponse.json(body as Record<string, unknown>, { status });
  }),

  // Per-proposal review verdicts (the HITL gate before approve).
  http.get('/api/regulations/:slug/review', async ({ params }) => {
    await delay();
    const { status, body } = extractionReviewMock(String(params.slug));
    return HttpResponse.json(body as Record<string, unknown>, { status });
  }),

  http.put('/api/regulations/:slug/review/:tempId', async ({ params, request }) => {
    await delay(200);
    const payload = (await request.json().catch(() => ({}))) as Record<string, unknown> | null;
    const { status, body } = putVerdictMock(
      String(params.slug), String(params.tempId), payload ?? {});
    return HttpResponse.json(body as Record<string, unknown>, { status });
  }),

  // Wizard finale (mock-only): certify → the jurisdiction goes live. Creates
  // the filing obligation the registry cards + filing dashboard key off.
  http.post('/api/onboarding/go-live', async ({ request }) => {
    await delay(600);
    const payload = (await request.json().catch(() => null)) as { jurisdiction?: string } | null;
    const { status, body } = goLiveJurisdictionMock(payload?.jurisdiction ?? '');
    return HttpResponse.json(body as Record<string, unknown>, { status });
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

  http.post(`${API_BASE}/filing/:filingId/send`, async ({ params, request }) => {
    await delay(900);
    const draft = (await request.json().catch(() => ({}))) as
      { subject?: string; body?: string; to?: string[] } | null;
    const { status, body: payload } = sendFiling(String(params.filingId), draft ?? {});
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
