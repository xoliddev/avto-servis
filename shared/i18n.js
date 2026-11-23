// JS port of avtoservis/i18n.py: locale templates with escaped params and the formatters every screen needs. The
// Mini App and the browser demo's bot use it, so every sentence reads exactly like the real bot's.
import { civil } from './clock.js';
import { group } from './money.js';

export class Raw {
  constructor(html) {
    this.html = String(html);
  }

  toString() {
    return this.html;
  }
}

export const escapeHtml = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

export function render(template, params = {}) {
  return template.replace(/\{(\w+)\}/g, (m, k) => {
    if (!(k in params)) return m;
    const v = params[k];
    return v instanceof Raw ? v.html : escapeHtml(v);
  });
}

export const normLang = (code) => (code && String(code).slice(0, 2).toLowerCase() === 'ru' ? 'ru' : 'uz');

/** t(lang, key, params) over {uz, ru} catalogs, falling back to Uzbek, then to the key. */
export function makeT(catalogs) {
  return (lang, key, params) => {
    const l = normLang(lang);
    const template = catalogs[l]?.[key] || catalogs.uz?.[key] || key;
    return render(template, params);
  };
}

export const money = (t, lang, n) => t(lang, 'fmt.sum', { n: group(n) });
export const km = (t, lang, n) => t(lang, 'fmt.km', { n: group(n) });

export function dateShort(t, lang, day) {
  const [, m, d] = civil(day);
  return t(lang, 'fmt.day', { d, month: t(lang, `month.${m}`) });
}

export function dateFull(day) {
  const [y, m, d] = civil(day);
  return `${String(d).padStart(2, '0')}.${String(m).padStart(2, '0')}.${y}`;
}

export function whenDay(t, lang, day, today) {
  const gap = day - today;
  if (gap === 0) return t(lang, 'when.today');
  if (gap === 1) return t(lang, 'when.tomorrow');
  if (gap < 0) return t(lang, 'when.ago', { n: -gap, date: new Raw(dateShort(t, lang, day)) });
  return t(lang, 'when.in', { n: gap, date: new Raw(dateShort(t, lang, day)) });
}

export const itemName = (t, lang, item, season = null) => t(lang, season ? `item.${item}_${season}` : `item.${item}`);

/** The one sentence for a plan item: the plan, the reminders and the passport all use it. */
export function dueLine(t, lang, st, today) {
  const name = new Raw(`<b>${itemName(t, lang, st.id, st.season)}</b>`);
  if (st.state === 'unknown') return t(lang, 'due.unknown', { name });
  if (st.km_left !== null && st.basis === 'km') {
    if (st.km_left <= 0) return t(lang, 'due.over_km', { name, km: new Raw(km(t, lang, -st.km_left)) });
    if (st.due_day === null) return t(lang, 'due.left_km', { name, km: new Raw(km(t, lang, st.km_left)) });
    return t(lang, 'due.left', { name, km: new Raw(km(t, lang, st.km_left)), when: new Raw(whenDay(t, lang, st.due_day, today)) });
  }
  if (st.days_left !== null && st.days_left < 0) return t(lang, 'due.late', { name, n: -st.days_left });
  return t(lang, 'due.date', { name, when: new Raw(whenDay(t, lang, st.due_day, today)) });
}

export const carLine = (card) => [card.title, card.plate].filter(Boolean).join(' · ');
export const fuel = (t, lang, f) => t(lang, `fuel.${f}`);
