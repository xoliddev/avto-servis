"""Service history: self-logged records, the owner's "Tasdiqlaysizmi?" for a workshop's record, receipt photos,
spending stats (per month, per item, so'm per km) and the CSV export."""

from __future__ import annotations

import json

from .base import checked
from .common import Refused
from .core import odometer, records, stats

MAX_PENDING = 3


def record_view(r: dict, workshop: str = "") -> dict:
    items = r["items"] if isinstance(r["items"], list) else json.loads(r["items"])
    return {"id": r["id"], "car_id": r["car_id"], "day": r["day"], "km": r["km"], "items": items, "labour": r["labour"],
            "parts": r["parts"], "total": r["labour"] + r["parts"], "shop": workshop or r["shop"],
            "verified": r["workshop_id"] is not None and r["status"] == "ok", "status": r["status"],
            "photo": bool(r.get("photo")), "note": r["note"]}


class History:
    async def check_fits(self, c, car: dict, rec: dict) -> dict:
        snap = await self.snapshot(c, car)
        checked(odometer.fits, snap["points"], rec["day"], rec["km"])
        if snap["points"] and rec["day"] >= snap["points"][-1][0] and rec["km"] < snap["points"][-1][1]:
            raise Refused("odo_back")
        return snap

    async def add_record(self, uid: int, cid: object, d: object) -> dict:
        """The owner logs a service himself ("O'zi yozgan")."""
        async with self.db.tx() as c:
            car = await self.own_car(c, uid, cid)
            snap = await self.snapshot(c, car)
            rec = checked(records.validate, d, [it["id"] for it in snap["items"]], self.today())
            await self.check_fits(c, car, rec)
            cur = await c.execute("INSERT INTO records (car_id, day, km, items, labour, parts, shop, by, note, status, created_at) "
                                  "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ok', ?)",
                                  (car["id"], rec["day"], rec["km"], json.dumps(rec["items"]), rec["labour"], rec["parts"],
                                   rec["shop"], uid, rec["note"], self.now()))
            rid = cur.lastrowid
        return {"record_id": rid, "view": await self.car_view(uid, cid)}

    async def history(self, uid: int, cid: object) -> list[dict]:
        car = await self.own_car(self.db.conn, uid, cid)
        rows = await self.db.all("SELECT r.*, w.name AS wname FROM records r LEFT JOIN workshops w ON w.id = r.workshop_id "
                                 "WHERE r.car_id = ? AND r.status IN ('ok', 'pending') ORDER BY r.day DESC, r.km DESC, r.id DESC",
                                 (car["id"],))
        return [record_view(r, r["wname"] or "") for r in rows]

    async def own_record(self, c, uid: int, rid: object) -> tuple[dict, dict]:
        if not isinstance(rid, int) or isinstance(rid, bool):
            raise Refused("not_found")
        r = await self.q1(c, "SELECT r.* FROM records r JOIN cars k ON k.id = r.car_id WHERE r.id = ? AND k.owner = ?", (rid, uid))
        if not r:
            raise Refused("not_found")
        return r, await self.q1(c, "SELECT * FROM cars WHERE id = ?", (r["car_id"],))

    async def record(self, uid: int, rid: object) -> dict:
        r, _ = await self.own_record(self.db.conn, uid, rid)
        ws = await self.db.one("SELECT name FROM workshops WHERE id = ?", (r["workshop_id"],)) if r["workshop_id"] else None
        return record_view(r, ws["name"] if ws else "")

    async def decide(self, uid: int, rid: object, yes: object, allow: object = False) -> tuple[dict, list[dict]]:
        """The owner confirms (or rejects) a workshop's record; only then it counts. ``allow`` lets that workshop
        send invitations when a service is due."""
        if not isinstance(yes, bool):
            raise Refused("generic")
        async with self.db.tx() as c:
            r, car = await self.own_record(c, uid, rid)
            if r["status"] != "pending":
                raise Refused("decided")
            if yes:
                await self.check_fits(c, car, {"day": r["day"], "km": r["km"]})
            await c.execute("UPDATE records SET status = ?, decided_at = ? WHERE id = ?",
                            ("ok" if yes else "rejected", self.now(), r["id"]))
            if yes and allow is True:
                await c.execute("UPDATE access SET allow = 1 WHERE car_id = ? AND workshop_id = ?", (car["id"], r["workshop_id"]))
            ws = await self.q1(c, "SELECT * FROM workshops WHERE id = ?", (r["workshop_id"],))
        view = await self.record(uid, rid)
        return view, [{"type": "decided", "to": ws["owner"], "record_id": r["id"], "yes": yes, "car_id": car["id"]}]

    async def set_photo(self, uid: int, rid: object, file_id: object) -> dict:
        if not isinstance(file_id, str) or not 10 <= len(file_id) <= 200 or not file_id.isascii():
            raise Refused("generic")
        async with self.db.tx() as c:
            r, _ = await self.own_record(c, uid, rid)
            await c.execute("UPDATE records SET photo = ? WHERE id = ?", (file_id, r["id"]))
        return await self.record(uid, rid)

    async def photo(self, uid: int, rid: object) -> str | None:
        r, _ = await self.own_record(self.db.conn, uid, rid)
        return r["photo"]

    async def stats(self, uid: int, cid: object) -> dict:
        car = await self.own_car(self.db.conn, uid, cid)
        snap = await self.snapshot(self.db.conn, car)
        pts = snap["points"]
        driven = pts[-1][1] - pts[0][1] if pts else 0
        s = stats.spending(snap["records"], 12, self.today())
        return {**s, "km": driven, "per_km": stats.per_km(s["total"], driven), "since": pts[0][0] if pts else None,
                "car": self.card(car, snap["odo"])}

    async def export_rows(self, uid: int, cid: object) -> tuple[dict, list[dict]]:
        car = await self.own_car(self.db.conn, uid, cid)
        rows = await self.db.all("SELECT r.*, w.name AS wname FROM records r LEFT JOIN workshops w ON w.id = r.workshop_id "
                                 "WHERE r.car_id = ? AND r.status = 'ok' ORDER BY r.day, r.km, r.id", (car["id"],))
        return car, [record_view(r, r["wname"] or "") for r in rows]

    async def pending_for(self, uid: int) -> list[dict]:
        rows = await self.db.all("SELECT r.*, w.name AS wname FROM records r JOIN cars k ON k.id = r.car_id JOIN workshops w ON "
                                 "w.id = r.workshop_id WHERE k.owner = ? AND r.status = 'pending' ORDER BY r.id", (uid,))
        return [record_view(r, r["wname"]) for r in rows]
