// Spending (per month, per item, so'm per km, CSV to the bot), the car code for workshops with their permissions,
// and the Servis pasporti links (create for 7 / 30 / 90 days, copy, revoke).
import { localDay } from '../shared/clock.js';
import { dateShort, itemName } from '../shared/i18n.js';
import { group } from '../shared/money.js';
import { monthBars } from './chart.js';
import { h } from './util.js';

export function shareScreens(ctx, nav) {
  const { api, P, T } = ctx;
  const K = (n) => P('fmt.km', { n: group(n) });
  const S = (n) => P('fmt.sum', { n: group(n) });
  const link = (tok) => (ctx.share?.link ? ctx.share.link(tok) : `${window.location.origin}/webapp/#p=${tok}`);

  function statsScreen(cid) {
    let st = null;
    return {
      name: 'stats',
      async load() { st = await api.stats(cid); },
      render: () => h('div', { class: 'g-screen', 'data-testid': 'stats' },
        h('h2', { class: 'g-h2' }, `${P('app.stats')} · ${st.car.title}`),
        h('div', { class: 'g-kpis' },
          h('div', { class: 'g-kpi' }, h('small', {}, P('app.spent')), h('b', { 'data-testid': 'stats-total' }, S(st.total))),
          h('div', { class: 'g-kpi accent' }, h('small', {}, P('app.per_km')),
            h('b', { 'data-testid': 'per-km' }, st.per_km === null ? '—' : P('fmt.per_km', { n: group(st.per_km) })), h('small', {}, K(st.km)))),
        h('section', { class: 'g-card' }, h('b', {}, P('app.by_month')), monthBars(st.months, { T, lang: ctx.lang })),
        h('section', { class: 'g-card' }, h('b', {}, P('app.by_item')),
          h('div', { class: 'g-items-list' }, st.items.map((i) => h('div', { class: 'g-item-row' },
            h('span', {}, itemName(T, ctx.lang, i.id)), h('i', { style: { width: `${Math.max(4, Math.round((i.total * 100) / Math.max(1, st.items[0].total)))}%` } }),
            h('b', {}, S(i.total))))), h('small', { class: 'g-hint' }, P('app.by_item_hint'))),
        h('button', { class: 'g-btn wide', type: 'button', 'data-testid': 'csv', onclick: async () => {
          if (await nav.run(() => api.csv(cid))) ctx.toast(P('app.csv_sent'));
        } }, P('app.csv'))),
    };
  }

  function codeScreen(cid) {
    let v = null;
    const act = async (fn) => { const next = await nav.run(fn); if (next) { v = next; nav.show(screen, true); } };
    const screen = {
      name: 'code',
      async load() { v = await api.car(cid); },
      render: () => h('div', { class: 'g-screen' },
        h('h2', { class: 'g-h2' }, P('app.code')),
        h('div', { class: 'g-code', 'data-testid': 'car-code' }, v.car.code),
        h('p', { class: 'g-hint' }, P('app.code_hint')),
        h('button', { class: 'g-btn wide', type: 'button', 'data-testid': 'new-code', onclick: () => act(() => api.rotateCode(cid)) }, P('app.new_code')),
        h('section', { class: 'g-card' }, h('b', {}, P('app.shops')),
          v.shops.length ? v.shops.map((s) => h('div', { class: 'g-shop', 'data-testid': `shop-${s.workshop_id}` },
            h('span', {}, h('b', {}, s.name), h('small', {}, s.address)),
            h('label', { class: 'g-check' }, h('input', { type: 'checkbox', checked: s.allow, onchange: (e) => act(() => api.setShop(cid, s.workshop_id, { allow: e.target.checked })) }),
              h('span', {}, P('app.allow'))),
            h('button', { class: 'g-link', type: 'button', onclick: () => act(() => api.setShop(cid, s.workshop_id, { remove: true })) }, P('app.remove'))))
            : h('p', { class: 'g-hint' }, P('code.no_shops')))),
    };
    return screen;
  }

  function passportScreen(cid) {
    let items = [];
    let title = '';
    let made = null;
    let days = 30;
    const owner = h('input', { type: 'checkbox', 'data-testid': 'p-owner' });
    async function create() {
      const out = await nav.run(() => api.share(cid, days, owner.checked));
      if (out) { made = out; items = out.items; nav.show(screen, true); }
    }
    async function revoke(sid) {
      const out = await nav.run(() => api.revoke(cid, sid));
      if (out) { items = out.items; if (made?.id === sid) made = null; ctx.toast(P('pass.revoked')); nav.show(screen, true); }
    }
    const copy = async (url) => {
      try { await navigator.clipboard.writeText(url); ctx.toast(P('app.copied')); } catch { ctx.toast(url); }
    };
    const until = (ms) => P('app.pass_until', { date: dateShort(T, ctx.lang, localDay(ms)) });
    const screen = {
      name: 'passport-admin',
      async load() { [items, title] = [(await api.shares(cid)).items, (await api.car(cid)).car.title]; },
      render: () => h('div', { class: 'g-screen', 'data-testid': 'passport-admin' },
        h('h2', { class: 'g-h2' }, `${P('app.passport')} · ${title}`),
        h('p', { class: 'g-hint' }, P('app.pass_hint')),
        h('div', { class: 'g-card' },
          h('b', { class: 'g-label' }, P('app.pass_days')),
          h('div', { class: 'g-seg' }, [7, 30, 90].map((n) => h('label', {}, h('input', { type: 'radio', name: 'days', checked: n === days, 'data-testid': `p-days-${n}`,
            onchange: () => { days = n; } }), h('span', {}, P('app.days', { n }))))),
          h('label', { class: 'g-check' }, owner, h('span', {}, P('app.pass_owner'))),
          h('button', { class: 'g-btn primary wide', type: 'button', 'data-testid': 'p-make', onclick: create }, P('app.pass_make'))),
        made ? h('div', { class: 'g-made', 'data-testid': 'p-link' }, h('code', {}, link(made.token)),
          h('button', { class: 'g-btn', type: 'button', onclick: () => copy(link(made.token)) }, P('app.pass_copy'))) : null,
        h('section', { class: 'g-card' }, items.length ? items.map((s) => h('div', { class: 'g-share', 'data-testid': `share-${s.id}` },
          h('span', {}, `#${s.id} · ${until(s.expires_at)}${s.show_owner ? ` · ${P('pass.with_owner').replace(' · ', '')}` : ''}`),
          h('button', { class: 'g-btn danger', type: 'button', 'data-testid': `revoke-${s.id}`, onclick: () => revoke(s.id) }, P('app.revoke'))))
          : h('p', { class: 'g-hint' }, P('app.pass_none')))),
    };
    return screen;
  }

  return { statsScreen, codeScreen, passportScreen };
}
