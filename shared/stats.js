// JS port of avtoservis/core/stats.py: spending per month and per item, so'm per km, CSV.
import { civil, fdiv } from './clock.js';
import { divRound, split } from './money.js';

export function spending(records, months, today) {
  const [y, m] = civil(today);
  const keys = [];
  for (let k = months - 1; k >= 0; k--) {
    const idx = y * 12 + (m - 1) - k;
    keys.push([fdiv(idx, 12), idx - fdiv(idx, 12) * 12 + 1]);
  }
  const perMonth = new Map(keys.map(([yy, mm]) => [`${yy}-${mm}`, 0]));
  const perItem = new Map();
  let total = 0;
  let labour = 0;
  let parts = 0;
  for (const r of records) {
    const cost = r.labour + r.parts;
    total += cost;
    labour += r.labour;
    parts += r.parts;
    const [yy, mm] = civil(r.day);
    const key = `${yy}-${mm}`;
    if (perMonth.has(key)) perMonth.set(key, perMonth.get(key) + cost);
    split(cost, r.items.length).forEach((share, i) => perItem.set(r.items[i], (perItem.get(r.items[i]) ?? 0) + share));
  }
  const items = [...perItem.entries()].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  return { months: keys.map(([yy, mm]) => ({ y: yy, m: mm, total: perMonth.get(`${yy}-${mm}`) })),
    items: items.map(([id, t]) => ({ id, total: t })), total, labour, parts, n: records.length };
}

export const perKm = (total, kmDriven) => (kmDriven >= 100 ? divRound(total, kmDriven) : null);

function cell(value) {
  let s = String(value);
  if (['=', '+', '-', '@', '\t', '\r'].includes(s.slice(0, 1))) s = `'${s}`;
  return /[,"\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export const csv = (rows) => rows.map((row) => `${row.map(cell).join(',')}\r\n`).join('');
