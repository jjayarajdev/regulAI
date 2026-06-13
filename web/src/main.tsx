import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './app/App.tsx';
import './styles/index.css';

// ── Mock ↔ live switch ──────────────────────────────────────────────
// VITE_API_MODE=mock (default) → MSW intercepts /api/rhs/* with fixtures.
// VITE_API_MODE=live           → requests pass through to the FastAPI
//                                server (Vite dev proxy → localhost:8765).
// Set it in .env.development / .env.local, or per-run:
//   VITE_API_MODE=live pnpm dev
const API_MODE = import.meta.env.VITE_API_MODE ?? 'mock';

async function prepare() {
  if (API_MODE !== 'live') {
    const { worker } = await import('./mocks/browser');
    await worker.start({ onUnhandledRequest: 'bypass' });
    console.info('[regulAI] running in MOCK mode — set VITE_API_MODE=live for the real API');
  } else {
    console.info('[regulAI] running in LIVE mode against /api/rhs');
  }
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,            // matches the old workstation's 30s cycle
      refetchInterval: 30_000,      // auto-refresh…
      refetchIntervalInBackground: false, // …but never from a hidden tab
      refetchOnWindowFocus: true,   // catch up when the tab regains focus
      retry: 1,
    },
  },
});

prepare().then(() => {
  createRoot(document.getElementById('root')!).render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
});
