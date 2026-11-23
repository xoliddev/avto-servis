"""Shared helpers: the seeded world in a database, a clock the tests can move, the people of the story and the
story's car (Jasur's Cobalt on metan)."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from avtoservis.core import seedgen
from avtoservis.db import Database
from avtoservis.service import Service

ROOT = Path(__file__).resolve().parent.parent
NOW = 1_795_000_000_000  # Wednesday 2026-11-18, 16:06 in Tashkent (the same moment as the shared vectors)
DAY = 86_400_000
# Seeded people have negative ids (nobody can sign in as them); the tests make them positive so they can also use
# the Mini App API like real people.
DRIVER, MASTER, BUYER, ADMIN = -seedgen.DRIVER, -seedgen.MASTER, -seedgen.BUYER, -seedgen.ADMIN
MASTER2 = -seedgen.MASTER2
STRANGER = 7777
NEXIA = seedgen.NEXIA
COBALT = {"model": "cobalt", "year": 2021, "fuel": "metan", "usage": "shaxsiy", "odo": 86_900, "plate": "01 A 123 BC", "last_oil": 80_900}
OIL = {"items": ["motor_moyi", "moy_filtri"], "labour": 60_000, "parts": 405_000, "note": "5W-30, 4 litr"}


def load(name: str):
    with open(ROOT / "shared" / "data" / f"{name}.json", encoding="utf-8") as fh:
        return json.load(fh)


def positive(world: dict) -> dict:
    out = json.loads(json.dumps(world))
    for u in out["users"]:
        u["id"] = abs(u["id"])
    for w in out["workshops"]:
        w["owner"] = abs(w["owner"])
    for k in out["cars"]:
        k["owner"] = abs(k["owner"])
    for r in out["records"]:
        r["by"] = abs(r["by"])
    return out


class Clock:
    def __init__(self, start: int = NOW) -> None:
        self.now = start

    def __call__(self) -> int:
        return self.now

    def skip(self, minutes: float = 0, days: float = 0) -> None:
        self.now += int((minutes * 60 + days * 86_400) * 1000)


@asynccontextmanager
async def service_env(clock: Clock | None = None, path: str = ":memory:", seed: bool = True):
    clock = clock or Clock()
    db = await Database.open(path)
    svc = Service(db, clock=clock, admins=frozenset({ADMIN}), share_secret=b"test-only-secret")
    if seed:
        await svc.seed(positive(seedgen.world(load("people"), load("models"), load("plan"), clock())))
    for uid in (STRANGER, 5555):
        await svc.touch_user(uid, "Test", "uz")
    try:
        yield svc, clock
    finally:
        await db.close()


async def cobalt(svc: Service) -> dict:
    return await svc.add_car(DRIVER, COBALT)


def st(view: dict, item: str) -> dict:
    return next(s for s in view["statuses"] if s["id"] == item)


async def code_of(svc: Service, cid: int) -> str:
    return (await svc.db.one("SELECT code FROM cars WHERE id = ?", (cid,)))["code"]
