// The guided scenario. Each step does what a person would do, through the three phones' Mini Apps and bots. Steps
// run in order (with pauses), all at once ("Hammasini ko'rsatish"), or clicked out of order: a step first quietly
// does whatever it needs from earlier steps. js-tests/demo.test.mjs runs the same steps headless.
import { atLocal } from '../shared/clock.js';
import { AIR, BUYER, COBALT, DRIVER, MASTER, NEXIA, OIL, READING, TYPO } from './seed.js';

export const STEPS = ['step1', 'step2', 'step3', 'step4', 'step5', 'step6', 'step7', 'step8', 'step9', 'step10'];
const NEEDS = { 2: [1], 3: [2], 4: [3], 5: [4], 6: [5], 8: [6], 9: [6], 10: [9] };

const cobalt = (env) => env.backend.cars.find((c) => c.id === env.car) ?? null;
const pending = (env) => env.backend.records.find((r) => r.car_id === env.car && r.status === 'pending') ?? null;

/** Jump the demo clock to `days` after the car was added, at 09:30 Tashkent time (reminders sleep at night). */
function jumpTo(env, days) {
  const b = env.backend;
  const target = atLocal(cobalt(env).created_day + days, 9 * 60 + 30);
  if (target > b.nowMs()) b.advance(target - b.nowMs());
}

const ACTIONS = {
  // 1. Jasur adds his Cobalt 2021 on metan: 86 900 km, the oil was changed at 80 900.
  async 1(env) {
    const { backend: b, ui, focus, pause } = env;
    if (cobalt(env)) return;
    focus(DRIVER, 'app');
    if (ui) env.car = await ui.addCar(COBALT);
    else env.car = b.addCar(DRIVER, COBALT).car.id;
    await pause(900);
  },
  // 2. The plan appears with forecasts; he changed the air filter himself and logs it ("O'zi yozgan").
  async 2(env) {
    const { backend: b, ui, focus, pause } = env;
    focus(DRIVER, 'app');
    await ui?.showPlan(env.car);
    await pause(1600);
    if (!b.records.some((r) => r.car_id === env.car && r.items.includes('havo_filtri'))) {
      if (ui) await ui.logSelf(env.car, AIR);
      else b.addRecord(DRIVER, env.car, AIR);
    }
    await pause(700);
  },
  // 3. Five days later he sends the odometer: 87 160 km. Daily km is measured now, and the fan tightens.
  async 3(env) {
    const { backend: b, ui, focus, pause } = env;
    if (b.readings.some((r) => r.car_id === env.car && r.km >= READING)) return;
    jumpTo(env, 5);
    focus(DRIVER, 'app');
    if (ui) await ui.sendKm(env.car, READING);
    else b.addReading(DRIVER, env.car, READING);
    await pause(1500);
  },
  // 4. Two days on, 09:30: the bot reminds him — "Motor moyi: 436 km qoldi".
  async 4(env) {
    const { backend: b, focus, pause } = env;
    if (!env.reminded) {
      jumpTo(env, 7);
      b.tick();
      env.reminded = true;
    }
    focus(DRIVER, 'chat');
    await pause(1800);
  },
  // 5. At Turbo Servis the master opens the car by its code and records oil + filter: labour and parts.
  async 5(env) {
    const { backend: b, ui, focus, pause } = env;
    if (pending(env) || b.records.some((r) => r.car_id === env.car && r.workshop_id !== null)) return;
    const code = b.carView(DRIVER, env.car).car.code;
    focus(MASTER, 'app');
    if (ui) await ui.workshopRecord(code, OIL);
    else {
      const v = b.openCar(MASTER, code);
      b.wsRecord(MASTER, v.car.id, OIL);
    }
    await pause(900);
  },
  // 6. Jasur gets "Tasdiqlaysizmi?" and confirms: the oil forecast starts over, the record shows "Servis tasdiqlagan".
  async 6(env) {
    const { backend: b, ui, bots, focus, pause } = env;
    const rec = pending(env);
    if (rec) {
      focus(DRIVER, 'chat');
      await pause(1200);
      const msg = bots[DRIVER].messages.findLast((m) => m.kb.flat().some((k) => k.data === `ok:${rec.id}:a`));
      if (msg) bots[DRIVER].press(msg.id, `ok:${rec.id}:a`);
      else b.decide(DRIVER, rec.id, true, true);
      await pause(1400);
    }
    focus(DRIVER, 'app');
    await ui?.showHistory(env.car);
    await pause(1300);
  },
  // 7. Spending: the Nexia's two years — per month, per item, so'm per km.
  async 7({ ui, focus, pause }) {
    focus(DRIVER, 'app');
    await ui?.showStats(NEXIA);
    await pause(1600);
  },
  // 8. A typo: 87 029 instead of 87 290 — refused, the odometer does not go back.
  async 8(env) {
    const { backend: b, ui, focus, pause } = env;
    focus(DRIVER, 'app');
    if (ui) await ui.sendKm(env.car, TYPO);
    else {
      try {
        b.addReading(DRIVER, env.car, TYPO);
      } catch (e) {
        env.refused = e.code;
      }
    }
    await pause(1800);
  },
  // 9. Selling the car: a Servis pasporti link for 30 days; the buyer opens it and sees the verified timeline.
  async 9(env) {
    const { backend: b, ui, bots, focus, pause } = env;
    if (!env.token) {
      focus(DRIVER, 'app');
      env.token = ui ? await ui.makeLink(env.car) : b.share(DRIVER, env.car, 30, false).token;
      await pause(900);
    }
    focus(BUYER, 'chat');
    bots[BUYER].start(`p_${env.token}`);
    await pause(1300);
    if (ui) await ui.openPassport(env.token);
    await pause(1600);
  },
  // 10. The car is sold: Jasur revokes the link, and the buyer's page says it is no longer valid.
  async 10(env) {
    const { backend: b, ui, focus, pause } = env;
    const live = b.shares.find((s) => s.car_id === env.car && s.revoked_at === null);
    if (live) {
      focus(DRIVER, 'app');
      if (ui) await ui.revoke(env.car, live.id);
      else b.revoke(DRIVER, env.car, live.id);
      await pause(700);
    }
    focus(BUYER, 'app');
    await ui?.refreshPassport();
    await pause(1500);
  },
};

export async function runStep(n, env, quick = false, done = env.done ?? (env.done = new Set())) {
  for (const k of NEEDS[n] ?? []) if (!done.has(k)) await runStep(k, env, true, done);
  const wait = quick ? async () => {} : env.wait ?? (async () => {});
  const ctx = new Proxy(env, { get: (target, key) => {
    if (key === 'ui') return quick ? null : target.ui;
    if (key === 'focus') return quick ? () => {} : target.focus ?? (() => {});
    if (key === 'pause') return (ms = 650) => wait(ms);
    return target[key];
  }, set: (target, key, value) => { target[key] = value; return true; } });
  await ACTIONS[n](ctx);
  done.add(n);
}
