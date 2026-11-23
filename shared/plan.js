// JS port of avtoservis/core/plan.py: the plan for a car and each item's status (the one function every screen uses).
import { addMonths, civil, daysFromCivil, fdiv } from './clock.js';
import { dayFor, odoOn } from './forecast.js';
import { divRound } from './money.js';
import { InputError, whole } from './text.js';

export const ALL_FUELS = ['benzin', 'metan', 'propan', 'gibrid', 'elektr'];
export const SEASONS = ['winter', 'summer'];
export const STATE_ORDER = { due: 0, soon: 1, ok: 2, unknown: 3 };

export function interval(item, fuel, usage) {
  let km = item.km;
  if (km) {
    let pct = item.fuel_pct?.[fuel] ?? 100;
    if (usage === 'taksi') pct = fdiv(pct * (item.taxi_pct ?? 100), 100);
    km = divRound(km * pct, 10_000) * 100;
  }
  const months = usage === 'taksi' && item.taxi_months ? item.taxi_months : item.months;
  return [km || null, months || null];
}

export function itemsFor(cfg, model, fuel, usage, overrides = {}) {
  const out = [];
  for (const it of cfg.items) {
    if (!(it.fuels ?? ALL_FUELS).includes(fuel) || (it.belt && model.grm !== 'belt')) continue;
    const [km0, months0] = interval(it, fuel, usage);
    const o = overrides?.[it.id] ?? {};
    const km = o.km || km0;
    const months = o.months || months0;
    out.push({ id: it.id, km: it.km ? km : null, months, calendar: Boolean(it.calendar), season: it.season ?? null, off: Boolean(o.off), base_km: km0 });
  }
  return out;
}

export function checkOverride(item, km, months) {
  const out = {};
  if (km !== null && km !== undefined && km !== '' && item.km) out.km = whole(km, 500, 200_000, 'interval');
  if (months !== null && months !== undefined && months !== '' && item.months) out.months = whole(months, 1, 120, 'interval');
  if (!Object.keys(out).length) throw new InputError('interval');
  return out;
}

export function nextSeason(season, day) {
  const y = civil(day)[0];
  let best = null;
  for (const yy of [y, y + 1]) {
    season.forEach(([m, d], i) => {
      const dd = daysFromCivil(yy, m, d);
      if (dd > day && (best === null || dd < best[0])) best = [dd, SEASONS[i]];
    });
  }
  return best;
}

export function status(it, last, fc, today, cfg) {
  const out = { id: it.id, km_iv: it.km, months: it.months, due_km: null, due_day: null, km_left: null, days_left: null, lo_day: null,
    hi_day: null, basis: 'date', guess: Boolean(last.guess), season: null, last_km: last.km ?? null, last_day: last.day ?? null };
  const hasDay = last.day !== null && last.day !== undefined;
  if (it.season) {
    [out.due_day, out.season] = nextSeason(it.season, hasDay ? last.day : today - 1);
    out.guess = !hasDay;
    out.cycle = String(out.due_day);
  } else if (it.km === null) {
    if (hasDay) out.due_day = addMonths(last.day, it.months);
    out.cycle = `-:${hasDay ? last.day : 'None'}`;
  } else {
    const dueKm = last.km + it.km;
    const kmDay = dayFor(fc, dueKm);
    let loDay = dayFor(fc, dueKm, fc.hi);
    let hiDay = dayFor(fc, dueKm, fc.lo);
    const dateDay = it.months && hasDay ? addMonths(last.day, it.months) : null;
    const days = [kmDay, dateDay].filter((x) => x !== null);
    Object.assign(out, { due_km: dueKm, km_left: dueKm - odoOn(fc, today), due_day: days.length ? Math.min(...days) : null,
      basis: dateDay !== null && (kmDay === null || dateDay < kmDay) ? 'date' : 'km' });
    if (dateDay !== null) {
      loDay = loDay === null ? dateDay : Math.min(loDay, dateDay);
      hiDay = hiDay === null ? dateDay : Math.min(hiDay, dateDay);
    }
    Object.assign(out, { lo_day: loDay, hi_day: hiDay, cycle: `${last.km}:${hasDay ? last.day : 'None'}` });
  }
  if (out.due_day !== null) out.days_left = out.due_day - today;
  const kl = out.km_left;
  const dl = out.days_left;
  if (kl === null && dl === null) out.state = 'unknown';
  else if ((kl !== null && kl <= 0) || (dl !== null && dl <= 0)) out.state = 'due';
  else if ((kl !== null && kl <= cfg.soon_km) || (dl !== null && dl <= cfg.soon_days)) out.state = 'soon';
  else out.state = 'ok';
  return out;
}

export const sortKey = (st) => [STATE_ORDER[st.state], st.due_day ?? 1e9, st.id];
export function byUrgency(a, b) {
  const x = sortKey(a);
  const y = sortKey(b);
  return x[0] - y[0] || x[1] - y[1] || (x[2] < y[2] ? -1 : x[2] > y[2] ? 1 : 0);
}

export function defaultLast(it, odo, today, lastOil) {
  if (it.season || it.calendar) return { km: null, day: null, guess: true };
  if ((it.id === 'motor_moyi' || it.id === 'moy_filtri') && lastOil !== null && lastOil !== undefined) return { km: lastOil, day: today, guess: false };
  const km = it.km ? fdiv(odo, it.km) * it.km : null;
  return { km, day: today, guess: true };
}
