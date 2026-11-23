// JS port of avtoservis/core/forecast.py: daily km as a weighted median of the rates between readings (metres per
// day, whole numbers), the forecast fan, and when a km mark will be reached.
import { fdiv } from './clock.js';
import { ceilDiv } from './money.js';

export const MAX_INTERVALS = 12;
export const WEIGHT_CAP_DAYS = 30;
export const DEFAULT_MARGIN = 45;

export function points(readings) {
  const best = new Map();
  for (const [day, km] of readings) best.set(day, Math.max(km, best.get(day) ?? km));
  return [...best.keys()].sort((a, b) => a - b).map((d) => [d, best.get(d)]);
}

export function intervals(pts) {
  const pairs = [];
  for (let i = 1; i < pts.length; i++) pairs.push([pts[i - 1], pts[i]]);
  return pairs.slice(-MAX_INTERVALS).map(([a, b], i) => {
    const days = b[0] - a[0];
    return [fdiv((b[1] - a[1]) * 1000, days), Math.min(days, WEIGHT_CAP_DAYS) * (i + 1)];
  });
}

export function wquantile(iv, num, den) {
  const ordered = [...iv].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const total = ordered.reduce((s, [, w]) => s + w, 0);
  let cum = 0;
  for (const [rate, w] of ordered) {
    cum += w;
    if (cum * den >= total * num) return rate;
  }
  return ordered.at(-1)[0];
}

export function estimate(readings, defaultKm) {
  const pts = points(readings);
  const iv = intervals(pts);
  let rate;
  let margin;
  let loQ;
  let hiQ;
  if (iv.length) {
    rate = wquantile(iv, 1, 2);
    margin = Math.max(8, fdiv(36, iv.length));
    loQ = wquantile(iv, 1, 5);
    hiQ = wquantile(iv, 4, 5);
  } else {
    rate = defaultKm * 1000;
    margin = DEFAULT_MARGIN;
    loQ = rate;
    hiQ = rate;
  }
  const lo = Math.min(loQ, fdiv(rate * (100 - margin), 100));
  const hi = Math.max(hiQ, ceilDiv(rate * (100 + margin), 100));
  const last = pts.at(-1) ?? [null, null];
  return { rate, lo, hi, n: iv.length, margin, day: last[0], km: last[1] };
}

export const odoOn = (fc, day, rate = fc.rate) => fc.km + fdiv(rate * Math.max(0, day - fc.day), 1000);

export function dayFor(fc, km, rate = fc.rate) {
  if (km <= fc.km) return fc.day;
  if (rate <= 0) return null;
  return fc.day + ceilDiv((km - fc.km) * 1000, rate);
}
