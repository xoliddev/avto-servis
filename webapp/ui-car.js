// The car's inner screens: one plan item (done today, document expiry, own interval, off the plan), logging a
// service ("O'zi yozgan"), and the history with "Servis tasdiqlagan" / "O'zi yozgan" badges. Stats, the car code and
// the Servis pasporti links are in ui-share.js.
import { localDay } from '../shared/clock.js';
import { dateFull, dateShort, dueLine, itemName } from '../shared/i18n.js';
import { group } from '../shared/money.js';
import { shareScreens } from './ui-share.js';
import { h, num } from './util.js';

export function carMore(ctx, nav) {
  const { api, P, T } = ctx;
  const K = (n) => P('fmt.km', { n: group(n) });
  const S = (n) => P('fmt.sum', { n: group(n) });
  const field = (label, input) => h('label', { class: 'g-field' }, h('span', {}, label), input);
  const share = shareScreens(ctx, nav);

  function itemScreen(cid, id) {
    let v = null;
    const date = h('input', { 'data-testid': 'i-date', maxlength: 12, placeholder: '12.03.2027', autocomplete: 'off' });
    const kmIv = h('input', { 'data-testid': 'i-km', inputmode: 'numeric', maxlength: 6, autocomplete: 'off' });
    const moIv = h('input', { 'data-testid': 'i-months', inputmode: 'numeric', maxlength: 3, autocomplete: 'off' });
    const change = async (data) => {
      const next = await nav.run(() => api.setItem(cid, id, data));
      if (next) { v = next; ctx.toast(P('app.saved')); nav.show(screen, true); }
    };
    const screen = {
      name: 'item',
      async load() { v = await api.car(cid); },
      render() {
        const st = v.statuses.concat(v.off).find((x) => x.id === id);
        const off = v.off.some((x) => x.id === id);
        const docs = st.months && !st.km_iv;
        return h('div', { class: 'g-screen' },
          h('h2', { class: 'g-h2' }, itemName(T, ctx.lang, st.id, st.season)),
          h('p', { class: 'g-due big', html: dueLine(T, ctx.lang, st, v.today) }),
          st.last_day !== null && !st.season ? h('p', { class: 'g-hint' }, [st.last_km !== null ? K(st.last_km) : null, dateShort(T, ctx.lang, st.last_day)]
            .filter(Boolean).join(' · ') + (st.guess ? ` (${P('app.guess')})` : '')) : null,
          h('button', { class: 'g-btn primary wide', type: 'button', 'data-testid': 'i-done', onclick: () => change({ done: true }) }, P('app.done_today')),
          docs ? h('form', { class: 'g-form', onsubmit: (e) => { e.preventDefault(); change({ expires: date.value }); } }, field(P('app.expires'), date),
            h('button', { class: 'g-btn', type: 'submit', 'data-testid': 'i-save-date' }, P('app.set_date'))) : null,
          st.season ? null : h('form', { class: 'g-form', onsubmit: (e) => { e.preventDefault(); change({ km: num(kmIv.value), months: num(moIv.value) }); } },
            st.km_iv ? field(P('app.own_interval'), Object.assign(kmIv, { placeholder: String(st.km_iv) })) : null,
            st.months ? field(P('app.own_months'), Object.assign(moIv, { placeholder: String(st.months) })) : null,
            h('button', { class: 'g-btn', type: 'submit' }, P('app.save'))),
          h('button', { class: 'g-btn ghost wide', type: 'button', 'data-testid': 'i-off', onclick: () => change({ off: !off }) }, P(off ? 'app.on' : 'app.off')));
      },
    };
    return screen;
  }

  function logScreen(cid) {
    let v = null;
    const chosen = new Set();
    const inputs = {
      km: h('input', { inputmode: 'numeric', maxlength: 9, 'data-testid': 'l-km', autocomplete: 'off' }),
      day: h('input', { maxlength: 12, 'data-testid': 'l-day', autocomplete: 'off' }),
      labour: h('input', { inputmode: 'numeric', maxlength: 9, 'data-testid': 'l-labour', autocomplete: 'off', placeholder: '0' }),
      parts: h('input', { inputmode: 'numeric', maxlength: 9, 'data-testid': 'l-parts', autocomplete: 'off', placeholder: '0' }),
      shop: h('input', { maxlength: 60, 'data-testid': 'l-shop', autocomplete: 'off' }),
      note: h('input', { maxlength: 300, 'data-testid': 'l-note', autocomplete: 'off' }),
    };
    const total = h('b', { 'data-testid': 'l-total' });
    const sum = () => { total.textContent = S((Number(num(inputs.labour.value)) || 0) + (Number(num(inputs.parts.value)) || 0)); };
    inputs.labour.addEventListener('input', sum);
    inputs.parts.addEventListener('input', sum);
    async function save(e) {
      e.preventDefault();
      const out = await nav.run(() => api.addRecord(cid, { items: [...chosen], km: num(inputs.km.value), day: inputs.day.value.trim() || 'today',
        labour: num(inputs.labour.value || 0), parts: num(inputs.parts.value || 0), shop: inputs.shop.value, note: inputs.note.value }));
      if (out) { ctx.toast(P('app.saved')); await nav.pop(); }
    }
    return {
      name: 'log',
      async load() { v = await api.car(cid); inputs.km.value = String(v.car.odo); inputs.day.value = dateFull(localDay(ctx.now())); },
      render: () => h('form', { class: 'g-screen g-form', onsubmit: save, 'data-testid': 'log-form' },
        h('h2', { class: 'g-h2' }, `${P('app.log')} · ${v.car.title}`),
        h('b', { class: 'g-label' }, P('app.log_items')),
        h('div', { class: 'g-tiles' }, v.statuses.concat(v.off).map((st) => h('label', { class: 'g-tile', 'data-testid': `l-item-${st.id}` },
          h('input', { type: 'checkbox', onchange: (e) => (e.target.checked ? chosen.add(st.id) : chosen.delete(st.id)) }),
          h('span', {}, itemName(T, ctx.lang, st.id))))),
        h('div', { class: 'g-two' }, field(P('app.km'), inputs.km), field(P('app.date'), inputs.day)),
        h('div', { class: 'g-two' }, field(P('app.labour'), inputs.labour), field(P('app.parts'), inputs.parts)),
        h('p', { class: 'g-money' }, `${P('app.total')}: `, total),
        field(P('app.shop'), inputs.shop), field(P('app.note'), inputs.note),
        h('button', { class: 'g-btn primary wide', type: 'submit', 'data-testid': 'l-save' }, P('app.save'))),
      mounted: sum,
    };
  }

  function recordCard(r, { receipts = true } = {}) {
    const badge = r.status === 'pending' ? h('span', { class: 'g-pill amber' }, P('app.waiting'))
      : r.verified ? h('span', { class: 'g-badge ok', 'data-testid': 'badge-verified' }, `✓ ${P('app.verified')}`)
        : h('span', { class: 'g-badge self', 'data-testid': 'badge-self' }, `✍ ${P('app.self')}`);
    return h('article', { class: `g-record ${r.verified ? 'verified' : ''}`, 'data-testid': `record-${r.id}` },
      h('div', { class: 'g-record-head' }, h('b', {}, dateShort(T, ctx.lang, r.day)), h('span', {}, K(r.km)), badge),
      h('p', { class: 'g-items' }, r.items.map((i) => itemName(T, ctx.lang, i)).join(', ')),
      h('p', { class: 'g-record-foot' }, r.shop ? h('span', {}, r.shop) : null, r.total !== undefined ? h('b', {}, S(r.total)) : null,
        receipts && r.photo ? h('button', { class: 'g-link', type: 'button', onclick: () => nav.run(() => api.receipt(r.id)) }, `🧾 ${P('app.receipt')}`) : null),
      r.note ? h('p', { class: 'g-hint' }, r.note) : null);
  }

  function historyScreen(cid) {
    let items = [];
    let title = '';
    let sig = '';
    return {
      name: 'history',
      async load() { [items, title] = [(await api.history(cid)).items, (await api.car(cid)).car.title]; sig = JSON.stringify(items); },
      async poll() { const n = (await api.history(cid)).items; const s2 = JSON.stringify(n); if (s2 === sig) return false; items = n; sig = s2; return true; },
      render: () => h('div', { class: 'g-screen', 'data-testid': 'history' }, h('h2', { class: 'g-h2' }, `${P('app.history')} · ${title}`),
        items.length ? items.map((r) => recordCard(r)) : h('p', { class: 'g-empty' }, P('hist.empty'))),
    };
  }

  return { itemScreen, logScreen, historyScreen, recordCard, ...share };
}
