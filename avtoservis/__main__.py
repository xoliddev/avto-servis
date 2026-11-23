"""Run everything in one process: ``python -m avtoservis``.

* the Telegram bot (long polling),
* the aiohttp server: the Mini App "Garaj" (/webapp/), its API and the public Servis pasporti call,
* the scheduler: reminders, each sent exactly once.
State lives in SQLite, so a restart loses nothing.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.types import MenuButtonWebApp, WebAppInfo
from aiohttp import web

from . import scheduler
from .base import load
from .bot.notify import Notifier
from .bot.setup import BotConfig, build_dispatcher
from .config import Settings
from .core import seedgen, token
from .db import Database
from .service import Service
from .web import make_app

log = logging.getLogger("avtoservis")


async def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = Settings.from_env()
    db = await Database.open(cfg.db_path)
    service = Service(db, admins=cfg.admin_ids, share_secret=token.secret_from(cfg.share_secret or cfg.bot_token))
    if cfg.seed_demo and await service.seed(seedgen.world(load("people"), load("models"), load("plan"), service.now())):
        log.info("seeded the fictional world (7 cars, 3 workshops)")
    bot = Bot(cfg.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    me = await bot.get_me()
    bcfg = BotConfig(me.username or "", cfg.webapp_url)
    dp = build_dispatcher(service, bot, bcfg, cfg.rate_per_minute)
    notifier = Notifier(bot, service, bcfg)
    if cfg.webapp_url:
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Garaj", web_app=WebAppInfo(url=cfg.webapp_url)))
    app = make_app(service, cfg.bot_token, notifier, cfg.initdata_max_age, cfg.api_rate_per_minute, cfg.passport_rate_per_minute,
                   cfg.trust_proxy)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, cfg.host, cfg.port).start()
    ticker = asyncio.create_task(scheduler.run(service, notifier))
    log.info("Mini App on http://%s:%s/webapp/  bot: @%s", cfg.host, cfg.port, me.username)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        ticker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await ticker
        await runner.cleanup()
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
