// The Mini App's API, answered by the in-browser backend instead of HTTP (same method names as webapp/api.js and the
// same shapes and error codes as the server), so the Mini App code is identical in Telegram and in the demo.
export function run(fn) {
  return Promise.resolve().then(() => {
    try {
      return structuredClone(fn());
    } catch (e) {
      if (!e.code) throw e;
      throw Object.assign(new Error(e.code), { code: e.code });
    }
  });
}

export function apiFor(b, uid, { onCsv = () => {}, onReceipt = () => {} } = {}) {
  const n = Number;
  return {
    me: () => run(() => b.me(uid)),
    setLang: (lang) => run(() => ({ lang: b.setLang(uid, lang) })),
    cars: () => run(() => ({ items: b.myCars(uid) })),
    addCar: (car) => run(() => b.addCar(uid, car)),
    car: (cid) => run(() => b.carView(uid, n(cid))),
    reading: (cid, km, confirm = false) => run(() => b.addReading(uid, n(cid), km, confirm === true)),
    setItem: (cid, item, data) => run(() => b.setItem(uid, n(cid), item, data)),
    rotateCode: (cid) => run(() => b.rotateCode(uid, n(cid))),
    setShop: (cid, wid, data) => run(() => b.setShop(uid, n(cid), n(wid), data)),
    history: (cid) => run(() => ({ items: b.history(uid, n(cid)) })),
    addRecord: (cid, record) => run(() => b.addRecord(uid, n(cid), record)),
    decide: (rid, yes, allow = false) => run(() => b.decide(uid, n(rid), yes, allow === true)[0]),
    receipt: (rid) => run(() => { const r = b.record(uid, n(rid)); onReceipt(r); return { sent: r.photo }; }),
    stats: (cid) => run(() => b.stats(uid, n(cid))),
    csv: (cid) => run(() => { const [car, recs] = b.exportRows(uid, n(cid)); onCsv(car, recs); return { sent: true, n: recs.length }; }),
    shares: (cid) => run(() => ({ items: b.shareList(uid, n(cid)) })),
    share: (cid, days, showOwner) => run(() => b.share(uid, n(cid), days, showOwner === true)),
    revoke: (cid, sid) => run(() => ({ items: b.revoke(uid, n(cid), n(sid)) })),
    passport: (token) => run(() => b.passport(token)),
    wsHome: () => run(() => b.wsHome(uid)),
    wsOpen: (code) => run(() => b.openCar(uid, code)),
    wsCar: (cid) => run(() => b.wsCar(uid, n(cid))),
    wsRecord: (cid, record) => run(() => b.wsRecord(uid, n(cid), record)[0]),
    wsInvite: (cid, item) => run(() => b.wsInvite(uid, n(cid), item)[0]),
  };
}
