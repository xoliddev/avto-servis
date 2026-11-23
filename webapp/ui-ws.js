// The workshop's side: open a car by the code its owner gave, clients whose service is due soon (only those who
// allowed it) with one invitation per item, and recording a service that waits for the owner's "Tasdiqlash".
import { carLine, dueLine, itemName } from '../shared/i18n.js';
import { group } from '../shared/money.js';
import { carMore } from './ui-car.js';
import { h, num } from './util.js';

const DOT = { due: 'red', soon: 'amber', ok: 'green', unknown: 'grey' };

export function workshopScreens(ctx, nav) {
  const { api, P, T } = ctx;
  const K = (n) => P('fmt.km', { n: group(n) });
  const S = (n) => P('fmt.sum', { n: group(n) });
  const field = (label, input) => h('label', { class: 'g-field' }, h('span', {}, label), input);
  const { recordCard } = carMore(ctx, nav);

  function home() {
    let w = null;
    let sig = '';
    const code = h('input', { 'data-testid': 'ws-code', maxlength: 12, autocomplete: 'off', placeholder: 'ABCD-EF23', 'aria-label': P('app.ws_code') });
    async function open(e) {
      e.preventDefault();
      const v = await nav.run(() => api.wsOpen(code.value));
      if (v) await nav.show(carScreen(v.car.id));
    }
    async function invite(cid, item) {
      const next = await nav.run(() => api.wsInvite(cid, item));
      if (next) { w = next; sig = JSON.stringify(next); ctx.toast(P('ws.invited')); nav.show(screen, true); }
    }
    const screen = {
      name: 'ws-home',
      async load() { w = await api.wsHome(); sig = JSON.stringify(w); },
      async poll() { const n = await api.wsHome(); const s2 = JSON.stringify(n); if (s2 === sig) return false; w = n; sig = s2; return true; },
      render: () => h('div', { class: 'g-screen', 'data-testid': 'ws-home' },
        h('section', { class: 'g-hero ws' }, h('h2', {}, w.workshop.name), h('small', {}, w.workshop.address),
          h('form', { class: 'g-km', onsubmit: open }, code, h('button', { class: 'g-btn primary', type: 'submit', 'data-testid': 'ws-open' }, P('app.ws_open')))),
        h('section', { class: 'g-card' }, h('b', {}, P('app.ws_due')),
          w.due.length ? w.due.map((d) => h('div', { class: 'g-due-row', 'data-testid': `ws-due-${d.car.id}-${d.status.id}` },
            h('i', { class: `g-dot ${DOT[d.status.state]}` }),
            h('span', { class: 'g-plan-main' }, h('b', {}, carLine(d.car)), h('span', { class: 'g-due', html: dueLine(T, ctx.lang, d.status, w.today) })),
            d.invited ? h('span', { class: 'g-pill' }, P('app.invited'))
              : h('button', { class: 'g-btn small', type: 'button', 'data-testid': `invite-${d.car.id}-${d.status.id}`, onclick: () => invite(d.car.id, d.status.id) },
                P('app.invite'))))
            : h('p', { class: 'g-hint' }, P('app.no_due'))),
        h('section', { class: 'g-card' }, h('b', {}, P('app.ws_cars')),
          w.cars.map((c) => h('button', { class: 'g-list-btn', type: 'button', 'data-testid': `ws-car-${c.id}`, onclick: () => nav.show(carScreen(c.id)) },
            h('span', {}, carLine(c)), h('small', {}, K(c.odo))))),
        w.records.length ? h('section', { class: 'g-card' }, h('b', {}, P('app.ws_mine')), w.records.slice(0, 6).map((r) => recordCard(r, { receipts: false }))) : null),
    };
    return screen;
  }

  function carScreen(cid) {
    let v = null;
    const chosen = new Set();
    const inputs = {
      km: h('input', { inputmode: 'numeric', maxlength: 9, 'data-testid': 'w-km', autocomplete: 'off' }),
      labour: h('input', { inputmode: 'numeric', maxlength: 9, 'data-testid': 'w-labour', autocomplete: 'off', placeholder: '0' }),
      parts: h('input', { inputmode: 'numeric', maxlength: 9, 'data-testid': 'w-parts', autocomplete: 'off', placeholder: '0' }),
      note: h('input', { maxlength: 300, 'data-testid': 'w-note', autocomplete: 'off' }),
    };
    const total = h('b', { 'data-testid': 'w-total' });
    const sum = () => { total.textContent = S((Number(num(inputs.labour.value)) || 0) + (Number(num(inputs.parts.value)) || 0)); };
    inputs.labour.addEventListener('input', sum);
    inputs.parts.addEventListener('input', sum);
    async function send(e) {
      e.preventDefault();
      const next = await nav.run(() => api.wsRecord(cid, { items: [...chosen], km: num(inputs.km.value), labour: num(inputs.labour.value || 0),
        parts: num(inputs.parts.value || 0), note: inputs.note.value }));
      if (next) {
        v = next;
        chosen.clear();
        for (const k of ['labour', 'parts', 'note']) inputs[k].value = '';
        ctx.toast(P('app.ws_sent'));
        nav.show(screen, true);
      }
    }
    const screen = {
      name: 'ws-car',
      get id() { return cid; },
      async load() { v = await api.wsCar(cid); inputs.km.value = String(v.car.odo); },
      async poll() { const n = await api.wsCar(cid); if (JSON.stringify(n) === JSON.stringify(v)) return false; v = n; return true; },
      render: () => h('div', { class: 'g-screen', 'data-testid': 'ws-car' },
        h('section', { class: 'g-hero' }, h('div', { class: 'g-hero-top' }, h('h2', {}, v.car.title), v.car.plate ? h('span', { class: 'g-plate' }, v.car.plate) : null),
          h('div', { class: 'g-odo' }, h('small', {}, P('app.odo_now')), h('b', {}, K(v.car.odo)))),
        h('section', { class: 'g-card' }, h('div', { class: 'g-plan' }, v.statuses.slice(0, 5).map((st) => h('div', { class: `g-plan-row ${st.state}` },
          h('i', { class: `g-dot ${DOT[st.state]}` }), h('span', { class: 'g-plan-main' }, h('span', { class: 'g-due', html: dueLine(T, ctx.lang, st, v.today) })))))),
        h('form', { class: 'g-card g-form', onsubmit: send, 'data-testid': 'ws-form' }, h('b', {}, P('app.ws_record')),
          h('div', { class: 'g-tiles' }, v.items.map((id) => h('label', { class: 'g-tile', 'data-testid': `w-item-${id}` },
            h('input', { type: 'checkbox', checked: chosen.has(id), onchange: (e) => (e.target.checked ? chosen.add(id) : chosen.delete(id)) }), h('span', {}, itemName(T, ctx.lang, id))))),
          field(P('app.km'), inputs.km),
          h('div', { class: 'g-two' }, field(P('app.labour'), inputs.labour), field(P('app.parts'), inputs.parts)),
          h('p', { class: 'g-money' }, `${P('app.total')}: `, total), field(P('app.note'), inputs.note),
          h('button', { class: 'g-btn primary wide', type: 'submit', 'data-testid': 'w-send' }, P('app.ws_send'))),
        v.records.length ? h('section', { class: 'g-card' }, h('b', {}, P('app.ws_mine')), v.records.map((r) => recordCard(r, { receipts: false }))) : null),
      mounted: sum,
    };
    return screen;
  }

  return { home, carScreen, open: (cid) => nav.show(carScreen(cid)) };
}
