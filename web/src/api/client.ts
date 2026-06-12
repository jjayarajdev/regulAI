// Thin fetch wrapper for the RHS API. The base path is identical in mock and
// live mode — mock mode intercepts these URLs in the browser via MSW, live
// mode reaches the FastAPI server through the Vite dev proxy (see
// vite.config.ts) or same-origin serving in production.

export const API_BASE = '/api/rhs';

export class ApiError extends Error {
  constructor(public status: number, public path: string) {
    super(`GET ${path} → ${status}`);
  }
}

export async function getJson<T>(path: string): Promise<T> {
  const r = await fetch(API_BASE + path);
  if (!r.ok) throw new ApiError(r.status, path);
  return r.json() as Promise<T>;
}

export async function getText(path: string): Promise<string> {
  const r = await fetch(API_BASE + path);
  if (!r.ok) throw new ApiError(r.status, path);
  return r.text();
}

export async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(API_BASE + path, {
    method: 'POST',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new ApiError(r.status, path);
  return r.json() as Promise<T>;
}
