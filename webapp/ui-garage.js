// The driver's Garaj: the list of cars, adding a car, and the car screen (odometer with the anomaly guard, the
// workshop records waiting for "Tasdiqlash", the odometer chart with its forecast fan, the plan, and the actions).
import { FUELS, USAGES } from '../shared/cars.js';
import { civil, localDay } from '../shared/clock.js';
import { dateShort, dueLine, itemName } from '../shared/i18n.js';
import { group } from '../shared/money.js';
import { odometerChart } from './chart.js';
import { carMore } from './ui-car.js';
import { h, num } from './util.js';

const DOT = { due: 'red', soon: 'amber', ok: 'green', unknown: 'grey' };

export function garageScreens(ctx, nav) {
  const { api, P, T } = ctx;
  const more = carMore(ctx, nav);
  const K = (n) => P('fmt.km', { n: group(n) });
  const S = (n) => P('fmt.sum', { n: group(n) });
  const field = (label, input, hint) => h('label', { class: 'g-field' }, h('span', {}, label), input, hint ? h('small', {}, hint) : null);

  function home() {
    let cars = [];
    let sig = '';
    return {
      name: 'cars',
      async load() { cars = (await api.cars()).items; sig = JSON.stringify(cars); },
      async poll() { const next = (await api.cars()).items; const s2 = JSON.stringify(next); if (s2 === sig) return false; cars = next; sig = s2; return true; },
      render: () => h('div', { class: 'g-screen' },
        h('h2', { class: 'g-h2' }, P('app.my_cars')),
        cars.length ? null : h('p', { class: 'g-empty' }, P('app.empty')),
        cars.map((c) => h('button', { class: 'g-car-card', type: 'button', 'data-testid': `car-${c.id}`, onclick: () => nav.show(carScreen(c.id)) },
          h('span', { class: 'g-car-title' }, c.title),
          c.plate ? h('span', { class: 'g-plate' }, c.plate) : null,
          h('span', { class: 'g-car-odo' }, K(c.odo)),
          h('span', { class: `g-pill ${c.attention ? 'amber' : 'green'}` }, c.attention ? P('app.attention', { n: c.attention }) : P('app.all_ok')),
          c.next[0] ? h('span', { class: 'g-car-next', html: dueLine(T, ctx.lang, c.next[0], localDay(ctx.now())) }) : null)),
        h('button', { class: 'g-btn primary wide', type: 'button', 'data-testid': 'add-car', onclick: () => nav.show(addCar()) }, `＋ ${P('app.add_car')}`)),
    };
  }

  function addCar() {
    const year = civil(localDay(ctx.now()))[0];
    const model = h('select', { 'data-testid': 'f-model' }, ctx.models.map((m) => h('option', { value: m.id }, m.name || P('model.other'))));
    const name = h('input', { 'data-testid': 'f-name', maxlength: 40, autocomplete: 'off' });
    const years = h('select', { 'data-testid': 'f-year' });
    const fuel = h('div', { class: 'g-seg', role: 'radiogroup' });
    const usage = h('div', { class: 'g-seg', role: 'radiogroup' }, USAGES.map((u, i) => h('label', {}, h('input', { type: 'radio', name: 'usage', value: u,
      checked: i === 0, 'data-testid': `f-usage-${u}` }), h('span', {}, P(`usage.${u}`)))));
    const odo = h('input', { inputmode: 'numeric', 'data-testid': 'f-odo', maxlength: 9, autocomplete: 'off', placeholder: '86 900' });
    const plate = h('input', { 'data-testid': 'f-plate', maxlength: 16, autocomplete: 'off', placeholder: P('app.plate_hint') });
    const oil = h('input', { inputmode: 'numeric', 'data-testid': 'f-oil', maxlength: 9, autocomplete: 'off' });
    const nameRow = field(P('app.name'), name);
    function sync() {
      const m = ctx.models.find((x) => x.id === model.value);
      nameRow.hidden = m.id !== 'other';
      const top = Math.min(m.to ?? year, year);
      const keep = years.value;
      years.replaceChildren(...Array.from({ length: top - m.from + 1 }, (_, i) => h('option', { value: top - i }, String(top - i))));
      if (keep && Number(keep) <= top && Number(keep) >= m.from) years.value = keep;
      const was = fuel.querySelector('input:checked')?.value;
      fuel.replaceChildren(...FUELS.filter((f) => m.fuels.includes(f)).map((f, i) => h('label', {}, h('input', { type: 'radio', name: 'fuel', value: f,
        checked: was ? was === f : i === 0, 'data-testid': `f-fuel-${f}` }), h('span', {}, P(`fuel.${f}`)))));
      if (!fuel.querySelector('input:checked')) fuel.querySelector('input').checked = true;
    }
    model.addEventListener('change', sync);
    async function save(e) {
      e.preventDefault();
      const car = { model: model.value, name: name.value, year: Number(years.value), fuel: fuel.querySelector('input:checked').value,
        usage: usage.querySelector('input:checked').value, odo: num(odo.value), plate: plate.value, last_oil: oil.value.trim() ? num(oil.value) : null };
      const v = await nav.run(() => api.addCar(car));
      if (v) await nav.show(carScreen(v.car.id), true);
    }
    return {
      name: 'add-car',
      render: () => h('form', { class: 'g-screen g-form', onsubmit: save, 'data-testid': 'add-form' },
        h('h2', { class: 'g-h2' }, P('app.add_car')),
        field(P('app.model'), model), nameRow, field(P('app.year'), years), field(P('app.fuel'), fuel), field(P('app.usage'), usage),
        field(P('app.odo'), odo), field(P('app.plate'), plate), field(P('app.last_oil'), oil, P('app.last_oil_hint')),
        h('button', { class: 'g-btn primary wide', type: 'submit', 'data-testid': 'f-save' }, P('app.save_car'))),
      mounted: () => sync(),
    };
  }

  function carScreen(cid) {
    let v = null;
    let sig = '';
    let jump = null;
    const set = (next) => { v = next; sig = JSON.stringify(next); };
    async function send(input, confirm = false) {
      const out = await nav.run(() => api.reading(cid, confirm ? jump.km : num(input.value), confirm));
      if (!out) return;
      if (out.confirm) { jump = out; nav.show(screen, true); return; }
      jump = null;
      set(out.view);
      ctx.toast(P('app.saved_km', { km: K(out.km) }));
      nav.show(screen, true);
    }
    function kmBox() {
      const input = h('input', { inputmode: 'numeric', maxlength: 9, autocomplete: 'off', placeholder: P('app.km_placeholder'), 'data-testid': 'km-input',
        'aria-label': P('app.send_km') });
      const form = h('form', { class: 'g-km', onsubmit: (e) => { e.preventDefault(); send(input); } }, input,
        h('button', { class: 'g-btn primary', type: 'submit', 'data-testid': 'km-send' }, P('app.send')));
      if (!jump) return form;
      return h('div', {}, form, h('div', { class: 'g-warn', 'data-testid': 'jump' }, h('b', {}, P('app.jump_title')),
        h('p', {}, P('km.jump', { days: jump.days, km: `${jump.km} km`, per_day: jump.per_day })),
        h('div', { class: 'g-row' }, h('button', { class: 'g-btn primary', type: 'button', 'data-testid': 'jump-yes', onclick: () => send(input, true) }, P('app.yes')),
          h('button', { class: 'g-btn', type: 'button', onclick: () => { jump = null; nav.show(screen, true); } }, P('app.cancel')))));
    }
    function pendingCard(p) {
      const allow = h('input', { type: 'checkbox', 'data-testid': `allow-${p.id}` });
      const decide = async (yes) => {
        const r = await nav.run(() => api.decide(p.id, yes, allow.checked));
        if (r) { set(await api.car(cid)); ctx.toast(P(yes ? 'notify.confirmed' : 'notify.rejected')); nav.show(screen, true); }
      };
      return h('div', { class: 'g-pending', 'data-testid': `pending-${p.id}` },
        h('div', { class: 'g-pending-head' }, h('b', {}, p.workshop), h('span', { class: 'g-pill amber' }, P('app.pending'))),
        h('p', {}, `${K(p.km)} · ${dateShort(T, ctx.lang, p.day)}`),
        h('p', { class: 'g-items' }, p.items.map((i) => itemName(T, ctx.lang, i)).join(', ')),
        h('p', { class: 'g-money' }, `${P('app.total')}: `, h('b', {}, S(p.labour + p.parts))),
        h('label', { class: 'g-check' }, allow, h('span', {}, P('app.confirm_allow'))),
        h('div', { class: 'g-row' }, h('button', { class: 'g-btn primary', type: 'button', 'data-testid': `confirm-${p.id}`, onclick: () => decide(true) }, P('app.confirm')),
          h('button', { class: 'g-btn', type: 'button', 'data-testid': `reject-${p.id}`, onclick: () => decide(false) }, P('app.reject'))));
    }
    function planRow(st) {
      const window = st.lo_day !== null && st.hi_day !== null && st.hi_day > st.lo_day && st.state !== 'due'
        ? P('app.window', { from: dateShort(T, ctx.lang, st.lo_day), to: dateShort(T, ctx.lang, st.hi_day) }) : null;
      return h('button', { class: `g-plan-row ${st.state}`, type: 'button', 'data-testid': `plan-${st.id}`, onclick: () => nav.show(more.itemScreen(cid, st.id)) },
        h('i', { class: `g-dot ${DOT[st.state]}` }),
        h('span', { class: 'g-plan-main' }, h('span', { class: 'g-due', 'data-testid': `due-${st.id}`, html: dueLine(T, ctx.lang, st, v.today) }),
          window ? h('small', {}, window) : null),
        st.guess && st.state !== 'unknown' ? h('span', { class: 'g-chip' }, P('app.guess')) : null);
    }
    const screen = {
      name: 'car',
      get id() { return cid; },
      async load() { set(await api.car(cid)); },
      async poll() { const next = await api.car(cid); const s2 = JSON.stringify(next); if (s2 === sig) return false; set(next); return true; },
      render() {
        const c = v.car;
        const last = v.points.at(-1);
        const act = (id, label, scr) => h('button', { class: 'g-act', type: 'button', 'data-testid': `act-${id}`, onclick: () => nav.show(scr()) }, label);
        return h('div', { class: 'g-screen', 'data-testid': 'car-screen' },
          h('section', { class: 'g-hero' },
            h('div', { class: 'g-hero-top' }, h('h2', {}, c.title), c.plate ? h('span', { class: 'g-plate' }, c.plate) : null),
            h('div', { class: 'g-chips' }, h('span', { class: 'g-chip' }, P(`fuel.${c.fuel}`)), h('span', { class: 'g-chip' }, P(`usage.${c.usage}`))),
            h('div', { class: 'g-odo' }, h('small', {}, P('app.odo_now')), h('b', { 'data-testid': 'odo' }, K(last[1])),
              h('span', { 'data-testid': 'rate' }, v.fc.n ? P('app.rate', { n: Math.floor(v.fc.rate / 1000) }) : P('app.rate_default'))),
            kmBox()),
          v.pending.length ? h('section', { class: 'g-card' }, v.pending.map(pendingCard)) : null,
          h('section', { class: 'g-card' }, h('div', { class: 'g-card-head' }, h('b', {}, P('app.chart')),
            h('span', { class: 'g-pill', 'data-testid': 'fan' }, P('app.fan', { n: v.fc.margin }))),
          odometerChart(v, { T, lang: ctx.lang, P }), h('small', { class: 'g-hint' }, P('app.chart_hint'))),
          h('section', { class: 'g-card' }, h('div', { class: 'g-card-head' }, h('b', {}, P('app.plan'))), h('small', { class: 'g-hint' }, P('app.plan_hint')),
            h('div', { class: 'g-plan', 'data-testid': 'plan' }, v.statuses.map(planRow)),
            v.off.length ? h('small', { class: 'g-hint' }, `${P('app.off_list')}: ${v.off.map((st) => itemName(T, ctx.lang, st.id)).join(', ')}`) : null),
          h('section', { class: 'g-acts' }, act('log', P('app.log'), () => more.logScreen(cid)), act('history', P('app.history'), () => more.historyScreen(cid)),
            act('stats', P('app.stats'), () => more.statsScreen(cid)), act('code', P('app.code'), () => more.codeScreen(cid)),
            act('passport', P('app.passport'), () => more.passportScreen(cid))));
      },
    };
    return screen;
  }

  return { home, addCar, carScreen, more, open: (cid) => nav.show(carScreen(cid)) };
}
