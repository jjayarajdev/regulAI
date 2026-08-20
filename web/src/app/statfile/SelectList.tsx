// SelectList — the shared master list for choosing among data-driven entities
// (bulletins, mapping specs, documents). Built to scale: compact fixed-height
// rows, a search box that filters on title + meta (so "FL" narrows to a
// state), and its own scrollbar so 4 items or 400 occupy the same real
// estate. Fixed sub-views (Registry | Add a jurisdiction) keep underline
// tabs; anything that grows with the data uses this instead.
import { useMemo, useState } from 'react';

export interface SelectItem {
  id: string;
  title: string;
  meta?: string;      // one small line under the title (jurisdiction · date · counts)
  tag?: string;       // trailing status chip
  tagClass?: string;  // 'tag-neutral' | 'tag-accent' | 'tag-outline'
}

export function SelectList({ items, value, onChange, label, height }: {
  items: SelectItem[];
  value: string | null;
  onChange: (id: string) => void;
  label: string;                 // kicker above the list ("Commissioner's bulletins")
  height?: string;               // CSS height for the scroll pane
}) {
  const [q, setQ] = useState('');
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return items;
    return items.filter((it) =>
      (it.title + ' ' + (it.meta ?? '') + ' ' + (it.tag ?? '')).toLowerCase().includes(needle));
  }, [items, q]);

  return (
    <aside style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 0 }}>
      <div className="k">{label}</div>
      {items.length > 6 && (
        <input
          value={q} onChange={(e) => setQ(e.target.value)} placeholder="filter…"
          style={{
            padding: '6px 9px', fontSize: 12, fontFamily: 'var(--font-body)',
            border: '1px solid var(--color-divider)', borderRadius: 0,
            background: 'color-mix(in srgb,var(--color-text) 4%,transparent)',
            color: 'var(--color-text)',
          }}
        />
      )}
      <div style={{
        border: '1px solid var(--color-divider)',
        overflow: 'auto',
        height: height ?? 'max(360px, calc(100vh - 320px))',
      }}>
        {filtered.map((it) => {
          const on = it.id === value;
          return (
            <div key={it.id} className="rowlink" onClick={() => onChange(it.id)}
              style={{
                padding: '9px 12px',
                borderBottom: '1px solid color-mix(in srgb,var(--color-text) 7%,transparent)',
                borderLeft: '3px solid ' + (on ? 'var(--color-accent)' : 'transparent'),
                background: on ? 'color-mix(in srgb,#5980a6 10%,transparent)' : undefined,
              }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{
                  flex: 1, minWidth: 0, fontSize: 12.5, fontWeight: on ? 500 : 400,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {it.title}
                </span>
                {it.tag && (
                  <span className={'tag ' + (it.tagClass ?? 'tag-outline')} style={{ flex: 'none', fontSize: 9.5 }}>
                    {it.tag}
                  </span>
                )}
              </div>
              {it.meta && (
                <div className="mono muted" style={{
                  fontSize: 10, marginTop: 3,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {it.meta}
                </div>
              )}
            </div>
          );
        })}
        {filtered.length === 0 && (
          <div className="k" style={{ padding: 14 }}>no matches</div>
        )}
      </div>
    </aside>
  );
}
