// Thin fetch wrapper for the RHS API. The base path is identical in mock and
// live mode — mock mode intercepts these URLs in the browser via MSW, live
// mode reaches the FastAPI server through the Vite dev proxy (see
// vite.config.ts) or same-origin serving in production.

export const API_BASE = '/api/rhs';

// Which warehouse the backend is running (REGULAI_DB). Baked at build time so
// the UI labels match the deployed engine; defaults to Databricks (the hosted
// demo). Set VITE_ENGINE_LABEL / VITE_ENGINE_CONSOLE_URL to change.
export const ENGINE_LABEL = import.meta.env.VITE_ENGINE_LABEL ?? 'Databricks';
export const ENGINE_CONSOLE_URL = import.meta.env.VITE_ENGINE_CONSOLE_URL ?? 'https://www.databricks.com/';

export class ApiError extends Error {
  constructor(public status: number, public path: string, detail?: string) {
    super(detail ?? `${path} → ${status}`);
  }
}

// ── Identity (RBAC phase 2: login sessions) ────────────────────────────────
// Login stores a session token; every request carries it as X-Auth-Token so
// the backend can role-gate mutations and stamp the audit trail.
const TOKEN_KEY = 'regulai-token';
export const getToken = (): string | null => {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
};
export const setToken = (token: string | null): void => {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch { /* private mode — session just won't persist */ }
};
const actorHeaders = (): Record<string, string> => {
  const t = getToken();
  return t ? { 'X-Auth-Token': t } : {};
};

export async function getJson<T>(path: string): Promise<T> {
  const r = await fetch(API_BASE + path, { headers: actorHeaders() });
  if (!r.ok) {
    const detail = await r.json().then((j) => j?.detail).catch(() => undefined);
    throw new ApiError(r.status, path, detail);
  }
  return r.json() as Promise<T>;
}

export async function getText(path: string): Promise<string> {
  const r = await fetch(API_BASE + path, { headers: actorHeaders() });
  if (!r.ok) throw new ApiError(r.status, path);
  return r.text();
}

export async function patchJson<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(API_BASE + path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...actorHeaders() },
    body: JSON.stringify(body ?? {}),
  });
  if (!r.ok) {
    const detail = await r.json().then((j) => j?.detail).catch(() => undefined);
    throw new ApiError(r.status, path, detail);
  }
  return r.json() as Promise<T>;
}

export async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(API_BASE + path, {
    method: 'POST',
    headers: {
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...actorHeaders(),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    // FastAPI ships error context as {"detail": "..."} — surface it.
    const detail = await r.json().then((j) => j?.detail).catch(() => undefined);
    throw new ApiError(r.status, path, detail);
  }
  return r.json() as Promise<T>;
}
