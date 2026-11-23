"""Texts for the bot, read from shared/locales/*.json (the Mini App and the browser demo read the same files), plus
the formatters every screen needs. shared/i18n.js is the same code for the browser, and shared/test_vectors.json
checks that both write the same sentence ("Motor moyi: 620 km qoldi — taxminan 4-dekabr (11 kundan keyin)")."""

from __future__ import annotations

import html
import json
import re
from functools import cache
from pathlib import Path

from .core.clock import civil
from .core.money import group

LOCALE_DIR = Path(__file__).resolve().parent.parent / "shared" / "locales"
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def norm_lang(code: str | None) -> str:
    return "ru" if code and str(code)[:2].lower() == "ru" else "uz"


class Raw(str):
    """A parameter that is already safe HTML (for example a nested, already-rendered text)."""


@cache
def catalog(lang: str) -> dict[str, str]:
    with open(LOCALE_DIR / f"{lang}.json", encoding="utf-8") as fh:
        return json.load(fh)


def render(template: str, params: dict) -> str:
    def sub(m: re.Match) -> str:
        if m.group(1) not in params:
            return m.group(0)
        value = params[m.group(1)]
        return value if isinstance(value, Raw) else html.escape(str(value), quote=False)

    return _PLACEHOLDER.sub(sub, template)


def t(lang: str, key: str, **params: object) -> str:
    """Localized text; parameters are HTML-escaped unless wrapped in ``Raw``."""
    lang = norm_lang(lang)
    template = catalog(lang).get(key) or catalog("uz").get(key) or key
    return render(template, params)


def plain(text: str) -> str:
    """For callback alerts, which show plain text."""
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def money(lang: str, n: int) -> str:
    return t(lang, "fmt.sum", n=group(n))


def km(lang: str, n: int) -> str:
    return t(lang, "fmt.km", n=group(n))


def date_short(lang: str, day: int) -> str:
    y, m, d = civil(day)
    return t(lang, "fmt.day", d=d, month=t(lang, f"month.{m}"))


def date_full(lang: str, day: int) -> str:
    y, m, d = civil(day)
    return f"{d:02d}.{m:02d}.{y}"


def when_day(lang: str, day: int, today: int) -> str:
    """ "bugun", "ertaga", "4-dekabr (11 kundan keyin)", "3 kun oldin"."""
    gap = day - today
    if gap == 0:
        return t(lang, "when.today")
    if gap == 1:
        return t(lang, "when.tomorrow")
    if gap < 0:
        return t(lang, "when.ago", n=-gap, date=Raw(date_short(lang, day)))
    return t(lang, "when.in", n=gap, date=Raw(date_short(lang, day)))


def item_name(lang: str, item: str, season: str | None = None) -> str:
    return t(lang, f"item.{item}_{season}" if season else f"item.{item}")


def due_line(lang: str, st: dict, today: int) -> str:
    """The one sentence for a plan item, used by the plan, the reminders and the passport alike."""
    name = Raw(f"<b>{item_name(lang, st['id'], st.get('season'))}</b>")
    if st["state"] == "unknown":
        return t(lang, "due.unknown", name=name)
    if st["km_left"] is not None and st["basis"] == "km":
        if st["km_left"] <= 0:
            return t(lang, "due.over_km", name=name, km=Raw(km(lang, -st["km_left"])))
        if st["due_day"] is None:
            return t(lang, "due.left_km", name=name, km=Raw(km(lang, st["km_left"])))
        return t(lang, "due.left", name=name, km=Raw(km(lang, st["km_left"])), when=Raw(when_day(lang, st["due_day"], today)))
    if st["days_left"] is not None and st["days_left"] < 0:
        return t(lang, "due.late", name=name, n=-st["days_left"])
    return t(lang, "due.date", name=name, when=Raw(when_day(lang, st["due_day"], today)))


def car_line(lang: str, card: dict) -> str:
    parts = [card["title"]]
    if card.get("plate"):
        parts.append(card["plate"])
    return " · ".join(parts)


def fuel(lang: str, f: str) -> str:
    return t(lang, f"fuel.{f}")
