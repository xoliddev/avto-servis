// What the story "does with its fingers": taps, typing and scrolling inside the three phones' real Mini App
// screens, so the guided story shows the very same UI a person would use.
export function makeUi({ apps, phones, env, wait, uids: { DRIVER, MASTER, BUYER }, buyer }) {
  const pane = (uid) => phones[uid].appRoot;
  const $ = (uid, sel) => pane(uid).querySelector(sel);
  async function until(uid, sel, ms = 6000) {
    for (let i = 0; i < ms / 50; i++) {
      const el = $(uid, sel);
      if (el && !el.disabled) return el;
      await wait(50);
    }
    throw new Error(`demo: ${sel} did not appear`);
  }
  const scroller = (uid) => pane(uid);
  async function scrollTo(uid, sel, gap = 70) {
    const el = await until(uid, sel);
    const root = scroller(uid);
    root.scrollTo({ top: Math.max(0, el.getBoundingClientRect().top - root.getBoundingClientRect().top + root.scrollTop - gap), behavior: 'smooth' });
    await wait(550);
    return el;
  }
  const tap = async (uid, sel, gap = 160) => { (await scrollTo(uid, sel, gap)).click(); await wait(260); };
  async function type(el, value, slow = true) {
    el.focus?.();
    const v = String(value);
    if (slow) {
      for (let i = 1; i < v.length; i += 2) {
        el.value = v.slice(0, i);
        el.dispatchEvent(new Event('input', { bubbles: true }));
        await wait(28);
      }
    }
    el.value = v;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.blur?.();
  }
  // Screens re-render when the demo clock moves, so always type into the element that is on screen now.
  async function typeIn(uid, sel, value, { slow = true, gap = 120 } = {}) {
    await scrollTo(uid, sel, gap);
    await type($(uid, sel), value, slow);
  }
  const pick = (el, value) => { el.value = String(value); el.dispatchEvent(new Event('change', { bubbles: true })); };
  async function carScreen(cid) {
    const a = apps[DRIVER];
    if (a.screen !== 'car' || a.top?.id !== cid) {
      await a.home();
      await a.open(({ screens }) => screens.open(cid));
    }
    await until(DRIVER, '[data-testid=car-screen]');
  }
  const submitted = async (uid, name) => { for (let i = 0; i < 100 && apps[uid].screen !== name; i++) await wait(50); };

  return {
    async addCar(car) {
      await apps[DRIVER].home();
      await tap(DRIVER, '[data-testid=add-car]');
      await until(DRIVER, '[data-testid=add-form]');
      pick($(DRIVER, '[data-testid=f-model]'), car.model);
      await wait(250);
      pick($(DRIVER, '[data-testid=f-year]'), car.year);
      $(DRIVER, `[data-testid=f-fuel-${car.fuel}]`).click();
      $(DRIVER, `[data-testid=f-usage-${car.usage}]`).click();
      await wait(300);
      await typeIn(DRIVER, '[data-testid=f-odo]', car.odo);
      await typeIn(DRIVER, '[data-testid=f-plate]', car.plate, { slow: false });
      await typeIn(DRIVER, '[data-testid=f-oil]', car.last_oil);
      await tap(DRIVER, '[data-testid=f-save]');
      await submitted(DRIVER, 'car');
      return apps[DRIVER].top.id;
    },
    async showPlan(cid) {
      await carScreen(cid);
      await scrollTo(DRIVER, '[data-testid=odo-chart]', 60);
      await wait(1200);
      await scrollTo(DRIVER, '[data-testid=plan]', 50);
    },
    async logSelf(cid, rec) {
      await carScreen(cid);
      await tap(DRIVER, '[data-testid=act-log]');
      await until(DRIVER, '[data-testid=log-form]');
      for (const it of rec.items) await tap(DRIVER, `[data-testid=l-item-${it}] span`, 120);
      await typeIn(DRIVER, '[data-testid=l-parts]', rec.parts, { gap: 120 });
      await typeIn(DRIVER, '[data-testid=l-shop]', rec.shop, { slow: false });
      await wait(400);
      await tap(DRIVER, '[data-testid=l-save]');
      await submitted(DRIVER, 'car');
    },
    async sendKm(cid, km) {
      await carScreen(cid);
      await typeIn(DRIVER, '[data-testid=km-input]', km);
      await wait(300);
      $(DRIVER, '[data-testid=km-send]').click();
      await wait(700);
      await scrollTo(DRIVER, '[data-testid=odo-chart]', 60).catch(() => {});
    },
    async workshopRecord(code, rec) {
      await apps[MASTER].home();
      await typeIn(MASTER, '[data-testid=ws-code]', code, { gap: 80 });
      await tap(MASTER, '[data-testid=ws-open]');
      await submitted(MASTER, 'ws-car');
      await scrollTo(MASTER, '[data-testid=ws-form]', 40);
      for (const it of rec.items) await tap(MASTER, `[data-testid=w-item-${it}] span`, 120);
      await typeIn(MASTER, '[data-testid=w-km]', rec.km, { gap: 140 });
      await typeIn(MASTER, '[data-testid=w-labour]', rec.labour);
      await typeIn(MASTER, '[data-testid=w-parts]', rec.parts);
      await typeIn(MASTER, '[data-testid=w-note]', rec.note, { slow: false });
      await scrollTo(MASTER, '[data-testid=w-total]', 160);
      await wait(700);
      await tap(MASTER, '[data-testid=w-send]');
      await wait(400);
    },
    async showHistory(cid) {
      await carScreen(cid);
      await tap(DRIVER, '[data-testid=act-history]');
      await until(DRIVER, '[data-testid=badge-verified]');
    },
    async showStats(cid) {
      await carScreen(cid);
      await tap(DRIVER, '[data-testid=act-stats]');
      await scrollTo(DRIVER, '[data-testid=month-bars]', 140);
    },
    async makeLink(cid) {
      await carScreen(cid);
      await tap(DRIVER, '[data-testid=act-passport]');
      await tap(DRIVER, '[data-testid=p-days-30]', 120);
      await tap(DRIVER, '[data-testid=p-make]');
      await until(DRIVER, '[data-testid=p-link]');
      return env.backend.shareList(DRIVER, cid)[0].token;
    },
    async openPassport(token) {
      await buyer.open(token);
      await until(BUYER, '[data-testid=passport]');
      await scrollTo(BUYER, '[data-testid=pp-check]', 60);
      await wait(1100);
      await scrollTo(BUYER, '[data-testid^=pp-rec-]', 90);
    },
    async revoke(cid, sid) {
      if (apps[DRIVER].screen !== 'passport-admin') {
        await carScreen(cid);
        await tap(DRIVER, '[data-testid=act-passport]');
      }
      await tap(DRIVER, `[data-testid=revoke-${sid}]`);
    },
    async refreshPassport() {
      await buyer.refresh();
      await until(BUYER, '[data-testid=pp-gone]');
    },
  };
}
