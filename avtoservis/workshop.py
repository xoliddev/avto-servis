"""The workshop's side. A workshop opens a car only by the code its owner gave (typed, or the QR deep link), sees
only those cars and only the records it made itself, records a service that waits for the owner's "Tasdiqlaysizmi?",
and may invite only the owners who allowed it, once per due item. New workshops join with a one-time link."""

from __future__ import annotations

import json

from .base import checked
from .common import LINK, Refused, link_hash, new_link
from .core import cars as carlib
from .core import records
from .core.text import clean
from .history import MAX_PENDING, record_view


class Workshops:
    async def ws(self, c, uid: int) -> dict:
        w = await self.q1(c, "SELECT * FROM workshops WHERE owner = ? AND blocked = 0", (uid,))
        if not w:
            raise Refused("not_found")
        return w

    async def ws_access(self, c, w: dict, cid: object) -> dict:
        if not isinstance(cid, int) or isinstance(cid, bool):
            raise Refused("not_found")
        car = await self.q1(c, "SELECT k.*, a.allow FROM cars k JOIN access a ON a.car_id = k.id AND a.workshop_id = ? "
                               "WHERE k.id = ?", (w["id"], cid))
        if not car:
            raise Refused("not_found")
        return car

    async def open_car(self, uid: int, code: object) -> dict:
        w = await self.ws(self.db.conn, uid)
        if not self.code_tries.allow(("code", w["id"])):
            raise Refused("rate")
        norm = carlib.norm_code(code)
        car = await self.db.one("SELECT * FROM cars WHERE code = ?", (norm,)) if norm else None
        if not car:
            raise Refused("code")
        async with self.db.tx() as c:
            await c.execute("INSERT OR IGNORE INTO access (car_id, workshop_id, since_day, at) VALUES (?, ?, ?, ?)",
                            (car["id"], w["id"], self.today(), self.now()))
        return await self.ws_car(uid, car["id"])

    async def ws_car(self, uid: int, cid: object) -> dict:
        c = self.db.conn
        w = await self.ws(c, uid)
        car = await self.ws_access(c, w, cid)
        snap = await self.snapshot(c, car)
        mine = await self.qa(c, "SELECT * FROM records WHERE car_id = ? AND workshop_id = ? AND status IN ('ok', 'pending') "
                                "ORDER BY day DESC, id DESC", (car["id"], w["id"]))
        return {"car": self.card(car, snap["odo"]), "statuses": snap["statuses"], "items": [i["id"] for i in snap["items"]],
                "records": [record_view(r, w["name"]) for r in mine], "allow": bool(car["allow"]), "today": self.today()}

    async def ws_record(self, uid: int, cid: object, d: object) -> tuple[dict, list[dict]]:
        async with self.db.tx() as c:
            w = await self.ws(c, uid)
            car = await self.ws_access(c, w, cid)
            snap = await self.snapshot(c, car)
            rec = checked(records.validate, d, [it["id"] for it in snap["items"]], self.today())
            if rec["day"] < self.today() - 7:
                raise Refused("date")
            waiting = await self.q1(c, "SELECT COUNT(*) AS n FROM records WHERE car_id = ? AND workshop_id = ? AND status = "
                                       "'pending'", (car["id"], w["id"]))
            if waiting["n"] >= MAX_PENDING:
                raise Refused("limit")
            await self.check_fits(c, car, rec)
            cur = await c.execute("INSERT INTO records (car_id, day, km, items, labour, parts, shop, workshop_id, by, note, status, "
                                  "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
                                  (car["id"], rec["day"], rec["km"], json.dumps(rec["items"]), rec["labour"], rec["parts"], w["name"],
                                   w["id"], uid, rec["note"], self.now()))
            rid = cur.lastrowid
        return await self.ws_car(uid, cid), [{"type": "confirm", "to": car["owner"], "record_id": rid, "car_id": car["id"]}]

    async def ws_home(self, uid: int) -> dict:
        c = self.db.conn
        w = await self.ws(c, uid)
        cars = await self.qa(c, "SELECT k.*, a.allow, a.at AS seen FROM cars k JOIN access a ON a.car_id = k.id WHERE "
                                "a.workshop_id = ? ORDER BY a.at DESC, k.id DESC LIMIT 50", (w["id"],))
        sent = {(r["car_id"], r["item"], r["cycle"]) for r in
                await self.qa(c, "SELECT car_id, item, cycle FROM invites WHERE workshop_id = ?", (w["id"],))}
        due, listed = [], []
        for car in cars:
            snap = await self.snapshot(c, car)
            listed.append({**self.card(car, snap["odo"]), "allow": bool(car["allow"])})
            if car["allow"]:
                for st in snap["statuses"]:
                    if st["state"] in ("soon", "due"):
                        due.append({"car": self.card(car, snap["odo"]), "status": st,
                                    "invited": (car["id"], st["id"], st["cycle"]) in sent})
        due.sort(key=lambda x: (x["status"]["days_left"] if x["status"]["days_left"] is not None else 10**6, x["car"]["id"]))
        mine = await self.qa(c, "SELECT * FROM records WHERE workshop_id = ? AND status IN ('ok', 'pending') ORDER BY id DESC "
                                "LIMIT 20", (w["id"],))
        return {"workshop": {"id": w["id"], "name": w["name"], "address": w["address"]}, "cars": listed, "due": due,
                "records": [record_view(r, w["name"]) for r in mine], "today": self.today()}

    async def ws_invite(self, uid: int, cid: object, item: object) -> tuple[dict, list[dict]]:
        async with self.db.tx() as c:
            w = await self.ws(c, uid)
            car = await self.ws_access(c, w, cid)
            if not car["allow"]:
                raise Refused("not_allowed")
            snap = await self.snapshot(c, car)
            st = next((s for s in snap["statuses"] if s["id"] == item), None)
            if st is None or st["state"] not in ("soon", "due"):
                raise Refused("not_due")
            cur = await c.execute("INSERT OR IGNORE INTO invites (workshop_id, car_id, item, cycle, at) VALUES (?, ?, ?, ?, ?)",
                                  (w["id"], car["id"], st["id"], st["cycle"], self.now()))
            if cur.rowcount != 1:
                raise Refused("invited")
        note = {"type": "invite", "to": car["owner"], "car_id": car["id"], "item": st["id"], "workshop_id": w["id"]}
        return await self.ws_home(uid), [note]

    # ── joining as a workshop (one-time links made by an admin) ──
    async def make_link(self, uid: int) -> str:
        self.admin_only(uid)
        token = new_link()
        async with self.db.tx() as c:
            await c.execute("INSERT INTO links (token_hash, made_by, made_at) VALUES (?, ?, ?)", (link_hash(token), uid, self.now()))
        return token

    async def check_link(self, token: object) -> None:
        if not isinstance(token, str) or not LINK.match(token):
            raise Refused("link_used")
        row = await self.db.one("SELECT used_by FROM links WHERE token_hash = ?", (link_hash(token),))
        if not row or row["used_by"] is not None:
            raise Refused("link_used")

    async def join(self, uid: int, token: object, name: object, address: object) -> dict:
        n, a = clean(name, 60), clean(address, 120)
        if len(n) < 2:
            raise Refused("name")
        await self.check_link(token)
        async with self.db.tx() as c:
            if await self.q1(c, "SELECT 1 FROM workshops WHERE owner = ?", (uid,)):
                raise Refused("already")
            cur = await c.execute("UPDATE links SET used_by = ? WHERE token_hash = ? AND used_by IS NULL", (uid, link_hash(token)))
            if cur.rowcount != 1:
                raise Refused("link_used")
            await c.execute("INSERT INTO workshops (owner, name, address, created_at) VALUES (?, ?, ?, ?)", (uid, n, a, self.now()))
        return await self.ws_home(uid)

    async def admin_home(self, uid: int) -> dict:
        self.admin_only(uid)
        count = {}
        for table in ("users", "cars", "workshops", "readings", "records", "shares"):
            count[table] = (await self.db.one(f"SELECT COUNT(*) AS n FROM {table}"))["n"]  # noqa: S608 - fixed names
        return count
