// JS port of avtoservis/core/clock.py: Tashkent time (UTC+5, no DST) with whole numbers only.
export const TZ_OFFSET_MS = 5 * 3_600_000;
export const DAY_MS = 86_400_000;
export const HOUR_MS = 3_600_000;
export const MIN_MS = 60_000;
export const fdiv = (a, b) => Math.floor(a / b);
const mod = (a, b) => ((a % b) + b) % b;

export const localDay = (ms) => fdiv(ms + TZ_OFFSET_MS, DAY_MS);
export const localMinute = (ms) => fdiv(mod(ms + TZ_OFFSET_MS, DAY_MS), MIN_MS);
export const weekday = (day) => mod(day + 3, 7);

export function civil(day) {
  const z = day + 719_468;
  const era = fdiv(z, 146_097);
  const doe = z - era * 146_097;
  const yoe = fdiv(doe - fdiv(doe, 1460) + fdiv(doe, 36_524) - fdiv(doe, 146_096), 365);
  const y = yoe + era * 400;
  const doy = doe - (365 * yoe + fdiv(yoe, 4) - fdiv(yoe, 100));
  const mp = fdiv(5 * doy + 2, 153);
  const d = doy - fdiv(153 * mp + 2, 5) + 1;
  const m = mp < 10 ? mp + 3 : mp - 9;
  return [m <= 2 ? y + 1 : y, m, d];
}

export const atLocal = (day, minute) => day * DAY_MS + minute * MIN_MS - TZ_OFFSET_MS;
export const hhmm = (minute) => `${String(fdiv(minute, 60)).padStart(2, '0')}:${String(minute % 60).padStart(2, '0')}`;

export function daysFromCivil(y0, m, d) {
  const y = m <= 2 ? y0 - 1 : y0;
  const era = fdiv(y, 400);
  const yoe = y - era * 400;
  const doy = fdiv(153 * (m > 2 ? m - 3 : m + 9) + 2, 5) + d - 1;
  const doe = yoe * 365 + fdiv(yoe, 4) - fdiv(yoe, 100) + doy;
  return era * 146_097 + doe - 719_468;
}

export function monthLen(y, m) {
  if (m === 2) return y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0) ? 29 : 28;
  return [4, 6, 9, 11].includes(m) ? 30 : 31;
}

export function addMonths(day, months) {
  const [y, m, d] = civil(day);
  const k = y * 12 + (m - 1) + months;
  const y2 = fdiv(k, 12);
  const m2 = mod(k, 12) + 1;
  return daysFromCivil(y2, m2, Math.min(d, monthLen(y2, m2)));
}

/** "12.11.2026", "12/11/2026" or "12.11.26" -> day number, or null. */
export function parseDate(text) {
  if (typeof text !== 'string' || text.length > 12) return null;
  const parts = text.trim().replace(/[/-]/g, '.').split('.');
  if (parts.length !== 3 || !parts.every((p) => /^[0-9]{1,4}$/.test(p))) return null;
  let [d, m, y] = parts.map(Number);
  if (y < 100) y += 2000;
  if (!(y >= 1990 && y <= 2100 && m >= 1 && m <= 12 && d >= 1 && d <= monthLen(y, m))) return null;
  return daysFromCivil(y, m, d);
}
