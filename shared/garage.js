// JS port of compute() / merge_last() in avtoservis/base.py: a car's plan today from its rows. The browser demo's
// backend and the Python service build every screen, reminder and passport from this one function.
import { model as findModel } from './cars.js';
import { estimate, odoOn, points } from './forecast.js';
import { byUrgency, itemsFor, status } from './plan.js';

export function mergeLast(row, recs, item) {
  let last = row ? { km: row.last_km, day: row.last_day, guess: Boolean(row.guess) } : { km: null, day: null, guess: true };
  for (const r of recs) {
    if (!r.items.includes(item.id)) continue;
    const newer = item.km && last.km !== null ? r.km >= last.km : last.day === null || r.day >= last.day;
    if (last.guess || newer) last = { km: r.km, day: r.day, guess: false };
  }
  return last;
}

export function compute(car, rows, readings, recs, models, cfg, today) {
  const byItem = Object.fromEntries(rows.map((r) => [r.item, r]));
  const overrides = Object.fromEntries(rows.map((r) => [r.item, { km: r.km, months: r.months, off: r.off }]));
  const items = itemsFor(cfg, findModel(models, car.model), car.fuel, car.usage, overrides);
  const pts = points(readings.map((r) => [r.day, r.km]).concat(recs.map((r) => [r.day, r.km])));
  const fc = estimate(pts, cfg.daily_km[car.usage]);
  const statuses = [];
  const off = [];
  for (const it of items) {
    const st = status(it, mergeLast(byItem[it.id], recs, it), fc, today, cfg);
    (it.off ? off : statuses).push(st);
  }
  statuses.sort(byUrgency);
  return { items, statuses, off, fc, points: pts, odo: odoOn(fc, today) };
}
