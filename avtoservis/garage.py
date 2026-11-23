"""The owner's garage: adding a car, odometer readings with the anomaly guard, the plan with forecasts, per-item
edits, the car code for workshops and which workshops may see the car."""

from __future__ import annotations

import json

from .base import checked
from .common import Refused
from .core import cars as carlib
from .core import odometer, plan
from .core.clock import add_months, civil
from .core.records import day_of

MAX_CARS = 10
MAX_READINGS_A_DAY = 20


class Garage:
    async def add_car(self, uid: int, d: object) -> dict:
        today = self.today()
        car = checked(carlib.validate, d, self.models, civil(today)[0])
        async with self.db.tx() as c:
            n = await self.q1(c, "SELECT COUNT(*) AS n FROM cars WHERE owner = ?", (uid,))
            if n["n"] >= MAX_CARS:
                raise Refused("limit")
            code = await self.new_code(c)
            cur = await c.execute("INSERT INTO cars (owner, model, name, year, fuel, usage, plate, code, created_day, created_at) "
                                  "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (uid, car["model"], car["name"], car["year"], car["fuel"],
                                                                            car["usage"], car["plate"], code, today, self.now()))
            cid = cur.lastrowid
            await c.execute("INSERT INTO readings (car_id, day, km, at) VALUES (?, ?, ?, ?)", (cid, today, car["odo"], self.now()))
            row = await self.q1(c, "SELECT * FROM cars WHERE id = ?", (cid,))
            items = plan.items_for(self.cfg, carlib.model(self.models, car["model"]), car["fuel"], car["usage"])
            for it in items:
                last = plan.default_last(it, car["odo"], today, car["last_oil"])
                await c.execute("INSERT INTO car_items (car_id, item, last_km, last_day, guess) VALUES (?, ?, ?, ?, ?)",
                                (cid, it["id"], last["km"], last["day"], int(last["guess"])))
            await self.mark_sent(c, cid, await self.snapshot(c, row))  # already due shows on the plan now: no reminder
        return await self.car_view(uid, cid)

    async def my_cars(self, uid: int) -> list[dict]:
        out = []
        for car in await self.db.all("SELECT * FROM cars WHERE owner = ? ORDER BY id", (uid,)):
            snap = await self.snapshot(self.db.conn, car)
            out.append({**self.card(car, snap["odo"]), "next": snap["statuses"][:3],
                        "attention": sum(1 for s in snap["statuses"] if s["state"] in ("soon", "due"))})
        return out

    async def car_view(self, uid: int, cid: object) -> dict:
        c = self.db.conn
        car = await self.own_car(c, uid, cid)
        snap = await self.snapshot(c, car)
        pending = await self.qa(c, "SELECT r.id, r.day, r.km, r.items, r.labour, r.parts, w.name AS workshop FROM records r "
                                   "JOIN workshops w ON w.id = r.workshop_id WHERE r.car_id = ? AND r.status = 'pending' "
                                   "ORDER BY r.id", (car["id"],))
        shops = await self.qa(c, "SELECT a.workshop_id, a.allow, w.name, w.address FROM access a JOIN workshops w ON w.id = "
                                 "a.workshop_id WHERE a.car_id = ? ORDER BY a.at, a.workshop_id", (car["id"],))
        return {"car": {**self.card(car, snap["odo"]), "code": carlib.show_code(car["code"])}, "today": self.today(),
                "now": self.now(), "fc": snap["fc"], "points": snap["points"], "statuses": snap["statuses"], "off": snap["off"],
                "pending": [{**p, "items": json.loads(p["items"])} for p in pending],
                "shops": [{**s, "allow": bool(s["allow"])} for s in shops]}

    async def add_reading(self, uid: int, cid: object, km: object, confirm: object = False) -> dict:
        """-> {confirm: True, km, per_day, days} when the jump needs a yes, else {confirm: False, km, view}."""
        today = self.today()
        async with self.db.tx() as c:
            car = await self.own_car(c, uid, cid)
            snap = await self.snapshot(c, car)
            last = snap["points"][-1] if snap["points"] else None
            n, ask = checked(odometer.check, last, today, km, confirm is True, self.cfg["jump_km_per_day"])
            if ask:
                days = max(1, today - last[0])
                return {"confirm": True, "km": n, "per_day": (n - last[1]) // days, "days": days}
            count = await self.q1(c, "SELECT COUNT(*) AS n FROM readings WHERE car_id = ? AND day = ?", (car["id"], today))
            if count["n"] >= MAX_READINGS_A_DAY:
                raise Refused("limit")
            jump = int(last is not None and n - last[1] > self.cfg["jump_km_per_day"] * max(1, today - last[0]))
            await c.execute("INSERT INTO readings (car_id, day, km, at, jump) VALUES (?, ?, ?, ?, ?)",
                            (car["id"], today, n, self.now(), jump))
        return {"confirm": False, "km": n, "view": await self.car_view(uid, cid)}

    async def set_item(self, uid: int, cid: object, item: object, d: object) -> dict:
        """One plan item: done today, last km / date, the expiry of a document, an own interval, or off the plan."""
        if not isinstance(d, dict):
            raise Refused("generic")
        today = self.today()
        async with self.db.tx() as c:
            car = await self.own_car(c, uid, cid)
            snap = await self.snapshot(c, car)
            it = next((x for x in snap["items"] if x["id"] == item), None)
            if it is None:
                raise Refused("not_found")
            sets = self._item_changes(it, d, snap["odo"], today)
            cols = ", ".join(f"{k} = ?" for k in sets)
            await c.execute(f"UPDATE car_items SET {cols} WHERE car_id = ? AND item = ?",  # noqa: S608 - names from code
                            (*sets.values(), car["id"], item))
        return await self.car_view(uid, cid)

    def _item_changes(self, it: dict, d: dict, odo: int, today: int) -> dict:
        sets: dict = {}
        if d.get("done") is True:
            sets.update(last_km=odo if it["km"] else None, last_day=today, guess=0)
        if d.get("last_km") not in (None, ""):
            if not it["km"]:
                raise Refused("generic")
            km = checked(odometer.check, None, today, d["last_km"], True, 0)[0]
            if km > odo:
                raise Refused("last_km")
            sets.update(last_km=km, guess=0)
        if d.get("last_day") not in (None, ""):
            sets.update(last_day=checked(day_of, d["last_day"], today), guess=0)
            if it["km"] and "last_km" not in sets:
                sets["last_km"] = odo  # "done on 12.11" without km: today's odometer is the best guess
        if d.get("expires") not in (None, ""):
            if not it["months"]:
                raise Refused("generic")
            sets.update(last_day=add_months(checked(day_of, d["expires"], today, 3650), -it["months"]), guess=0)
        if d.get("km") not in (None, "") or d.get("months") not in (None, ""):
            cfg_item = next(x for x in self.cfg["items"] if x["id"] == it["id"])
            sets.update(checked(plan.check_override, cfg_item, d.get("km"), d.get("months")))
        if d.get("reset") is True:
            sets.update(km=None, months=None)
        if isinstance(d.get("off"), bool):
            sets["off"] = int(d["off"])
        if not sets:
            raise Refused("generic")
        return sets

    async def rotate_code(self, uid: int, cid: object) -> dict:
        """A new car code: the old one stops opening the car (workshops that already have it keep their access)."""
        async with self.db.tx() as c:
            car = await self.own_car(c, uid, cid)
            await c.execute("UPDATE cars SET code = ? WHERE id = ?", (await self.new_code(c), car["id"]))
        return await self.car_view(uid, cid)

    async def set_shop(self, uid: int, cid: object, wid: object, allow: object = None, remove: object = False) -> dict:
        """Allow or forbid a workshop's invitations, or take its access away."""
        async with self.db.tx() as c:
            car = await self.own_car(c, uid, cid)
            row = await self.q1(c, "SELECT * FROM access WHERE car_id = ? AND workshop_id = ?", (car["id"], wid))
            if not row:
                raise Refused("not_found")
            if remove is True:
                await c.execute("DELETE FROM access WHERE car_id = ? AND workshop_id = ?", (car["id"], wid))
            elif isinstance(allow, bool):
                await c.execute("UPDATE access SET allow = ? WHERE car_id = ? AND workshop_id = ?", (int(allow), car["id"], wid))
            else:
                raise Refused("generic")
        return await self.car_view(uid, cid)
