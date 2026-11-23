"""/start with its deep links (``c_<car code>`` for a workshop, ``p_<passport link>`` for a buyer, ``w_<one-time link>``
for a new workshop), the main menu, the language switch and the stale-button fallback. ``/start`` is the only
command: everything else is buttons, and every screen has "⬅️ Orqaga"."""

from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from ..common import LINK, Refused
from ..i18n import plain, t
from . import views, views_more
from .cb import Flow
from .setup import show

router = Router(name="main")
fallback = Router(name="fallback")
CODE = re.compile(r"^c_([A-Z0-9]{8})$")
PASS = re.compile(r"^p_([A-Za-z0-9_-]{32})$")


async def menu(event, svc, me: int, cfg, hello: bool = False) -> None:
    user = await svc.user(me)
    await show(event, views.menu(user["lang"], await svc.my_cars(me), await svc.roles(me), hello), cfg)


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, svc, me, lang, cfg, command: CommandObject | None = None) -> None:
    await state.clear()
    arg = (command.args or "") if command else ""
    if arg.startswith("w_") and LINK.match(arg[2:]):
        await svc.check_link(arg[2:])
        await state.set_state(Flow.join_name)
        await state.update_data(link=arg[2:])
        await message.answer(t(lang, "join.hi"), reply_markup=ReplyKeyboardRemove())
        return
    if m := CODE.match(arg):
        if not (await svc.roles(me))["workshop"]:
            await message.answer(t(lang, "ws.only_ws"))
            return
        await show(message, views_more.ws_car(lang, await svc.open_car(me, m.group(1))), cfg)
        return
    if m := PASS.match(arg):
        try:
            p = await svc.passport(m.group(1))
        except Refused:
            await message.answer(t(lang, "err.link_gone"), reply_markup=ReplyKeyboardRemove())
            return
        await show(message, views_more.passport_card(lang, p, m.group(1)), cfg)
        return
    await message.answer("👋", reply_markup=ReplyKeyboardRemove())
    await menu(message, svc, me, cfg, hello=True)


@router.callback_query(F.data == "n:menu")
async def nav_menu(cq: CallbackQuery, state: FSMContext, svc, me, cfg) -> None:
    await state.clear()
    await menu(cq, svc, me, cfg)


@router.callback_query(F.data == "n:lang")
async def nav_lang(cq: CallbackQuery, svc, me, lang, cfg) -> None:
    await svc.set_lang(me, "ru" if lang == "uz" else "uz")
    await menu(cq, svc, me, cfg)


@fallback.callback_query()
async def stale(cq: CallbackQuery, lang) -> None:
    await cq.answer(plain(t(lang, "err.stale")), show_alert=True)


@fallback.message()
async def anything(message: Message, state: FSMContext, svc, me, cfg) -> None:
    await state.clear()
    await menu(message, svc, me, cfg)
