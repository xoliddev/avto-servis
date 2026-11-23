// The demo backend's workshop side, Servis pasporti links and reminders: the same rules as avtoservis/workshop.py,
// passport.py and reminding.py. Mixed into DemoBackend (backend.js).
import * as carlib from '../shared/cars.js';
import * as odometer from '../shared/odometer.js';
import { validate as validateRecord } from '../shared/records.js';
import { keysFor, quiet } from '../shared/reminders.js';
import { hex, make, nonceOf, secretFrom } from '../shared/token.js';

const SECRET = secretFrom('in-browser demo');

export function installWorkshop(Backend, { Refused, checked, recordView, isId, DAY_MS }) {
  const P = Backend.prototype;

  P.ws = function ws(uid) {
    const w = this.workshopOf(uid);
    if (!w) throw new Refused('not_found');
    return w;
  };

  P.wsAccess = function wsAccess(w, cid) {
    const a = isId(cid) ? this.access.find((x) => x.car_id === cid && x.workshop_id === w.id) : null;
    if (!a) throw new Refused('not_found');
    return [this.cars.find((c) => c.id === cid), a];
  };

  P.openCar = function openCar(uid, code) {
    const w = this.ws(uid);
    const norm = carlib.normCode(code);
    const car = norm ? this.cars.find((c) => c.code === norm) : null;
    if (!car) throw new Refused('code');
    if (!this.access.some((a) => a.car_id === car.id && a.workshop_id === w.id)) {
      this.access.push({ car_id: car.id, workshop_id: w.id, allow: false, since_day: this.today(), at: ++this.ids.at });
    }
    this.send([]);
    return this.wsCar(uid, car.id);
  };

  P.wsCar = function wsCar(uid, cid) {
    const w = this.ws(uid);
    const [car, a] = this.wsAccess(w, cid);
    const snap = this.snapshot(car);
    const mine = this.records.filter((r) => r.car_id === car.id && r.workshop_id === w.id && (r.status === 'ok' || r.status === 'pending'))
      .sort((x, y) => y.day - x.day || y.id - x.id).map((r) => recordView(r, w.name));
    return structuredClone({ car: this.card(car, snap.odo), statuses: snap.statuses, items: snap.items.map((i) => i.id), records: mine, allow: Boolean(a.allow),
      today: this.today() });
  };

  P.wsRecord = function wsRecord(uid, cid, d) {
    const w = this.ws(uid);
    const [car] = this.wsAccess(w, cid);
    const rec = checked(validateRecord, d, this.snapshot(car).items.map((i) => i.id), this.today());
    if (rec.day < this.today() - 7) throw new Refused('date');
    if (this.records.filter((r) => r.car_id === car.id && r.workshop_id === w.id && r.status === 'pending').length >= 3) throw new Refused('limit');
    this.checkFits(car, rec);
    const row = { id: ++this.ids.record, car_id: car.id, ...rec, shop: w.name, workshop_id: w.id, by: uid, photo: null, status: 'pending' };
    this.records.push(row);
    const notes = [{ type: 'confirm', to: car.owner, record_id: row.id, car_id: car.id }];
    this.send(notes);
    return [this.wsCar(uid, cid), notes];
  };

  P.wsHome = function wsHome(uid) {
    const w = this.ws(uid);
    const rows = this.access.filter((a) => a.workshop_id === w.id).sort((x, y) => y.at - x.at || y.car_id - x.car_id).slice(0, 50);
    const due = [];
    const cars = rows.map((a) => {
      const car = this.cars.find((c) => c.id === a.car_id);
      const snap = this.snapshot(car);
      if (a.allow) {
        for (const st of snap.statuses) {
          if (st.state === 'soon' || st.state === 'due') {
            due.push({ car: this.card(car, snap.odo), status: st, invited: this.invites.has(`${w.id}|${car.id}|${st.id}|${st.cycle}`) });
          }
        }
      }
      return { ...this.card(car, snap.odo), allow: Boolean(a.allow) };
    });
    due.sort((x, y) => (x.status.days_left ?? 1e6) - (y.status.days_left ?? 1e6) || x.car.id - y.car.id);
    const records = this.records.filter((r) => r.workshop_id === w.id && (r.status === 'ok' || r.status === 'pending')).sort((x, y) => y.id - x.id).slice(0, 20)
      .map((r) => recordView(r, w.name));
    return structuredClone({ workshop: { id: w.id, name: w.name, address: w.address }, cars, due, records, today: this.today() });
  };

  P.wsInvite = function wsInvite(uid, cid, item) {
    const w = this.ws(uid);
    const [car, a] = this.wsAccess(w, cid);
    if (!a.allow) throw new Refused('not_allowed');
    const st = this.snapshot(car).statuses.find((s) => s.id === item);
    if (!st || (st.state !== 'soon' && st.state !== 'due')) throw new Refused('not_due');
    const key = `${w.id}|${car.id}|${st.id}|${st.cycle}`;
    if (this.invites.has(key)) throw new Refused('invited');
    this.invites.add(key);
    const notes = [{ type: 'invite', to: car.owner, car_id: car.id, item: st.id, workshop_id: w.id }];
    this.send(notes);
    return [this.wsHome(uid), notes];
  };

  // ── Servis pasporti ──
  P.shareList = function shareList(uid, cid) {
    const car = this.ownCar(uid, cid);
    return this.shares.filter((s) => s.car_id === car.id && s.revoked_at === null && s.expires_at > this.nowMs()).sort((x, y) => y.id - x.id)
      .map((s) => ({ id: s.id, token: make(SECRET, Uint8Array.from(s.nonce.match(/../g).map((x) => Number.parseInt(x, 16)))), created_at: s.created_at,
        expires_at: s.expires_at, show_owner: Boolean(s.show_owner) }));
  };

  P.share = function share(uid, cid, days, showOwner = false) {
    if (![7, 30, 90].includes(days) || typeof showOwner !== 'boolean') throw new Refused('generic');
    const car = this.ownCar(uid, cid);
    const now = this.nowMs();
    if (this.shares.filter((s) => s.car_id === car.id && s.revoked_at === null && s.expires_at > now).length >= 5) throw new Refused('limit');
    const nonce = globalThis.crypto.getRandomValues(new Uint8Array(12));
    const row = { id: ++this.ids.share, car_id: car.id, nonce: hex(nonce), show_owner: showOwner, created_at: now, expires_at: now + days * DAY_MS, revoked_at: null };
    this.shares.push(row);
    this.send([]);
    return { id: row.id, token: make(SECRET, nonce), expires_at: row.expires_at, items: this.shareList(uid, cid) };
  };

  P.revoke = function revoke(uid, cid, sid) {
    const car = this.ownCar(uid, cid);
    const row = this.shares.find((s) => s.id === sid && s.car_id === car.id && s.revoked_at === null);
    if (!row) throw new Refused('not_found');
    row.revoked_at = this.nowMs();
    this.send([]);
    return this.shareList(uid, cid);
  };

  P.passport = function passport(tok) {
    const nonce = nonceOf(SECRET, tok);
    const row = nonce ? this.shares.find((s) => s.nonce === nonce) : null;
    if (!row || row.revoked_at !== null || row.expires_at <= this.nowMs()) throw new Refused('link_gone');
    const car = this.cars.find((c) => c.id === row.car_id);
    const snap = this.snapshot(car);
    const timeline = this.records.filter((r) => r.car_id === car.id && r.status === 'ok').sort((a, b) => b.day - a.day || b.km - a.km || b.id - a.id)
      .map((r) => { const v = recordView(r, this.wsName(r)); return { id: v.id, day: v.day, km: v.km, items: v.items, shop: v.shop, verified: v.verified }; });
    const u = this.users[car.owner];
    const c = this.card(car, snap.odo);
    const last = snap.points.at(-1);
    return structuredClone({ car: { title: c.title, model: c.model, name: c.name, year: c.year, fuel: c.fuel, usage: c.usage, plate: c.plate },
      owner: row.show_owner ? { name: u.name, phone: u.phone } : null, last: last ? { day: last[0], km: last[1] } : null, since: car.created_day,
      check: odometer.consistency(snap.points, this.cfg.jump_km_per_day), timeline, verified: timeline.filter((x) => x.verified).length,
      self: timeline.filter((x) => !x.verified).length, next: snap.statuses.filter((s) => s.state !== 'unknown').slice(0, 6), expires_at: row.expires_at,
      today: this.today() });
  };

  // ── reminders: each key once ──
  P.markSent = function markSent(cid, snap) {
    for (const k of keysFor(snap.statuses, this.today(), snap.points.at(-1)[0], this.cfg)) this.sent.add(`${cid}|${k.key}`);
  };

  P.tick = function tick() {
    if (quiet(this.minute())) return [];
    const notes = [];
    for (const car of this.cars) {
      const snap = this.snapshot(car);
      const fresh = keysFor(snap.statuses, this.today(), snap.points.at(-1)[0], this.cfg).filter((k) => !this.sent.has(`${car.id}|${k.key}`));
      for (const k of fresh) this.sent.add(`${car.id}|${k.key}`);
      if (fresh.length) {
        notes.push({ type: 'remind', to: car.owner, car_id: car.id, items: fresh.filter((k) => k.item).map((k) => ({ id: k.item, kind: k.kind })),
          ask: fresh.some((k) => k.kind === 'ask') });
      }
    }
    if (notes.length) this.send(notes);
    return notes;
  };
}
