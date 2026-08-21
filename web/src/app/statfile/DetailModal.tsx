// DetailModal — the standard home for row-click detail, as a SIDE DRAWER:
// a full-height panel sliding in from the right, so the detail reads beside
// the list that opened it instead of covering it. Structure: kicker + title
// + status chips header, scrollable body, pinned action footer (mutating
// buttons live there so they never scroll away). Close via X, Esc, or the
// backdrop. One component — every modal in the app inherits the behavior.
import { useEffect, type ReactNode } from 'react';

export function DetailModal({ open, onClose, kicker, title, tags, footer, width, children }: {
  open: boolean;
  onClose: () => void;
  kicker?: ReactNode;         // small caps line above the title
  title: ReactNode;
  tags?: ReactNode;           // chips rendered beside the title
  footer?: ReactNode;         // pinned action row (never scrolls away)
  width?: number;             // drawer width in px, default 700
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
        background: 'color-mix(in srgb, var(--color-text) 28%, transparent)',
        animation: 'sf-fade-in 140ms ease-out',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        role="dialog" aria-modal="true"
        style={{
          position: 'absolute', top: 0, right: 0, bottom: 0,
          width: 'min(94vw, ' + (width ?? 700) + 'px)',
          display: 'flex', flexDirection: 'column',
          background: 'var(--color-bg, #fff)',
          borderLeft: '1px solid var(--color-divider)',
          boxShadow: '-14px 0 48px color-mix(in srgb, var(--color-text) 22%, transparent)',
          animation: 'sf-drawer-in 180ms ease-out',
        }}
      >
        <div style={{
          padding: '16px 20px 13px', borderBottom: '1px solid var(--color-divider)',
          display: 'flex', alignItems: 'flex-start', gap: 12, flex: 'none',
        }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            {kicker && <div className="k" style={{ marginBottom: 4 }}>{kicker}</div>}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 600, fontSize: 18, lineHeight: 1.3 }}>
                {title}
              </span>
              {tags}
            </div>
          </div>
          <button onClick={onClose} aria-label="close" title="close (Esc)"
            style={{
              background: 'none', border: '1px solid var(--color-divider)', cursor: 'pointer',
              width: 28, height: 28, display: 'grid', placeItems: 'center', flex: 'none',
              fontSize: 14, color: 'var(--color-text)', borderRadius: 0,
            }}>
            ×
          </button>
        </div>

        <div style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: '18px 20px' }}>
          {children}
        </div>

        {footer && (
          <div style={{ padding: '13px 20px', borderTop: '1px solid var(--color-divider)', flex: 'none' }}>
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
