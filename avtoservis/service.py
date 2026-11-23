"""All the rules in one object: the bot handlers, the Mini App API and the scheduler call the same ``Service``.
Every method takes the caller's Telegram id first and checks it: owners see only their own cars, workshops only the
cars whose code they were given and only their own records. Methods that make the bot speak return "notes"
(``{"type", "to", ...}``) that the notifier turns into messages."""

from __future__ import annotations

import json

from .base import Base
from .garage import Garage
from .history import History
from .passport import Passport
from .reminding import Reminding
from .security import RateLimiter
from .workshop import Workshops


class Service(Garage, History, Workshops, Passport, Reminding, Base):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.code_tries = RateLimiter(10)  # car codes a workshop may try per minute

    async def seed(self, world: dict) -> bool:
        """Fill an empty database with the fictional world. Returns False when there is data already. Car codes get
        fresh random values here (the shared seed only has placeholders), so nobody can open a seeded car by guessing."""
        if await self.db.one("SELECT id FROM users LIMIT 1"):
            return False
        now = self.now()
        async with self.db.tx() as c:
            for u in world["users"]:
                await c.execute("INSERT INTO users (id, name, phone, created_at) VALUES (?, ?, ?, ?)",
                                (u["id"], u["name"], u["phone"], now))
            for w in world["workshops"]:
                await c.execute("INSERT INTO workshops (id, owner, name, district, address, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                                (w["id"], w["owner"], w["name"], w["district"], w["address"], now))
            for k in world["cars"]:
                await c.execute("INSERT INTO cars (id, owner, model, name, year, fuel, usage, plate, code, created_day, created_at) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (k["id"], k["owner"], k["model"], k["name"], k["year"],
                                                                             k["fuel"], k["usage"], k["plate"], await self.new_code(c),
                                                                             k["created_day"], now))
            for r in world["readings"]:
                await c.execute("INSERT INTO readings (car_id, day, km, at) VALUES (?, ?, ?, ?)", (r["car_id"], r["day"], r["km"], now))
            for it in world["items"]:
                await c.execute("INSERT INTO car_items (car_id, item, last_km, last_day, guess) VALUES (?, ?, ?, ?, ?)",
                                (it["car_id"], it["item"], it["last_km"], it["last_day"], int(it["guess"])))
            for r in world["records"]:
                await c.execute("INSERT INTO records (id, car_id, day, km, items, labour, parts, shop, workshop_id, by, note, status, "
                                "created_at, decided_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ok', ?, ?)",
                                (r["id"], r["car_id"], r["day"], r["km"], json.dumps(r["items"]), r["labour"], r["parts"], r["shop"],
                                 r["workshop_id"], r["by"], r["note"], now, now))
            for a in world["access"]:
                await c.execute("INSERT INTO access (car_id, workshop_id, allow, since_day, at) VALUES (?, ?, ?, ?, ?)",
                                (a["car_id"], a["workshop_id"], int(a["allow"]), a["since_day"], now))
            for k in world["cars"]:
                car = await self.q1(c, "SELECT * FROM cars WHERE id = ?", (k["id"],))
                await self.mark_sent(c, k["id"], await self.snapshot(c, car))
        return True
