// The browser demo's logic, headless: the story on any date (30 days in a row, across New Year, morning and night),
// in order and out of order, the reminder once, the workshop record waiting for the owner, the passport and its
// revocation, forged bot buttons, and the API stand-ins with the server's error codes.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { makeT } from '../shared/i18n.js';
import { apiFor } from '../demo/api.js';
import { BotSim } from '../demo/bot.js';
import { makeViews } from '../demo/bot-views.js';
import { BUYER, COBALT, createDemo, DRIVER, MASTER, NEXIA, OIL } from '../demo/seed.js';
import { runStep, STEPS } from '../demo/story.js';

const read = (p) => JSON.parse(readFileSync(new URL(p, import.meta.url), 'utf8'));
const data = { people: read('../shared/data/people.json'), models: read('../shared/data/models.json'), plan: read('../shared/data/plan.json') };
const t = makeT({ uz: read('../shared/locales/uz.json'), ru: read('../shared/locales/ru.json') });
const HOUR = 3_600_000;
const at = (iso, hh, mm = 0) => Date.parse(`${iso}T00:00:00Z`) + (hh - 5) * HOUR + mm * 60_000; // Tashkent time

function world(startMs, lang = 'uz') {
  let now = startMs;
  const backend = createDemo({ data, now: () => now, lang });
  const views = makeViews(t);
  const alerts = [];
  const bots = {};
  for (const uid of [DRIVER, MASTER, BUYER]) bots[uid] = new BotSim(backend, uid, t, views, { onAlert: (x) => alerts.push(x) });
  backend.on((ev) => { if (ev.type === 'note') bots[ev.note.to]?.deliver(ev.note); });
  for (const b of Object.values(bots)) b.start();
  return { backend, bots, alerts, advance: (ms) => { now += ms; } };
}
const all = (bot) => bot.messages.map((m) => m.html).join('\n');
const st = (v, id) => v.statuses.find((s) => s.id === id);

test('the whole story works on 30 consecutive days, across New Year, morning and night', async () => {
  for (let d = 0; d < 30; d++) {
    const day = new Date(Date.parse('2026-12-10T00:00:00Z') + d * 86_400_000).toISOString().slice(0, 10);
    for (const hour of [0, 9, 23]) {
      const w = world(at(day, hour, 30));
      const { backend: b, bots } = w;
      for (let n = 1; n <= STEPS.length; n++) await runStep(n, w);
      const v = b.carView(DRIVER, w.car);
      assert.equal(v.fc.rate, 52_000, `${day} ${hour}`);
      assert.equal(st(v, 'motor_moyi').km_left, 6800 - (v.car.odo - 87_290));
      assert.match(all(bots[DRIVER]), /<b>Motor moyi<\/b>: 436 km qoldi — taxminan/, `${day} ${hour}`);
      assert.match(all(bots[DRIVER]), /<b>Turbo Servis<\/b> xizmatni yozdi/);
      assert.match(all(bots[DRIVER]), /Tasdiqlandi/);
      assert.match(all(bots[MASTER]), /Egasi tasdiqladi/);
      assert.match(all(bots[BUYER]), /Servis pasporti: Chevrolet Cobalt 2021 · 01 A 123 BC/);
      assert.equal(w.refused, 'odo_back');
      const hist = b.history(DRIVER, w.car);
      assert.deepEqual(hist.map((r) => [r.verified, r.shop]), [[true, 'Turbo Servis'], [false, "O'zim, garajda"]]);
      assert.throws(() => b.passport(w.token), { code: 'link_gone' });
    }
  }
});

test('steps clicked out of order quietly do what they need, and twice changes nothing', async () => {
  const w = world(at('2026-11-23', 14));
  await runStep(9, w);
  assert.deepEqual([...w.done].sort((a, c) => a - c), [1, 2, 3, 4, 5, 6, 9]);
  const p = w.backend.passport(w.token);
  assert.ok(p.check.ok && p.verified === 1 && p.self === 1);
  await runStep(10, w);
  await runStep(7, w);
  await runStep(4, w);
  await runStep(6, w);
  assert.equal(w.backend.records.filter((r) => r.car_id === w.car).length, 2, 'no second record');
  assert.equal(w.bots[DRIVER].messages.filter((m) => m.html.startsWith('🔔 <b>Chevrolet Cobalt')).length, 1, 'one reminder');
});

test('the forecast tightens with readings and the reminder fires once', () => {
  const { backend: b, advance } = world(at('2026-12-31', 10));
  const v0 = b.addCar(DRIVER, COBALT);
  assert.deepEqual([st(v0, 'motor_moyi').km_left, st(v0, 'motor_moyi').days_left, v0.fc.margin], [800, 18, 45]);
  advance(5 * 86_400_000);
  const v1 = b.addReading(DRIVER, v0.car.id, 87_160).view;
  assert.ok(v1.fc.hi - v1.fc.lo < v0.fc.hi - v0.fc.lo, 'the fan is narrower');
  advance(2 * 86_400_000);
  assert.ok(b.tick().some((n) => n.car_id === v0.car.id));
  assert.ok(!b.tick().some((n) => n.car_id === v0.car.id));
  assert.throws(() => b.addReading(DRIVER, v0.car.id, 87_000), { code: 'odo_back' });
  const jump = b.addReading(DRIVER, v0.car.id, 95_000);
  assert.equal(jump.confirm, true);
});

test('workshops see only cars with their code, and owners only their own', () => {
  const { backend: b } = world(at('2026-11-23', 12));
  const v = b.addCar(DRIVER, COBALT);
  assert.throws(() => b.wsCar(MASTER, v.car.id), { code: 'not_found' });
  assert.throws(() => b.openCar(DRIVER, v.car.code), { code: 'not_found' });
  assert.throws(() => b.openCar(MASTER, 'ZZZZ-ZZZZ'), { code: 'code' });
  b.openCar(MASTER, v.car.code.toLowerCase());
  const [ws] = b.wsRecord(MASTER, v.car.id, OIL);
  assert.equal(ws.records[0].status, 'pending');
  assert.throws(() => b.carView(BUYER, v.car.id), { code: 'not_found' });
  assert.throws(() => b.decide(BUYER, ws.records[0].id, true), { code: 'not_found' });
  const nexia = b.wsCar(MASTER, NEXIA);
  assert.ok(nexia.records.every((r) => r.shop === 'Turbo Servis'));
  const home = b.wsHome(MASTER);
  assert.ok(home.due.length && home.due.every((d) => [2, 3, 4, 6].includes(d.car.id)));
});

test("forged bot buttons and other people's ids are refused", () => {
  const { bots, alerts } = world(at('2026-11-23', 12));
  bots[BUYER].press(1, `c:${NEXIA}`);
  bots[BUYER].press(1, 'ok:1:y');
  bots[BUYER].press(1, `r:${NEXIA}:99999`);
  bots[DRIVER].press(1, 'zz');
  assert.equal(alerts.length, 4);
  assert.match(alerts[0], /Topilmadi|tegishli emas/);
  assert.match(alerts.at(-1), /eskirgan/);
});

test("the API stand-ins answer with the server's shapes and error codes", async () => {
  const { backend: b } = world(at('2026-11-23', 12));
  const api = apiFor(b, DRIVER);
  assert.equal((await api.me()).roles.workshop, null);
  await assert.rejects(api.addCar({ ...COBALT, plate: 'xx' }), { code: 'plate' });
  await assert.rejects(api.addCar({ ...COBALT, year: 2040 }), { code: 'year' });
  await assert.rejects(apiFor(b, BUYER).car(NEXIA), { code: 'not_found' });
  await assert.rejects(api.wsHome(), { code: 'not_found' });
  await assert.rejects(api.share(NEXIA, 5, false), { code: 'generic' });
  const made = await api.share(NEXIA, 7, true);
  assert.equal((await api.passport(made.token)).owner.name, 'Jasur Karimov');
  await assert.rejects(api.passport(`${made.token.slice(0, 31)}A`), { code: 'link_gone' });
  const s = await api.stats(NEXIA);
  assert.ok(s.per_km > 100 && s.months.length === 12);
});
