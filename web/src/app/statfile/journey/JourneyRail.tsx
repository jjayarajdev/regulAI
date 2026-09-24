// The journey rail — the spine of the filing-work screens. Six stages in
// order; done stages carry a tick, the stage the filing is on is raised in
// the sider navy, the screen you're on is marked. Lives in the header so
// every journey screen shows where it sits.
import { CheckOutlined } from '@ant-design/icons';
import { Tooltip } from 'antd';
import { canSee, type AppUser } from '../api';
import type { ScreenId } from '../data';
import { stageForScreen, type Journey } from './useJourney';

export function JourneyRail({ journey, screen, go, user }: {
  journey: Journey;
  screen: ScreenId;
  go: (s: ScreenId) => () => void;
  user: AppUser;
}) {
  const here = stageForScreen(screen, journey);
  return (
    <div className="jrail" role="navigation" aria-label="Filing journey">
      {journey.stages.map((s) => {
        const raised = s.key === journey.current;
        const allowed = canSee(user, s.goTo);
        const cls = [
          'jrail-st',
          s.state === 'done' ? 'is-done' : s.state === 'blocked' ? 'is-blocked' : s.state === 'waiting' ? 'is-wait' : '',
          raised ? 'is-cur' : '',
          here === s.key ? 'is-here' : '',
        ].filter(Boolean).join(' ');
        const btn = (
          <button
            key={s.key} type="button" className={cls}
            onClick={allowed ? go(s.goTo) : undefined}
            disabled={!allowed}
            aria-current={here === s.key ? 'step' : undefined}
          >
            <span className="jrail-t">
              <span className="jrail-ic">{s.state === 'done' ? <CheckOutlined /> : s.n}</span>
              {s.label}
            </span>
            <span className="jrail-d">{s.detail}</span>
          </button>
        );
        return allowed ? btn : <Tooltip key={s.key} title="not visible to your role">{btn}</Tooltip>;
      })}
    </div>
  );
}
