// The JS port of the core must give exactly what the Python core gives (shared/test_vectors.json).
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import * as cars from '../shared/cars.js';
import * as clock from '../shared/clock.js';
import * as forecast from '../shared/forecast.js';
import { compute } from '../shared/garage.js';
import * as i18n from '../shared/i18n.js';
import * as money from '../shared/money.js';
import * as odometer from '../shared/odometer.js';
import * as plan from '../shared/plan.js';
import * as records from '../shared/records.js';
import * as reminders from '../shared/reminders.js';
import * as seedgen from '../shared/seedgen.js';
import * as stats from '../shared/stats.js';
import * as text from '../shared/text.js';
import * as token from '../shared/token.js';

const read = (p) => JSON.parse(readFileSync(new URL(p, import.meta.url), 'utf8'));
const V = read('../shared/test_vectors.json');
const data = { people: read('../shared/data/people.json'), models: read('../shared/data/models.json'), plan: read('../shared/data/plan.json') };
const TODAY = V.today;
const t = i18n.makeT({ uz: read('../shared/locales/uz.json'), ru: read('../shared/locales/ru.json') });

function res(fn) {
  try {
    return { ok: fn() ?? null };
  } catch (e) {
    if (e instanceof text.InputError) return { error: e.code };
    throw e;
  }
}

test('Tashkent calendar, month arithmetic, dates typed by people, text cleaning, FNV-1a', () => {
  for (const v of V.civil) {
    assert.deepEqual(clock.civil(v.day), v.out, String(v.day));
    assert.equal(clock.daysFromCivil(...v.out), v.back);
  }
  for (const v of V.add_months) assert.equal(clock.addMonths(v.day, v.n), v.out, JSON.stringify(v));
  for (const v of V.parse_date) assert.equal(clock.parseDate(v.in), v.out, String(v.in));
  for (const v of V.clean) assert.equal(text.clean(v.in, v.n), v.out, String(v.in));
  for (const v of V.whole) assert.deepEqual(res(() => text.whole(v.in, 1, 5, 'n')), v.out, JSON.stringify(v.in));
  for (const v of V.h32) assert.equal(text.h32(v.in), v.out, v.in);
  for (const v of V.split) assert.deepEqual(money.split(v.t, v.n), v.out);
});

test('cars: models, years, fuels, plates, the car code', () => {
  for (const v of V.car) assert.deepEqual(res(() => cars.validate(v.in, data.models, 2026)), v.out, JSON.stringify(v.in));
  for (const v of V.code) assert.equal(cars.codeFrom(v.n), v.out);
  for (const v of V.norm_code) assert.equal(cars.normCode(v.in), v.out, String(v.in));
  assert.deepEqual([['cobalt', ''], ['other', 'Lada Vesta']].map(([m, n]) => cars.title(data.models, { model: m, name: n, year: 2020 })), V.title);
});

test('daily km (weighted median), the fan, odometer guard, records between readings, consistency', () => {
  for (const v of V.forecast) {
    const fc = forecast.estimate(v.in, 45);
    assert.deepEqual(fc, v.fc, JSON.stringify(v.in));
    assert.deepEqual([0, 1, 30].map((d) => forecast.odoOn(fc, TODAY + d)), v.odo);
    const out = [];
    for (const k of [-5, 0, 1, 600, 10_000]) for (const r of [fc.rate, fc.lo, fc.hi, 0]) out.push(forecast.dayFor(fc, fc.km + k, r));
    assert.deepEqual(out, v.day_for);
  }
  for (const v of V.check) assert.deepEqual(res(() => odometer.check(...v.in, 1500)), v.out, JSON.stringify(v.in));
  const pts = [[TODAY - 20, 100], [TODAY - 10, 400], [TODAY, 900]];
  for (const v of V.fits) assert.deepEqual(res(() => odometer.fits(pts, v.day, v.km)), v.out, JSON.stringify(v));
  assert.deepEqual([pts, [], [[1, 5]], [[1, 5], [2, 4], [3, 9000]]].map((p) => odometer.consistency(p, 1500)), V.consistency);
});

test('plan: intervals by fuel and taxi use, items per car, seasons, every status, defaults, own intervals', () => {
  for (const v of V.interval) {
    const it = data.plan.items.find((x) => x.id === v.item);
    assert.deepEqual(plan.interval(it, v.fuel, v.usage), v.out, JSON.stringify(v));
  }
  for (const v of V.items_for) {
    assert.deepEqual(plan.itemsFor(data.plan, cars.model(data.models, v.model), v.fuel, v.usage, { motor_moyi: { km: 7000, months: null, off: 0 } }), v.out);
  }
  for (const v of V.season) assert.deepEqual(plan.nextSeason([[11, 15], [3, 15]], v.day), v.out, String(v.day));
  for (const v of V.status) assert.deepEqual(plan.status(v.it, v.last, v.fc, TODAY, data.plan), v.out, JSON.stringify([v.it.id, v.last]));
  for (const v of V.default_last) {
    const lo = V.default_last.indexOf(v) % 2 === 0 ? null : 80_900;
    assert.deepEqual(plan.defaultLast(v.it, 86_900, TODAY, lo), v.out, v.it.id);
  }
  for (const v of V.override) assert.deepEqual(res(() => plan.checkOverride(data.plan.items[0], ...v.in)), v.out, JSON.stringify(v.in));
});

test('records, dates, spending per month and item, so\'m per km, CSV without formulas, reminder keys', () => {
  for (const v of V.record) assert.deepEqual(res(() => records.validate(v.in, ['motor_moyi', 'moy_filtri', 'havo_filtri'], TODAY)), v.out, JSON.stringify(v.in));
  for (const v of V.day_of) assert.deepEqual(res(() => records.dayOf(v.in, TODAY, v.ahead)), v.out, JSON.stringify(v));
  for (const v of V.spending) assert.deepEqual(stats.spending(v.recs, v.m, TODAY), v.out);
  for (const v of V.per_km) assert.equal(stats.perKm(v.t, v.km), v.out);
  assert.equal(stats.csv(V.csv.rows), V.csv.out);
  for (const v of V.keys) assert.deepEqual(reminders.keysFor(v.st, v.today, v.last, data.plan), v.out);
});

test('Servis pasporti tokens: SHA-256 / HMAC like Python, forged or cut tokens refused', () => {
  const secret = token.secretFrom(V.token.seed);
  assert.equal(token.hex(secret), V.token.secret);
  for (const m of V.token.made) {
    const nonce = Uint8Array.from(m.nonce.match(/../g).map((x) => Number.parseInt(x, 16)));
    assert.equal(token.make(secret, nonce), m.token);
  }
  for (const v of V.token.check) assert.equal(token.nonceOf(secret, v.in), v.out, String(v.in));
});

test('the seeded world and the Nexia\'s plan are the same in Python and JS (also on New Year\'s Eve)', () => {
  for (const [now, { world, nexia }] of Object.entries(V.world)) {
    const w = seedgen.world(data.people, data.models, data.plan, Number(now));
    assert.deepEqual(w, world, now);
    const car = w.cars[0];
    const rows = w.items.filter((r) => r.car_id === car.id).map((r) => ({ ...r, km: null, months: null, off: 0 }));
    const snap = compute(car, rows, w.readings.filter((r) => r.car_id === car.id), w.records.filter((r) => r.car_id === car.id), data.models, data.plan, w.today);
    assert.deepEqual(snap, nexia, now);
  }
});

test('the same sentence in Python and JS: "Motor moyi: 540 km qoldi — taxminan ..." in Uzbek and Russian', () => {
  for (const v of V.lines) {
    assert.equal(i18n.dueLine(t, 'uz', v.st, v.today), v.uz);
    assert.equal(i18n.dueLine(t, 'ru', v.st, v.today), v.ru);
  }
  for (const v of V.dates) {
    assert.deepEqual([i18n.whenDay(t, 'uz', v.day, v.today), i18n.whenDay(t, 'ru', v.day, v.today), i18n.dateFull(v.day)], [v.uz, v.ru, v.full]);
  }
  const uz = Object.keys(read('../shared/locales/uz.json')).sort();
  assert.deepEqual(Object.keys(read('../shared/locales/ru.json')).sort(), uz, 'both locales have the same keys');
});
