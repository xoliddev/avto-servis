"""Regenerate shared/test_vectors.json from the Python core.

pytest checks that the file is up to date (so the Python core and the vectors never drift apart), and
``node --test`` checks the JS port against the very same vectors.

    python scripts/make_vectors.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from avtoservis import i18n  # noqa: E402
from avtoservis.base import compute  # noqa: E402
from avtoservis.core import cars, clock, forecast, odometer, plan, records, reminders, seedgen, stats, text, token  # noqa: E402

OUT = ROOT / "shared" / "test_vectors.json"
NOW = 1_795_000_000_000  # 2026-11-18 16:06 in Tashkent, a Wednesday
NYE = 1_798_736_400_000  # 2026-12-31 22:00 in Tashkent
TODAY = clock.local_day(NOW)


def load(name: str):
    with open(ROOT / "shared" / "data" / f"{name}.json", encoding="utf-8") as fh:
        return json.load(fh)


def res(fn, *args):
    try:
        return {"ok": fn(*args)}
    except text.InputError as e:
        return {"error": e.code}


def basics(v: dict) -> None:
    v["civil"] = [{"day": d, "out": list(clock.civil(d)), "back": clock.days_from_civil(*clock.civil(d))}
                  for d in (0, 59, 365, 11_016, 20_775, 20_818, 20_819, 21_184, -1, -719_468)]
    v["add_months"] = [{"day": d, "n": n, "out": clock.add_months(d, n)} for d in (20_484, 20_513, 20_819, 20_775) for n in (-12, -1, 1, 6, 13)]
    v["parse_date"] = [{"in": s, "out": clock.parse_date(s)} for s in
                       ("12.11.2026", "1/3/2027", "29.02.2027", "29-02-2028", "31.04.2026", "12.11.26", "12.11", "", "a.b.c", 5)]
    v["clean"] = [{"in": s, "n": n, "out": text.clean(s, n)} for s, n in (("  a \t b\n", 10), ("abc" + chr(0x202E) + "def", 20),
                                                                           ("x" * 20, 5), (None, 5), ("😀😀😀", 2))]
    v["whole"] = [{"in": x, "out": res(text.whole, x, 1, 5, "n")} for x in (1, 5, 0, 6, "3", "", "x", True, 2.5, None)]
    v["h32"] = [{"in": s, "out": text.h32(s)} for s in ("", "a", "gap:1:0", "Jasur Karimov", "мотор")]
    v["split"] = [{"t": t, "n": n, "out": stats.split(t, n)} for t, n in ((100, 3), (465_000, 2), (0, 4), (7, 1), (5, 0))]


def car_rules(v: dict) -> None:
    models = load("models")
    base = {"model": "cobalt", "year": 2021, "fuel": "metan", "usage": "shaxsiy", "odo": "86900", "plate": "01a123bc", "last_oil": 80900}
    tries = [base, {**base, "plate": "01 123 abc"}, {**base, "plate": "AA 123"}, {**base, "year": 2030}, {**base, "fuel": "elektr"},
             {**base, "odo": -1}, {**base, "last_oil": 90000}, {**base, "model": "x"}, {**base, "model": "other", "name": " Lada  "},
             {**base, "model": "other", "name": "L"}, {**base, "usage": "kran"}, {**base, "model": "nexia3", "year": 2022}, "x"]
    v["car"] = [{"in": d, "out": res(cars.validate, d, models, 2026)} for d in tries]
    v["code"] = [{"n": n, "out": cars.code_from(n)} for n in (0, 1, 2**40 - 1, 123_456_789_012)]
    v["norm_code"] = [{"in": s, "out": cars.norm_code(s)} for s in ("abcd-ef23", "ABCD EF23", "ABCDEF2", "ABCDEF20", 12, "ab cd ef 23 ")]
    v["title"] = [cars.title(models, {"model": m, "name": n, "year": 2020}) for m, n in (("cobalt", ""), ("other", "Lada Vesta"))]


def forecasting(v: dict) -> None:
    cases = [[[TODAY, 86_900]], [[TODAY - 5, 86_900], [TODAY, 87_160]],
             [[TODAY - 40, 50_000], [TODAY - 30, 50_400], [TODAY - 21, 50_800], [TODAY - 9, 51_300], [TODAY - 2, 51_700], [TODAY, 51_790]],
             [[TODAY - 3, 1000], [TODAY - 3, 1200], [TODAY, 1500], [TODAY - 1, 1300]], [[TODAY - 10, 500], [TODAY, 500]],
             [[TODAY - 300 + 7 * i, 10_000 + i * 300 + (i % 3) * 90] for i in range(30)]]
    v["forecast"] = []
    for pts in cases:
        fc = forecast.estimate(pts, 45)
        v["forecast"].append({"in": pts, "fc": fc, "odo": [forecast.odo_on(fc, TODAY + d) for d in (0, 1, 30)],
                              "day_for": [forecast.day_for(fc, fc["km"] + k, r) for k in (-5, 0, 1, 600, 10_000) for r in
                                          (fc["rate"], fc["lo"], fc["hi"], 0)]})
    v["check"] = [{"in": [last, day, km, conf], "out": res(odometer.check, last, day, km, conf, 1500)} for last, day, km, conf in
                  ((None, TODAY, 100, False), ([TODAY - 2, 87_160], TODAY, 87_029, False), ([TODAY - 2, 87_160], TODAY, 90_200, False),
                   ([TODAY - 2, 87_160], TODAY, 90_000, True), ([TODAY, 5], TODAY, 1505, False), ([TODAY, 5], TODAY, 1506, False),
                   ([TODAY, 5], TODAY, "x", False), ([TODAY, 5], TODAY, 2_000_001, False))]
    pts = [[TODAY - 20, 100], [TODAY - 10, 400], [TODAY, 900]]
    v["fits"] = [{"day": d, "km": k, "out": res(odometer.fits, pts, d, k)} for d, k in
                 ((TODAY - 15, 300), (TODAY - 15, 50), (TODAY - 15, 450), (TODAY - 10, 401), (TODAY + 1, 950), (TODAY - 30, 90))]
    v["consistency"] = [odometer.consistency(p, 1500) for p in (pts, [], [[1, 5]], [[1, 5], [2, 4], [3, 9000]])]


def planning(v: dict) -> None:
    cfg, models = load("plan"), load("models")
    v["interval"] = [{"item": it["id"], "fuel": f, "usage": u, "out": list(plan.interval(it, f, u))}
                     for it in cfg["items"] for f in ("benzin", "metan") for u in ("shaxsiy", "taksi")]
    v["items_for"] = [{"model": m, "fuel": f, "usage": u, "out": plan.items_for(cfg, cars.model(models, m), f, u,
                                                                                  {"motor_moyi": {"km": 7000, "months": None, "off": 0}})}
                      for m, f, u in (("cobalt", "metan", "shaxsiy"), ("malibu", "benzin", "taksi"), ("byd_song", "elektr", "shaxsiy"))]
    v["season"] = [{"day": d, "out": list(plan.next_season([[11, 15], [3, 15]], d))} for d in (20_772, 20_773, 20_774, 20_892, 20_893, 20_818)]
    fc = forecast.estimate([[TODAY - 5, 86_900], [TODAY, 87_160]], 45)
    items = plan.items_for(cfg, cars.model(models, "cobalt"), "metan", "shaxsiy")
    lasts = ({"km": 80_900, "day": TODAY - 5, "guess": False}, {"km": 86_000, "day": TODAY - 200, "guess": True},
             {"km": None, "day": None, "guess": True}, {"km": None, "day": TODAY - 340, "guess": False},
             {"km": 70_000, "day": TODAY - 30, "guess": False})
    v["status"] = [{"it": it, "last": la, "fc": fc, "out": plan.status(it, la, fc, TODAY, cfg)} for it in items for la in lasts
                   if (it["km"] is not None) == (la["km"] is not None)]
    v["default_last"] = [{"it": it, "out": plan.default_last(it, 86_900, TODAY, lo)} for it in items for lo in (None, 80_900)]
    v["override"] = [{"in": [km, mo], "out": res(plan.check_override, cfg["items"][0], km, mo)} for km, mo in
                     ((7000, None), ("6000", 4), (100, None), (None, None), (None, 200))]


def history(v: dict) -> None:
    allowed = ["motor_moyi", "moy_filtri", "havo_filtri"]
    tries = [{"items": ["moy_filtri", "motor_moyi"], "km": 87_290, "labour": 60_000, "parts": "405000", "note": " Moy 5W-30 ", "day": "today"},
             {"items": [], "km": 1}, {"items": ["x"], "km": 1}, {"items": ["motor_moyi", "motor_moyi"], "km": 1},
             {"items": ["motor_moyi"], "km": 1, "labour": -1}, {"items": ["motor_moyi"], "km": 1, "day": "yesterday", "labour": None},
             {"items": ["motor_moyi"], "km": 1, "day": "01.01.2010"}, {"items": ["motor_moyi"], "km": 1, "day": TODAY + 1}, None]
    v["record"] = [{"in": d, "out": res(records.validate, d, allowed, TODAY)} for d in tries]
    v["day_of"] = [{"in": x, "ahead": a, "out": res(records.day_of, x, TODAY, a)} for x in ("today", "yesterday", "12.11.2026", "1.1.2027",
                                                                                           TODAY - 3651, "x") for a in (0, 365)]
    recs = [{"day": TODAY - 400, "items": ["motor_moyi"], "labour": 40_000, "parts": 300_000},
            {"day": TODAY - 20, "items": ["motor_moyi", "moy_filtri", "havo_filtri"], "labour": 61_000, "parts": 405_000},
            {"day": TODAY, "items": ["shina"], "labour": 80_000, "parts": 0}]
    v["spending"] = [{"recs": recs, "m": m, "out": stats.spending(recs, m, TODAY)} for m in (1, 12)]
    v["per_km"] = [{"t": t, "km": k, "out": stats.per_km(t, k)} for t, k in ((545_000, 390), (1, 99), (6_000_000, 28_697))]
    v["csv"] = {"rows": [["Sana", "Km"], ["=1+1", 'a"b,c'], ["-5", "x;y"], ["@x", "ok"]],
                "out": stats.csv([["Sana", "Km"], ["=1+1", 'a"b,c'], ["-5", "x;y"], ["@x", "ok"]])}


def security(v: dict) -> None:
    secret = token.secret_from("123456:TEST-ONLY")
    nonces = [bytes(range(12)), bytes([255] * 12), b"pasport-0001"]
    v["token"] = {"seed": "123456:TEST-ONLY", "secret": secret.hex(),
                  "made": [{"nonce": n.hex(), "token": token.make(secret, n)} for n in nonces]}
    t0 = v["token"]["made"][0]["token"]
    bad = [t0[:-1] + ("A" if t0[-1] != "A" else "B"), t0[:31], t0 + "x", "!" * 32, None, 5, ""]
    v["token"]["check"] = [{"in": x, "out": token.nonce_of(secret, x)} for x in [t0, *bad]]


def main() -> None:
    v: dict = {"today": TODAY}
    basics(v)
    car_rules(v)
    forecasting(v)
    planning(v)
    history(v)
    security(v)
    cfg = load("plan")
    statuses = v["status"][:6]
    v["keys"] = [{"st": [s["out"] for s in statuses], "today": TODAY, "last": d,
                  "out": reminders.keys_for([s["out"] for s in statuses], TODAY, d, cfg)} for d in (TODAY - 1, TODAY - 14)]
    worlds = {}
    for n in (NOW, NYE):
        w = seedgen.world(load("people"), load("models"), cfg, n)
        car = w["cars"][0]
        recs = [r for r in w["records"] if r["car_id"] == car["id"]]
        rows = [{**r, "km": None, "months": None, "off": 0} for r in w["items"] if r["car_id"] == car["id"]]
        snap = compute(car, rows, [r for r in w["readings"] if r["car_id"] == car["id"]], recs, load("models"), cfg, w["today"])
        worlds[str(n)] = {"world": w, "nexia": snap}
    v["world"] = worlds
    sts = [s["out"] for s in v["status"]] + worlds[str(NYE)]["nexia"]["statuses"]
    v["lines"] = [{"st": s, "today": t, "uz": i18n.due_line("uz", s, t), "ru": i18n.due_line("ru", s, t)}
                  for s in sts for t in (TODAY, worlds[str(NYE)]["world"]["today"]) if s["due_day"] is None or abs(s["due_day"] - t) < 4000]
    v["dates"] = [{"day": d, "today": TODAY, "uz": i18n.when_day("uz", d, TODAY), "ru": i18n.when_day("ru", d, TODAY),
                   "full": i18n.date_full("uz", d)} for d in (TODAY - 3, TODAY, TODAY + 1, TODAY + 13, TODAY + 44)]
    OUT.write_bytes((json.dumps(v, ensure_ascii=False, indent=1) + "\n").encode())
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
