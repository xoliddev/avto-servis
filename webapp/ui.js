// The Mini App shell: role tabs (Garaj for every driver, Servis for a workshop), a back stack with "⬅️ Orqaga" on
// every inner screen (and Telegram's BackButton), the language switch and polling. Each role's screens live in their
// own module. The same code runs inside Telegram and in the browser demo's phones.
import { makeT } from '../shared/i18n.js';
import { garageScreens } from './ui-garage.js';
import { workshopScreens } from './ui-ws.js';
import { errText, h, makeText, toast } from './util.js';

const ROLES = { owner: garageScreens, ws: workshopScreens };

export function mountApp(root, { api, catalogs, models, plan, lang: lang0, tg = null, view = null, start = null, poll = 2500, onLang,
  now = () => Date.now(), share = null }) {
  const t = makeT(catalogs);
  const text = makeText(catalogs);
  const head = h('header', { class: 'g-head' });
  const body = h('main', { class: 'g-body', oninput: (e) => { if (e.target.matches('input:not([type=checkbox]):not([type=radio]), textarea')) body.dataset.dirty = '1'; } });
  const app = h('div', { class: 'g-app' }, head, body);
  root.replaceChildren(app);
  const ctx = {
    api, models, plan, tg, root: app, now, share, lang: lang0 === 'ru' ? 'ru' : 'uz',
    t: (key, params) => t(ctx.lang, key, params),
    P: (key, params) => text(ctx.lang, key, params),
    T: t,
    toast: (msg, kind) => toast(app, msg, kind),
    fail: (e) => toast(app, errText(t, ctx.lang, e), 'bad'),
    me: null,
  };
  let role = view ?? 'owner';
  let screens = null;
  const stack = [];
  let timer = 0;
  let alive = true;

  async function run(fn) {
    try {
      return await fn();
    } catch (e) {
      ctx.fail(e);
      return null;
    }
  }

  function paintHead() {
    const roles = view ? [view] : ['owner', ...(ctx.me?.roles.workshop ? ['ws'] : [])];
    const back = stack.length > 1 ? h('button', { class: 'g-back', type: 'button', 'data-testid': 'back', onclick: () => pop() }, ctx.P('app.back')) : null;
    const tabs = roles.length > 1 && !back ? h('nav', { class: 'g-tabs' }, roles.map((r) => h('button', {
      class: r === role ? 'on' : '', type: 'button', 'data-testid': `tab-${r}`, onclick: () => switchRole(r) }, ctx.P(`app.tab_${r}`)))) : null;
    const title = !back && !tabs ? h('b', { class: 'g-title', text: role === 'ws' ? (ctx.me?.roles.workshop_name || ctx.P('app.tab_ws')) : ctx.P('app.tab_owner') }) : null;
    head.replaceChildren(back ?? tabs ?? title, h('span', { class: 'g-grow' }),
      h('button', { class: 'g-lang', type: 'button', 'data-testid': 'app-lang', onclick: () => setLang(ctx.lang === 'uz' ? 'ru' : 'uz') }, ctx.P('app.lang')));
    if (tg?.BackButton) {
      if (stack.length > 1) tg.BackButton.show();
      else tg.BackButton.hide();
    }
  }

  /** Show a screen: {name, load?(), render(): Node, poll?(): Promise<bool>, mounted?(), leave?()} */
  async function show(screen, replace = false) {
    stack.at(-1)?.leave?.();
    if (replace && stack.length) stack.pop();
    stack.push(screen);
    await paint();
  }

  async function pop() {
    if (stack.length < 2) return;
    stack.pop().leave?.();
    await paint();
  }

  async function home() {
    while (stack.length) stack.pop().leave?.();
    stack.push(screens.home());
    await paint();
  }

  async function paint() {
    paintHead();
    const top = stack.at(-1);
    if (!top) return;
    await run(() => top.load?.());
    if (top !== stack.at(-1)) return;
    body.replaceChildren(top.render());
    body.dataset.screen = top.name;
    body.dataset.dirty = '';
    top.mounted?.();
    root.scrollTop = 0;
    if (tg) window.scrollTo(0, 0);
  }

  /** Re-fetch the visible screen (polling and the demo's live events); re-render only when something changed. */
  async function refresh() {
    const top = stack.at(-1);
    if (!top?.poll) return;
    const changed = await run(() => top.poll());
    if (changed && top === stack.at(-1)) {
      const y = root.scrollTop;
      if (body.dataset.dirty === '1') return; // never wipe what a person has typed
      body.replaceChildren(top.render());
      top.mounted?.(true);
      root.scrollTop = y;
    }
  }

  async function switchRole(r) {
    role = r;
    screens = ROLES[r](ctx, { show, pop, home, refresh, run });
    await home();
  }

  async function setLang(next) {
    if (next === ctx.lang) return;
    ctx.lang = next;
    await run(() => api.setLang(next));
    onLang?.(next);
    await paint();
  }

  const loop = () => {
    if (!alive) return;
    refresh().finally(() => { timer = setTimeout(loop, poll); });
  };

  const ready = (async () => {
    ctx.me = await run(() => api.me());
    if (ctx.me?.lang && !lang0) ctx.lang = ctx.me.lang;
    if (!view && start === 'ws' && ctx.me?.roles.workshop) role = 'ws';
    await switchRole(role);
    if (tg?.BackButton) tg.BackButton.onClick(() => pop());
    if (poll > 0) timer = setTimeout(loop, poll);
  })();

  return {
    ready, refresh, ctx,
    open: async (fn) => { await ready; await fn({ show, home, screens, ctx }); },
    setLang: async (l) => { ctx.lang = l; await paint(); },
    get screen() { return stack.at(-1)?.name; },
    get top() { return stack.at(-1); },
    get screens() { return screens; },
    show, home,
    destroy: () => { alive = false; clearTimeout(timer); while (stack.length) stack.pop().leave?.(); },
  };
}
