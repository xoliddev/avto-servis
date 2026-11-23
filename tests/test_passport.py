"""Servis pasporti: what the buyer sees, and that a link is signed, expiring, revocable and not guessable."""

from __future__ import annotations

import pytest

from avtoservis.common import Refused
from avtoservis.core import token

from .helpers import DAY, DRIVER, MASTER, NEXIA, OIL, STRANGER, cobalt, code_of, service_env


async def gone(svc, tok) -> None:
    with pytest.raises(Refused) as err:
        await svc.passport(tok)
    assert err.value.code == "link_gone"


async def test_the_buyer_sees_the_verified_timeline_and_the_odometer_check():
    async with service_env() as (svc, _):
        link = await svc.share(DRIVER, NEXIA, 30)
        p = await svc.passport(link["token"])
        assert p["car"]["title"] == "Chevrolet Nexia 3 2019" and p["owner"] is None
        assert p["check"]["ok"] and p["check"]["back"] == 0 and p["check"]["n"] > 50
        assert p["verified"] >= 4 and p["self"] >= 1 and p["verified"] + p["self"] == len(p["timeline"])
        assert {"labour", "parts", "total", "note"}.isdisjoint(p["timeline"][0]), "no money and no notes for the buyer"
        assert p["timeline"][0]["day"] >= p["timeline"][-1]["day"] and p["next"]
        text = repr(p)
        assert "Jasur" not in text and "+998" not in text
        shown = await svc.share(DRIVER, NEXIA, 7, True)
        assert (await svc.passport(shown["token"]))["owner"]["name"] == "Jasur Karimov"


async def test_links_expire_get_revoked_and_cannot_be_forged():
    async with service_env() as (svc, clock):
        link = await svc.share(DRIVER, NEXIA, 7)
        assert [s["token"] for s in await svc.shares(DRIVER, NEXIA)] == [link["token"]]
        forged = link["token"][:-2] + ("AA" if link["token"][-2:] != "AA" else "BB")
        await gone(svc, forged)
        await gone(svc, token.make(token.secret_from("someone else"), bytes(12)))
        for bad in ("", "x" * 33, None, 7, "../../etc/passwd"):
            await gone(svc, bad)
        with pytest.raises(Refused):
            await svc.revoke(STRANGER, NEXIA, link["id"])
        assert await svc.revoke(DRIVER, NEXIA, link["id"]) == []
        await gone(svc, link["token"])
        late = await svc.share(DRIVER, NEXIA, 7)
        clock.skip(days=7)
        await gone(svc, late["token"])
        assert late["expires_at"] == clock.now - 0 and clock.now - late["expires_at"] < DAY


async def test_only_the_owner_shares_and_there_are_limits():
    async with service_env() as (svc, _):
        for bad in ((STRANGER, NEXIA, 30), (DRIVER, NEXIA, 5), (DRIVER, NEXIA, True)):
            with pytest.raises(Refused):
                await svc.share(*bad)
        for _ in range(5):
            await svc.share(DRIVER, NEXIA, 90)
        with pytest.raises(Refused) as err:
            await svc.share(DRIVER, NEXIA, 90)
        assert err.value.code == "limit"


async def test_a_new_car_passport_after_the_workshop_record():
    async with service_env() as (svc, clock):
        cid = (await cobalt(svc))["car"]["id"]
        await svc.add_record(DRIVER, cid, {"items": ["havo_filtri"], "km": 86_900, "parts": 65_000})
        clock.skip(days=7)
        await svc.open_car(MASTER, await code_of(svc, cid))
        ws, _ = await svc.ws_record(MASTER, cid, {**OIL, "km": 87_290})
        await svc.decide(DRIVER, ws["records"][0]["id"], True)
        p = await svc.passport((await svc.share(DRIVER, cid, 30))["token"])
        assert [(x["verified"], x["shop"]) for x in p["timeline"]] == [(True, "Turbo Servis"), (False, "")]
        assert p["check"] == {**p["check"], "ok": True, "back": 0, "first_km": 86_900, "last_km": 87_290}
