#!/usr/bin/env bash
# Start RegulAI — backend (FastAPI) + frontend (Vite dev) together.
#
#   ./run.sh
#
# Ctrl+C stops both. Override any variable inline, e.g.:
#   BACKEND_PORT=9000 VITE_API_MODE=mock ./run.sh
set -uo pipefail

# ── configuration ──────────────────────────────────────────────────────────
export REGULAI_DB="${REGULAI_DB:-databricks}"    # data engine (always Databricks)
BACKEND_PORT="${BACKEND_PORT:-8765}"             # FastAPI port
FRONTEND_PORT="${FRONTEND_PORT:-5173}"           # Vite dev port
export VITE_API_MODE="${VITE_API_MODE:-live}"    # live = hit the real API (not MSW mocks)
export VITE_ENGINE_LABEL="${VITE_ENGINE_LABEL:-Databricks}"
# Vite proxies /api → this URL, so the frontend reaches the backend:
export REGULAI_API_URL="http://localhost:${BACKEND_PORT}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PM="pnpm"; command -v pnpm >/dev/null 2>&1 || PM="npm"

# ── free the ports (avoid "address already in use") ────────────────────────
for p in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  pids="$(lsof -ti:"$p" 2>/dev/null || true)"
  [ -n "$pids" ] && { echo "freeing port $p"; echo "$pids" | xargs kill 2>/dev/null || true; }
done

# ── start backend ──────────────────────────────────────────────────────────
echo "▶ backend   http://localhost:${BACKEND_PORT}       (REGULAI_DB=${REGULAI_DB})"
uv run uvicorn api.main:app --reload --port "$BACKEND_PORT" &
BACKEND_PID=$!

cleanup() {
  echo; echo "stopping…"
  kill "$BACKEND_PID" 2>/dev/null || true
  lsof -ti:"$FRONTEND_PORT" 2>/dev/null | xargs kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# ── wait for the backend to answer before starting the frontend ────────────
printf "  waiting for backend"
for _ in $(seq 1 40); do
  curl -sf "http://localhost:${BACKEND_PORT}/api/rhs/filings" >/dev/null 2>&1 && break
  printf "."; sleep 1
done
echo " up."

# ── start frontend (foreground; Ctrl+C here tears both down) ───────────────
echo "▶ frontend  http://localhost:${FRONTEND_PORT}       (VITE_API_MODE=${VITE_API_MODE} · proxy → :${BACKEND_PORT})"
echo "  open the app at → http://localhost:${FRONTEND_PORT}"
cd web
"$PM" install >/dev/null 2>&1 || true
"$PM" run dev -- --port "$FRONTEND_PORT" --strictPort
