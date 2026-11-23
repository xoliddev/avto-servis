// JS port of avtoservis/core/seedgen.py: the same fictional world, relative to "today" (shared/test_vectors.json).
import { model as findModel } from './cars.js';
import { addMonths, fdiv, localDay } from './clock.js';
import { defaultLast, itemsFor } from './plan.js';
import { h32 } from './text.js';

export const DRIVER = -101;
export const MASTER = -201;
export const BUYER = -301;
export const ADMIN = -901;
export const MASTER2 = -202;
export const MASTER3 = -203;
export const NEXIA = 1;
const LEFTS = [350, 620, 1500, 2600, 3900, 4800];
const SELF_SHOP = '';

export const rnd = (seed, lo, hi) => lo + (h32(seed) % (hi - lo + 1));

export function track(cid, startDay, startKm, daily, today) {
  const out = [[startDay, startKm]];
  let day = startDay;
  let km = startKm;
  for (let k = 0; ; k++) {
    const gap = rnd(`gap:${cid}:${k}`, 6, 16);
    if (day + gap > today - 4) break;
    day += gap;
    km += fdiv(daily * gap * rnd(`km:${cid}:${k}`, 70, 130), 100);
    out.push([day, km]);
  }
  const last = today - rnd(`last:${cid}`, 1, 3);
  out.push([last, km + daily * (last - day)]);
  return out;
}

export function cost(plan, items, seed) {
  const prices = Object.fromEntries(plan.items.map((it) => [it.id, it.price]));
  const pct = rnd(seed, 92, 112);
  const sum = (k) => items.reduce((s, i) => s + prices[i][k], 0);
  return [fdiv(fdiv(sum(0) * pct, 100), 1000) * 1000, fdiv(fdiv(sum(1) * pct, 100), 1000) * 1000];
}

function oilRecords(car, pts, plan, planItems, left, daily) {
  const ids = Object.fromEntries(planItems.map((it) => [it.id, it]));
  if (!ids.motor_moyi) return [];
  const step = Math.min(ids.motor_moyi.km, fdiv(daily * 180, 100) * 100);
  const marks = [];
  for (let km = pts.at(-1)[1] - step + left; km > pts[0][1] + 300; km -= step) marks.push(km);
  return marks.reverse().map((km, i) => {
    const day = Math.max(...pts.filter(([, k]) => k <= km).map(([d]) => d));
    let want = ['motor_moyi', 'moy_filtri'].concat(i % 2 === 1 ? ['havo_filtri', 'salon_filtri'] : []);
    want = want.concat(i % 4 === 3 ? ['tormoz_kolodka'] : [], i % 4 === 2 ? ['svecha'] : []);
    const items = Object.keys(ids).filter((x) => want.includes(x));
    const [labour, parts] = cost(plan, items, `cost:${car.id}:${i}`);
    const mine = i % 3 === 2;
    return { car_id: car.id, day, km, items, labour: mine ? 0 : labour, parts, shop: SELF_SHOP, workshop_id: mine ? null : car.shop,
      by: mine ? car.owner : car.master, note: '' };
  });
}

function extraNexia(car, pts, plan, today) {
  return [['akkumulyator', 300, null], ['antifriz', 250, 2]].map(([item, back, shop]) => {
    const day = Math.max(...pts.filter(([d]) => d <= today - back).map(([d]) => d));
    const km = Math.max(...pts.filter(([d]) => d === day).map(([, k]) => k));
    const [labour, parts] = cost(plan, [item], `extra:${item}`);
    return { car_id: car.id, day, km, items: [item], labour: shop === null ? 0 : labour, parts, shop: SELF_SHOP, workshop_id: shop,
      by: shop === null ? car.owner : MASTER2, note: '' };
  });
}

export function world(people, models, plan, now) {
  const today = localDay(now);
  const users = [{ id: DRIVER, ...people.driver }, { id: MASTER, ...people.master }, { id: BUYER, ...people.buyer },
    { id: ADMIN, name: people.admin.name, phone: '' }];
  const masters = [MASTER, MASTER2, MASTER3];
  users.push({ id: MASTER2, name: 'Otabek Nurmatov', phone: '' }, { id: MASTER3, name: 'Sanjar Xolmatov', phone: '' });
  const shops = people.workshops.map((w, i) => ({ id: i + 1, owner: masters[i], ...w }));
  const specs = [{ ...people.nexia, owner: DRIVER, age: 730, left: 2600, shop: 1 }];
  people.owners.forEach((o, i) => {
    users.push({ id: -102 - i, name: o.name, phone: '' });
    specs.push({ ...o, owner: -102 - i, age: 420 - i * 37, left: LEFTS[i], shop: i === 3 || i === 5 ? 2 : 1 });
  });
  const cars = [];
  const readings = [];
  let records = [];
  const rows = [];
  const access = [];
  specs.forEach((sp, n) => {
    const cid = n + 1;
    const start = today - sp.age;
    const car = { id: cid, owner: sp.owner, model: sp.model, name: '', year: sp.year, fuel: sp.fuel, usage: sp.usage, plate: sp.plate,
      created_day: start, code: `SEED${String(cid).padStart(4, '0')}`, shop: sp.shop, master: masters[sp.shop - 1] };
    const pts = track(cid, start, sp.start_km, sp.daily, today);
    const planItems = itemsFor(plan, findModel(models, sp.model), sp.fuel, sp.usage);
    let recs = oilRecords(car, pts, plan, planItems, sp.left, sp.daily);
    if (cid === NEXIA) recs = recs.concat(extraNexia(car, pts, plan, today));
    const done = new Set(recs.flatMap((r) => r.items));
    for (const it of planItems) {
      let last = defaultLast(it, sp.start_km, start, null);
      const seed = `last:${cid}:${it.id}`;
      if (it.calendar) {
        const day = cid === NEXIA && it.id === 'osago' ? addMonths(today + 12, -12) : today - rnd(seed, 40, 330);
        last = { km: null, day, guess: false };
      } else if (!done.has(it.id) && !it.season) {
        const km = it.km ? Math.max(0, pts.at(-1)[1] - fdiv(it.km * rnd(seed, 10, 60), 100)) : null;
        last = { km, day: today - rnd(`day:${cid}:${it.id}`, 20, 300), guess: false };
      }
      rows.push({ car_id: cid, item: it.id, last_km: last.km, last_day: last.day, guess: last.guess });
    }
    recs.sort((a, b) => a.day - b.day || a.km - b.km);
    readings.push(...pts.map(([d, k]) => ({ car_id: cid, day: d, km: k })));
    records = records.concat(recs);
    access.push({ car_id: cid, workshop_id: sp.shop, allow: [2, 3, 4, 6].includes(cid), since_day: start });
    if (cid === NEXIA) access.push({ car_id: cid, workshop_id: 2, allow: false, since_day: start + 200 });
    const { shop, master, ...plain } = car; // eslint-disable-line no-unused-vars
    cars.push(plain);
  });
  records.forEach((r, i) => { r.id = i + 1; });
  return { today, users, workshops: shops, cars, readings, records, items: rows, access };
}
