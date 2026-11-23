"""The car code for workshops (and which workshops may send invitations), and the Servis pasporti links."""

from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.types import CallbackQuery

from ..i18n import t
from . import views, views_more
from .cb import N
from .setup import show

router = Router(name="share")


@router.callback_query(F.data.regexp(r"^(k|kr):" + N + "$").as_("m"))
async def code(cq: CallbackQuery, m: re.Match, svc, me, lang, cfg) -> None:
    cid = int(m.group(2))
    v = await svc.rotate_code(me, cid) if m.group(1) == "kr" else await svc.car_view(me, cid)
    await show(cq, views.code(lang, v, cfg.bot_username), cfg)


@router.callback_query(F.data.regexp(r"^ka:" + N + ":" + N + ":([01])$").as_("m"))
async def allow(cq: CallbackQuery, m: re.Match, svc, me, lang, cfg) -> None:
    v = await svc.set_shop(me, int(m.group(1)), int(m.group(2)), allow=m.group(3) == "1")
    await show(cq, views.code(lang, v, cfg.bot_username), cfg)


@router.callback_query(F.data.regexp(r"^kd:" + N + ":" + N + "$").as_("m"))
async def remove(cq: CallbackQuery, m: re.Match, svc, me, lang, cfg) -> None:
    v = await svc.set_shop(me, int(m.group(1)), int(m.group(2)), remove=True)
    await show(cq, views.code(lang, v, cfg.bot_username), cfg)


@router.callback_query(F.data.regexp(r"^g:" + N + "$").as_("m"))
async def passport(cq: CallbackQuery, m: re.Match, svc, me, lang, cfg) -> None:
    cid = int(m.group(1))
    v = await svc.car_view(me, cid)
    await show(cq, views_more.passport(lang, v, await svc.shares(me, cid)), cfg)


@router.callback_query(F.data.regexp(r"^gn:" + N + r":(7|30|90):([01])$").as_("m"))
async def new_link(cq: CallbackQuery, m: re.Match, svc, me, lang, cfg) -> None:
    cid = int(m.group(1))
    made = await svc.share(me, cid, int(m.group(2)), m.group(3) == "1")
    text, rows = views_more.passport(lang, await svc.car_view(me, cid), made["items"])
    await show(cq, (views_more.passport_made(lang, cfg, made) + "\n\n" + text, rows), cfg)


@router.callback_query(F.data.regexp(r"^gr:" + N + ":" + N + "$").as_("m"))
async def revoke(cq: CallbackQuery, m: re.Match, svc, me, lang, cfg) -> None:
    cid = int(m.group(1))
    shares = await svc.revoke(me, cid, int(m.group(2)))
    text, rows = views_more.passport(lang, await svc.car_view(me, cid), shares)
    await show(cq, (t(lang, "pass.revoked") + "\n\n" + text, rows), cfg)
