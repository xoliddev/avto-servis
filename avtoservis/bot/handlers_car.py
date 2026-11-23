"""Adding a car by buttons (model → year → fuel → use → odometer → plate → last oil change), the car screen, sending
the odometer (typed, or one tap on today's estimate, with the anomaly guard), the plan and one item's screen."""

from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..core import cars as carlib
from ..core.clock import civil
from ..i18n import Raw, km, t
from . import views
from .cb import Flow, N, W
from .setup import show

router = Router(name="car")


async def car_screen(event, svc, me, lang, cfg, cid: int) -> None:
    await show(event, views.car(lang, await svc.car_view(me, cid)), cfg)


# ── adding a car ──
@router.callback_query(F.data == "a:new")
async def add_start(cq: CallbackQuery, state: FSMContext, svc, lang, cfg) -> None:
    await state.clear()
    await show(cq, views.add_models(lang, svc.models), cfg)


@router.callback_query(F.data.regexp(r"^a:m:" + W + "$").as_("m"))
async def add_model(cq: CallbackQuery, m: re.Match, state: FSMContext, svc, lang, cfg) -> None:
    model = next((x for x in svc.models if x["id"] == m.group(1)), None)
    if model is None:
        await cq.answer()
        return
    await state.update_data(car={"model": model["id"]})
    if model["id"] == "other":
        await state.set_state(Flow.add_name)
        await show(cq, (t(lang, "add.name"), [views.back(lang, "a:new")]), cfg)
        return
    await show(cq, views.add_years(lang, model, civil(svc.today())[0]), cfg)


@router.message(Flow.add_name, F.text)
async def add_name(message: Message, state: FSMContext, svc, lang, cfg) -> None:
    car = (await state.get_data()).get("car", {})
    await state.update_data(car={**car, "name": message.text[:40]})
    await state.set_state(Flow.add_year)
    await message.answer(t(lang, "add.year_typed"))


async def _after_year(event, state: FSMContext, svc, lang, cfg, year: int) -> None:
    car = (await state.get_data()).get("car", {})
    await state.update_data(car={**car, "year": year})
    await state.set_state(None)
    await show(event, views.add_fuels(lang, carlib.model(svc.models, car.get("model", "other"))), cfg)


@router.callback_query(F.data.regexp(r"^a:y:(\d{4}|x)$").as_("m"))
async def add_year(cq: CallbackQuery, m: re.Match, state: FSMContext, svc, lang, cfg) -> None:
    if m.group(1) == "x":
        await state.set_state(Flow.add_year)
        await show(cq, (t(lang, "add.year_typed"), [views.back(lang, "a:new")]), cfg)
        return
    await _after_year(cq, state, svc, lang, cfg, int(m.group(1)))


@router.message(Flow.add_year, F.text)
async def add_year_typed(message: Message, state: FSMContext, svc, lang, cfg) -> None:
    text = message.text.strip()
    if not (text.isascii() and text.isdigit() and len(text) == 4):
        await message.answer(t(lang, "err.year"))
        return
    await _after_year(message, state, svc, lang, cfg, int(text))


@router.callback_query(F.data.regexp(r"^a:f:(benzin|metan|propan|gibrid|elektr)$").as_("m"))
async def add_fuel(cq: CallbackQuery, m: re.Match, state: FSMContext, lang, cfg) -> None:
    car = (await state.get_data()).get("car", {})
    await state.update_data(car={**car, "fuel": m.group(1)})
    await show(cq, views.add_usage(lang), cfg)


@router.callback_query(F.data.regexp(r"^a:u:(shaxsiy|taksi)$").as_("m"))
async def add_usage(cq: CallbackQuery, m: re.Match, state: FSMContext, lang, cfg) -> None:
    car = (await state.get_data()).get("car", {})
    await state.update_data(car={**car, "usage": m.group(1)})
    await state.set_state(Flow.add_odo)
    await show(cq, (t(lang, "add.odo"), [views.back(lang, "a:new")]), cfg)


@router.message(Flow.add_odo, F.text)
async def add_odo(message: Message, state: FSMContext, lang, cfg) -> None:
    text = message.text.replace(" ", "").strip()
    if not (text.isascii() and text.isdigit() and len(text) <= 7):
        await message.answer(t(lang, "err.odo"))
        return
    car = (await state.get_data()).get("car", {})
    await state.update_data(car={**car, "odo": int(text)})
    await state.set_state(Flow.add_plate)
    await show(message, (t(lang, "add.plate"), views.skip(lang)), cfg)


@router.message(Flow.add_plate, F.text)
async def add_plate(message: Message, state: FSMContext, lang, cfg) -> None:
    try:
        plate = carlib.plate(message.text)
    except ValueError:
        await message.answer(t(lang, "err.plate"))
        return
    car = (await state.get_data()).get("car", {})
    await state.update_data(car={**car, "plate": plate})
    await state.set_state(Flow.add_oil)
    await show(message, (t(lang, "add.last_oil"), views.skip(lang)), cfg)


@router.callback_query(F.data == "a:skip")
async def add_skip(cq: CallbackQuery, state: FSMContext, svc, me, lang, cfg) -> None:
    current = await state.get_state()
    if current == Flow.add_plate.state:
        await state.set_state(Flow.add_oil)
        await show(cq, (t(lang, "add.last_oil"), views.skip(lang)), cfg)
    elif current == Flow.add_oil.state:
        await _create(cq, state, svc, me, lang, cfg, None)
    else:
        await cq.answer(t(lang, "err.stale"), show_alert=True)


@router.message(Flow.add_oil, F.text)
async def add_oil(message: Message, state: FSMContext, svc, me, lang, cfg) -> None:
    await _create(message, state, svc, me, lang, cfg, message.text.replace(" ", "").strip())


async def _create(event, state: FSMContext, svc, me, lang, cfg, last_oil) -> None:
    car = (await state.get_data()).get("car", {})
    v = await svc.add_car(me, {**car, "last_oil": last_oil})
    await state.clear()
    text, rows = views.car(lang, v)
    await show(event, (t(lang, "add.done") + "\n\n" + text, rows), cfg)


# ── the car, the odometer, the plan ──
@router.callback_query(F.data.regexp(r"^c:" + N + "$").as_("m"))
async def car(cq: CallbackQuery, m: re.Match, state: FSMContext, svc, me, lang, cfg) -> None:
    await state.clear()
    await car_screen(cq, svc, me, lang, cfg, int(m.group(1)))


@router.callback_query(F.data.regexp(r"^c:" + N + ":km$").as_("m"))
async def km_ask(cq: CallbackQuery, m: re.Match, state: FSMContext, svc, me, lang, cfg) -> None:
    v = await svc.car_view(me, int(m.group(1)))
    await state.set_state(Flow.km)
    await state.update_data(cid=v["car"]["id"])
    await show(cq, views.km_ask(lang, v), cfg)


async def _reading(event, svc, me, lang, cfg, cid: int, value, confirm: bool = False) -> None:
    out = await svc.add_reading(me, cid, value, confirm)
    if out["confirm"]:
        await show(event, views.jump(lang, cid, out), cfg)
        return
    text, rows = views.car(lang, out["view"])
    await show(event, (t(lang, "km.saved", km=Raw(km(lang, out["km"]))) + "\n\n" + text, rows), cfg)


@router.message(Flow.km, F.text)
async def km_typed(message: Message, state: FSMContext, svc, me, lang, cfg) -> None:
    cid = (await state.get_data()).get("cid")
    await _reading(message, svc, me, lang, cfg, cid, message.text.replace(" ", "").strip())
    await state.clear()


@router.callback_query(F.data.regexp(r"^(r|rj):" + N + ":" + r"(\d{1,7})$").as_("m"))
async def km_tap(cq: CallbackQuery, m: re.Match, state: FSMContext, svc, me, lang, cfg) -> None:
    await state.clear()
    await _reading(cq, svc, me, lang, cfg, int(m.group(2)), int(m.group(3)), m.group(1) == "rj")


@router.callback_query(F.data.regexp(r"^p:" + N + "$").as_("m"))
async def plan(cq: CallbackQuery, m: re.Match, svc, me, lang, cfg) -> None:
    await show(cq, views.plan(lang, await svc.car_view(me, int(m.group(1)))), cfg)


@router.callback_query(F.data.regexp(r"^i:" + N + ":" + W + "$").as_("m"))
async def item(cq: CallbackQuery, m: re.Match, svc, me, lang, cfg) -> None:
    v = await svc.car_view(me, int(m.group(1)))
    if not any(s["id"] == m.group(2) for s in v["statuses"] + v["off"]):
        await cq.answer()
        return
    await show(cq, views.item(lang, v, m.group(2)), cfg)


@router.callback_query(F.data.regexp(r"^(id|io):" + N + ":" + W + "$").as_("m"))
async def item_change(cq: CallbackQuery, m: re.Match, svc, me, lang, cfg) -> None:
    cid, it = int(m.group(2)), m.group(3)
    if m.group(1) == "id":
        v = await svc.set_item(me, cid, it, {"done": True})
    else:
        before = await svc.car_view(me, cid)
        v = await svc.set_item(me, cid, it, {"off": not any(s["id"] == it for s in before["off"])})
    await show(cq, views.item(lang, v, it), cfg)


@router.callback_query(F.data.regexp(r"^ie:" + N + ":" + W + "$").as_("m"))
async def item_expires(cq: CallbackQuery, m: re.Match, state: FSMContext, lang, cfg) -> None:
    await state.set_state(Flow.expires)
    await state.update_data(cid=int(m.group(1)), item=m.group(2))
    text = t(lang, "item.expires_ask", name=t(lang, f"item.{m.group(2)}"))
    await show(cq, (text, [views.back(lang, f"i:{m.group(1)}:{m.group(2)}")]), cfg)


@router.message(Flow.expires, F.text)
async def item_expires_typed(message: Message, state: FSMContext, svc, me, lang, cfg) -> None:
    d = await state.get_data()
    v = await svc.set_item(me, d.get("cid"), d.get("item"), {"expires": message.text.strip()[:12]})
    await state.clear()
    text, rows = views.item(lang, v, d["item"])
    await show(message, (t(lang, "item.saved") + "\n\n" + text, rows), cfg)
