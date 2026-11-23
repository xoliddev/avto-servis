// Hand-drawn SVG charts: the odometer (real readings, the forecast line with its uncertainty fan, and markers where
// each service falls due, with the range of days it may land on) and the monthly spending bars. No chart library.
import { odoOn } from '../shared/forecast.js';
import { dateShort, itemName } from '../shared/i18n.js';
import { group } from '../shared/money.js';
import { s } from './util.js';

const W = 340;
const H = 210;
const PAD = { l: 46, r: 12, t: 14, b: 26 };

function niceStep(span) {
  for (const st of [100, 200, 500, 1000, 2000, 5000, 10_000, 20_000, 50_000]) if (span / st <= 4) return st;
  return 100_000;
}

/** The odometer chart. `v` is a car view (points, fc, statuses, today). */
export function odometerChart(v, { T, lang, P }) {
  const { points, fc, today } = v;
  const upcoming = v.statuses.filter((st) => st.due_km !== null && st.due_day !== null && st.due_day <= today + 75 && st.due_day >= today - 30);
  const soonest = [...new Set(upcoming.map((st) => st.hi_day ?? st.due_day))].sort((a, b) => a - b).slice(0, 2);
  const horizon = Math.min(today + 75, Math.max(today + 30, ...soonest.map((d) => d + 6)));
  const marks = upcoming.filter((st) => st.due_day <= horizon);
  const from = Math.max(points[0][0], Math.min(today - 30, fc.day - 10));
  const shown = points.filter(([d]) => d >= from);
  const real = shown.length ? shown : [points.at(-1)];
  const kmLo = Math.min(...real.map(([, k]) => k));
  const kmHi = Math.max(odoOn(fc, horizon, fc.hi), ...marks.map((st) => st.due_km));
  const step = niceStep(Math.max(500, kmHi - kmLo));
  const y0 = Math.floor(kmLo / step) * step;
  const y1 = Math.ceil(kmHi / step) * step;
  const x = (d) => PAD.l + Math.round(((d - from) * (W - PAD.l - PAD.r)) / Math.max(1, horizon - from));
  const y = (k) => H - PAD.b - Math.round(((k - y0) * (H - PAD.t - PAD.b)) / Math.max(1, y1 - y0));
  const kids = [];
  for (let k = y0; k <= y1; k += step) {
    kids.push(s('line', { x1: PAD.l, x2: W - PAD.r, y1: y(k), y2: y(k), class: 'c-grid' }),
      s('text', { x: PAD.l - 6, y: y(k) + 4, class: 'c-axis', 'text-anchor': 'end' }, group(k)));
  }
  for (const d of [from, today, Math.round((today + horizon) / 2), horizon]) {
    if (d === from && today - from < 8) continue;
    kids.push(s('text', { x: x(d), y: H - 8, class: 'c-axis', 'text-anchor': d === from ? 'start' : d === horizon ? 'end' : 'middle' }, dateShort(T, lang, d)));
  }
  const fan = [[fc.day, fc.km], [horizon, odoOn(fc, horizon, fc.hi)], [horizon, odoOn(fc, horizon, fc.lo)]];
  kids.push(s('polygon', { points: fan.map(([d, k]) => `${x(d)},${y(k)}`).join(' '), class: 'c-fan', 'data-testid': 'chart-fan' }));
  kids.push(s('line', { x1: x(today), x2: x(today), y1: PAD.t, y2: H - PAD.b, class: 'c-today' }),
    s('text', { x: x(today) + 4, y: PAD.t + 9, class: 'c-axis c-today-label' }, P('when.today')));
  kids.push(s('line', { x1: x(fc.day), y1: y(fc.km), x2: x(horizon), y2: y(odoOn(fc, horizon)), class: 'c-forecast' }));
  kids.push(s('polyline', { points: real.map(([d, k]) => `${x(d)},${y(k)}`).join(' '), class: 'c-real' }));
  for (const [d, k] of real) kids.push(s('circle', { cx: x(d), cy: y(k), r: 3.2, class: 'c-dot' }));
  const groups = new Map();
  for (const st of marks) {
    const key = `${st.due_day}:${st.due_km}`;
    if (!groups.has(key)) groups.set(key, { ...st, names: [] });
    groups.get(key).names.push(itemName(T, lang, st.id));
  }
  [...groups.values()].sort((a, b) => a.due_day - b.due_day).slice(0, 3).forEach((g, i) => {
    const gx = x(Math.min(g.due_day, horizon));
    const gy = y(g.due_km);
    const cls = `c-mark ${g.state}`;
    if (g.lo_day !== null && g.hi_day !== null) {
      kids.push(s('line', { x1: x(Math.max(from, g.lo_day)), x2: x(Math.min(horizon, g.hi_day)), y1: gy, y2: gy, class: `c-range ${g.state}` }));
    }
    kids.push(s('circle', { cx: gx, cy: gy, r: 5.5, class: cls, 'data-testid': `mark-${g.id}` }));
    const label = g.names.length > 1 ? `${g.names[0]} +${g.names.length - 1}` : g.names[0];
    const left = gx > W - 120;
    kids.push(s('text', { x: left ? gx - 9 : gx + 9, y: gy - 8 - (i % 2) * 2, class: 'c-label', 'text-anchor': left ? 'end' : 'start' }, label));
  });
  return s('svg', { viewBox: `0 0 ${W} ${H}`, class: 'c-chart', role: 'img', 'aria-label': P('app.chart'), 'data-testid': 'odo-chart' }, kids);
}

/** Spending per month: twelve bars, the biggest one labelled. */
export function monthBars(months, { T, lang }) {
  const w = 340;
  const hgt = 150;
  const max = Math.max(1, ...months.map((m) => m.total));
  const bw = Math.floor((w - 20) / months.length);
  const kids = [];
  months.forEach((m, i) => {
    const bh = Math.round(((hgt - 42) * m.total) / max);
    const bx = 10 + i * bw;
    kids.push(s('rect', { x: bx + 3, y: hgt - 22 - bh, width: bw - 6, height: Math.max(bh, m.total ? 3 : 1), rx: 3,
      class: m.total === max && m.total ? 'c-bar top' : 'c-bar', 'data-testid': `bar-${i}` }));
    kids.push(s('text', { x: bx + bw / 2, y: hgt - 7, class: 'c-axis', 'text-anchor': 'middle' }, T(lang, `mon.${m.m}`)));
    if (m.total === max && m.total) {
      kids.push(s('text', { x: bx + bw / 2, y: hgt - 28 - bh, class: 'c-label', 'text-anchor': i > months.length - 3 ? 'end' : 'middle' },
        T(lang, 'fmt.thousand', { n: group(Math.round(m.total / 1000)) })));
    }
  });
  return s('svg', { viewBox: `0 0 ${w} ${hgt}`, class: 'c-chart', role: 'img', 'data-testid': 'month-bars' }, kids);
}
