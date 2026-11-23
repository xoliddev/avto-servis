// JS port of avtoservis/core/records.py: a service record's checks.
import { MAX_KM } from './cars.js';
import { parseDate } from './clock.js';
import { clean, InputError, whole } from './text.js';

export const MAX_MONEY = 50_000_000;
export const MAX_ITEMS = 12;
export const OLDEST_DAYS = 3650;

export function dayOf(value, today, ahead = 0) {
  if (value === null || value === undefined || value === '' || value === 'today') return today;
  if (value === 'yesterday') return today - 1;
  let day;
  if (typeof value === 'number' && Number.isInteger(value)) day = value;
  else {
    day = parseDate(value);
    if (day === null) throw new InputError('date');
  }
  if (!(day >= today - OLDEST_DAYS && day <= today + ahead)) throw new InputError('date');
  return day;
}

export function validate(d, allowed, today) {
  if (!d || typeof d !== 'object' || Array.isArray(d)) throw new InputError('generic');
  const items = d.items;
  if (!Array.isArray(items) || items.length < 1 || items.length > MAX_ITEMS) throw new InputError('items');
  if (items.some((i) => typeof i !== 'string' || !allowed.includes(i)) || new Set(items).size !== items.length) throw new InputError('items');
  const labour = whole(d.labour ?? 0, 0, MAX_MONEY, 'money');
  const parts = whole(d.parts ?? 0, 0, MAX_MONEY, 'money');
  return { items: allowed.filter((i) => items.includes(i)), day: dayOf(d.day, today), km: whole(d.km, 0, MAX_KM, 'odo'), labour, parts,
    note: clean(d.note, 300), shop: clean(d.shop, 60) };
}
