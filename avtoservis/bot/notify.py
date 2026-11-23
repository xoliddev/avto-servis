"""Messages the bot sends on its own, from the service's notes: reminders ("Motor moyiga ~440 km qoldi"), the owner's
"Tasdiqlaysizmi?", the workshop's answer, invitations. Used by the bot handlers, the Mini App API and the scheduler."""

from __future__ import annotations

import json
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile

from ..i18n import t
from .markup import markup
from .views_more import confirm, decided, invite, remind

log = logging.getLogger(__name__)


class Notifier:
    def __init__(self, bot: Bot, service, cfg) -> None:
        self.bot, self.svc, self.cfg = bot, service, cfg

    async def _send(self, uid: int, text: str, rows=None) -> bool:
        if uid <= 0:  # the seeded, fictional people
            return False
        try:
            await self.bot.send_message(uid, text, reply_markup=markup(rows or [], self.cfg.webapp_url), disable_web_page_preview=True)
            return True
        except TelegramAPIError as err:  # blocked the bot, deleted account...
            log.info("could not notify %s: %s", uid, err)
            return False

    async def document(self, uid: int, name: str, data: bytes, title: str) -> None:
        lang = ((await self.svc.user(uid)) or {}).get("lang", "uz")
        await self.bot.send_document(uid, BufferedInputFile(data, filename=name), caption=t(lang, "csv.caption", title=title))

    async def send(self, notes: list[dict]) -> None:
        for n in notes:
            try:
                lang = ((await self.svc.user(n["to"])) or {}).get("lang", "uz")
                await getattr(self, f"on_{n['type']}")(n, lang)
            except Exception:  # one failed message never stops the rest
                log.exception("note %s failed", n.get("type"))

    async def on_remind(self, n: dict, lang: str) -> None:
        v = await self.svc.car_view(n["to"], n["car_id"])
        await self._send(n["to"], *remind(lang, v, n["items"], n["ask"]))

    async def on_confirm(self, n: dict, lang: str) -> None:
        r = await self.svc.record(n["to"], n["record_id"])
        car = await self.svc.db.one("SELECT * FROM cars WHERE id = ?", (n["car_id"],))
        await self._send(n["to"], *confirm(lang, r, self.svc.title(car)))

    async def on_decided(self, n: dict, lang: str) -> None:
        r = await self.svc.db.one("SELECT items FROM records WHERE id = ?", (n["record_id"],))
        car = await self.svc.db.one("SELECT * FROM cars WHERE id = ?", (n["car_id"],))
        await self._send(n["to"], decided(lang, n["yes"], self.svc.title(car), json.loads(r["items"])),
                         [[(t(lang, "btn.workshop"), "w:home")]])

    async def on_invite(self, n: dict, lang: str) -> None:
        v = await self.svc.car_view(n["to"], n["car_id"])
        shop = await self.svc.db.one("SELECT id, name, address FROM workshops WHERE id = ?", (n["workshop_id"],))
        if any(s["id"] == n["item"] for s in v["statuses"]):
            await self._send(n["to"], *invite(lang, shop, v, n["item"]))
