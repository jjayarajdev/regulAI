# regulAI Web — React frontend

React + Vite + Tailwind v4 + shadcn/ui rebuild of the regulAI workstation,
based on the Figma wireframes in `refinedUI/` ([original Figma file](https://www.figma.com/design/EF6tZeCEchAgD8PY51Xcoe/Create-Underwriting-Workbench-Wireframes--Community-)).
Data flows through TanStack Query hooks (`src/api/hooks.ts`) — components
never call `fetch` directly.

## Run

```bash
cd web
pnpm install
pnpm dev          # http://localhost:5173
```

## Mock ↔ live data switch

One flag controls the data source: `VITE_API_MODE` in `.env.development`.

| Mode | What happens | Needs |
|------|--------------|-------|
| `mock` (default) | MSW intercepts `/api/rhs/*` in the browser and answers from `src/mocks/fixtures.ts` | nothing |
| `live` | Requests pass through the Vite dev proxy to the FastAPI server on `localhost:8765` | running backend + Snowflake |

Switch per-run without editing files:

```bash
VITE_API_MODE=live pnpm dev
```

Point live mode at a remote backend (e.g. Fly.io):

```bash
REGULAI_API_URL=https://<your-app>.fly.dev VITE_API_MODE=live pnpm dev
```

The blue banner at the bottom of the Overview screen always tells you which
mode the app is running in.

## Where things live

- `src/api/types.ts` — response types mirrored from `api/rhs_demo.py`. The
  single source of truth shared by the live client and the mocks; update it
  first when the backend changes.
- `src/api/client.ts` — fetch wrapper (`/api/rhs` base path).
- `src/api/hooks.ts` — one TanStack Query hook per endpoint. Caching,
  30s auto-refresh, pause-when-hidden, and refetch-on-focus are configured
  globally in `src/main.tsx`.
- `src/mocks/fixtures.ts` — mock data for three filings in different states
  (violations open / clean / early draft). Edit values here to exercise UI
  states; add latency or errors in `src/mocks/handlers.ts`.
- `src/app/ws/` — the workstation screens (Overview, Filing workshop,
  Regulations, Bulletins, Audit log), all wired to live hooks. Mutations
  (apply/reset bulletin, sign-off chain, TICO ACK) work in both modes — the
  mock db in `src/mocks/db.ts` mirrors the backend's state transitions.
- `src/app/components/` — the original Figma wireframe screens, kept at
  `?ui=wireframe` for design reference.

## Production build

```bash
pnpm build        # outputs to dist/
```

In production, serve `dist/` from the FastAPI app (same origin as `/api/rhs`)
and no proxy is involved. MSW is only ever started when `VITE_API_MODE` is not
`live`, and the service worker file is harmless when unused.
