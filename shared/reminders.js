// JS port of avtoservis/core/reminders.py: which reminder keys one car has today.
import { fdiv } from './clock.js';

export const QUIET_FROM = 21 * 60;
export const QUIET_TO = 9 * 60;

export function keysFor(statuses, today, lastReadingDay, cfg) {
  const out = [];
  for (const st of statuses) {
    if (st.state !== 'soon' && st.state !== 'due') continue;
    const base = `${st.id}:${st.cycle}`;
    if (st.state === 'soon') {
      out.push({ key: `${base}:soon`, item: st.id, kind: 'soon' });
      continue;
    }
    const over = st.days_left !== null && st.days_left < 0 ? -st.days_left : 0;
    const week = fdiv(over, 7);
    out.push({ key: week === 0 ? `${base}:due` : `${base}:late${week}`, item: st.id, kind: week === 0 ? 'due' : 'late' });
  }
  if (today - lastReadingDay >= cfg.ask_after_days) out.push({ key: `ask:${lastReadingDay}`, item: null, kind: 'ask' });
  return out;
}

export const quiet = (minute) => minute >= QUIET_FROM || minute < QUIET_TO;
