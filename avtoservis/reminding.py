"""Reminders: the scheduler's tick claims each reminder key once in the database (``INSERT OR IGNORE``), so every
reminder is sent exactly once, also across restarts. Quiet between 21:00 and 09:00 Tashkent time."""

from __future__ import annotations

from .core import reminders


class Reminding:
    async def mark_sent(self, c, cid: int, snap: dict) -> None:
        """Keys that are true right now count as sent (used when a car is added: its plan is on the screen)."""
        last_day = snap["points"][-1][0]
        for k in reminders.keys_for(snap["statuses"], self.today(), last_day, self.cfg):
            await c.execute("INSERT OR IGNORE INTO reminders (car_id, key, at) VALUES (?, ?, ?)", (cid, k["key"], self.now()))

    async def tick(self) -> list[dict]:
        if reminders.quiet(self.minute()):
            return []
        notes = []
        for car in await self.db.all("SELECT * FROM cars ORDER BY id"):
            async with self.db.tx() as c:
                snap = await self.snapshot(c, car)
                fresh = []
                for k in reminders.keys_for(snap["statuses"], self.today(), snap["points"][-1][0], self.cfg):
                    cur = await c.execute("INSERT OR IGNORE INTO reminders (car_id, key, at) VALUES (?, ?, ?)",
                                          (car["id"], k["key"], self.now()))
                    if cur.rowcount == 1:
                        fresh.append(k)
            if fresh:
                notes.append({"type": "remind", "to": car["owner"], "car_id": car["id"],
                              "items": [{"id": k["item"], "kind": k["kind"]} for k in fresh if k["item"]],
                              "ask": any(k["kind"] == "ask" for k in fresh)})
        return notes
