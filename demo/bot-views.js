// The bot's screens for the browser demo: the same texts, buttons and callback data as avtoservis/bot/views.py and
// views_more.py (menu, car, the reminder, "Tasdiqlaysizmi?", the decision, the invitation, the buyer's passport card).
// Screens are {html, kb: [[{text, data} | {text, app}]]}.
import { carLine, dateFull, dateShort, dueLine, escapeHtml, itemName, km, money, Raw, whenDay } from '../shared/i18n.js';

const DOT = { due: '🔴', soon: '🟠', ok: '🟢', unknown: '⚪' };

export function makeViews(t) {
  const btn = (text, data) => (data.startsWith('@app') ? { text, app: data.slice(4) } : { text, data });
  const rows = (rs) => rs.map((r) => r.map(([text, data]) => btn(text, data)));
  const back = (lang, data = 'n:menu') => [t(lang, 'btn.back'), data];
  const items = (lang, ids) => ids.map((i) => itemName(t, lang, i)).join(', ');

  function menu(lang, cars, roles, hello = false) {
    const lines = [t(lang, hello ? 'bot.hello' : 'bot.menu'), ''];
    if (cars.length) {
      lines.push(t(lang, 'bot.cars'));
      for (const c of cars) lines.push(`• ${escapeHtml(carLine(c))} — ${c.attention ? t(lang, 'bot.attention', { n: c.attention }) : t(lang, 'bot.all_ok')}`);
    } else lines.push(t(lang, 'bot.no_cars'));
    const rs = cars.map((c) => [[`🚗 ${c.title}`, `c:${c.id}`]]);
    rs.push([[t(lang, 'btn.add_car'), '@app#new']]);
    if (roles.workshop) rs.push([[t(lang, 'btn.workshop'), 'w:home']]);
    rs.push([[t(lang, 'btn.app'), '@app#'], [t(lang, 'btn.lang'), 'n:lang']]);
    return { html: lines.join('\n'), kb: rows(rs) };
  }

  function car(lang, v, n = 4) {
    const c = v.car;
    const last = v.points.at(-1);
    const lines = [t(lang, 'car.head', { title: c.title, plate: c.plate ? ` · ${c.plate}` : '' }),
      t(lang, 'car.odo', { km: new Raw(km(t, lang, last[1])), when: new Raw(whenDay(t, lang, last[0], v.today)), per_day: t(lang, 'fmt.per_day', { n: Math.floor(v.fc.rate / 1000) }) }), ''];
    if (v.fc.n === 0) lines.push(t(lang, 'car.default_rate'), '');
    lines.push(t(lang, 'car.next'), ...v.statuses.slice(0, n).map((s) => `${DOT[s.state]} ${dueLine(t, lang, s, v.today)}`));
    if (v.pending.length) lines.push('', t(lang, 'car.pending', { n: v.pending.length }));
    const cid = c.id;
    return { html: lines.join('\n'), kb: rows([[[t(lang, 'btn.km'), `c:${cid}:km`]], [[t(lang, 'btn.plan'), `@app#c=${cid}`], [t(lang, 'btn.history'), `@app#h=${cid}`]],
      [[t(lang, 'btn.passport'), `@app#g=${cid}`], [t(lang, 'btn.chart'), `@app#c=${cid}`]], [back(lang)]]) };
  }

  function remind(lang, v, list, ask) {
    const cid = v.car.id;
    const wanted = new Set(list.map((i) => i.id));
    const lines = v.statuses.filter((s) => wanted.has(s.id)).map((s) => `${DOT[s.state]} ${dueLine(t, lang, s, v.today)}`);
    const html = ask && !lines.length ? t(lang, 'notify.ask', { car: carLine(v.car), days: v.today - v.points.at(-1)[0] })
      : `${t(lang, 'notify.remind', { car: carLine(v.car), lines: new Raw(lines.join('\n')) })}\n\n${t(lang, 'notify.remind_tail')}`;
    const rs = [];
    if (v.car.odo > v.points.at(-1)[1]) rs.push([[t(lang, 'btn.km_ok', { km: km(t, lang, v.car.odo) }), `r:${cid}:${v.car.odo}`]]);
    rs.push([[t(lang, 'btn.km_other'), `c:${cid}:km`]], [[t(lang, 'btn.car'), `c:${cid}`]]);
    return { html, kb: rows(rs) };
  }

  function confirm(lang, r, title) {
    const note = r.note ? `\n📝 ${escapeHtml(r.note)}` : '';
    const html = t(lang, 'notify.confirm', { shop: r.shop, car: title, km: new Raw(km(t, lang, r.km)), date: dateFull(r.day), items: items(lang, r.items),
      labour: new Raw(money(t, lang, r.labour)), parts: new Raw(money(t, lang, r.parts)), total: new Raw(money(t, lang, r.total)), note: new Raw(note) });
    return { html, kb: rows([[[t(lang, 'btn.yes'), `ok:${r.id}:y`]], [[t(lang, 'btn.yes_allow'), `ok:${r.id}:a`]], [[t(lang, 'btn.no'), `ok:${r.id}:n`]]]) };
  }

  const decided = (lang, yes, title, ids) => ({ html: t(lang, yes ? 'notify.decided_yes' : 'notify.decided_no', { car: title, items: items(lang, ids) }),
    kb: rows([[[t(lang, 'btn.workshop'), 'w:home']]]) });

  function invite(lang, shop, v, item) {
    const st = v.statuses.find((s) => s.id === item);
    return { html: t(lang, 'notify.invite', { shop: shop.name, address: shop.address, line: new Raw(dueLine(t, lang, st, v.today)) }),
      kb: rows([[[t(lang, 'btn.no_invites'), `ka:${v.car.id}:${shop.id}:0`]], [[t(lang, 'btn.car'), `c:${v.car.id}`]]]) };
  }

  function passportCard(lang, p, tok) {
    const check = p.check.ok ? t(lang, 'pass.check_ok') : t(lang, 'pass.check_bad', { n: p.check.back });
    const head = t(lang, 'pass.bot', { title: carLine(p.car), check, verified: p.verified, self: p.self, km: new Raw(km(t, lang, p.last.km)),
      date: dateShort(t, lang, p.last.day) });
    const lines = [head, '', ...p.next.slice(0, 4).map((s) => `${DOT[s.state]} ${dueLine(t, lang, s, p.today)}`)];
    return { html: lines.join('\n'), kb: rows([[[t(lang, 'btn.open_passport'), `@app#p=${tok}`]], [[t(lang, 'btn.menu'), 'n:menu']]]) };
  }

  const wsHome = (lang, h) => ({ html: `${t(lang, 'ws.head', { name: h.workshop.name, cars: h.cars.length, due: h.due.length })}`,
    kb: rows([[[t(lang, 'btn.open_code'), '@app#w']], [back(lang)]]) });

  return { menu, car, remind, confirm, decided, invite, passportCard, wsHome, text: (lang, key, params) => ({ html: t(lang, key, params), kb: [] }) };
}
