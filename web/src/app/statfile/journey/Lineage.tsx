// The lineage chain: source → rule → records. One horizontal chain with
// three joined columns and arrow joins, used on the Rules screen (a rule's
// provenance), the Amendments screen (what a bulletin changes) and, in strip
// form, inside an exception's detail.
import type { ReactNode } from 'react';
import { ArrowRightOutlined } from '@ant-design/icons';
import { Button, Typography } from 'antd';

const { Text } = Typography;

export type LineageKind = 'source' | 'rule' | 'records';
export type LineageTone = 'neutral' | 'changed' | 'pending' | 'hurt';

export interface LineageCol {
  kind: LineageKind;
  title: string;
  badge?: ReactNode;          // small right-aligned status word
  body: ReactNode;
  excerpt?: ReactNode;        // quote (source), code (rule) or ids (records)
  provenance?: ReactNode;     // where this column's fact is stored
  tone?: LineageTone;
}

export function Lineage({ cols }: { cols: LineageCol[] }) {
  return (
    <div className="lineage">
      {cols.map((c, i) => (
        <div key={i} className={`ln ln-${c.kind} tone-${c.tone ?? 'neutral'}`}>
          <div className="ln-hd">
            <span className="ln-sw" />
            <span className="ln-t">{c.title}</span>
            {c.badge && <span className="ln-w">{c.badge}</span>}
          </div>
          <div className="ln-body">{c.body}</div>
          {c.excerpt && <div className="ln-ex">{c.excerpt}</div>}
          {c.provenance && <div className="ln-prov">{c.provenance}</div>}
          {i < cols.length - 1 && <span className="ln-arrow"><ArrowRightOutlined /></span>}
        </div>
      ))}
    </div>
  );
}

// Compact one-line form for drawers: pills joined by arrows.
export function LineageStrip({ source, rule, records, onOpenRule }: {
  source: ReactNode; rule: ReactNode; records: ReactNode; onOpenRule?: () => void;
}) {
  return (
    <div className="linstrip">
      <span className="linstrip-pill p-source"><i />{source}</span>
      <ArrowRightOutlined className="linstrip-ar" />
      <span className="linstrip-pill p-rule"><i />{rule}</span>
      <ArrowRightOutlined className="linstrip-ar" />
      <span className="linstrip-pill p-records"><i />{records}</span>
      {onOpenRule && (
        <Button type="link" size="small" onClick={onOpenRule} style={{ paddingInline: 6 }}>
          Open in rulebook →
        </Button>
      )}
      <Text type="secondary" style={{ fontSize: 11, marginLeft: 'auto' }}>source → rule → records</Text>
    </div>
  );
}
