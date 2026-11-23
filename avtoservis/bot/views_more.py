"""Bot screens for the Servis pasporti, the workshop panel, the admin and the messages the bot sends on its own
(reminders, "Tasdiqlaysizmi?", decisions, invitations)."""

from __future__ import annotations

import html

from ..core.clock import local_day
from ..i18n import Raw, car_line, date_full, date_short, due_line, item_name, km, money, t
from .views import DOT, Rows, back, items_text, record_line


def passport_links(cfg, tok: str) -> str:
    """The buyer's link: the web page when the Mini App has a public address, and the bot deep link."""
    out = []
    if cfg.webapp_url:
        out.append(f"{cfg.webapp_url}#p={tok}")
    out.append(f"https://t.me/{cfg.bot_username}?start=p_{tok}")
    return "\n".join(out)


def passport(lang: str, v: dict, shares: list[dict]) -> tuple[str, Rows]:
    cid = v["car"]["id"]
    lines = [t(lang, "pass.head", title=v["car"]["title"]), t(lang, "pass.body"), ""]
    if shares:
        lines.append(t(lang, "pass.active"))
        lines += [t(lang, "pass.line", id=s["id"], until=date_short(lang, local_day(s["expires_at"])),
                    owner=t(lang, "pass.with_owner") if s["show_owner"] else "") for s in shares]
    else:
        lines.append(t(lang, "pass.none"))
    rows: Rows = [[(t(lang, "btn.share", n=n), f"gn:{cid}:{n}:0") for n in (7, 30, 90)],
                  [(t(lang, "btn.share_owner"), f"gn:{cid}:30:1")]]
    rows += [[(t(lang, "btn.revoke", id=s["id"]), f"gr:{cid}:{s['id']}")] for s in shares]
    return "\n".join(lines), [*rows, back(lang, f"c:{cid}")]


def passport_made(lang: str, cfg, made: dict) -> str:
    return t(lang, "pass.made", until=date_short(lang, local_day(made["expires_at"])), link=passport_links(cfg, made["token"]))


def passport_card(lang: str, p: dict, tok: str) -> tuple[str, Rows]:
    """What a buyer who opened the deep link sees in the bot (the full page opens in the Mini App)."""
    check = t(lang, "pass.check_ok") if p["check"]["ok"] else t(lang, "pass.check_bad", n=p["check"]["back"])
    last = p["last"]
    text = t(lang, "pass.bot", title=car_line(lang, p["car"]), check=check, verified=p["verified"], self=p["self"],
             km=Raw(km(lang, last["km"])), date=date_short(lang, last["day"]))
    lines = [text, ""] + [f"{DOT[s['state']]} {due_line(lang, s, p['today'])}" for s in p["next"][:4]]
    return "\n".join(lines), [[(t(lang, "btn.open_passport"), f"@app#p={tok}")], [(t(lang, "btn.menu"), "n:menu")]]


def ws_home(lang: str, h: dict) -> tuple[str, Rows]:
    lines = [t(lang, "ws.head", name=h["workshop"]["name"], cars=len(h["cars"]), due=len(h["due"])), ""]
    rows: Rows = [[(t(lang, "btn.open_code"), "w:code")], [(t(lang, "btn.clients"), "w:cars")]]
    if not h["due"]:
        lines.append(t(lang, "ws.due_none"))
    for d in h["due"][:8]:
        lines.append(f"{DOT[d['status']['state']]} {car_line(lang, d['car'])}: {due_line(lang, d['status'], h['today'])}"
                     + (" ✉️" if d["invited"] else ""))
        if not d["invited"]:
            rows.append([(t(lang, "btn.invite", car=d["car"]["title"], item=item_name(lang, d["status"]["id"])),
                          f"wi:{d['car']['id']}:{d['status']['id']}")])
    return "\n".join(lines), [*rows, back(lang)]


def ws_cars(lang: str, h: dict) -> tuple[str, Rows]:
    rows: Rows = [[(f"🚗 {car_line(lang, c)}", f"wc:{c['id']}")] for c in h["cars"][:20]]
    return t(lang, "ws.clients"), [*rows, back(lang, "w:home")]


def ws_car(lang: str, v: dict) -> tuple[str, Rows]:
    c = v["car"]
    plate = f" · {c['plate']}" if c["plate"] else ""
    lines = [t(lang, "ws.car", title=c["title"], plate=plate, km=Raw(km(lang, c["odo"]))), ""]
    lines += [f"{DOT[s['state']]} {due_line(lang, s, v['today'])}" for s in v["statuses"][:5]]
    if v["records"]:
        lines += ["", t(lang, "ws.mine")] + [record_line(lang, r) for r in v["records"][:5]]
    return "\n".join(lines), [[(t(lang, "btn.ws_log"), f"wr:{c['id']}")], back(lang, "w:home")]


def admin(lang: str, counts: dict) -> tuple[str, Rows]:
    return t(lang, "admin.head", **counts), [[(t(lang, "btn.make_link"), "x:link")], back(lang)]


# ── messages the bot sends on its own ──
def remind(lang: str, v: dict, items: list[dict], ask: bool) -> tuple[str, Rows]:
    cid, today = v["car"]["id"], v["today"]
    wanted = {i["id"] for i in items}
    lines = [f"{DOT[s['state']]} {due_line(lang, s, today)}" for s in v["statuses"] if s["id"] in wanted]
    if ask and not lines:
        text = t(lang, "notify.ask", car=car_line(lang, v["car"]), days=today - v["points"][-1][0])
    else:
        text = t(lang, "notify.remind", car=car_line(lang, v["car"]), lines=Raw("\n".join(lines))) + "\n\n" + t(lang, "notify.remind_tail")
    rows: Rows = []
    if v["car"]["odo"] > v["points"][-1][1]:
        rows.append([(t(lang, "btn.km_ok", km=km(lang, v["car"]["odo"])), f"r:{cid}:{v['car']['odo']}")])
    rows += [[(t(lang, "btn.km_other"), f"c:{cid}:km")], [(t(lang, "btn.car"), f"c:{cid}")]]
    return text, rows


def confirm(lang: str, r: dict, title: str) -> tuple[str, Rows]:
    note = f"\n📝 {html.escape(r['note'], quote=False)}" if r["note"] else ""
    text = t(lang, "notify.confirm", shop=r["shop"], car=title, km=Raw(km(lang, r["km"])), date=date_full(lang, r["day"]),
             items=items_text(lang, r["items"]), labour=Raw(money(lang, r["labour"])), parts=Raw(money(lang, r["parts"])),
             total=Raw(money(lang, r["total"])), note=Raw(note))
    rid = r["id"]
    return text, [[(t(lang, "btn.yes"), f"ok:{rid}:y")], [(t(lang, "btn.yes_allow"), f"ok:{rid}:a")], [(t(lang, "btn.no"), f"ok:{rid}:n")]]


def decided(lang: str, yes: bool, title: str, items: list[str]) -> str:
    return t(lang, "notify.decided_yes" if yes else "notify.decided_no", car=title, items=items_text(lang, items))


def invite(lang: str, shop: dict, v: dict, item: str) -> tuple[str, Rows]:
    st = next(s for s in v["statuses"] if s["id"] == item)
    text = t(lang, "notify.invite", shop=shop["name"], address=shop["address"], line=Raw(due_line(lang, st, v["today"])))
    cid = v["car"]["id"]
    return text, [[(t(lang, "btn.no_invites"), f"ka:{cid}:{shop['id']}:0")], [(t(lang, "btn.car"), f"c:{cid}")]]
