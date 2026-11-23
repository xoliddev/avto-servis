// The people of the demo and the story's car. The world itself (Jasur's two-year-old Nexia, six other drivers who
// visit Turbo Servis, three workshops) comes from the shared seed generator and is always relative to "now", so the
// demo works on any date and hour.
import { BUYER, DRIVER, MASTER, NEXIA } from '../shared/seedgen.js';
import { DemoBackend } from './backend.js';

export { BUYER, DRIVER, MASTER, NEXIA };

export const COBALT = { model: 'cobalt', year: 2021, fuel: 'metan', usage: 'shaxsiy', odo: 86_900, plate: '01 A 123 BC', last_oil: 80_900 };
export const AIR = { items: ['havo_filtri'], km: 86_900, labour: 0, parts: 65_000, shop: "O'zim, garajda" };
export const OIL = { items: ['motor_moyi', 'moy_filtri'], km: 87_290, labour: 60_000, parts: 405_000, note: '5W-30, 4 litr' };
export const READING = 87_160;
export const TYPO = 87_029;

export function createDemo({ now, data, lang = 'uz' }) {
  return new DemoBackend({ now, data, lang });
}
