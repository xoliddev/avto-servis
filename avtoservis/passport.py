"""Servis pasporti: a read-only, signed, expiring, revocable link for a used-car buyer. It shows the car, its
service timeline (workshop-confirmed vs self-logged), whether the odometer ever went back, and what is due next.
No money, and no owner name or phone unless the owner chose to show them."""

from __future__ import annotations

import secrets

from .common import Refused
from .core import odometer, token
from .core.clock import DAY_MS
from .history import record_view

DAYS = (7, 30, 90)
MAX_ACTIVE = 5


class Passport:
    async def share(self, uid: int, cid: object, days: object, show_owner: object = False) -> dict:
        if days not in DAYS or isinstance(days, bool) or not isinstance(show_owner, bool):
            raise Refused("generic")
        now = self.now()
        async with self.db.tx() as c:
            car = await self.own_car(c, uid, cid)
            active = await self.q1(c, "SELECT COUNT(*) AS n FROM shares WHERE car_id = ? AND revoked_at IS NULL AND expires_at > ?",
                                   (car["id"], now))
            if active["n"] >= MAX_ACTIVE:
                raise Refused("limit")
            nonce = secrets.token_bytes(12)
            cur = await c.execute("INSERT INTO shares (car_id, nonce, show_owner, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
                                  (car["id"], nonce.hex(), int(show_owner), now, now + days * DAY_MS))
            sid = cur.lastrowid
        return {"id": sid, "token": token.make(self.secret, nonce), "expires_at": now + days * DAY_MS,
                "items": await self.shares(uid, cid)}

    async def shares(self, uid: int, cid: object) -> list[dict]:
        car = await self.own_car(self.db.conn, uid, cid)
        rows = await self.db.all("SELECT * FROM shares WHERE car_id = ? AND revoked_at IS NULL AND expires_at > ? ORDER BY id DESC",
                                 (car["id"], self.now()))
        return [{"id": r["id"], "token": token.make(self.secret, bytes.fromhex(r["nonce"])), "created_at": r["created_at"],
                 "expires_at": r["expires_at"], "show_owner": bool(r["show_owner"])} for r in rows]

    async def revoke(self, uid: int, cid: object, sid: object) -> list[dict]:
        async with self.db.tx() as c:
            car = await self.own_car(c, uid, cid)
            cur = await c.execute("UPDATE shares SET revoked_at = ? WHERE id = ? AND car_id = ? AND revoked_at IS NULL",
                                  (self.now(), sid if isinstance(sid, int) else -1, car["id"]))
            if cur.rowcount != 1:
                raise Refused("not_found")
        return await self.shares(uid, cid)

    async def passport(self, tok: object) -> dict:
        """The buyer's page. A forged, revoked or expired link all answer the same "link_gone"."""
        nonce = token.nonce_of(self.secret, tok)
        row = await self.db.one("SELECT * FROM shares WHERE nonce = ?", (nonce,)) if nonce else None
        if not row or row["revoked_at"] is not None or row["expires_at"] <= self.now():
            raise Refused("link_gone")
        c = self.db.conn
        car = await self.q1(c, "SELECT * FROM cars WHERE id = ?", (row["car_id"],))
        snap = await self.snapshot(c, car)
        rows = await self.qa(c, "SELECT r.*, w.name AS wname FROM records r LEFT JOIN workshops w ON w.id = r.workshop_id WHERE "
                                "r.car_id = ? AND r.status = 'ok' ORDER BY r.day DESC, r.km DESC, r.id DESC", (car["id"],))
        timeline = []
        for r in rows:
            v = record_view(r, r["wname"] or "")
            timeline.append({k: v[k] for k in ("id", "day", "km", "items", "shop", "verified")})
        owner = None
        if row["show_owner"]:
            u = await self.q1(c, "SELECT name, phone FROM users WHERE id = ?", (car["owner"],))
            owner = {"name": u["name"], "phone": u["phone"]}
        card = self.card(car, snap["odo"])
        last = snap["points"][-1] if snap["points"] else None
        return {"car": {k: card[k] for k in ("title", "model", "name", "year", "fuel", "usage", "plate")}, "owner": owner,
                "last": {"day": last[0], "km": last[1]} if last else None, "since": car["created_day"],
                "check": odometer.consistency(snap["points"], self.cfg["jump_km_per_day"]), "timeline": timeline,
                "verified": sum(1 for x in timeline if x["verified"]), "self": sum(1 for x in timeline if not x["verified"]),
                "next": [s for s in snap["statuses"] if s["state"] != "unknown"][:6], "expires_at": row["expires_at"],
                "today": self.today()}
