// README media from the real demo: desktop + phone screenshots (JPEG), an 800x500 portfolio thumbnail and a GIF of
// the forecast tightening, the workshop record being confirmed and the buyer's passport. JPEG is encoded by the
// browser (canvas), the GIF by gifenc.
//   PW_CHANNEL=chrome node scripts/shots.mjs [outDir]       (needs playwright + gifenc)
import { mkdirSync, writeFileSync } from 'node:fs';
import gifenc from 'gifenc';
import { chromium } from 'playwright';
import { startServer } from './serve.mjs';

const { GIFEncoder, quantize, applyPalette } = gifenc;
const OUT = process.argv[2] ?? 'docs/media';
const PORT = Number(process.env.SHOTS_PORT ?? 4363);
mkdirSync(OUT, { recursive: true });
const server = await startServer(PORT);
const browser = await chromium.launch({ channel: process.env.PW_CHANNEL || undefined });
const b64 = (buf) => buf.toString('base64');
const ONLY = new Set((process.env.ONLY ?? 'desktop,thumb,mobile,gif').split(','));

async function open(width, height) {
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1, timezoneId: 'Asia/Tashkent' });
  await ctx.route('https://telegram.org/**', (route) => route.fulfill({ status: 200, contentType: 'text/javascript', body: '' }));
  const page = await ctx.newPage();
  await page.goto(`http://127.0.0.1:${PORT}/`);
  await page.waitForSelector('body[data-ready="1"]');
  return page;
}
const done = (page, n) => page.waitForFunction((k) => document.querySelector(`[data-testid=story-${k}]`).classList.contains('done'), n, { timeout: 90_000 });
const step = async (page, n) => { await page.getByTestId(`story-${n}`).click(); await done(page, n); };
const toPhones = (page) => page.evaluate(() => {
  const top = document.querySelector('[data-testid=driver-phone]').getBoundingClientRect().top + window.scrollY;
  window.scrollTo(0, top - 46);
});
const scrollApp = (page, who, sel, gap = 60) => page.evaluate(([w, s, g]) => {
  const pane = document.querySelector(`[data-testid=${w}-app]`);
  const el = pane.querySelector(s);
  if (el) pane.scrollTop = el.getBoundingClientRect().top - pane.getBoundingClientRect().top + pane.scrollTop - g;
}, [who, sel, gap]);

async function canvasOut(page, fn, args) { return Buffer.from(await page.evaluate(fn, args), 'base64'); }
async function jpeg(page, png, name, w, h) {
  const out = await canvasOut(page, async ([src, W, H]) => {
    const img = new Image();
    img.src = `data:image/png;base64,${src}`;
    await img.decode();
    const cv = document.createElement('canvas');
    cv.width = W;
    cv.height = H;
    const g = cv.getContext('2d');
    g.imageSmoothingQuality = 'high';
    g.drawImage(img, 0, 0, W, H);
    return cv.toDataURL('image/jpeg', 0.88).split(',')[1];
  }, [b64(png), w, h]);
  writeFileSync(`${OUT}/${name}`, out);
  console.log('wrote', name); // eslint-disable-line no-console
}

async function thumb(page, shots) {
  const out = await canvasOut(page, async ([a, b, c]) => {
    const load = async (s) => { const i = new Image(); i.src = `data:image/png;base64,${s}`; await i.decode(); return i; };
    const [drv, mst, buy] = await Promise.all([a, b, c].map(load));
    const cv = document.createElement('canvas');
    cv.width = 1600;
    cv.height = 1000;
    const g = cv.getContext('2d');
    const bg = g.createLinearGradient(0, 0, 1600, 1000);
    bg.addColorStop(0, '#2a333c');
    bg.addColorStop(0.55, '#1b2127');
    bg.addColorStop(1, '#111518');
    g.fillStyle = bg;
    g.fillRect(0, 0, 1600, 1000);
    const glow = g.createRadialGradient(1150, 420, 30, 1150, 420, 640);
    glow.addColorStop(0, 'rgba(255,106,43,0.30)');
    glow.addColorStop(1, 'rgba(255,106,43,0)');
    g.fillStyle = glow;
    g.fillRect(0, 0, 1600, 1000);
    // an odometer-like forecast: a solid line of readings, then a dashed line inside a fan
    g.fillStyle = 'rgba(255,106,43,0.13)';
    g.beginPath(); g.moveTo(330, 900); g.lineTo(640, 760); g.lineTo(640, 880); g.closePath(); g.fill();
    g.lineWidth = 5; g.lineCap = 'round'; g.lineJoin = 'round';
    g.strokeStyle = 'rgba(244,241,234,0.85)';
    g.beginPath(); g.moveTo(80, 955); g.lineTo(170, 940); g.lineTo(250, 921); g.lineTo(330, 900); g.stroke();
    g.setLineDash([14, 12]); g.strokeStyle = '#ff6a2b';
    g.beginPath(); g.moveTo(330, 900); g.lineTo(640, 820); g.stroke(); g.setLineDash([]);
    for (const [x, y] of [[80, 955], [170, 940], [250, 921], [330, 900]]) { g.fillStyle = '#f4f1ea'; g.beginPath(); g.arc(x, y, 8, 0, 7); g.fill(); }
    g.fillStyle = '#f0a01c'; g.beginPath(); g.arc(560, 841, 13, 0, 7); g.fill();
    g.fillStyle = '#ffb48f';
    g.font = '700 22px -apple-system, Segoe UI, Roboto, sans-serif';
    g.fillText('T E L E G R A M   B O T   +   M I N I   A P P', 82, 160);
    g.fillStyle = '#ffffff';
    g.font = '800 96px -apple-system, Segoe UI, Roboto, sans-serif';
    g.fillText('Avto', 76, 275);
    g.fillText('Servis', 76, 378);
    ['Moy vaqti kilometrdan oldindan', 'Servis tasdiqlagan tarix', 'Xaridor uchun Servis pasporti'].forEach((s, i) => {
      g.fillStyle = ['#18a06b', '#f0a01c', '#ff6a2b'][i];
      g.beginPath(); g.arc(92, 470 + i * 60, 8, 0, 7); g.fill();
      g.fillStyle = '#e6e2d8';
      g.font = '500 33px -apple-system, Segoe UI, Roboto, sans-serif';
      g.fillText(s, 118, 482 + i * 60);
    });
    g.fillStyle = 'rgba(255,180,143,0.95)';
    g.font = '600 25px -apple-system, Segoe UI, Roboto, sans-serif';
    g.fillText('xoliddev', 82, 690);
    const H = 700;
    const draw = (img, cx, cy, rot) => {
      const w = (img.width * H) / img.height;
      g.save();
      g.translate(cx, cy);
      g.rotate(rot);
      g.shadowColor = 'rgba(0,0,0,0.55)';
      g.shadowBlur = 50;
      g.shadowOffsetY = 26;
      g.beginPath();
      g.roundRect(-w / 2, -H / 2, w, H, (56 * H) / img.height);
      g.fillStyle = '#000';
      g.fill();
      g.shadowColor = 'transparent';
      g.clip();
      g.drawImage(img, -w / 2, -H / 2, w, H);
      g.restore();
    };
    draw(buy, 1385, 525, 0.03);
    draw(mst, 890, 525, -0.03);
    draw(drv, 1138, 505, 0);
    const out = document.createElement('canvas');
    out.width = 800;
    out.height = 500;
    const o = out.getContext('2d');
    o.imageSmoothingQuality = 'high';
    o.drawImage(cv, 0, 0, 800, 500);
    return out.toDataURL('image/jpeg', 0.9).split(',')[1];
  }, shots.map(b64));
  writeFileSync(`${OUT}/thumb.jpg`, out);
  console.log('wrote thumb.jpg'); // eslint-disable-line no-console
}

if (ONLY.has('desktop') || ONLY.has('thumb')) {
  const page = await open(1440, 900);
  for (const n of [1, 2, 3]) await step(page, n);
  await scrollApp(page, 'driver', '[data-testid=odo-chart]', 150);
  const drv = await page.getByTestId('driver-phone').screenshot();
  for (const n of [4, 5]) await step(page, n);
  await scrollApp(page, 'master', '[data-testid=ws-form]', 10);
  const mst = await page.getByTestId('master-phone').screenshot();
  await step(page, 6);
  await step(page, 9);
  await scrollApp(page, 'buyer', '[data-testid=passport]', 0);
  await page.waitForTimeout(300);
  const buy = await page.getByTestId('buyer-phone').screenshot();
  if (ONLY.has('thumb')) await thumb(page, [drv, mst, buy]);
  if (ONLY.has('desktop')) {
    await page.locator('[data-testid=driver-app] [data-testid=back]').click();
    await page.waitForTimeout(400);
    await scrollApp(page, 'driver', '[data-testid=odo-chart]', 160);
    await scrollApp(page, 'buyer', '[data-testid=pp-check]', 210);
    await scrollApp(page, 'master', '[data-testid^=record-]', 60);
    await toPhones(page);
    await page.waitForTimeout(200);
    await jpeg(page, await page.screenshot(), 'demo-desktop.jpg', 1440, 900);
  }
  await page.context().close();
}

if (ONLY.has('mobile')) {
  const page = await open(390, 844);
  for (const n of [1, 2, 3]) await step(page, n);
  await page.evaluate(() => window.scrollTo(0, document.querySelector('[data-testid=driver-phone]').getBoundingClientRect().top + window.scrollY - 6));
  await scrollApp(page, 'driver', '[data-testid=odo-chart]', 120);
  await page.waitForTimeout(250);
  await jpeg(page, await page.screenshot(), 'demo-mobile.jpg', 390, 844);
  await page.context().close();
}

if (ONLY.has('gif')) {
  const page = await open(1280, 860);
  await toPhones(page);
  const clip = await page.evaluate(() => {
    const a = document.querySelector('[data-testid=driver-phone]').getBoundingClientRect();
    const c = document.querySelector('[data-testid=buyer-phone]').getBoundingClientRect();
    return { x: Math.max(0, a.left - 8), y: Math.max(0, a.top - 4), width: c.right - a.left + 16, height: Math.min(window.innerHeight - a.top, a.height * 0.86) };
  });
  const W = 720;
  const H = Math.round((W * clip.height) / clip.width / 2) * 2;
  const gif = GIFEncoder();
  async function frame(delay) {
    const png = await page.screenshot({ clip });
    const rgba = await page.evaluate(async ([src, w, h]) => {
      const img = new Image();
      img.src = `data:image/png;base64,${src}`;
      await img.decode();
      const c = document.createElement('canvas');
      c.width = w;
      c.height = h;
      const g = c.getContext('2d');
      g.imageSmoothingQuality = 'high';
      g.drawImage(img, 0, 0, w, h);
      const bytes = g.getImageData(0, 0, w, h).data;
      let bin = '';
      for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
      return btoa(bin);
    }, [b64(png), W, H]);
    const data = new Uint8Array(Buffer.from(rgba, 'base64'));
    const palette = quantize(data, 128);
    gif.writeFrame(applyPalette(data, palette), W, H, { palette, delay });
  }
  async function film(n, every = 450, max = 40) {
    await page.evaluate((k) => document.querySelector(`[data-testid=story-${k}]`).click(), n); // no scrolling to the button
    await toPhones(page);
    for (let k = 0; k < max; k++) {
      await frame(every);
      if (await page.evaluate((s) => document.querySelector(`[data-testid=story-${s}]`).classList.contains('done'), n)) break;
      await page.waitForTimeout(every - 150);
    }
  }
  for (const n of [1, 2]) {
    await page.evaluate((k) => document.querySelector(`[data-testid=story-${k}]`).click(), n);
    await done(page, n);
  }
  await toPhones(page);
  await scrollApp(page, 'driver', '[data-testid=odo-chart]', 150);
  await frame(1400);
  for (const n of [3, 4, 5, 6, 9, 10]) await film(n);
  await frame(2400);
  gif.finish();
  writeFileSync(`${OUT}/forecast-confirm-passport.gif`, gif.bytes());
  console.log('wrote forecast-confirm-passport.gif'); // eslint-disable-line no-console
  await page.context().close();
}
await browser.close();
server.close();
