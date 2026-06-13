// Manual-fix editor for reason codes — suggestion heuristics ported from
// workstation.html's suggestFixes(): J-combination splits, L companions,
// invalid-character replacements. Saves via POST /bronze/fix.

import { useState } from 'react';
import { useFixBronze } from '../../api/hooks';

const VALID = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K', 'L', 'M', 'N', 'P', 'Q', 'R', 'S', 'T', 'X', 'Y', 'Z'];

function suggestFixes(currentCode: string): { code: string; why: string }[] {
  const c = (currentCode || '').toUpperCase();
  const sg: { code: string; why: string }[] = [];
  if (c.includes('J') && c.length > 1) {
    sg.push({ code: 'J', why: 'just J alone (market withdrawal)' });
    const others = c.replace(/J/g, '');
    if (others) sg.push({ code: others, why: `keep '${others}' (drop J)` });
  }
  if (c === 'L') {
    sg.push({ code: 'LD', why: 'L + claims history' });
    sg.push({ code: 'LK', why: 'L + location of risk' });
    sg.push({ code: 'LM', why: 'L + roof condition' });
  }
  if ([...c].some((ch) => !VALID.includes(ch))) {
    sg.push({ code: 'D', why: 'claims history' });
    sg.push({ code: 'Y', why: "at insured's request" });
    sg.push({ code: 'A', why: 'failure to pay' });
  }
  if (sg.length < 3) sg.push({ code: '', why: 'clear (no reason code)' });
  return sg.slice(0, 4);
}

interface FixEditorProps {
  policy: string;
  currentCode: string;
  ruleNum: string;
  onDone: () => void;
  onCancel: () => void;
}

export function FixEditor({ policy, currentCode, ruleNum, onDone, onCancel }: FixEditorProps) {
  const [value, setValue] = useState('');
  const fix = useFixBronze();
  const suggestions = suggestFixes(currentCode);

  const save = async () => {
    try {
      await fix.mutateAsync({ policy_number: policy, field: 'reason_code', new_value: value.toUpperCase() });
      onDone();
    } catch {
      /* error surfaced below via fix.isError */
    }
  };

  return (
    <div className="fix-editor">
      <div className="fe-head">Manually fix · {policy} · violates rule {ruleNum}</div>
      <div className="fe-row">
        <span style={{ color: 'var(--ink-2)' }}>Current:</span>
        <span className="fe-current">{currentCode || '—'}</span>
        <span style={{ color: 'var(--ink-3)' }}>→</span>
        <input
          type="text"
          className="fe-input"
          maxLength={3}
          placeholder="new"
          value={value}
          autoFocus
          onChange={(e) => setValue(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === 'Enter' && save()}
        />
      </div>
      <div className="fe-row" style={{ marginBottom: 6, color: 'var(--ink-3)', fontSize: 12 }}>
        Suggested corrections (click to fill):
      </div>
      <div className="fe-suggest">
        {suggestions.map((s) => (
          <span className="fe-sg" key={s.code + s.why} onClick={() => setValue(s.code)}>
            {s.code || '∅'}<span className="why">{s.why}</span>
          </span>
        ))}
      </div>
      <div className="fe-actions">
        <button className="btn primary" style={{ padding: '6px 14px', fontSize: 12 }} disabled={fix.isPending} onClick={save}>
          {fix.isPending ? 'Saving…' : 'Save fix'}
        </button>
        <button className="btn" style={{ padding: '6px 14px', fontSize: 12 }} onClick={onCancel}>Cancel</button>
      </div>
      <div className={`fe-msg ${fix.isError ? 'err' : ''}`}>
        {fix.isError ? String((fix.error as Error).message) : ''}
      </div>
    </div>
  );
}
