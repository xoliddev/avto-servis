"""The owner logs a service by buttons (items → km → labour → parts → where → receipt photo), the history with its
"Servis tasdiqlagan" / "O'zi yozgan" badges, spending stats, the CSV file, and the answer to "Tasdiqlaysizmi?"."""

from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from ..core import stats as statlib
from ..i18n import Raw, date_full, item_name, km, t
from . import views
from .cb import Flow, N, W
from .setup import show

router = Router(name="log")


def csv_text(lang: str, recs: list[dict]) -> str:
    rows = [t(lang, "csv.head").split(",")]
    for r in recs:
        rows.append([date_full(lang, r["day"]), r["km"], "; ".join(item_name(lang, i) for i in r["items"]), r["labour"], r["parts"],
                     r["total"], r["shop"], t(lang, "csv.verified" if r["verified"] else "csv.self"), r["note"]])
    return "﻿" + statlib.csv(rows)  # BOM: spreadsheets then read the Uzbek and Russian letters right


@router.callback_query(F.data.regexp(r"^s:" + N + "$").as_("m"))
async def log_start(cq: CallbackQuery, m: re.Match, state: FSMContext, svc, me, lang, cfg) -> None:
    v = await svc.car_view(me, int(m.group(1)))
    await state.set_state(Flow.log_items)
    await state.update_data(cid=v["car"]["id"], items=[])
    await show(cq, views.log_items(lang, v, []), cfg)


@router.callback_query(Flow.log_items, F.data.regexp(r"^st:" + W + "$").as_("m"))
async def log_toggle(cq: CallbackQuery, m: re.Match, state: FSMContext, svc, me, lang, cfg) -> None:
    d = await state.get_data()
    v = await svc.car_view(me, d.get("cid"))
    if m.group(1) == "ok" and d.get("items"):
        await state.set_state(Flow.log_km)
        odo = v["car"]["odo"]
        rows = [[(km(lang, odo), f"sk:{odo}")], views.back(lang, f"c:{v['car']['id']}")]
        await show(cq, (t(lang, "log.km", km=Raw(km(lang, odo))), rows), cfg)
        return
    ids = {s["id"] for s in v["statuses"] + v["off"]}
    items = list(d.get("items", []))
    if m.group(1) in ids:
        items = [i for i in items if i != m.group(1)] if m.group(1) in items else [*items, m.group(1)]
    await state.update_data(items=items)
    await show(cq, views.log_items(lang, v, items), cfg)


async def _next(event, state: FSMContext, lang, cfg, key: str, value) -> None:
    """Store one answer and ask the next question."""
    await state.update_data(**{key: value})
    cid = (await state.get_data()).get("cid")
    steps = {"km": (Flow.log_labour, "log.labour", "s0"), "labour": (Flow.log_parts, "log.parts", "s0"),
             "parts": (Flow.log_shop, "log.shop", "s:skip"), "shop": (Flow.log_photo, "log.photo", "s:skip")}
    st, text, button = steps[key]
    await state.set_state(st)
    label = t(lang, "btn.zero") if button == "s0" else t(lang, "btn.skip")
    await show(event, (t(lang, text), [[(label, button)], views.back(lang, f"c:{cid}")]), cfg)


def _number(text: str) -> int | None:
    s = text.replace(" ", "").replace("'", "").strip()
    return int(s) if s.isascii() and s.isdigit() and len(s) <= 9 else None


@router.message(Flow.log_km, F.text)
async def log_km(message: Message, state: FSMContext, lang, cfg) -> None:
    n = _number(message.text)
    if n is None:
        await message.answer(t(lang, "err.odo"))
        return
    await _next(message, state, lang, cfg, "km", n)


@router.callback_query(Flow.log_km, F.data.regexp(r"^sk:(\d{1,7})$").as_("m"))
async def log_km_tap(cq: CallbackQuery, m: re.Match, state: FSMContext, lang, cfg) -> None:
    await _next(cq, state, lang, cfg, "km", int(m.group(1)))


@router.message(Flow.log_labour, F.text)
@router.message(Flow.log_parts, F.text)
async def log_money(message: Message, state: FSMContext, lang, cfg) -> None:
    n = _number(message.text)
    if n is None:
        await message.answer(t(lang, "err.money"))
        return
    key = "labour" if await state.get_state() == Flow.log_labour.state else "parts"
    await _next(message, state, lang, cfg, key, n)


@router.callback_query(F.data == "s0")
async def log_zero(cq: CallbackQuery, state: FSMContext, lang, cfg) -> None:
    current = await state.get_state()
    if current not in (Flow.log_labour.state, Flow.log_parts.state):
        await cq.answer(t(lang, "err.stale"), show_alert=True)
        return
    await _next(cq, state, lang, cfg, "labour" if current == Flow.log_labour.state else "parts", 0)


@router.message(Flow.log_shop, F.text)
async def log_shop(message: Message, state: FSMContext, lang, cfg) -> None:
    await _next(message, state, lang, cfg, "shop", message.text[:60])


async def _save(event, state: FSMContext, svc, me, lang, cfg, photo: str | None) -> None:
    d = await state.get_data()
    out = await svc.add_record(me, d.get("cid"), {k: d.get(k) for k in ("items", "km", "labour", "parts", "shop")})
    await state.clear()
    if photo:
        await svc.set_photo(me, out["record_id"], photo)
    text, rows = views.car(lang, out["view"])
    await show(event, (t(lang, "log.saved") + "\n\n" + text, rows), cfg)


@router.callback_query(F.data == "s:skip")
async def log_skip(cq: CallbackQuery, state: FSMContext, svc, me, lang, cfg) -> None:
    current = await state.get_state()
    if current == Flow.log_shop.state:
        await _next(cq, state, lang, cfg, "shop", "")
    elif current == Flow.log_photo.state:
        await _save(cq, state, svc, me, lang, cfg, None)
    else:
        await cq.answer(t(lang, "err.stale"), show_alert=True)


@router.message(Flow.log_photo, F.photo)
async def log_photo(message: Message, state: FSMContext, svc, me, lang, cfg) -> None:
    await _save(message, state, svc, me, lang, cfg, message.photo[-1].file_id)


# ── history, receipts, stats, CSV ──
@router.callback_query(F.data.regexp(r"^h:" + N + "$").as_("m"))
async def history(cq: CallbackQuery, m: re.Match, svc, me, lang, cfg) -> None:
    v = await svc.car_view(me, int(m.group(1)))
    await show(cq, views.history(lang, v["car"]["id"], v["car"]["title"], await svc.history(me, v["car"]["id"])), cfg)


@router.callback_query(F.data.regexp(r"^hp:" + N + "$").as_("m"))
async def receipt(cq: CallbackQuery, m: re.Match, svc, me) -> None:
    file_id = await svc.photo(me, int(m.group(1)))
    await cq.answer()
    if file_id:
        await cq.bot.send_photo(me, file_id)


@router.callback_query(F.data.regexp(r"^hx:" + N + "$").as_("m"))
async def export(cq: CallbackQuery, m: re.Match, svc, me, lang) -> None:
    car, recs = await svc.export_rows(me, int(m.group(1)))
    await cq.answer()
    data = csv_text(lang, recs).encode()
    await cq.bot.send_document(me, BufferedInputFile(data, filename=f"avtoservis-{car['id']}.csv"),
                               caption=t(lang, "csv.caption", title=svc.title(car)))


@router.callback_query(F.data.regexp(r"^e:" + N + "$").as_("m"))
async def spending(cq: CallbackQuery, m: re.Match, svc, me, lang, cfg) -> None:
    cid = int(m.group(1))
    await show(cq, views.stats(lang, cid, await svc.stats(me, cid)), cfg)


@router.callback_query(F.data.regexp(r"^ok:" + N + ":([yan])$").as_("m"))
async def decide(cq: CallbackQuery, m: re.Match, svc, me, lang, cfg, notifier) -> None:
    rec, notes = await svc.decide(me, int(m.group(1)), m.group(2) != "n", m.group(2) == "a")
    await notifier.send(notes)
    v = await svc.car_view(me, rec["car_id"])
    text, rows = views.car(lang, v)
    head = t(lang, "notify.confirmed" if rec["status"] == "ok" else "notify.rejected")
    await show(cq, (head + "\n\n" + text, rows), cfg)
