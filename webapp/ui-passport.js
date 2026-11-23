// The buyer's page: Servis pasporti, read-only. The car, the odometer check ("spidometr ketma-ket, orqaga
// qaytmagan" ✓), the timeline with "Servis tasdiqlagan" vs "O'zi yozgan", and what is due next. No money, no owner
// unless the owner chose to show them. It re-checks the link now and then, so a revoked link shows it at once.
import { localDay } from '../shared/clock.js';
import { dateShort, dueLine, itemName, makeT } from '../shared/i18n.js';
import { group } from '../shared/money.js';
import { h, makeText } from './util.js';

const DOT = { due: 'red', soon: 'amber', ok: 'green', unknown: 'grey' };

export function mountPassport(root, { fetchPassport, token, catalogs, lang: lang0 = 'uz', poll = 4000, onLang }) {
  const T = makeT(catalogs);
  const text = makeText(catalogs);
  let lang = lang0 === 'ru' ? 'ru' : 'uz';
  const P = (k, p) => text(lang, k, p);
  const K = (n) => P('fmt.km', { n: group(n) });
  let data = null;
  let gone = false;
  let sig = '';
  let timer = 0;
  let alive = true;

  function paint() {
    const head = h('header', { class: 'g-head' }, h('b', { class: 'g-title' }, P('pp.title')), h('span', { class: 'g-grow' }),
      h('button', { class: 'g-lang', type: 'button', 'data-testid': 'pp-lang', onclick: () => { lang = lang === 'uz' ? 'ru' : 'uz'; onLang?.(lang); paint(); } }, P('app.lang')));
    let body;
    if (gone) {
      body = h('div', { class: 'g-screen pp-gone', 'data-testid': 'pp-gone' }, h('div', { class: 'pp-gone-icon', 'aria-hidden': 'true' }, '!'),
        h('h2', { class: 'g-h2' }, P('pp.gone')), h('p', { class: 'g-hint' }, P('pp.gone_hint')));
    } else if (!data) {
      body = h('div', { class: 'g-screen' }, h('p', { class: 'g-hint' }, P('pp.loading')));
    } else {
      const c = data.check;
      const perDay = c.per_day !== null ? P('fmt.per_day', { n: c.per_day }) : '';
      body = h('div', { class: 'g-screen', 'data-testid': 'passport' },
        h('section', { class: 'g-hero pp' },
          h('small', { class: 'pp-kicker' }, P('pp.title')),
          h('div', { class: 'g-hero-top' }, h('h2', {}, data.car.title), data.car.plate ? h('span', { class: 'g-plate' }, data.car.plate) : null),
          h('div', { class: 'g-chips' }, h('span', { class: 'g-chip' }, P(`fuel.${data.car.fuel}`)), h('span', { class: 'g-chip' }, P(`usage.${data.car.usage}`)),
            h('span', { class: 'g-chip' }, P('pp.since', { date: dateShort(T, lang, data.since) }))),
          data.last ? h('div', { class: 'g-odo' }, h('small', {}, P('pp.last')), h('b', {}, K(data.last.km)), h('span', {}, dateShort(T, lang, data.last.day))) : null,
          data.owner ? h('p', { class: 'pp-owner' }, `${P('pp.owner')}: ${data.owner.name}${data.owner.phone ? ` · ${data.owner.phone}` : ''}`) : null),
        h('section', { class: `g-card pp-check ${c.ok ? 'ok' : 'bad'}`, 'data-testid': 'pp-check' },
          h('div', { class: 'pp-check-mark', 'aria-hidden': 'true' }, c.ok ? '✓' : '!'),
          h('div', {}, h('b', {}, c.ok ? P('pp.check_ok') : P('pp.check_bad', { n: c.back })),
            h('small', {}, P('pp.readings', { n: c.n, per_day: perDay })),
            c.jumps ? h('small', {}, P('pp.jumps', { n: c.jumps })) : null)),
        h('section', { class: 'g-card' }, h('div', { class: 'g-card-head' }, h('b', {}, P('pp.timeline')),
          h('span', { class: 'g-pill', 'data-testid': 'pp-counts' }, P('pp.counts', { v: data.verified, s: data.self }))),
        h('ol', { class: 'pp-timeline' }, data.timeline.map((r) => h('li', { class: r.verified ? 'verified' : 'self', 'data-testid': `pp-rec-${r.id}` },
          h('div', { class: 'g-record-head' }, h('b', {}, dateShort(T, lang, r.day)), h('span', {}, K(r.km)),
            r.verified ? h('span', { class: 'g-badge ok' }, `✓ ${P('app.verified')}`) : h('span', { class: 'g-badge self' }, `✍ ${P('app.self')}`)),
          h('p', { class: 'g-items' }, r.items.map((i) => itemName(T, lang, i)).join(', ')),
          r.shop ? h('small', { class: 'g-hint' }, r.shop) : null)))),
        h('section', { class: 'g-card' }, h('b', {}, P('pp.next')),
          h('div', { class: 'g-plan' }, data.next.map((st) => h('div', { class: `g-plan-row ${st.state}` }, h('i', { class: `g-dot ${DOT[st.state]}` }),
            h('span', { class: 'g-plan-main' }, h('span', { class: 'g-due', html: dueLine(T, lang, st, data.today) })))))),
        h('p', { class: 'g-hint center' }, P('pp.until', { date: dateShort(T, lang, localDay(data.expires_at)) })));
    }
    root.replaceChildren(h('div', { class: 'g-app' }, head, h('main', { class: 'g-body' }, body)));
  }

  async function load() {
    try {
      const next = await fetchPassport(token);
      const s2 = JSON.stringify(next);
      if (s2 !== sig || gone) { data = next; sig = s2; gone = false; paint(); }
    } catch (e) {
      if (e?.code === 'link_gone' || e?.code === 'not_found') {
        if (!gone) { gone = true; data = null; paint(); }
      }
    }
  }

  const loop = () => { if (alive) load().finally(() => { timer = setTimeout(loop, poll); }); };
  paint();
  const ready = load().then(() => { if (poll > 0) timer = setTimeout(loop, poll); });
  return { ready, refresh: load, setLang: (l) => { lang = l; paint(); }, destroy: () => { alive = false; clearTimeout(timer); }, get gone() { return gone; } };
}

