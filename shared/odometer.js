// JS port of avtoservis/core/odometer.py: the odometer guard and the passport's consistency check.
import { fdiv } from './clock.js';
import { MAX_KM } from './cars.js';
import { InputError, whole } from './text.js';

export function check(last, day, km, confirmed, jumpPerDay) {
  const n = whole(km, 0, MAX_KM, 'odo');
  if (last === null || last === undefined) return [n, false];
  if (n < last[1]) throw new InputError('odo_back');
  const days = Math.max(1, day - last[0]);
  return [n, n - last[1] > jumpPerDay * days && !confirmed];
}

export function fits(points, day, km) {
  const before = points.filter(([d]) => d < day).map(([, k]) => k);
  const after = points.filter(([d]) => d > day).map(([, k]) => k);
  if ((before.length && km < Math.max(...before)) || (after.length && km > Math.min(...after))) throw new InputError('odo_order');
}

export function consistency(points, jumpPerDay) {
  let back = 0;
  let jumps = 0;
  for (let i = 1; i < points.length; i++) {
    const [a, b] = [points[i - 1], points[i]];
    if (b[1] < a[1]) back += 1;
    if (b[1] - a[1] > jumpPerDay * Math.max(1, b[0] - a[0])) jumps += 1;
  }
  const first = points[0];
  const last = points.at(-1);
  const span = points.length ? last[0] - first[0] : 0;
  const driven = points.length ? last[1] - first[1] : 0;
  return { ok: back === 0, back, jumps, n: points.length, first_day: first?.[0] ?? null, last_day: last?.[0] ?? null,
    first_km: first?.[1] ?? null, last_km: last?.[1] ?? null, per_day: span > 0 ? fdiv(driven, span) : null };
}
