// HTTP client for the Mini App API. Every request carries Telegram's signed initData; the server checks it. The
// buyer's passport page is the one call without initData (the token goes in the body, never in the URL).
// The browser demo provides an object with the same methods that runs in the page instead (demo/api.js).
async function call(method, path, body, initData) {
  let res;
  try {
    res = await fetch(path, { method, headers: { ...(initData ? { Authorization: `tma ${initData}` } : {}), 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw Object.assign(new Error('offline'), { code: 'offline' });
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.error ?? 'generic'), { code: data.error ?? 'generic' });
  return data;
}

export const publicPassport = (token) => call('POST', '/api/passport', { token });

export function httpApi(initData) {
  const go = (method, path, body) => call(method, path, body, initData);
  const id = (n) => Number(n);
  return {
    me: () => go('GET', '/api/me'),
    setLang: (lang) => go('POST', '/api/lang', { lang }),
    cars: () => go('GET', '/api/cars'),
    addCar: (car) => go('POST', '/api/cars', { car }),
    car: (cid) => go('GET', `/api/cars/${id(cid)}`),
    reading: (cid, km, confirm = false) => go('POST', `/api/cars/${id(cid)}/km`, { km, confirm }),
    setItem: (cid, item, data) => go('POST', `/api/cars/${id(cid)}/items/${encodeURIComponent(item)}`, data),
    rotateCode: (cid) => go('POST', `/api/cars/${id(cid)}/code`, {}),
    setShop: (cid, wid, data) => go('POST', `/api/cars/${id(cid)}/shops/${id(wid)}`, data),
    history: (cid) => go('GET', `/api/cars/${id(cid)}/records`),
    addRecord: (cid, record) => go('POST', `/api/cars/${id(cid)}/records`, { record }),
    decide: (rid, yes, allow = false) => go('POST', `/api/records/${id(rid)}/decide`, { yes, allow }),
    receipt: (rid) => go('POST', `/api/records/${id(rid)}/receipt`, {}),
    stats: (cid) => go('GET', `/api/cars/${id(cid)}/stats`),
    csv: (cid) => go('POST', `/api/cars/${id(cid)}/csv`, {}),
    shares: (cid) => go('GET', `/api/cars/${id(cid)}/shares`),
    share: (cid, days, showOwner) => go('POST', `/api/cars/${id(cid)}/shares`, { days, show_owner: showOwner }),
    revoke: (cid, sid) => go('POST', `/api/cars/${id(cid)}/shares/${id(sid)}/revoke`, {}),
    passport: (token) => publicPassport(token),
    wsHome: () => go('GET', '/api/ws'),
    wsOpen: (code) => go('POST', '/api/ws/open', { code }),
    wsCar: (cid) => go('GET', `/api/ws/cars/${id(cid)}`),
    wsRecord: (cid, record) => go('POST', `/api/ws/cars/${id(cid)}/records`, { record }),
    wsInvite: (cid, item) => go('POST', `/api/ws/cars/${id(cid)}/invite`, { item }),
  };
}
