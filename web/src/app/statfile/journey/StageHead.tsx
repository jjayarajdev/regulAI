// Stage header for a journey screen: the big step numeral, a headline that
// says what the stage does (not what the screen is called), a one-line
// summary of state, and the stage's actions on the right.
import type { ReactNode } from 'react';
import { Typography } from 'antd';

const { Title } = Typography;

export function StageHead({ n, title, summary, actions }: {
  n: number | string;
  title: string;
  summary?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="stagehead">
      <div className="stagehead-n">
        {n}
        <small>Step</small>
      </div>
      <div style={{ minWidth: 0 }}>
        <Title level={3} style={{ margin: 0, lineHeight: 1.1 }}>{title}</Title>
        {summary && <div className="stagehead-sum">{summary}</div>}
      </div>
      {actions && <div className="stagehead-acts">{actions}</div>}
    </div>
  );
}
