// PickerTabs — the shared item picker, in the same underline-tab language the
// Administration screen uses (Registry | Add a jurisdiction). Screens that
// select among a handful of entities (bulletins, mapping specs) render these
// instead of a left rail of cards, so every page reads the same way:
// segmented screen tabs → underline item tabs → full-width content.
export interface PickerItem {
  id: string;
  label: string;
  tag?: string;       // small trailing status chip (e.g. 'Applied', 'Compiled')
  tagClass?: string;  // 'tag-neutral' | 'tag-accent' | 'tag-outline'
}

export function PickerTabs({ items, value, onChange }: {
  items: PickerItem[];
  value: string | null;
  onChange: (id: string) => void;
}) {
  return (
    <div className="tabs-underline" style={{ flexWrap: 'wrap' }}>
      {items.map((it) => (
        <button key={it.id}
          className={'tab-underline' + (it.id === value ? ' on' : '')}
          onClick={() => onChange(it.id)}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          {it.label}
          {it.tag && <span className={'tag ' + (it.tagClass ?? 'tag-outline')} style={{ fontSize: 9.5 }}>{it.tag}</span>}
        </button>
      ))}
    </div>
  );
}
