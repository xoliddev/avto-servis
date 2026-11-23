"""The service plan: which items a car needs, their intervals (km AND/OR months, whichever comes first, adjusted by
fuel and taxi use), and each item's status today: km left, the expected day with its fan, ``ok`` / ``soon`` / ``due``.

``status`` is the one function every screen, reminder and passport uses, so a number shown in two places is the
same number."""

from __future__ import annotations

from .clock import add_months, civil, days_from_civil
from .forecast import day_for, odo_on
from .money import div_round
from .text import InputError, whole

ALL_FUELS = ("benzin", "metan", "propan", "gibrid", "elektr")
SEASONS = ("winter", "summer")  # the order of "season" pairs in plan.json
STATE_ORDER = {"due": 0, "soon": 1, "ok": 2, "unknown": 3}


def interval(item: dict, fuel: str, usage: str) -> tuple[int | None, int | None]:
    """(km, months) for this fuel and use; km rounded to 100."""
    km = item.get("km")
    if km:
        pct = item.get("fuel_pct", {}).get(fuel, 100)
        if usage == "taksi":
            pct = pct * item.get("taxi_pct", 100) // 100
        km = div_round(km * pct, 10_000) * 100
    months = item.get("taxi_months") if usage == "taksi" and item.get("taxi_months") else item.get("months")
    return km or None, months or None


def items_for(cfg: dict, model: dict, fuel: str, usage: str, overrides: dict | None = None) -> list[dict]:
    """The car's plan. ``overrides`` (per item id) may set ``km``, ``months`` or ``off``."""
    out = []
    for it in cfg["items"]:
        if fuel not in it.get("fuels", ALL_FUELS) or (it.get("belt") and model.get("grm") != "belt"):
            continue
        km, months = interval(it, fuel, usage)
        o = (overrides or {}).get(it["id"], {})
        km = o.get("km") or km
        months = o.get("months") or months
        out.append({"id": it["id"], "km": km if it.get("km") else None, "months": months, "calendar": bool(it.get("calendar")),
                    "season": it.get("season"), "off": bool(o.get("off")), "base_km": interval(it, fuel, usage)[0]})
    return out


def check_override(item: dict, km: object, months: object) -> dict:
    """An owner's own interval for one item (the workshop or the manual may say otherwise)."""
    out = {}
    if km not in (None, "") and item.get("km"):
        out["km"] = whole(km, 500, 200_000, "interval")
    if months not in (None, "") and item.get("months"):
        out["months"] = whole(months, 1, 120, "interval")
    if not out:
        raise InputError("interval")
    return out


def next_season(season: list, day: int) -> tuple[int, str]:
    """The first season change strictly after ``day``: (day, "winter" | "summer")."""
    y = civil(day)[0]
    best = None
    for yy in (y, y + 1):
        for i, (m, d) in enumerate(season):
            dd = days_from_civil(yy, m, d)
            if dd > day and (best is None or dd < best[0]):
                best = (dd, SEASONS[i])
    return best


def status(it: dict, last: dict, fc: dict, today: int, cfg: dict) -> dict:
    """``last`` = {km, day, guess} of the last time it was done (guess: assumed, not entered)."""
    out = {"id": it["id"], "km_iv": it["km"], "months": it["months"], "due_km": None, "due_day": None, "km_left": None,
           "days_left": None, "lo_day": None, "hi_day": None, "basis": "date", "guess": bool(last.get("guess")),
           "season": None, "last_km": last.get("km"), "last_day": last.get("day")}
    if it.get("season"):
        base = last["day"] if last.get("day") is not None else today - 1
        out["due_day"], out["season"] = next_season(it["season"], base)
        out["guess"] = last.get("day") is None
        out["cycle"] = str(out["due_day"])
    elif it["km"] is None:
        if last.get("day") is not None:
            out["due_day"] = add_months(last["day"], it["months"])
        out["cycle"] = f"-:{last.get('day')}"
    else:
        due_km = last["km"] + it["km"]
        km_day, lo_day, hi_day = day_for(fc, due_km), day_for(fc, due_km, fc["hi"]), day_for(fc, due_km, fc["lo"])
        date_day = add_months(last["day"], it["months"]) if it["months"] and last.get("day") is not None else None
        days = [x for x in (km_day, date_day) if x is not None]
        out.update(due_km=due_km, km_left=due_km - odo_on(fc, today), due_day=min(days) if days else None,
                   basis="date" if date_day is not None and (km_day is None or date_day < km_day) else "km")
        if date_day is not None:
            lo_day = date_day if lo_day is None else min(lo_day, date_day)
            hi_day = date_day if hi_day is None else min(hi_day, date_day)
        out.update(lo_day=lo_day, hi_day=hi_day, cycle=f"{last['km']}:{last.get('day')}")
    if out["due_day"] is not None:
        out["days_left"] = out["due_day"] - today
    kl, dl = out["km_left"], out["days_left"]
    if kl is None and dl is None:
        out["state"] = "unknown"
    elif (kl is not None and kl <= 0) or (dl is not None and dl <= 0):
        out["state"] = "due"
    elif (kl is not None and kl <= cfg["soon_km"]) or (dl is not None and dl <= cfg["soon_days"]):
        out["state"] = "soon"
    else:
        out["state"] = "ok"
    return out


def sort_key(st: dict) -> tuple:
    return STATE_ORDER[st["state"]], st["due_day"] if st["due_day"] is not None else 10**9, st["id"]


def default_last(it: dict, odo: int, today: int, last_oil: int | None) -> dict:
    """What a new car assumes: km items done on schedule (the last multiple of the interval), dated today; calendar
    items unknown until the owner enters a date; the oil change from the add-car form if given."""
    if it.get("season") or it.get("calendar"):
        return {"km": None, "day": None, "guess": True}
    if it["id"] in ("motor_moyi", "moy_filtri") and last_oil is not None:
        return {"km": last_oil, "day": today, "guess": False}
    km = odo // it["km"] * it["km"] if it["km"] else None
    return {"km": km, "day": today, "guess": True}
