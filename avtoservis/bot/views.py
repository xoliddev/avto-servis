"""The owner's bot screens as (text, rows of (label, callback data)). No I/O here: handlers fetch the data from the
service and pass it in. demo/bot-views.js draws the same screens in the browser demo."""

from __future__ import annotations

import html

from ..core import plan as planlib
from ..i18n import Raw, car_line, date_short, due_line, item_name, km, money, t, when_day

Rows = list[list[tuple[str, str]]]
DOT = {"due": "🔴", "soon": "🟠", "ok": "🟢", "unknown": "⚪"}


def back(lang: str, data: str = "n:menu") -> list[tuple[str, str]]:
    return [(t(lang, "btn.back"), data)]


def menu(lang: str, cars: list[dict], roles: dict, hello: bool = False) -> tuple[str, Rows]:
    lines = [t(lang, "bot.hello" if hello else "bot.menu"), ""]
    if cars:
        lines.append(t(lang, "bot.cars"))
        for c in cars:
            tail = t(lang, "bot.attention", n=c["attention"]) if c["attention"] else t(lang, "bot.all_ok")
            lines.append(f"• {html.escape(car_line(lang, c), quote=False)} — {tail}")
    else:
        lines.append(t(lang, "bot.no_cars"))
    rows: Rows = [[(f"🚗 {c['title']}", f"c:{c['id']}")] for c in cars]
    rows.append([(t(lang, "btn.add_car"), "a:new")])
    if roles.get("workshop"):
        rows.append([(t(lang, "btn.workshop"), "w:home")])
    if roles.get("admin"):
        rows.append([(t(lang, "btn.admin"), "x:home")])
    rows.append([(t(lang, "btn.app"), "@app#"), (t(lang, "btn.lang"), "n:lang")])
    return "\n".join(lines), rows


def per_day(lang: str, fc: dict) -> str:
    return t(lang, "fmt.per_day", n=fc["rate"] // 1000)


def car(lang: str, v: dict, n_lines: int = 4) -> tuple[str, Rows]:
    c, cid, today = v["car"], v["car"]["id"], v["today"]
    last = v["points"][-1]
    plate = f" · {c['plate']}" if c["plate"] else ""
    lines = [t(lang, "car.head", title=c["title"], plate=plate),
             t(lang, "car.odo", km=Raw(km(lang, last[1])), when=Raw(when_day(lang, last[0], today)), per_day=per_day(lang, v["fc"])), ""]
    if v["fc"]["n"] == 0:
        lines += [t(lang, "car.default_rate"), ""]
    lines.append(t(lang, "car.next"))
    lines += [f"{DOT[s['state']]} {due_line(lang, s, today)}" for s in v["statuses"][:n_lines]]
    if v["pending"]:
        lines += ["", t(lang, "car.pending", n=len(v["pending"]))]
    rows: Rows = [[(t(lang, "btn.km"), f"c:{cid}:km")],
                  [(t(lang, "btn.plan"), f"p:{cid}"), (t(lang, "btn.history"), f"h:{cid}")],
                  [(t(lang, "btn.log"), f"s:{cid}"), (t(lang, "btn.stats"), f"e:{cid}")],
                  [(t(lang, "btn.code"), f"k:{cid}"), (t(lang, "btn.passport"), f"g:{cid}")],
                  [(t(lang, "btn.chart"), f"@app#c={cid}")], back(lang)]
    return "\n".join(lines), rows


def km_ask(lang: str, v: dict) -> tuple[str, Rows]:
    """Typed odometer, plus one tap on today's estimate."""
    c, last, odo = v["car"], v["points"][-1], v["car"]["odo"]
    rows: Rows = []
    if odo > last[1]:
        rows.append([(t(lang, "btn.km_ok", km=km(lang, odo)), f"r:{c['id']}:{odo}")])
    rows.append(back(lang, f"c:{c['id']}"))
    return t(lang, "km.ask", title=c["title"], km=Raw(km(lang, last[1]))), rows


def jump(lang: str, cid: int, ask: dict) -> tuple[str, Rows]:
    return (t(lang, "km.jump", days=ask["days"], km=Raw(km(lang, ask["km"])), per_day=ask["per_day"]),
            [[(t(lang, "btn.confirm_jump"), f"rj:{cid}:{ask['km']}")], back(lang, f"c:{cid}")])


def plan(lang: str, v: dict) -> tuple[str, Rows]:
    cid, today = v["car"]["id"], v["today"]
    lines = [t(lang, "plan.head", title=v["car"]["title"]), t(lang, "plan.legend"), ""]
    lines += [f"{DOT[s['state']]} {due_line(lang, s, today)}" for s in v["statuses"]]
    if v["off"]:
        lines += ["", t(lang, "plan.off", list=", ".join(item_name(lang, s["id"], s.get("season")) for s in v["off"]))]
    names = [(item_name(lang, s["id"], s.get("season")), f"i:{cid}:{s['id']}") for s in v["statuses"] + v["off"]]
    rows: Rows = [names[i:i + 2] for i in range(0, len(names), 2)]
    rows.append(back(lang, f"c:{cid}"))
    return "\n".join(lines), rows


def interval_text(lang: str, st: dict) -> str:
    parts = []
    if st["km_iv"]:
        parts.append(t(lang, "item.iv_km", km=Raw(km(lang, st["km_iv"]))))
    if st["months"]:
        parts.append(t(lang, "item.iv_months", n=st["months"]))
    return t(lang, "item.iv_or").join(parts)


def item(lang: str, v: dict, item_id: str) -> tuple[str, Rows]:
    cid, today = v["car"]["id"], v["today"]
    off = any(s["id"] == item_id for s in v["off"])
    st = next(s for s in v["statuses"] + v["off"] if s["id"] == item_id)
    lines = [t(lang, "item.head", name=item_name(lang, st["id"], st.get("season"))), due_line(lang, st, today)]
    if not st.get("season"):
        lines.append(t(lang, "item.interval", iv=Raw(interval_text(lang, st))))
    what = [km(lang, st["last_km"])] if st["last_km"] is not None else []
    if st["last_day"] is not None:
        what.append(date_short(lang, st["last_day"]))
    if what and not st.get("season"):
        lines.append(t(lang, "item.last_guess" if st["guess"] else "item.last", what=", ".join(what)))
    elif not st.get("season"):
        lines.append(t(lang, "item.never"))
    rows: Rows = [[(t(lang, "btn.today_done"), f"id:{cid}:{item_id}")]]
    if st["months"] and not st["km_iv"]:
        rows.append([(t(lang, "btn.expires"), f"ie:{cid}:{item_id}")])
    rows.append([(t(lang, "btn.on" if off else "btn.off"), f"io:{cid}:{item_id}")])
    rows.append(back(lang, f"p:{cid}"))
    return "\n".join(lines), rows


def add_models(lang: str, models: list[dict]) -> tuple[str, Rows]:
    btns = [(m["name"] or t(lang, "model.other"), f"a:m:{m['id']}") for m in models]
    return t(lang, "add.model"), [btns[i:i + 2] for i in range(0, len(btns), 2)] + [back(lang)]


def add_years(lang: str, model: dict, this_year: int) -> tuple[str, Rows]:
    top = min(model.get("to", this_year), this_year)
    years = [y for y in range(top, max(model["from"], top - 11) - 1, -1)]
    btns = [(str(y), f"a:y:{y}") for y in years]
    rows: Rows = [btns[i:i + 4] for i in range(0, len(btns), 4)]
    if model["from"] < top - 11:
        rows.append([(t(lang, "add.other_year"), "a:y:x")])
    return t(lang, "add.year"), [*rows, back(lang, "a:new")]


def add_fuels(lang: str, model: dict) -> tuple[str, Rows]:
    return t(lang, "add.fuel"), [[(t(lang, f"fuel.{f}"), f"a:f:{f}") for f in model["fuels"]], back(lang, "a:new")]


def add_usage(lang: str) -> tuple[str, Rows]:
    return t(lang, "add.usage"), [[(t(lang, "btn.shaxsiy"), "a:u:shaxsiy"), (t(lang, "btn.taksi"), "a:u:taksi")], back(lang, "a:new")]


def skip(lang: str, data: str = "a:skip", back_to: str = "n:menu") -> Rows:
    return [[(t(lang, "btn.skip"), data)], back(lang, back_to)]


def log_items(lang: str, v: dict, chosen: list[str], prefix: str = "st") -> tuple[str, Rows]:
    btns = [(("☑️ " if s["id"] in chosen else "▫️ ") + item_name(lang, s["id"]), f"{prefix}:{s['id']}")
            for s in sorted(v["statuses"] + v["off"], key=lambda s: planlib.STATE_ORDER[s["state"]])]
    rows: Rows = [btns[i:i + 2] for i in range(0, len(btns), 2)]
    if chosen:
        rows.append([(t(lang, "btn.continue"), f"{prefix}:ok")])
    rows.append(back(lang, f"c:{v['car']['id']}" if prefix == "st" else f"wc:{v['car']['id']}"))
    return t(lang, "log.items", title=v["car"]["title"]), rows


def items_text(lang: str, items: list[str]) -> str:
    return ", ".join(item_name(lang, i) for i in items)


def record_line(lang: str, r: dict) -> str:
    line = t(lang, "hist.line", date=date_short(lang, r["day"]), km=Raw(km(lang, r["km"])), items=items_text(lang, r["items"]),
             total=Raw(money(lang, r["total"])))
    if r["status"] == "pending":
        badge = t(lang, "hist.pending", shop=r["shop"])
    elif r["verified"]:
        badge = t(lang, "hist.verified", shop=r["shop"])
    else:
        badge = t(lang, "hist.self")
    return f"{line}\n   {badge}"


def history(lang: str, cid: int, title: str, recs: list[dict]) -> tuple[str, Rows]:
    lines = [t(lang, "hist.head", title=title), ""]
    lines += [record_line(lang, r) for r in recs[:12]] or [t(lang, "hist.empty")]
    rows: Rows = [[(f"{t(lang, 'btn.receipt')} · {date_short(lang, r['day'])}", f"hp:{r['id']}")] for r in recs[:12] if r["photo"]]
    rows += [[(t(lang, "btn.csv"), f"hx:{cid}")], back(lang, f"c:{cid}")]
    return "\n".join(lines), rows


def stats(lang: str, cid: int, s: dict) -> tuple[str, Rows]:
    lines = [t(lang, "stats.head", title=s["car"]["title"]), ""]
    if not s["n"]:
        lines.append(t(lang, "stats.none"))
    else:
        lines += [t(lang, "stats.total", total=Raw(money(lang, s["total"])), n=s["n"]),
                  t(lang, "stats.split", labour=Raw(money(lang, s["labour"])), parts=Raw(money(lang, s["parts"])))]
        if s["per_km"] is not None:
            lines.append(t(lang, "stats.per_km", per_km=Raw(t(lang, "fmt.per_km", n=s["per_km"])), km=Raw(km(lang, s["km"]))))
        months = [m for m in s["months"][-6:] if m["total"]]
        if months:
            lines += ["", t(lang, "stats.months")]
            lines += ["• " + t(lang, "month." + str(m["m"])) + f" {m['y']}: {money(lang, m['total'])}" for m in months]
        lines += ["", t(lang, "stats.items")]
        lines += [f"• {item_name(lang, i['id'])}: {money(lang, i['total'])}" for i in s["items"][:5]]
    return "\n".join(lines), [[(t(lang, "btn.csv"), f"hx:{cid}")], back(lang, f"c:{cid}")]


def code_link(bot_username: str, code: str) -> str:
    return f"https://t.me/{bot_username}?start=c_{code.replace('-', '')}"


def code(lang: str, v: dict, bot_username: str) -> tuple[str, Rows]:
    cid = v["car"]["id"]
    lines = [t(lang, "code.head", title=v["car"]["title"]),
             t(lang, "code.body", code=v["car"]["code"], link=code_link(bot_username, v["car"]["code"])), ""]
    lines.append(t(lang, "code.shops") if v["shops"] else t(lang, "code.no_shops"))
    rows: Rows = [[(t(lang, "btn.new_code"), f"kr:{cid}")]]
    for s in v["shops"]:
        lines.append(f"• {s['name']}")
        rows.append([(t(lang, "btn.allow_on" if s["allow"] else "btn.allow_off", name=s["name"]),
                      f"ka:{cid}:{s['workshop_id']}:{0 if s['allow'] else 1}"),
                     (t(lang, "btn.shop_remove", name=s["name"]), f"kd:{cid}:{s['workshop_id']}")])
    return "\n".join(lines), [*rows, back(lang, f"c:{cid}")]

