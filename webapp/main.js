// Mini App entry. Inside Telegram it passes the signed initData along (the server checks it). "#c=5" opens that
// car (the bot's "📈 Grafik" button), "#w" the workshop panel. "#p=<token>" is a buyer's Servis pasporti: it opens
// in any browser, without Telegram.
import { normLang } from '../shared/i18n.js';
import { httpApi, publicPassport } from './api.js';
import { mountPassport } from './ui-passport.js';
import { mountApp } from './ui.js';
import { h, loadShared } from './util.js';

const tg = window.Telegram?.WebApp;
const root = document.getElementById('app');
const shared = await loadShared();
const hash = window.location.hash;
const pass = /^#p=([A-Za-z0-9_-]{32})$/.exec(hash);

if (pass) {
  tg?.ready?.();
  const lang = normLang(tg?.initDataUnsafe?.user?.language_code ?? navigator.language);
  mountPassport(root, { fetchPassport: publicPassport, token: pass[1], catalogs: shared.catalogs, lang });
  document.documentElement.lang = lang;
} else if (!tg?.initData) {
  root.replaceChildren(h('p', { class: 'g-outside' }, shared.catalogs.uz['app.open_in_telegram']),
    h('p', { class: 'g-outside' }, shared.catalogs.ru['app.open_in_telegram']));
} else {
  tg.ready();
  tg.expand();
  const api = httpApi(tg.initData);
  const app = mountApp(root, { ...shared, api, tg, lang: null, start: hash === '#w' ? 'ws' : null, poll: 4000 });
  await app.ready;
  const m = /^#c=(\d{1,9})$/.exec(hash);
  if (m) await app.open(({ screens }) => screens.open(Number(m[1])));
  document.documentElement.lang = normLang(tg.initDataUnsafe?.user?.language_code);
}
