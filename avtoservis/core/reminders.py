"""Which reminders one car has today (pure). The service stores each key once (``INSERT OR IGNORE``), so every
reminder goes out exactly once, also across restarts and with several processes.

* ``soon``  — about 500 km or 7 days left, once per service cycle;
* ``due``   — on the due day (or when the km mark is reached);
* ``late<k>`` — a gentle nudge every 7 days while it stays overdue;
* ``ask:<day>`` — no odometer reading for 14 days (once per last reading).

A cycle is "since the item was last done", so after a service record the reminders start over.
"""

from __future__ import annotations

QUIET_FROM, QUIET_TO = 21 * 60, 9 * 60  # no reminders between 21:00 and 09:00 Tashkent time


def keys_for(statuses: list[dict], today: int, last_reading_day: int, cfg: dict) -> list[dict]:
    out = []
    for st in statuses:
        if st["state"] not in ("soon", "due"):
            continue
        base = f"{st['id']}:{st['cycle']}"
        if st["state"] == "soon":
            out.append({"key": f"{base}:soon", "item": st["id"], "kind": "soon"})
            continue
        over = -st["days_left"] if st["days_left"] is not None and st["days_left"] < 0 else 0
        week = over // 7
        out.append({"key": f"{base}:due" if week == 0 else f"{base}:late{week}", "item": st["id"],
                    "kind": "due" if week == 0 else "late"})
    if today - last_reading_day >= cfg["ask_after_days"]:
        out.append({"key": f"ask:{last_reading_day}", "item": None, "kind": "ask"})
    return out


def quiet(minute: int) -> bool:
    return minute >= QUIET_FROM or minute < QUIET_TO
