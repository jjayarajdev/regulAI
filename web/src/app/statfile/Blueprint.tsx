// Blueprint frame — hairline box with the four registration-mark corners the
// whole design hangs on. Every framed panel in the mock is one of these.
import type { CSSProperties, MouseEventHandler, ReactNode } from 'react';

export function Blueprint({ className = '', style, onClick, children }: {
  className?: string;
  style?: CSSProperties;
  onClick?: MouseEventHandler<HTMLDivElement>;
  children: ReactNode;
}) {
  return (
    <div className={('blueprint ' + className).trim()} style={style} onClick={onClick}>
      <i className="corner tl" /><i className="corner tr" />
      <i className="corner bl" /><i className="corner br" />
      {children}
    </div>
  );
}
