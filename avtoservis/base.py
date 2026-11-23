"""The service's foundation: the clock, the shared data, people and roles, the seed, and the one place that turns a
car's rows into its plan (``snapshot``). Garage, history, workshop, passport and reminder rules live in their own
modules and are mixed into ``Service`` (service.py)."""

from __future__ import annotations

import json
import secrets
import time
from collections.abc import Callable
from pathlib import Path

from .common import Refused
from .core import cars as carlib
from .core import forecast, plan
from .core.clock import local_day, local_minute
from .core.text import InputError, clean
from .db import Database

DATA = Path(__file__).resolve().parent.parent / "shared" / "data"


def load(name: str):
    with open(DATA / f"{name}.json", encoding="utf-8") as fh:
        return json.load(fh)


def checked(fn, *args):
    """Run a core validator; its InputError becomes a Refused with the same code."""
    try:
        return fn(*args)
    except InputError as err:
        raise Refused(err.code) from err


def merge_last(row: dict | None, recs: list[dict], item: dict) -> dict:
    """The last time an item was done: the owner's entry (or the new-car guess), unless a confirmed record is newer."""
    last = {"km": row["last_km"], "day": row["last_day"], "guess": bool(row["guess"])} if row else {"km": None, "day": None,
                                                                                                    "guess": True}
    for r in recs:
        if item["id"] not in r["items"]:
            continue
        newer = r["km"] >= last["km"] if item["km"] and last["km"] is not None else last["day"] is None or r["day"] >= last["day"]
        if last["guess"] or newer:
            last = {"km": r["km"], "day": r["day"], "guess": False}
    return last


def compute(car: dict, rows: list[dict], readings: list[dict], recs: list[dict], models: list, cfg: dict, today: int) -> dict:
    """Pure: a car's plan today. ``recs`` are its confirmed records, oldest first. shared/garage.js is the same."""
    by_item = {r["item"]: r for r in rows}
    overrides = {r["item"]: {"km": r["km"], "months": r["months"], "off": r["off"]} for r in rows}
    items = plan.items_for(cfg, carlib.model(models, car["model"]), car["fuel"], car["usage"], overrides)
    pts = forecast.points([[r["day"], r["km"]] for r in readings] + [[r["day"], r["km"]] for r in recs])
    fc = forecast.estimate(pts, cfg["daily_km"][car["usage"]])
    statuses, off = [], []
    for it in items:
        st = plan.status(it, merge_last(by_item.get(it["id"]), recs, it), fc, today, cfg)
        (off if it["off"] else statuses).append(st)
    statuses.sort(key=plan.sort_key)
    return {"items": items, "statuses": statuses, "off": off, "fc": fc, "points": pts, "odo": forecast.odo_on(fc, today)}


class Base:
    def __init__(self, db: Database, clock: Callable[[], int] | None = None, admins: frozenset[int] = frozenset(),
                 share_secret: bytes = b"") -> None:
        self.db = db
        self.clock = clock or (lambda: int(time.time() * 1000))
        self.admins = set(admins)
        self.secret = share_secret or secrets.token_bytes(32)
        self.models, self.cfg, self.people = load("models"), load("plan"), load("people")

    def now(self) -> int:
        return self.clock()

    def today(self) -> int:
        return local_day(self.now())

    def minute(self) -> int:
        return local_minute(self.now())

    # ── people ──
    async def touch_user(self, uid: int, name: str, lang_code: str | None) -> dict:
        row = await self.db.one("SELECT * FROM users WHERE id = ?", (uid,))
        if row:
            return row
        lang = "ru" if (lang_code or "")[:2].lower() == "ru" else "uz"
        async with self.db.tx() as c:
            await c.execute("INSERT OR IGNORE INTO users (id, name, lang, created_at) VALUES (?, ?, ?, ?)",
                            (uid, clean(name, 64) or "Haydovchi", lang, self.now()))
        return await self.db.one("SELECT * FROM users WHERE id = ?", (uid,))

    async def user(self, uid: int) -> dict | None:
        return await self.db.one("SELECT * FROM users WHERE id = ?", (uid,))

    async def set_lang(self, uid: int, lang: object) -> str:
        if lang not in ("uz", "ru"):
            raise Refused("generic")
        async with self.db.tx() as c:
            await c.execute("UPDATE users SET lang = ? WHERE id = ?", (lang, uid))
        return lang

    async def workshop_of(self, uid: int) -> dict | None:
        return await self.db.one("SELECT * FROM workshops WHERE owner = ? AND blocked = 0", (uid,))

    async def roles(self, uid: int) -> dict:
        ws = await self.workshop_of(uid)
        return {"workshop": ws["id"] if ws else None, "workshop_name": ws["name"] if ws else "", "admin": uid in self.admins}

    def admin_only(self, uid: int) -> None:
        if uid not in self.admins:
            raise Refused("not_found")

    # ── shared helpers ──
    @staticmethod
    async def q1(c, sql: str, args: tuple = ()) -> dict | None:
        async with c.execute(sql, args) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    @staticmethod
    async def qa(c, sql: str, args: tuple = ()) -> list[dict]:
        async with c.execute(sql, args) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def own_car(self, c, uid: int, cid: object) -> dict:
        """The caller's own car, or "not_found" (the same answer for someone else's car and a car that does not exist)."""
        if not isinstance(cid, int) or isinstance(cid, bool):
            raise Refused("not_found")
        car = await self.q1(c, "SELECT * FROM cars WHERE id = ? AND owner = ?", (cid, uid))
        if not car:
            raise Refused("not_found")
        return car

    async def snapshot(self, c, car: dict) -> dict:
        rows = await self.qa(c, "SELECT * FROM car_items WHERE car_id = ?", (car["id"],))
        readings = await self.qa(c, "SELECT day, km FROM readings WHERE car_id = ? ORDER BY day, id", (car["id"],))
        recs = [{**r, "items": json.loads(r["items"])} for r in
                await self.qa(c, "SELECT * FROM records WHERE car_id = ? AND status = 'ok' ORDER BY day, km, id", (car["id"],))]
        snap = compute(car, rows, readings, recs, self.models, self.cfg, self.today())
        snap["records"] = recs
        return snap

    def title(self, car: dict) -> str:
        return carlib.title(self.models, car)

    def card(self, car: dict, odo: int | None = None) -> dict:
        """What the owner's screens and a workshop may see of a car (never the owner's name or phone)."""
        return {"id": car["id"], "title": self.title(car), "model": car["model"], "name": car["name"], "year": car["year"],
                "fuel": car["fuel"], "usage": car["usage"], "plate": car["plate"], "odo": odo}

    async def new_code(self, c) -> str:
        for _ in range(20):
            code = carlib.code_from(secrets.randbits(40))
            if not await self.q1(c, "SELECT 1 FROM cars WHERE code = ?", (code,)):
                return code
        raise Refused("generic")  # pragma: no cover - 2**40 codes
