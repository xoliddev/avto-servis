// JS port of avtoservis/core/money.py: whole so'm only.
import { fdiv } from './clock.js';

export const divRound = (a, b) => fdiv(2 * a + b, 2 * b);
export const ceilDiv = (a, b) => -fdiv(-a, b);
export const group = (n) => (n < 0 ? '-' : '') + String(Math.abs(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');

export function split(total, n) {
  if (n <= 0) return [];
  const base = fdiv(total, n);
  const rest = total - base * n;
  return Array.from({ length: n }, (_, i) => base + (i < rest ? 1 : 0));
}
