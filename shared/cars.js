// JS port of avtoservis/core/cars.py: models, plates, the car code.
import { clean, InputError, whole } from './text.js';

export const FUELS = ['benzin', 'metan', 'propan', 'gibrid', 'elektr'];
export const USAGES = ['shaxsiy', 'taksi'];
export const MAX_KM = 2_000_000;
export const CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';

export function model(models, mid) {
  const m = typeof mid === 'string' ? models.find((x) => x.id === mid) : null;
  if (!m) throw new InputError('model');
  return m;
}

export function plate(value) {
  if (value === null || value === undefined || value === '') return '';
  if (typeof value !== 'string' || value.length > 16) throw new InputError('plate');
  const s = value.replace(/[\s-]/g, '').toUpperCase();
  let m = /^(\d{2})([A-Z])(\d{3})([A-Z]{2})$/.exec(s);
  if (m) return m.slice(1).join(' ');
  m = /^(\d{2})(\d{3})([A-Z]{3})$/.exec(s);
  if (m) return m.slice(1).join(' ');
  throw new InputError('plate');
}

export function validate(d, models, thisYear) {
  if (!d || typeof d !== 'object' || Array.isArray(d)) throw new InputError('generic');
  const m = model(models, d.model);
  const year = whole(d.year, m.from, Math.min(m.to ?? thisYear, thisYear), 'year');
  const fuel = d.fuel;
  if (!m.fuels.includes(fuel)) throw new InputError('fuel');
  const usage = d.usage ?? 'shaxsiy';
  if (!USAGES.includes(usage)) throw new InputError('usage');
  const odo = whole(d.odo, 0, MAX_KM, 'odo');
  const name = m.id === 'other' ? clean(d.name, 40) : '';
  if (m.id === 'other' && Array.from(name).length < 2) throw new InputError('name');
  const raw = d.last_oil;
  const lastOil = raw === null || raw === undefined || raw === '' ? null : whole(raw, 0, odo, 'last_oil');
  return { model: m.id, name, year, fuel, usage, odo, plate: plate(d.plate), last_oil: lastOil };
}

export function title(models, car) {
  const m = models.find((x) => x.id === car.model);
  const name = car.name || (m ? m.name : '') || car.model;
  return `${name} ${car.year}`;
}

export function codeFrom(n) {
  let out = '';
  let x = n;
  for (let i = 0; i < 8; i++) {
    out += CODE_ALPHABET[x % 32];
    x = Math.floor(x / 32);
  }
  return out;
}

export function normCode(value) {
  if (typeof value !== 'string' || value.length > 20) return null;
  const s = value.replace(/[\s-]/g, '').toUpperCase();
  return s.length === 8 && [...s].every((ch) => CODE_ALPHABET.includes(ch)) ? s : null;
}

export const showCode = (code) => `${code.slice(0, 4)}-${code.slice(4)}`;
