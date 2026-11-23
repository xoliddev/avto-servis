"""Cars: Uzbek-market models, year, fuel, usage, odometer, number plate and the car code a workshop opens it by."""

from __future__ import annotations

import re

from .text import InputError, clean, whole

FUELS = ("benzin", "metan", "propan", "gibrid", "elektr")
USAGES = ("shaxsiy", "taksi")
MAX_KM = 2_000_000
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I: easy to read out loud at the workshop
_PERSONAL = re.compile(r"^(\d{2})([A-Z])(\d{3})([A-Z]{2})$")
_FIRM = re.compile(r"^(\d{2})(\d{3})([A-Z]{3})$")
_PLATE_DROP = re.compile(r"[\s\-]")


def model(models: list[dict], mid: object) -> dict:
    m = next((x for x in models if x["id"] == mid), None) if isinstance(mid, str) else None
    if m is None:
        raise InputError("model")
    return m


def plate(value: object) -> str:
    """ "01a123bc", "01 A 123 BC" -> "01 A 123 BC"; "01 123 ABC" for companies; "" = not given."""
    if value is None or value == "":
        return ""
    if not isinstance(value, str) or len(value) > 16:
        raise InputError("plate")
    s = _PLATE_DROP.sub("", value).upper()
    if m := _PERSONAL.match(s):
        return " ".join(m.groups())
    if m := _FIRM.match(s):
        return " ".join(m.groups())
    raise InputError("plate")


def validate(d: object, models: list[dict], this_year: int) -> dict:
    """A new car from the bot or the Mini App. ``last_oil`` (optional) is the odometer at the last oil change."""
    if not isinstance(d, dict):
        raise InputError("generic")
    m = model(models, d.get("model"))
    year = whole(d.get("year"), m["from"], min(m.get("to", this_year), this_year), "year")
    fuel = d.get("fuel")
    if fuel not in m["fuels"]:
        raise InputError("fuel")
    usage = d.get("usage", "shaxsiy")
    if usage not in USAGES:
        raise InputError("usage")
    odo = whole(d.get("odo"), 0, MAX_KM, "odo")
    name = clean(d.get("name"), 40) if m["id"] == "other" else ""
    if m["id"] == "other" and len(name) < 2:
        raise InputError("name")
    raw = d.get("last_oil")
    last_oil = None if raw in (None, "") else whole(raw, 0, odo, "last_oil")
    return {"model": m["id"], "name": name, "year": year, "fuel": fuel, "usage": usage, "odo": odo,
            "plate": plate(d.get("plate")), "last_oil": last_oil}


def title(models: list[dict], car: dict) -> str:
    """ "Chevrolet Cobalt 2021" (a custom name for "other")."""
    m = next((x for x in models if x["id"] == car["model"]), None)
    name = car.get("name") or (m["name"] if m else "") or car["model"]
    return f"{name} {car['year']}"


def code_from(n: int) -> str:
    """40 random bits -> 8 characters of the code alphabet."""
    out = []
    for _ in range(8):
        out.append(CODE_ALPHABET[n % 32])
        n //= 32
    return "".join(out)


def norm_code(value: object) -> str | None:
    """What a master types ("abcd-ef23", "ABCD EF23") -> "ABCDEF23", or None if it cannot be a code."""
    if not isinstance(value, str) or len(value) > 20:
        return None
    s = _PLATE_DROP.sub("", value).upper()
    return s if len(s) == 8 and all(ch in CODE_ALPHABET for ch in s) else None


def show_code(code: str) -> str:
    return f"{code[:4]}-{code[4:]}"
