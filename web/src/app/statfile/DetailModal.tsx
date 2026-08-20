// DetailModal — the standard home for row-click detail. Clicking a row in a
// full-width table used to render its detail somewhere below the fold; this
// opens it where the user is looking instead: a centered sheet in the
// blueprint design language with kicker + title, X / Esc / backdrop close,
// and a scrollable body. Keep actions (buttons that mutate) inside `footer`
// so they're always visible regardless of body scroll.
import { useEffect, type ReactNode } from 'react';

export function DetailModal({ open, onClose, kicker, title, tags, footer, width, children }: {
  open: boolean;
  onClose: () => void;
  kicker?: ReactNode;         // small caps line above the title
  title: ReactNode;
  tags?: ReactNode;           // chips rendered beside the title
  footer?: ReactNode;         // pinned action row (never scrolls away)
  width?: number;             // px, default 760
  children: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 60,
        background: 'color-mix(in srgb, var(--color-text) 32%, transparent)',
        display: 'grid', placeItems: 'center', padding: 28,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        role="dialog" aria-modal="true"
        style={{
          width: 'min(94vw, ' + (width ?? 760) + 'px)',
          maxHeight: 'min(88vh, 900px)',
          display: 'flex', flexDirection: 'column',
          background: 'var(--color-bg, #fff)',
          border: '1px solid var(--color-divider)',
          boxShadow: '0 18px 60px color-mix(in srgb, var(--color-text) 25%, transparent)',
        }}
      >
        <div style={{
          padding: '14px 18px 12px', borderBottom: '1px solid var(--color-divider)',
          display: 'flex', alignItems: 'flex-start', gap: 12, flex: 'none',
        }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            {kicker && <div className="k" style={{ marginBottom: 3 }}>{kicker}</div>}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 17, lineHeight: 1.3 }}>
                {title}
              </span>
              {tags}
            </div>
          </div>
          <button onClick={onClose} aria-label="close"
            style={{
              background: 'none', border: '1px solid var(--color-divider)', cursor: 'pointer',
              width: 28, height: 28, display: 'grid', placeItems: 'center', flex: 'none',
              fontSize: 14, color: 'var(--color-text)', borderRadius: 0,
            }}>
            ×
          </button>
        </div>

        <div style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: '16px 18px' }}>
          {children}
        </div>

        {footer && (
          <div style={{ padding: '12px 18px', borderTop: '1px solid var(--color-divider)', flex: 'none' }}>
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
