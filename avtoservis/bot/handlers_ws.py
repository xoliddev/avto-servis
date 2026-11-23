"""The workshop panel (open a car by its code, record a service for the owner to confirm, clients due soon with one
invitation per item), joining as a workshop with a one-time link, and the admin screen."""

from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..i18n import Raw, km, t
from . import views, views_more
from .cb import Flow, N, W
from .handlers_log import _number
from .setup import show

router = Router(name="workshop")


@router.callback_query(F.data == "w:home")
async def home(cq: CallbackQuery, state: FSMContext, svc, me, lang, cfg) -> None:
    await state.clear()
    await show(cq, views_more.ws_home(lang, await svc.ws_home(me)), cfg)


@router.callback_query(F.data == "w:cars")
async def clients(cq: CallbackQuery, svc, me, lang, cfg) -> None:
    await show(cq, views_more.ws_cars(lang, await svc.ws_home(me)), cfg)


@router.callback_query(F.data == "w:code")
async def code_ask(cq: CallbackQuery, state: FSMContext, svc, me, lang, cfg) -> None:
    await svc.ws_home(me)  # only workshops get this far
    await state.set_state(Flow.ws_code)
    await show(cq, (t(lang, "ws.code_ask"), [views.back(lang, "w:home")]), cfg)


@router.message(Flow.ws_code, F.text)
async def code_typed(message: Message, state: FSMContext, svc, me, lang, cfg) -> None:
    v = await svc.open_car(me, message.text.strip()[:20])
    await state.clear()
    await show(message, views_more.ws_car(lang, v), cfg)


@router.callback_query(F.data.regexp(r"^wc:" + N + "$").as_("m"))
async def car(cq: CallbackQuery, m: re.Match, state: FSMContext, svc, me, lang, cfg) -> None:
    await state.clear()
    await show(cq, views_more.ws_car(lang, await svc.ws_car(me, int(m.group(1)))), cfg)


@router.callback_query(F.data.regexp(r"^wi:" + N + ":" + W + "$").as_("m"))
async def invite(cq: CallbackQuery, m: re.Match, svc, me, lang, cfg, notifier) -> None:
    h, notes = await svc.ws_invite(me, int(m.group(1)), m.group(2))
    await notifier.send(notes)
    text, rows = views_more.ws_home(lang, h)
    await show(cq, (t(lang, "ws.invited") + "\n\n" + text, rows), cfg)


# ── recording a service for the owner to confirm: items → km → labour → parts ──
def _as_view(v: dict) -> dict:
    """The workshop's car card in the shape views.log_items expects."""
    return {"car": v["car"], "statuses": v["statuses"], "off": []}


@router.callback_query(F.data.regexp(r"^wr:" + N + "$").as_("m"))
async def record_start(cq: CallbackQuery, m: re.Match, state: FSMContext, svc, me, lang, cfg) -> None:
    v = await svc.ws_car(me, int(m.group(1)))
    await state.set_state(Flow.ws_items)
    await state.update_data(cid=v["car"]["id"], items=[])
    await show(cq, views.log_items(lang, _as_view(v), [], "wt"), cfg)


@router.callback_query(Flow.ws_items, F.data.regexp(r"^wt:" + W + "$").as_("m"))
async def record_toggle(cq: CallbackQuery, m: re.Match, state: FSMContext, svc, me, lang, cfg) -> None:
    d = await state.get_data()
    v = await svc.ws_car(me, d.get("cid"))
    if m.group(1) == "ok" and d.get("items"):
        await state.set_state(Flow.ws_km)
        odo = v["car"]["odo"]
        rows = [[(km(lang, odo), f"wk:{odo}")], views.back(lang, f"wc:{d['cid']}")]
        await show(cq, (t(lang, "log.km", km=Raw(km(lang, odo))), rows), cfg)
        return
    items = list(d.get("items", []))
    if m.group(1) in v["items"]:
        items = [i for i in items if i != m.group(1)] if m.group(1) in items else [*items, m.group(1)]
    await state.update_data(items=items)
    await show(cq, views.log_items(lang, _as_view(v), items, "wt"), cfg)


async def _ask(event, state, lang, cfg, key: str, value: int) -> None:
    await state.update_data(**{key: value})
    d = await state.get_data()
    nxt = {"km": (Flow.ws_labour, "log.labour"), "labour": (Flow.ws_parts, "log.parts")}
    st, text = nxt[key]
    await state.set_state(st)
    await show(event, (t(lang, text), [[(t(lang, "btn.zero"), "w0")], views.back(lang, f"wc:{d['cid']}")]), cfg)


async def _send(event, state: FSMContext, svc, me, lang, cfg, notifier) -> None:
    d = await state.get_data()
    v, notes = await svc.ws_record(me, d.get("cid"), {k: d.get(k) for k in ("items", "km", "labour", "parts")})
    await state.clear()
    await notifier.send(notes)
    text, rows = views_more.ws_car(lang, v)
    await show(event, (t(lang, "ws.sent") + "\n\n" + text, rows), cfg)


@router.message(Flow.ws_km, F.text)
@router.message(Flow.ws_labour, F.text)
@router.message(Flow.ws_parts, F.text)
async def record_typed(message: Message, state: FSMContext, svc, me, lang, cfg, notifier) -> None:
    n = _number(message.text)
    current = await state.get_state()
    if n is None:
        await message.answer(t(lang, "err.odo" if current == Flow.ws_km.state else "err.money"))
    elif current == Flow.ws_km.state:
        await _ask(message, state, lang, cfg, "km", n)
    elif current == Flow.ws_labour.state:
        await _ask(message, state, lang, cfg, "labour", n)
    else:
        await state.update_data(parts=n)
        await _send(message, state, svc, me, lang, cfg, notifier)


@router.callback_query(Flow.ws_km, F.data.regexp(r"^wk:(\d{1,7})$").as_("m"))
async def record_km_tap(cq: CallbackQuery, m: re.Match, state: FSMContext, lang, cfg) -> None:
    await _ask(cq, state, lang, cfg, "km", int(m.group(1)))


@router.callback_query(F.data == "w0")
async def record_zero(cq: CallbackQuery, state: FSMContext, svc, me, lang, cfg, notifier) -> None:
    current = await state.get_state()
    if current == Flow.ws_labour.state:
        await _ask(cq, state, lang, cfg, "labour", 0)
    elif current == Flow.ws_parts.state:
        await state.update_data(parts=0)
        await _send(cq, state, svc, me, lang, cfg, notifier)
    else:
        await cq.answer(t(lang, "err.stale"), show_alert=True)


# ── joining, admin ──
@router.message(Flow.join_name, F.text)
async def join_name(message: Message, state: FSMContext, lang) -> None:
    await state.update_data(name=message.text[:60])
    await state.set_state(Flow.join_address)
    await message.answer(t(lang, "join.address"))


@router.message(Flow.join_address, F.text)
async def join_address(message: Message, state: FSMContext, svc, me, lang, cfg) -> None:
    d = await state.get_data()
    h = await svc.join(me, d.get("link"), d.get("name"), message.text[:120])
    await state.clear()
    text, rows = views_more.ws_home(lang, h)
    await show(message, (t(lang, "join.done") + "\n\n" + text, rows), cfg)


@router.callback_query(F.data == "x:home")
async def admin(cq: CallbackQuery, svc, me, lang, cfg) -> None:
    await show(cq, views_more.admin(lang, await svc.admin_home(me)), cfg)


@router.callback_query(F.data == "x:link")
async def admin_link(cq: CallbackQuery, svc, me, lang, cfg) -> None:
    link = cfg.workshop_link(await svc.make_link(me))
    text, rows = views_more.admin(lang, await svc.admin_home(me))
    await show(cq, (t(lang, "admin.link", link=link) + "\n\n" + text, rows), cfg)
