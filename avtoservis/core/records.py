"""A service record: date, km, which plan items, labour and parts in whole so'm, the workshop's name, a note."""

from __future__ import annotations

from .cars import MAX_KM
from .clock import parse_date
from .text import InputError, clean, whole

MAX_MONEY = 50_000_000  # so'm, per field
MAX_ITEMS = 12
OLDEST_DAYS = 3650


def day_of(value: object, today: int, ahead: int = 0) -> int:
    """A day number, "today", "yesterday" or "12.11.2026" -> day number within the last 10 years and at most
    ``ahead`` days in the future (documents such as OSAGO expire in the future)."""
    if value in (None, "", "today"):
        return today
    if value == "yesterday":
        return today - 1
    if isinstance(value, int) and not isinstance(value, bool):
        day = value
    else:
        day = parse_date(value)
        if day is None:
            raise InputError("date")
    if not today - OLDEST_DAYS <= day <= today + ahead:
        raise InputError("date")
    return day


def validate(d: object, allowed: list[str], today: int) -> dict:
    if not isinstance(d, dict):
        raise InputError("generic")
    items = d.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_ITEMS:
        raise InputError("items")
    if any(not isinstance(i, str) or i not in allowed for i in items) or len(set(items)) != len(items):
        raise InputError("items")
    labour = whole(0 if d.get("labour") is None else d["labour"], 0, MAX_MONEY, "money")
    parts = whole(0 if d.get("parts") is None else d["parts"], 0, MAX_MONEY, "money")
    return {"items": [i for i in allowed if i in items], "day": day_of(d.get("day"), today),
            "km": whole(d.get("km"), 0, MAX_KM, "odo"), "labour": labour, "parts": parts,
            "note": clean(d.get("note"), 300), "shop": clean(d.get("shop"), 60)}
