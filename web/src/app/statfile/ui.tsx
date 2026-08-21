// Shared UI primitives — the four patterns every screen was hand-rolling
// slightly differently (the audit found stat-card value text at ten font
// sizes, three loading-state styles, and fixture data shown silently on most
// screens). One source of truth; screens compose these instead.
import type { CSSProperties, ReactNode } from 'react';
import { Blueprint } from './Blueprint';

// ── Stat — the KPI card: small-caps label, one canonical value size, note ──
export function Stat({ label, value, note, accent }: {
  label: string; value: ReactNode; note?: ReactNode; accent?: boolean;
}) {
  return (
    <Blueprint style={{ padding: '13px 15px 11px' }}>
      <div className="k">{label}</div>
      <div style={{
        fontFamily: 'var(--font-heading)', fontSize: 30, lineHeight: 1.05, marginTop: 5,
        color: accent ? 'var(--color-accent-700)' : undefined,
      }}>
        {value}
      </div>
      {note != null && (
        <div className="muted" style={{
          fontSize: 11, marginTop: 4,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {note}
        </div>
      )}
    </Blueprint>
  );
}

// A row of Stat cards at the standard gap.
export function StatRow({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  const count = Array.isArray(children) ? children.filter(Boolean).length : 1;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${count},1fr)`, gap: 20, marginBottom: 22, ...style }}>
      {children}
    </div>
  );
}

// ── SectionTitle — h4 + small-caps caption + optional right-aligned slot ───
export function SectionTitle({ title, caption, right, style }: {
  title: ReactNode; caption?: ReactNode; right?: ReactNode; style?: CSSProperties;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 12, flexWrap: 'wrap', ...style }}>
      <h4>{title}</h4>
      {caption && <span className="k">{caption}</span>}
      {right && <span style={{ marginLeft: 'auto', alignSelf: 'center' }}>{right}</span>}
    </div>
  );
}

// ── DemoTag — every screen showing fixture data says so, the same way ──────
export function DemoTag({ reason }: { reason?: string }) {
  return (
    <span className="tag tag-outline" title={reason ?? 'the live source is empty or unreachable — showing design fixtures'}>
      demo data
    </span>
  );
}

// ── LoadingLine — the one loading state ────────────────────────────────────
export function LoadingLine({ what }: { what?: string }) {
  return <span className="k">loading{what ? ` ${what}` : ''}…</span>;
}
