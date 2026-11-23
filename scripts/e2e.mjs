// Browser test of the demo at 1440 px and 375 px. Fails on any console error, page error or failed request.
//   PW_CHANNEL=chrome node scripts/e2e.mjs        (needs `playwright`: npm i --no-save playwright)
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
import { startServer } from './serve.mjs';

const PORT = Number(process.env.E2E_PORT ?? 4362);
const BASE = process.env.E2E_URL ?? `http://127.0.0.1:${PORT}/`;
const server = process.env.E2E_URL ? null : await startServer(PORT);
const browser = await chromium.launch({ channel: process.env.PW_CHANNEL || undefined });
const errors = [];
let checks = 0;
const ok = (cond, msg) => {
  assert.ok(cond, msg);
  checks += 1;
};

async function open(width, height, { lang = 'uz', path = '' } = {}) {
  const ctx = await browser.newContext({ viewport: { width, height }, locale: 'uz-UZ', timezoneId: 'Asia/Tashkent', acceptDownloads: true });
  await ctx.route('https://telegram.org/**', (route) => route.fulfill({ status: 200, contentType: 'text/javascript', body: '' }));
  await ctx.addInitScript((l) => { try { localStorage.setItem('avtoservis.lang', l); } catch { /* */ } }, lang);
  const page = await ctx.newPage();
  page.on('console', (m) => m.type() === 'error' && errors.push(`[${width}] ${m.text()}`));
  page.on('pageerror', (e) => errors.push(`[${width}] ${e.message}`));
  page.on('requestfailed', (r) => errors.push(`[${width}] request failed ${r.url()} ${r.failure()?.errorText}`));
  await page.goto(BASE + path);
  if (!path) await page.waitForSelector('body[data-ready="1"]', { timeout: 20_000 });
  return page;
}

const text = (page, sel) => page.evaluate((s) => document.querySelector(s)?.textContent ?? '', sel);
const has = (page, sel, s) => page.waitForFunction(([q, v]) => document.querySelector(q)?.textContent.includes(v), [sel, s], { timeout: 20_000 });
const noScroll = (page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
const done = (page, n) => page.waitForFunction((k) => document.querySelector(`[data-testid=story-${k}]`).classList.contains('done'), n, { timeout: 90_000 });
async function step(page, n) {
  await page.getByTestId(`story-${n}`).click();
  await done(page, n);
}
const D = '[data-testid=driver-app]';
const M = '[data-testid=master-app]';
const B = '[data-testid=buyer-app]';
const chat = (who) => `[data-testid=${who}-chat]`;

async function story(page, mobile) {
  ok((await text(page, '[data-testid=demo-badge]')).includes('brauzeringizda'), 'demo badge');
  if (mobile) ok(await page.getByTestId('driver-phone').isVisible() && !(await page.getByTestId('master-phone').isVisible()), 'one phone at a time');
  else ok(await page.getByTestId('master-phone').isVisible() && await page.getByTestId('buyer-phone').isVisible(), 'three phones at 1440 px');
  ok(await noScroll(page), 'no horizontal scroll');
  ok((await text(page, `${M} [data-testid=ws-home]`)).includes('Turbo Servis'), 'the workshop panel');
  await step(page, 1);
  ok((await text(page, `${D} [data-testid=odo]`)) === '86 900 km', 'the new car with its odometer');
  ok((await text(page, `${D} [data-testid=due-motor_moyi]`)).startsWith('Motor moyi: 800 km qoldi — taxminan'), 'oil: 800 km left');
  ok((await text(page, `${D} [data-testid=fan]`)).includes('45'), 'a wide fan with one reading');
  await step(page, 2);
  ok(await page.locator(`${D} [data-testid=odo-chart] [data-testid=chart-fan]`).count() === 1, 'the chart with the fan');
  ok(await page.locator(`${D} [data-testid=odo-chart] [data-testid^=mark-]`).count() >= 1, 'service markers on the chart');
  await step(page, 3);
  await has(page, `${D} [data-testid=rate]`, '52 km');
  ok((await text(page, `${D} [data-testid=fan]`)).includes('36'), 'the fan tightens after a reading');
  ok((await text(page, `${D} [data-testid=due-motor_moyi]`)).startsWith('Motor moyi: 540 km qoldi'), 'oil: 540 km left');
  await step(page, 4);
  await has(page, chat('driver'), 'Motor moyi: 436 km qoldi');
  ok(true, 'the reminder in the bot');
  await step(page, 5);
  await has(page, chat('driver'), 'Tasdiqlaysizmi?');
  ok((await text(page, chat('driver'))).includes("465 000 so'm"), 'the workshop record with labour + parts');
  await step(page, 6);
  await has(page, `${D} [data-testid=history]`, 'Servis tasdiqlagan');
  ok((await text(page, `${D} [data-testid=history]`)).includes("O'zi yozgan"), 'verified and self-logged badges');
  await has(page, chat('master'), 'Egasi tasdiqladi');
  ok(true, 'the workshop hears back');
  await step(page, 7);
  ok((await text(page, `${D} [data-testid=per-km]`)).includes("so'm / km"), "so'm per km");
  ok(await page.locator(`${D} [data-testid=month-bars] rect`).count() === 12, 'twelve month bars');
  await step(page, 8);
  await has(page, D, 'Spidometr orqaga ketmaydi');
  ok((await text(page, `${D} [data-testid=odo]`)) !== '87 029 km', 'the lower reading is refused');
  await step(page, 9);
  await has(page, `${B} [data-testid=pp-check]`, 'orqaga qaytmagan');
  ok((await text(page, `${B} [data-testid=passport]`)).includes('Servis tasdiqlagan'), 'the buyer sees the verified timeline');
  ok(!(await text(page, `${B} [data-testid=passport]`)).includes('Jasur'), 'no owner name on the passport');
  await step(page, 10);
  await has(page, `${B} [data-testid=pp-gone]`, 'endi amal qilmaydi');
  ok(true, 'revoked link');
  ok(await noScroll(page), 'still no horizontal scroll');
}

async function russian(page) {
  await step(page, 4);
  ok(await page.locator('[data-testid=story-3].done').count() === 1, 'needed steps marked done');
  await page.getByTestId('demo-lang').click();
  await has(page, '[data-testid=demo-badge]', 'браузере');
  await has(page, D, 'Моторное масло');
  ok(true, 'Russian switch');
}

try {
  for (const [w, h] of [[1440, 900], [375, 812]]) {
    const page = await open(w, h);
    await story(page, w < 760);
    await page.context().close();
  }
  const page = await open(375, 812);
  await russian(page);
  await page.context().close();
  const outside = await open(375, 700, { path: 'webapp/index.html' });
  await has(outside, '#app', 'Telegram ichida');
  ok(true, 'the Mini App outside Telegram asks to open it in Telegram');
  await outside.context().close();
  assert.deepEqual(errors, [], `console errors:\n${errors.join('\n')}`);
  console.log(`e2e: ${checks} checks passed at 1440 px and 375 px, 0 console errors`); // eslint-disable-line no-console
} finally {
  await browser.close();
  server?.close();
}
