// In-browser stand-in for the server: the same rules as avtoservis/base.py, garage.py and history.py, on the JS
// port of the core. Nothing leaves the browser. Every change emits {type: 'note', note} (what the bot would send)
// and {type: 'changed'}; the demo clock can jump days ahead for the story. Workshops, passports and reminders are
// in backend-ws.js.
import * as carlib from '../shared/cars.js';
import { addMonths, civil, DAY_MS, localDay, localMinute } from '../shared/clock.js';
import { compute } from '../shared/garage.js';
import * as odometer from '../shared/odometer.js';
import * as planlib from '../shared/plan.js';
import { dayOf, validate as validateRecord } from '../shared/records.js';
import { world } from '../shared/seedgen.js';
import * as statlib from '../shared/stats.js';
import { clean, InputError } from '../shared/text.js';
import { installWorkshop } from './backend-ws.js';

export class Refused extends Error {
  constructor(code) {
    super(code);
    this.code = code;
  }
}

export function checked(fn, ...args) {
  try {
    return fn(...args);
  } catch (e) {
    if (e instanceof InputError) throw new Refused(e.code);
    throw e;
  }
}

const isId = (x) => Number.isInteger(x);
export const recordView = (r, workshop = '') => ({ id: r.id, car_id: r.car_id, day: r.day, km: r.km, items: [...r.items], labour: r.labour, parts: r.parts,
  total: r.labour + r.parts, shop: workshop || r.shop, verified: r.workshop_id !== null && r.status === 'ok', status: r.status, photo: Boolean(r.photo), note: r.note });

export class DemoBackend {
  constructor({ now = () => Date.now(), data, lang = 'uz' }) {
    Object.assign(this, { realNow: now, offset: 0, data, listeners: new Set(), models: data.models, cfg: data.plan });
    const w = world(data.people, data.models, data.plan, this.nowMs());
    this.users = Object.fromEntries(w.users.map((u) => [u.id, { ...u, lang }]));
    this.workshops = w.workshops.map((x) => ({ ...x, blocked: 0 }));
    this.cars = w.cars.map((c) => ({ ...c, code: this.newCode() }));
    this.readings = w.readings.map((r) => ({ ...r, jump: 0 }));
    this.items = w.items.map((r) => ({ ...r, km: null, months: null, off: 0 }));
    this.records = w.records.map((r) => ({ ...r, photo: null, status: 'ok' }));
    this.access = w.access.map((a, i) => ({ ...a, at: i }));
    this.shares = [];
    this.sent = new Set();
    this.invites = new Set();
    this.ids = { car: this.cars.length, record: this.records.length, share: 0, at: this.access.length };
    for (const c of this.cars) this.markSent(c.id, this.snapshot(c));
  }

  // ── clock and events ──
  nowMs() { return this.realNow() + this.offset; }
  today() { return localDay(this.nowMs()); }
  minute() { return localMinute(this.nowMs()); }
  advance(ms) { this.offset += Math.max(0, ms); this.emit({ type: 'changed' }); }
  on(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
  emit(ev) { for (const fn of this.listeners) fn(ev); }
  send(notes) {
    for (const note of notes) this.emit({ type: 'note', note });
    this.emit({ type: 'changed' });
  }

  newCode() {
    const buf = new Uint32Array(2);
    for (;;) {
      globalThis.crypto.getRandomValues(buf);
      const code = carlib.codeFrom((buf[0] % 256) * 2 ** 32 + buf[1]);
      if (!this.cars?.some((c) => c.code === code)) return code;
    }
  }

  // ── people ──
  user(uid) { return this.users[uid]; }
  setLang(uid, lang) {
    if (lang !== 'uz' && lang !== 'ru') throw new Refused('generic');
    this.users[uid].lang = lang;
    return lang;
  }
  workshopOf(uid) { return this.workshops.find((w) => w.owner === uid && !w.blocked) ?? null; }
  roles(uid) { const w = this.workshopOf(uid); return { workshop: w ? w.id : null, workshop_name: w ? w.name : '', admin: false }; }
  me(uid) { const u = this.user(uid); return { id: uid, name: u.name, lang: u.lang, roles: this.roles(uid), now: this.nowMs(), today: this.today() }; }

  // ── the one place that turns rows into a plan ──
  ownCar(uid, cid) {
    const car = isId(cid) ? this.cars.find((c) => c.id === cid && c.owner === uid) : null;
    if (!car) throw new Refused('not_found');
    return car;
  }
  okRecords(cid) {
    return this.records.filter((r) => r.car_id === cid && r.status === 'ok').sort((a, b) => a.day - b.day || a.km - b.km || a.id - b.id);
  }
  snapshot(car) {
    const recs = this.okRecords(car.id);
    const snap = compute(car, this.items.filter((r) => r.car_id === car.id), this.readings.filter((r) => r.car_id === car.id), recs, this.models, this.cfg, this.today());
    return { ...snap, records: recs };
  }
  title(car) { return carlib.title(this.models, car); }
  card(car, odo = null) {
    return { id: car.id, title: this.title(car), model: car.model, name: car.name, year: car.year, fuel: car.fuel, usage: car.usage, plate: car.plate, odo };
  }

  // ── garage ──
  addCar(uid, d) {
    const today = this.today();
    const car = checked(carlib.validate, d, this.models, civil(today)[0]);
    if (this.cars.filter((c) => c.owner === uid).length >= 10) throw new Refused('limit');
    const row = { id: ++this.ids.car, owner: uid, model: car.model, name: car.name, year: car.year, fuel: car.fuel, usage: car.usage, plate: car.plate,
      code: this.newCode(), created_day: today };
    this.cars.push(row);
    this.readings.push({ car_id: row.id, day: today, km: car.odo, jump: 0 });
    for (const it of planlib.itemsFor(this.cfg, carlib.model(this.models, car.model), car.fuel, car.usage)) {
      const last = planlib.defaultLast(it, car.odo, today, car.last_oil);
      this.items.push({ car_id: row.id, item: it.id, last_km: last.km, last_day: last.day, guess: last.guess ? 1 : 0, km: null, months: null, off: 0 });
    }
    this.markSent(row.id, this.snapshot(row));
    this.send([]);
    return this.carView(uid, row.id);
  }

  myCars(uid) {
    return this.cars.filter((c) => c.owner === uid).map((c) => {
      const snap = this.snapshot(c);
      return { ...this.card(c, snap.odo), next: snap.statuses.slice(0, 3), attention: snap.statuses.filter((s) => s.state === 'soon' || s.state === 'due').length };
    });
  }

  carView(uid, cid) {
    const car = this.ownCar(uid, cid);
    const snap = this.snapshot(car);
    const pending = this.records.filter((r) => r.car_id === car.id && r.status === 'pending').sort((a, b) => a.id - b.id)
      .map((r) => ({ id: r.id, day: r.day, km: r.km, items: [...r.items], labour: r.labour, parts: r.parts, workshop: this.workshops.find((w) => w.id === r.workshop_id).name }));
    const shops = this.access.filter((a) => a.car_id === car.id).sort((a, b) => a.at - b.at || a.workshop_id - b.workshop_id).map((a) => {
      const w = this.workshops.find((x) => x.id === a.workshop_id);
      return { workshop_id: a.workshop_id, allow: Boolean(a.allow), name: w.name, address: w.address };
    });
    return structuredClone({ car: { ...this.card(car, snap.odo), code: carlib.showCode(car.code) }, today: this.today(), now: this.nowMs(), fc: snap.fc,
      points: snap.points, statuses: snap.statuses, off: snap.off, pending, shops });
  }

  addReading(uid, cid, km, confirm = false) {
    const today = this.today();
    const car = this.ownCar(uid, cid);
    const snap = this.snapshot(car);
    const last = snap.points.at(-1) ?? null;
    const [n, ask] = checked(odometer.check, last, today, km, confirm === true, this.cfg.jump_km_per_day);
    if (ask) {
      const days = Math.max(1, today - last[0]);
      return { confirm: true, km: n, per_day: Math.floor((n - last[1]) / days), days };
    }
    if (this.readings.filter((r) => r.car_id === car.id && r.day === today).length >= 20) throw new Refused('limit');
    const jump = last !== null && n - last[1] > this.cfg.jump_km_per_day * Math.max(1, today - last[0]) ? 1 : 0;
    this.readings.push({ car_id: car.id, day: today, km: n, jump });
    this.send([]);
    return { confirm: false, km: n, view: this.carView(uid, cid) };
  }

  setItem(uid, cid, item, d) {
    if (!d || typeof d !== 'object') throw new Refused('generic');
    const today = this.today();
    const car = this.ownCar(uid, cid);
    const snap = this.snapshot(car);
    const it = snap.items.find((x) => x.id === item);
    if (!it) throw new Refused('not_found');
    const sets = {};
    const given = (k) => d[k] !== null && d[k] !== undefined && d[k] !== '';
    if (d.done === true) Object.assign(sets, { last_km: it.km ? snap.odo : null, last_day: today, guess: 0 });
    if (given('last_km')) {
      if (!it.km) throw new Refused('generic');
      const [k] = checked(odometer.check, null, today, d.last_km, true, 0);
      if (k > snap.odo) throw new Refused('last_km');
      Object.assign(sets, { last_km: k, guess: 0 });
    }
    if (given('last_day')) {
      Object.assign(sets, { last_day: checked(dayOf, d.last_day, today), guess: 0 });
      if (it.km && !('last_km' in sets)) sets.last_km = snap.odo;
    }
    if (given('expires')) {
      if (!it.months) throw new Refused('generic');
      Object.assign(sets, { last_day: addMonths(checked(dayOf, d.expires, today, 3650), -it.months), guess: 0 });
    }
    if (given('km') || given('months')) Object.assign(sets, checked(planlib.checkOverride, this.cfg.items.find((x) => x.id === item), d.km, d.months));
    if (d.reset === true) Object.assign(sets, { km: null, months: null });
    if (typeof d.off === 'boolean') sets.off = d.off ? 1 : 0;
    if (!Object.keys(sets).length) throw new Refused('generic');
    Object.assign(this.items.find((r) => r.car_id === car.id && r.item === item), sets);
    this.send([]);
    return this.carView(uid, cid);
  }

  rotateCode(uid, cid) { this.ownCar(uid, cid).code = this.newCode(); this.send([]); return this.carView(uid, cid); }

  setShop(uid, cid, wid, { allow, remove } = {}) {
    const car = this.ownCar(uid, cid);
    const i = this.access.findIndex((a) => a.car_id === car.id && a.workshop_id === wid);
    if (i < 0) throw new Refused('not_found');
    if (remove === true) this.access.splice(i, 1);
    else if (typeof allow === 'boolean') this.access[i].allow = allow;
    else throw new Refused('generic');
    this.send([]);
    return this.carView(uid, cid);
  }

  // ── history ──
  checkFits(car, rec) {
    const snap = this.snapshot(car);
    checked(odometer.fits, snap.points, rec.day, rec.km);
    const last = snap.points.at(-1);
    if (last && rec.day >= last[0] && rec.km < last[1]) throw new Refused('odo_back');
  }

  addRecord(uid, cid, d) {
    const car = this.ownCar(uid, cid);
    const rec = checked(validateRecord, d, this.snapshot(car).items.map((it) => it.id), this.today());
    this.checkFits(car, rec);
    const row = { id: ++this.ids.record, car_id: car.id, ...rec, workshop_id: null, by: uid, photo: null, status: 'ok' };
    this.records.push(row);
    this.send([]);
    return { record_id: row.id, view: this.carView(uid, cid) };
  }

  wsName(r) { return r.workshop_id === null ? '' : this.workshops.find((w) => w.id === r.workshop_id).name; }

  history(uid, cid) {
    const car = this.ownCar(uid, cid);
    return this.records.filter((r) => r.car_id === car.id && (r.status === 'ok' || r.status === 'pending'))
      .sort((a, b) => b.day - a.day || b.km - a.km || b.id - a.id).map((r) => recordView(r, this.wsName(r)));
  }

  ownRecord(uid, rid) {
    const r = isId(rid) ? this.records.find((x) => x.id === rid) : null;
    if (!r || this.cars.find((c) => c.id === r.car_id).owner !== uid) throw new Refused('not_found');
    return r;
  }

  record(uid, rid) { const r = this.ownRecord(uid, rid); return recordView(r, this.wsName(r)); }

  decide(uid, rid, yes, allow = false) {
    if (typeof yes !== 'boolean') throw new Refused('generic');
    const r = this.ownRecord(uid, rid);
    if (r.status !== 'pending') throw new Refused('decided');
    const car = this.cars.find((c) => c.id === r.car_id);
    if (yes) this.checkFits(car, r);
    r.status = yes ? 'ok' : 'rejected';
    if (yes && allow === true) { const a = this.access.find((x) => x.car_id === car.id && x.workshop_id === r.workshop_id); if (a) a.allow = true; }
    const ws = this.workshops.find((w) => w.id === r.workshop_id);
    const notes = [{ type: 'decided', to: ws.owner, record_id: r.id, yes, car_id: car.id }];
    this.send(notes);
    return [this.record(uid, rid), notes];
  }

  stats(uid, cid) {
    const car = this.ownCar(uid, cid);
    const snap = this.snapshot(car);
    const pts = snap.points;
    const driven = pts.length ? pts.at(-1)[1] - pts[0][1] : 0;
    const s = statlib.spending(snap.records, 12, this.today());
    return { ...s, km: driven, per_km: statlib.perKm(s.total, driven), since: pts.length ? pts[0][0] : null, car: this.card(car, snap.odo) };
  }

  exportRows(uid, cid) {
    const car = this.ownCar(uid, cid);
    return [car, this.okRecords(car.id).map((r) => recordView(r, this.wsName(r)))];
  }
}

installWorkshop(DemoBackend, { Refused, checked, recordView, isId, DAY_MS, clean });
