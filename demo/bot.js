// The bot, simulated in the page: the menu, the car, the reminder with its one-tap reading, "Tasdiqlaysizmi?" with
// its three answers, the workshop's "Egasi tasdiqladi", the invitation, and the buyer's passport deep link. The same
// callback data and texts as avtoservis/bot. Messages are {id, from: 'bot' | 'me', html, kb, at}.
import { escapeHtml, km, Raw } from '../shared/i18n.js';
import { Refused } from './backend.js';

const strip = (html) => html.replace(/<[^>]+>/g, '').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');

export class BotSim {
  constructor(backend, uid, t, views, { onChange = () => {}, onAlert = () => {}, onApp = () => {} } = {}) {
    Object.assign(this, { b: backend, uid, t, v: views, onChange, onAlert, onApp });
    this.messages = [];
    this.ids = 1;
  }

  get lang() { return this.b.user(this.uid).lang; }

  push(screen, from = 'bot') {
    const msg = { id: this.ids++, from, html: screen.html, kb: screen.kb ?? [], at: this.b.nowMs() };
    this.messages.push(msg);
    this.onChange();
    return msg;
  }

  show(id, screen) {
    const msg = id && this.messages.find((m) => m.id === id);
    if (!msg) return this.push(screen);
    Object.assign(msg, { html: screen.html, kb: screen.kb ?? [] });
    this.onChange();
    return msg;
  }

  guard(fn) {
    try {
      return fn();
    } catch (e) {
      if (!(e instanceof Refused)) throw e;
      const key = this.t(this.lang, `err.${e.code}`) === `err.${e.code}` ? 'err.generic' : `err.${e.code}`;
      this.onAlert(strip(this.t(this.lang, key)));
      return null;
    }
  }

  menu(id, hello = false) { return this.show(id, this.v.menu(this.lang, this.b.myCars(this.uid), this.b.roles(this.uid), hello)); }

  start(arg = '') {
    this.push({ html: escapeHtml(arg ? `/start ${arg.slice(0, 12)}…` : '/start') }, 'me');
    const m = /^p_([A-Za-z0-9_-]{32})$/.exec(arg);
    if (m) {
      return this.guard(() => {
        try {
          return this.push(this.v.passportCard(this.lang, this.b.passport(m[1]), m[1]));
        } catch (e) {
          if (e instanceof Refused) return this.push(this.v.text(this.lang, 'err.link_gone'));
          throw e;
        }
      });
    }
    return this.menu(null, true);
  }

  type(text) {
    this.push({ html: escapeHtml(text) }, 'me');
    return this.menu(null);
  }

  press(id, data) {
    const r = this.guard(() => this.route(id, String(data)));
    if (r === false) this.onAlert(strip(this.t(this.lang, 'err.stale')));
  }

  reply(id, prefix, screen) {
    const old = this.messages.find((x) => x.id === id);
    if (old) Object.assign(old, { kb: [] });
    return this.push({ html: `${prefix}\n\n${screen.html}`, kb: screen.kb });
  }

  route(id, data) {
    let m;
    const lang = this.lang;
    if (data === 'n:menu') return this.menu(id);
    if (data === 'n:lang') { this.b.setLang(this.uid, lang === 'uz' ? 'ru' : 'uz'); return this.menu(id); }
    if (data === 'w:home') return this.show(id, this.v.wsHome(lang, this.b.wsHome(this.uid)));
    if ((m = /^c:(\d{1,9})$/.exec(data))) return this.show(id, this.v.car(lang, this.b.carView(this.uid, Number(m[1]))));
    if ((m = /^c:(\d{1,9}):km$/.exec(data))) { this.b.carView(this.uid, Number(m[1])); this.onApp(`#c=${m[1]}`); return true; }
    if ((m = /^r:(\d{1,9}):(\d{1,7})$/.exec(data))) {
      const out = this.b.addReading(this.uid, Number(m[1]), Number(m[2]));
      if (out.confirm) return this.push(this.v.text(lang, 'km.jump', { days: out.days, km: new Raw(km(this.t, lang, out.km)), per_day: out.per_day }));
      return this.reply(id, this.t(lang, 'km.saved', { km: new Raw(km(this.t, lang, out.km)) }), this.v.car(lang, out.view));
    }
    if ((m = /^ok:(\d{1,9}):([yan])$/.exec(data))) {
      const [rec] = this.b.decide(this.uid, Number(m[1]), m[2] !== 'n', m[2] === 'a');
      const head = this.t(lang, rec.status === 'ok' ? 'notify.confirmed' : 'notify.rejected');
      return this.reply(id, head, this.v.car(lang, this.b.carView(this.uid, rec.car_id)));
    }
    if ((m = /^ka:(\d{1,9}):(\d{1,9}):([01])$/.exec(data))) {
      this.b.setShop(this.uid, Number(m[1]), Number(m[2]), { allow: m[3] === '1' });
      return this.reply(id, '✅', this.v.car(lang, this.b.carView(this.uid, Number(m[1]))));
    }
    return false;
  }

  /** A note the service produced (what the real bot would send on its own). Returns the new message, or null. */
  deliver(n) {
    if (n.to !== this.uid) return null;
    const lang = this.lang;
    if (n.type === 'remind') return this.push(this.v.remind(lang, this.b.carView(this.uid, n.car_id), n.items, n.ask));
    if (n.type === 'confirm') {
      const r = this.b.record(this.uid, n.record_id);
      return this.push(this.v.confirm(lang, r, this.b.title(this.b.cars.find((c) => c.id === n.car_id))));
    }
    if (n.type === 'decided') {
      const r = this.b.records.find((x) => x.id === n.record_id);
      return this.push(this.v.decided(lang, n.yes, this.b.title(this.b.cars.find((c) => c.id === n.car_id)), r.items));
    }
    if (n.type === 'invite') {
      const shop = this.b.workshops.find((w) => w.id === n.workshop_id);
      return this.push(this.v.invite(lang, shop, this.b.carView(this.uid, n.car_id), n.item));
    }
    return null;
  }
}
