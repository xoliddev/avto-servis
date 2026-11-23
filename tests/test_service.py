"""The story end to end on the service: a new Cobalt, its forecast tightening, the reminder, the workshop's record
and the owner's confirmation, the odometer guard, and who may see what."""

from __future__ import annotations

import pytest

from avtoservis.common import Refused

from .helpers import ADMIN, COBALT, DRIVER, MASTER, MASTER2, NEXIA, OIL, STRANGER, Clock, cobalt, code_of, service_env, st


async def refused(code: str, coro) -> None:
    with pytest.raises(Refused) as err:
        await coro
    assert err.value.code == code


async def test_story_forecast_reminder_workshop_confirm_and_reset():
    clock = Clock(1_795_000_000_000 + 2 * 3_600_000)  # 18:06
    async with service_env(clock) as (svc, _):
        v = await cobalt(svc)
        cid = v["car"]["id"]
        oil = st(v, "motor_moyi")
        assert (oil["km_left"], oil["days_left"], v["fc"]["margin"]) == (800, 18, 45)
        assert v["car"]["plate"] == "01 A 123 BC" and len(v["car"]["code"]) == 9
        assert v["statuses"][-1]["state"] == "unknown", "documents without a date wait at the end"
        clock.skip(days=5)
        v = (await svc.add_reading(DRIVER, cid, "87160"))["view"]
        assert v["fc"]["rate"] == 52_000 and v["fc"]["margin"] == 36
        assert st(v, "motor_moyi")["km_left"] == 540 and st(v, "motor_moyi")["days_left"] == 11
        clock.skip(days=2)
        notes = [n for n in await svc.tick() if n["to"] == DRIVER and n["car_id"] == cid]
        assert notes == [{"type": "remind", "to": DRIVER, "car_id": cid, "ask": False,
                          "items": [{"id": "motor_moyi", "kind": "soon"}, {"id": "moy_filtri", "kind": "soon"}]}]
        assert not [n for n in await svc.tick() if n.get("car_id") == cid], "exactly once"
        assert st(await svc.car_view(DRIVER, cid), "motor_moyi")["km_left"] == 436
        ws = await svc.open_car(MASTER, (await code_of(svc, cid)).lower())
        assert ws["car"]["title"] == "Chevrolet Cobalt 2021" and "code" not in ws["car"] and ws["records"] == []
        ws, notes = await svc.ws_record(MASTER, cid, {**OIL, "km": 87_290})
        assert notes == [{"type": "confirm", "to": DRIVER, "record_id": ws["records"][0]["id"], "car_id": cid}]
        assert st(await svc.car_view(DRIVER, cid), "motor_moyi")["km_left"] == 436, "nothing counts before the owner says yes"
        rec, notes = await svc.decide(DRIVER, ws["records"][0]["id"], True, True)
        assert rec["verified"] and rec["shop"] == "Turbo Servis" and rec["total"] == 465_000 and notes[0]["to"] == MASTER
        v = await svc.car_view(DRIVER, cid)
        assert st(v, "motor_moyi")["km_left"] == 6800 and st(v, "motor_moyi")["state"] == "ok"
        assert v["shops"] == [{"workshop_id": 1, "allow": True, "name": "Turbo Servis", "address": "Chilonzor, Bunyodkor ko'chasi 21"}]
        await refused("decided", svc.decide(DRIVER, rec["id"], True))
        await refused("odo_back", svc.add_reading(DRIVER, cid, 87_029))
        hist = await svc.history(DRIVER, cid)
        assert [h["verified"] for h in hist] == [True]


async def test_jumps_ask_to_confirm_and_bad_numbers_are_refused():
    async with service_env() as (svc, clock):
        cid = (await cobalt(svc))["car"]["id"]
        clock.skip(days=1)
        ask = await svc.add_reading(DRIVER, cid, 89_000)
        assert ask == {"confirm": True, "km": 89_000, "per_day": 2100, "days": 1}
        assert (await svc.add_reading(DRIVER, cid, 89_000, True))["view"]["car"]["odo"] == 89_000
        for bad in ("-1", "12.5", "", None, True, 2_000_001, "١٢٣"):
            await refused("odo", svc.add_reading(DRIVER, cid, bad))


async def test_owners_and_workshops_see_only_their_own():
    async with service_env() as (svc, _):
        cid = (await cobalt(svc))["car"]["id"]
        await refused("not_found", svc.car_view(STRANGER, cid))
        await refused("not_found", svc.car_view(DRIVER, 2))
        await refused("not_found", svc.add_reading(STRANGER, cid, 90_000))
        await refused("not_found", svc.ws_car(MASTER, cid))
        await refused("not_found", svc.ws_car(MASTER2, 2)), "another workshop's client"
        await refused("not_found", svc.open_car(DRIVER, "ABCDEFGH")), "only workshops open cars"
        await refused("code", svc.open_car(MASTER, "ZZZZ-ZZZZ"))
        await svc.open_car(MASTER, await code_of(svc, cid))
        assert (await svc.ws_car(MASTER, cid))["records"] == []
        nexia = await svc.ws_car(MASTER, NEXIA)
        assert nexia["records"] and all(r["shop"] == "Turbo Servis" for r in nexia["records"]), "only its own records"
        hist = await svc.history(DRIVER, NEXIA)
        assert {r["shop"] for r in hist if r["verified"]} == {"Turbo Servis", "Avto Doktor"} and any(not r["verified"] for r in hist)


async def test_wrong_codes_are_rate_limited():
    async with service_env() as (svc, _):
        for _ in range(10):
            await refused("code", svc.open_car(MASTER, "ZZZZZZZZ"))
        await refused("rate", svc.open_car(MASTER, "ZZZZZZZZ"))


async def test_invitations_need_permission_and_go_once_per_item():
    async with service_env() as (svc, _):
        home = await svc.ws_home(MASTER)
        assert home["due"] and all(d["car"]["id"] in (2, 3, 4, 6) for d in home["due"])
        first = home["due"][0]
        home, notes = await svc.ws_invite(MASTER, first["car"]["id"], first["status"]["id"])
        assert notes[0]["type"] == "invite" and notes[0]["to"] == first["car"]["id"] + 100
        assert next(d for d in home["due"] if d["status"]["id"] == first["status"]["id"] and d["car"]["id"] == first["car"]["id"])["invited"]
        await refused("invited", svc.ws_invite(MASTER, first["car"]["id"], first["status"]["id"]))
        await refused("not_allowed", svc.ws_invite(MASTER, NEXIA, "motor_moyi"))
        await svc.set_shop(first["car"]["id"] + 100, first["car"]["id"], 1, allow=False)
        assert all(d["car"]["id"] != first["car"]["id"] for d in (await svc.ws_home(MASTER))["due"])


async def test_self_logged_record_stats_csv_and_order_of_records():
    async with service_env() as (svc, clock):
        cid = (await cobalt(svc))["car"]["id"]
        out = await svc.add_record(DRIVER, cid, {"items": ["havo_filtri"], "km": 86_900, "parts": 65_000, "shop": "O'zim"})
        assert st(out["view"], "havo_filtri")["last_km"] == 86_900
        await refused("odo_back", svc.add_record(DRIVER, cid, {"items": ["svecha"], "km": 86_000}))
        clock.skip(days=10)
        await svc.add_reading(DRIVER, cid, 87_400)
        await refused("odo_order", svc.add_record(DRIVER, cid, {"items": ["svecha"], "km": 87_500, "day": "yesterday"}))
        s = await svc.stats(DRIVER, 1)
        assert s["total"] >= sum(m["total"] for m in s["months"]) > 0 and s["total"] == s["labour"] + s["parts"]
        assert 100 < s["per_km"] < 2000 and s["n"] == 6 and s["items"][0]["total"] >= s["items"][-1]["total"]
        car, rows = await svc.export_rows(DRIVER, 1)
        assert car["id"] == 1 and len(rows) == s["n"]


async def test_set_item_documents_and_own_interval():
    async with service_env() as (svc, _):
        cid = (await cobalt(svc))["car"]["id"]
        today = svc.today()
        v = await svc.set_item(DRIVER, cid, "osago", {"expires": today + 20})
        assert st(v, "osago")["days_left"] == 20 and st(v, "osago")["state"] == "ok"
        v = await svc.set_item(DRIVER, cid, "motor_moyi", {"km": "6000"})
        assert st(v, "motor_moyi")["km_iv"] == 6000
        v = await svc.set_item(DRIVER, cid, "texnik_korik", {"off": True})
        assert "texnik_korik" not in [s["id"] for s in v["statuses"]] and v["off"][0]["id"] == "texnik_korik"
        await refused("last_km", svc.set_item(DRIVER, cid, "svecha", {"last_km": 99_000}))
        await refused("interval", svc.set_item(DRIVER, cid, "motor_moyi", {"km": 100}))
        await refused("not_found", svc.set_item(DRIVER, cid, "nothing", {"done": True}))


async def test_reminders_once_across_restart_and_quiet_at_night(tmp_path):
    path = str(tmp_path / "a.db")
    clock = Clock(1_795_000_000_000)
    async with service_env(clock, path) as (svc, _):
        cid = (await cobalt(svc))["car"]["id"]
        clock.skip(days=17)
        first = [n for n in await svc.tick() if n.get("car_id") == cid]
        assert first and first[0]["items"][0]["kind"] in ("soon", "due") and first[0]["ask"], "17 days without a reading"
    async with service_env(clock, path, seed=False) as (svc, _):
        assert not [n for n in await svc.tick() if n.get("car_id") == cid], "no repeat after a restart"
        clock.now = clock.now - clock.now % 86_400_000 + 18 * 3_600_000  # 23:00 Tashkent
        clock.skip(days=30)
        assert await svc.tick() == []
        clock.skip(minutes=11 * 60)  # 10:00
        late = [n for n in await svc.tick() if n.get("car_id") == cid]
        assert late and not late[0]["ask"] and any(i["kind"] == "late" for i in late[0]["items"]), "asked once per reading"


async def test_joining_as_a_workshop_with_a_one_time_link():
    async with service_env() as (svc, _):
        await refused("not_found", svc.make_link(STRANGER))
        link = await svc.make_link(ADMIN)
        assert (await svc.join(STRANGER, link, "Avto Usta", "Olmazor"))["workshop"]["name"] == "Avto Usta"
        await refused("link_used", svc.join(5555, link, "Boshqa", ""))
        assert (await svc.roles(STRANGER))["workshop"]


async def test_the_car_limit_and_validation():
    async with service_env() as (svc, _):
        await refused("year", svc.add_car(STRANGER, {**COBALT, "year": 2040}))
        await refused("fuel", svc.add_car(STRANGER, {**COBALT, "fuel": "elektr"}))
        await refused("plate", svc.add_car(STRANGER, {**COBALT, "plate": "<b>"}))
        for _ in range(10):
            await svc.add_car(STRANGER, COBALT)
        await refused("limit", svc.add_car(STRANGER, COBALT))
