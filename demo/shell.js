// Demo page: three phones (the driver, the workshop master, the buyer), each with the simulated bot and the real
// Mini App code on the in-page backend; the guided story (in order, all at once, or out of order), the demo clock
// and the language switch. Everything runs in this page.
import { dateFull, makeT } from '../shared/i18n.js';
import { localDay } from '../shared/clock.js';
import { csv as toCsv } from '../shared/stats.js';
import { mountPassport } from '../webapp/ui-passport.js';
import { mountApp } from '../webapp/ui.js';
import { h, loadShared, makeText, store } from '../webapp/util.js';
import { apiFor } from './api.js';
import { BotSim } from './bot.js';
import { makeViews } from './bot-views.js';
import { createPhone } from './phone.js';
import { BUYER, createDemo, DRIVER, MASTER } from './seed.js';
import { runStep, STEPS } from './story.js';
import { makeUi } from './story-ui.js';

const shared = await loadShared(new URL('../shared/', import.meta.url), true);
const t = makeT(shared.catalogs);
const text = makeText(shared.catalogs);
let lang = store.get('avtoservis.lang') === 'ru' ? 'ru' : 'uz';
const P = (key, params) => text(lang, key, params);
const backend = createDemo({ data: shared, lang });
const views = makeViews(t);
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const UIDS = [DRIVER, MASTER, BUYER];
const people = { [DRIVER]: { who: 'driver', label: 'demo.driver', role: 'demo.role_driver', view: 'owner' },
  [MASTER]: { who: 'master', label: 'demo.master', role: 'demo.role_master', view: 'ws' },
  [BUYER]: { who: 'buyer', label: 'demo.buyer', role: 'demo.role_buyer', view: 'owner' } };
const phones = {};
const bots = {};
const apps = {};
let shown = DRIVER;
const passportLink = (tok) => `${window.location.origin}${window.location.pathname.replace(/index\.html$/, '')}webapp/#p=${tok}`;

function focus(uid, pane) {
  phones[uid].show(pane);
  if (window.matchMedia('(max-width: 760px)').matches) pick(uid);
}

const buyer = {
  async open(token) {
    focus(BUYER, 'app');
    apps[BUYER]?.destroy();
    apps[BUYER] = mountPassport(phones[BUYER].appRoot, { fetchPassport: (tk) => apiFor(backend, BUYER).passport(tk), token, catalogs: shared.catalogs, lang, poll: 1500,
      onLang: (l) => setLang(l) });
    await apps[BUYER].ready;
  },
  refresh: () => apps[BUYER]?.refresh(),
};

async function openApp(uid, hash) {
  focus(uid, 'app');
  let m;
  if ((m = /^#p=([A-Za-z0-9_-]{32})$/.exec(hash))) { await buyer.open(m[1]); return; }
  await apps[uid].open(async ({ screens, show, home: toHome }) => {
    await toHome();
    if ((m = /^#([chg])=(\d+)$/.exec(hash))) {
      await screens.open(Number(m[2]));
      if (m[1] === 'h') await show(screens.more.historyScreen(Number(m[2])));
      if (m[1] === 'g') await show(screens.more.passportScreen(Number(m[2])));
    } else if (hash === '#new' && screens.addCar) await show(screens.addCar());
  });
}

function sendCsv(car, recs) {
  const rows = [t(lang, 'csv.head').split(',')].concat(recs.map((r) => [dateFull(r.day), r.km, r.items.map((i) => t(lang, `item.${i}`)).join('; '), r.labour,
    r.parts, r.total, r.shop, t(lang, r.verified ? 'csv.verified' : 'csv.self'), r.note]));
  const url = URL.createObjectURL(new Blob([`﻿${toCsv(rows)}`], { type: 'text/csv' }));
  bots[DRIVER].push({ html: `📎 avtoservis-${car.id}.csv\n${t(lang, 'csv.caption', { title: backend.title(car) })}`, kb: [] });
  const a = h('a', { href: url, download: `avtoservis-${car.id}.csv` });
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

for (const uid of UIDS) {
  bots[uid] = new BotSim(backend, uid, t, views, { onChange: () => phones[uid]?.renderChat(), onAlert: (x) => phones[uid].alert(x), onApp: (hash) => openApp(uid, hash) });
  phones[uid] = createPhone({ who: people[uid].who, label: '', role: people[uid].role, bot: bots[uid], texts: { P }, now: () => backend.nowMs(),
    onOpenApp: (hash) => openApp(uid, hash), onShowApp: () => apps[uid]?.refresh() });
}

const DOC = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l4 4v14H7z M14 3v4h4 M9.5 12.5l2 2 3.5-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/></svg>';
/** The buyer has no car here: his phone waits for a Servis pasporti link. */
function buyerWaiting() {
  const el = h('div', { class: 'pp-wait', 'data-testid': 'buyer-wait' }, h('span', { class: 'pp-wait-icon', html: DOC }), h('b', {}, P('pp.title')), h('span', {}, P('demo.buyer_wait')));
  phones[BUYER].appRoot.replaceChildren(el);
  return { ready: Promise.resolve(), refresh: async () => {}, setLang: () => buyerWaiting(), destroy: () => {} };
}

function mountApps() {
  for (const uid of UIDS) {
    apps[uid]?.destroy();
    if (uid === BUYER) { apps[uid] = buyerWaiting(); continue; }
    apps[uid] = mountApp(phones[uid].appRoot, { api: apiFor(backend, uid, { onCsv: sendCsv }), ...shared, lang, view: people[uid].view, poll: 1000,
      now: () => backend.nowMs(), onLang: (l) => setLang(l), share: { link: passportLink } });
  }
}

let pending = false;
backend.on((ev) => {
  if (ev.type === 'note') {
    const msg = bots[ev.note.to]?.deliver(ev.note);
    if (msg) phones[ev.note.to].ping(msg.html);
  }
  if (ev.type === 'changed' && !pending) {
    pending = true;
    queueMicrotask(() => {
      pending = false;
      for (const uid of UIDS) apps[uid]?.refresh();
      paintClock();
    });
  }
});
setInterval(() => backend.tick(), 5000);

// ── page ──
const timeEl = h('span', { class: 'demo-date', 'data-testid': 'demo-time' });
const badgeText = h('span');
const langBtn = h('button', { class: 'demo-btn', type: 'button', 'data-testid': 'demo-lang', onclick: () => setLang(lang === 'uz' ? 'ru' : 'uz') });
const resetBtn = h('button', { class: 'demo-btn', type: 'button', onclick: () => window.location.reload() });
const playBtn = h('button', { class: 'demo-btn solid', type: 'button', 'data-testid': 'play', onclick: () => play() });
const MARK = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4.5 15.5 6.2 10a2 2 0 0 1 1.9-1.4h7.8a2 2 0 0 1 1.9 1.4l1.7 5.5v3a1 1 0 0 1-1 1h-1.3a1 1 0 0 1-1-1v-1H7.8v1a1 1 0 0 1-1 1H5.5a1 1 0 0 1-1-1z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>';
const bar = h('header', { class: 'demo-bar' },
  h('a', { class: 'demo-logo', href: './' }, h('span', { class: 'demo-mark', html: MARK }), 'Avto Servis'),
  h('span', { class: 'demo-badge', 'data-testid': 'demo-badge' }, h('span', { class: 'dot' }), badgeText),
  h('span', { class: 'demo-time' }, timeEl),
  h('div', { class: 'demo-tools' }, playBtn, langBtn, resetBtn,
    h('a', { class: 'demo-btn gh', href: 'https://github.com/xoliddev/avto-servis', target: '_blank', rel: 'noopener' }, 'GitHub')));
const title = h('h1');
const lead = h('p');
const foot = h('p', { class: 'demo-foot' });
const env = { backend, bots, wait, focus, done: new Set() };
env.ui = makeUi({ apps, phones, env, wait, uids: { DRIVER, MASTER, BUYER }, buyer });
let running = false;
async function step(i) {
  if (running) return;
  running = true;
  paintStory();
  try {
    await runStep(i + 1, env);
  } catch (err) {
    console.warn(err); // eslint-disable-line no-console
    phones[shown].alert(P('err.generic'));
  }
  running = false;
  paintStory();
}
async function play() {
  for (let i = 0; i < STEPS.length; i++) if (!env.done.has(i + 1)) await step(i);
}
const storyBtns = STEPS.map((_, i) => h('button', { class: 'story-btn', type: 'button', 'data-testid': `story-${i + 1}`, onclick: () => step(i) },
  h('b', {}, String(i + 1)), h('span')));
function paintStory() {
  const next = STEPS.findIndex((_, i) => !env.done.has(i + 1));
  storyBtns.forEach((b, i) => {
    b.lastChild.textContent = P(`demo.${STEPS[i]}`);
    b.classList.toggle('done', env.done.has(i + 1));
    b.classList.toggle('next', i === next && !running);
    b.disabled = running;
  });
  playBtn.disabled = running || next < 0;
}
const whoBtns = UIDS.map((uid) => h('button', { type: 'button', 'data-testid': `switch-${people[uid].who}`, onclick: () => pick(uid) }));
function pick(uid) {
  shown = uid;
  whoBtns.forEach((b, i) => b.classList.toggle('on', UIDS[i] === uid));
  for (const id of UIDS) phones[id].side.classList.toggle('show', id === uid);
}
const paintClock = () => { timeEl.textContent = P('demo.time', { time: dateFull(localDay(backend.nowMs())) }); };
function paintTexts() {
  document.documentElement.lang = lang;
  badgeText.textContent = P('demo.badge');
  langBtn.textContent = lang === 'uz' ? 'RU' : 'UZ';
  resetBtn.textContent = P('demo.reset');
  playBtn.textContent = P('demo.play');
  title.textContent = P('demo.title');
  lead.textContent = P('demo.lead');
  foot.textContent = P('demo.foot');
  whoBtns.forEach((b, i) => { b.textContent = P(people[UIDS[i]].label); });
  paintStory();
  paintClock();
  for (const uid of UIDS) {
    phones[uid].renderLabels();
    phones[uid].side.querySelector('.side-label b').textContent = P(people[uid].label);
  }
}
function setLang(next) {
  if (next === lang) return;
  lang = next;
  store.set('avtoservis.lang', lang);
  for (const uid of UIDS) {
    backend.setLang(uid, lang);
    apps[uid].setLang(lang);
  }
  paintTexts();
}
setInterval(() => { paintClock(); for (const uid of UIDS) phones[uid].tick(); }, 15_000);

document.body.append(bar, h('section', { class: 'demo-intro' }, title, lead), h('nav', { class: 'story', 'aria-label': 'story' }, storyBtns),
  h('div', { class: 'who-switch', role: 'tablist' }, whoBtns), h('main', { class: 'demo-stage' }, UIDS.map((uid) => phones[uid].side)), foot);
mountApps();
for (const uid of UIDS) {
  bots[uid].start();
  phones[uid].show('app');
}
bots[MASTER].press(bots[MASTER].messages.at(-1).id, 'w:home');
pick(DRIVER);
paintTexts();
await Promise.all(UIDS.map((uid) => apps[uid].ready));
document.body.dataset.ready = '1';
