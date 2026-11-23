"""The fictional world of the demo (and of ``SEED_DEMO=1``), always relative to "today", so it works on any date.

Jasur's two-year-old Nexia 3 with its readings and records (workshop-confirmed and self-logged), six other drivers
whose cars visit Turbo Servis, and three workshops. People have negative ids: Telegram user ids are positive, so
nobody can sign in as them. Everything is derived from FNV-1a hashes of fixed strings: shared/seedgen.js builds the
very same world, checked by shared/test_vectors.json.
"""

from __future__ import annotations

from .cars import model as find_model
from .clock import add_months, local_day
from .plan import default_last, items_for
from .text import h32

DRIVER, MASTER, BUYER, ADMIN = -101, -201, -301, -901
MASTER2, MASTER3 = -202, -203
NEXIA = 1
LEFTS = (350, 620, 1500, 2600, 3900, 4800)  # km left to the next oil change today, per other driver
SELF_SHOP = ""


def rnd(seed: str, lo: int, hi: int) -> int:
    return lo + h32(seed) % (hi - lo + 1)


def track(cid: int, start_day: int, start_km: int, daily: int, today: int) -> list[list[int]]:
    """Odometer readings every 6..16 days, 70..130 % of the usual daily km; the last one 1..3 days ago."""
    out = [[start_day, start_km]]
    day, km, k = start_day, start_km, 0
    while True:
        gap = rnd(f"gap:{cid}:{k}", 6, 16)
        if day + gap > today - 4:
            break
        day += gap
        km += daily * gap * rnd(f"km:{cid}:{k}", 70, 130) // 100
        out.append([day, km])
        k += 1
    last = today - rnd(f"last:{cid}", 1, 3)
    out.append([last, km + daily * (last - day)])
    return out


def cost(plan: dict, items: list[str], seed: str) -> tuple[int, int]:
    prices = {it["id"]: it["price"] for it in plan["items"]}
    pct = rnd(seed, 92, 112)
    labour = sum(prices[i][0] for i in items) * pct // 100 // 1000 * 1000
    parts = sum(prices[i][1] for i in items) * pct // 100 // 1000 * 1000
    return labour, parts


def oil_records(car: dict, pts: list, plan: dict, plan_items: list[dict], left: int, daily: int) -> list[dict]:
    """Oil changes placed back from today so that ``left`` km remain; filters, pads and plugs now and then."""
    ids = {it["id"]: it for it in plan_items}
    if "motor_moyi" not in ids:
        return []
    step = min(ids["motor_moyi"]["km"], daily * 180 // 100 * 100)
    marks, km = [], pts[-1][1] - step + left
    while km > pts[0][1] + 300:
        marks.append(km)
        km -= step
    out = []
    for i, km in enumerate(reversed(marks)):
        day = max(d for d, k in pts if k <= km)
        items = ["motor_moyi", "moy_filtri"] + (["havo_filtri", "salon_filtri"] if i % 2 == 1 else [])
        items += ["tormoz_kolodka"] if i % 4 == 3 else []
        items += ["svecha"] if i % 4 == 2 else []
        items = [x for x in ids if x in items]
        labour, parts = cost(plan, items, f"cost:{car['id']}:{i}")
        mine = i % 3 == 2
        out.append({"car_id": car["id"], "day": day, "km": km, "items": items, "labour": 0 if mine else labour, "parts": parts,
                    "shop": SELF_SHOP if mine else "", "workshop_id": None if mine else car["shop"],
                    "by": car["owner"] if mine else car["master"], "note": ""})
    return out


def world(people: dict, models: list[dict], plan: dict, now: int) -> dict:
    today = local_day(now)
    users = [{"id": DRIVER, **people["driver"]}, {"id": MASTER, **people["master"]}, {"id": BUYER, **people["buyer"]},
             {"id": ADMIN, "name": people["admin"]["name"], "phone": ""}]
    masters = [MASTER, MASTER2, MASTER3]
    users += [{"id": MASTER2, "name": "Otabek Nurmatov", "phone": ""}, {"id": MASTER3, "name": "Sanjar Xolmatov", "phone": ""}]
    shops = [{"id": i + 1, "owner": masters[i], **w} for i, w in enumerate(people["workshops"])]
    specs = [{**people["nexia"], "owner": DRIVER, "age": 730, "left": 2600, "shop": 1}]
    for i, o in enumerate(people["owners"]):
        users.append({"id": -102 - i, "name": o["name"], "phone": ""})
        specs.append({**o, "owner": -102 - i, "age": 420 - i * 37, "left": LEFTS[i], "shop": 2 if i in (3, 5) else 1})
    cars, readings, records, rows, access = [], [], [], [], []
    for n, sp in enumerate(specs):
        cid = n + 1
        start = today - sp["age"]
        car = {"id": cid, "owner": sp["owner"], "model": sp["model"], "name": "", "year": sp["year"], "fuel": sp["fuel"],
               "usage": sp["usage"], "plate": sp["plate"], "created_day": start, "code": f"SEED{cid:04d}",
               "shop": sp["shop"], "master": masters[sp["shop"] - 1]}
        pts = track(cid, start, sp["start_km"], sp["daily"], today)
        plan_items = items_for(plan, find_model(models, sp["model"]), sp["fuel"], sp["usage"])
        recs = oil_records(car, pts, plan, plan_items, sp["left"], sp["daily"])
        if cid == NEXIA:
            recs += extra_nexia(car, pts, plan, today)
        done = {i for r in recs for i in r["items"]}
        for it in plan_items:
            last = default_last(it, sp["start_km"], start, None)
            seed = f"last:{cid}:{it['id']}"
            if it["calendar"]:
                day = add_months(today + 12, -12) if (cid, it["id"]) == (NEXIA, "osago") else today - rnd(seed, 40, 330)
                last = {"km": None, "day": day, "guess": False}
            elif it["id"] not in done and not it["season"]:
                km = max(0, pts[-1][1] - it["km"] * rnd(seed, 10, 60) // 100) if it["km"] else None
                last = {"km": km, "day": today - rnd(f"day:{cid}:{it['id']}", 20, 300), "guess": False}
            rows.append({"car_id": cid, "item": it["id"], "last_km": last["km"], "last_day": last["day"], "guess": last["guess"]})
        recs.sort(key=lambda r: (r["day"], r["km"]))
        readings += [{"car_id": cid, "day": d, "km": k} for d, k in pts]
        records += recs
        access.append({"car_id": cid, "workshop_id": sp["shop"], "allow": cid in (2, 3, 4, 6), "since_day": start})
        if cid == NEXIA:
            access.append({"car_id": cid, "workshop_id": 2, "allow": False, "since_day": start + 200})
        cars.append({k: v for k, v in car.items() if k not in ("shop", "master")})
    for i, r in enumerate(records):
        r["id"] = i + 1
    return {"today": today, "users": users, "workshops": shops, "cars": cars, "readings": readings, "records": records,
            "items": rows, "access": access}


def extra_nexia(car: dict, pts: list, plan: dict, today: int) -> list[dict]:
    """A battery bought by Jasur himself, an antifreeze change at Avto Doktor."""
    out = []
    for item, back, shop in (("akkumulyator", 300, None), ("antifriz", 250, 2)):
        day = max(d for d, _ in pts if d <= today - back)
        km = max(k for d, k in pts if d == day)
        labour, parts = cost(plan, [item], f"extra:{item}")
        out.append({"car_id": car["id"], "day": day, "km": km, "items": [item], "labour": 0 if shop is None else labour,
                    "parts": parts, "shop": SELF_SHOP, "workshop_id": shop, "by": car["owner"] if shop is None else MASTER2,
                    "note": ""})
    return out
