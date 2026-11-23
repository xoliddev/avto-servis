"""HTTP: initData HMAC + freshness, owners and workshops kept apart over the API, the public passport call (token in
the body, rate-limited, one answer for forged / revoked / expired), strict input checks, body cap, CSP, static files."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

from aiohttp.test_utils import TestClient, TestServer

from avtoservis.security import sign_init_data
from avtoservis.web import make_app

from .helpers import COBALT, DRIVER, MASTER, MASTER2, NEXIA, OIL, STRANGER, code_of, service_env

TOKEN = "123456:TEST-ONLY-NOT-A-REAL-TOKEN"


class Spy:
    def __init__(self) -> None:
        self.notes: list[dict] = []
        self.docs: list[tuple[int, str, bytes]] = []

    async def send(self, notes):
        self.notes.extend(notes)

    async def document(self, uid, name, data, title):
        self.docs.append((uid, name, data))


def init_data(uid: int, clock, age: int = 0, token: str = TOKEN) -> str:
    fields = {"auth_date": str(clock() // 1000 - age), "query_id": "AAE-test",
              "user": json.dumps({"id": uid, "first_name": f"U{uid}", "language_code": "uz"})}
    return sign_init_data(fields, token)


@asynccontextmanager
async def api(rate: int = 1000, passport_rate: int = 1000):
    async with service_env() as (svc, clock):
        spy = Spy()
        client = TestClient(TestServer(make_app(svc, TOKEN, spy, 3600, rate, passport_rate)))
        await client.start_server()

        def h(uid: int, age: int = 0, token: str = TOKEN) -> dict:
            return {"Authorization": "tma " + init_data(uid, clock, age, token)}

        try:
            yield client, svc, clock, h, spy
        finally:
            await client.close()


async def test_auth_is_required_and_checked():
    async with api() as (c, _, _clock, h, _):
        assert (await c.get("/api/me")).status == 401
        assert (await c.get("/api/me", headers={"Authorization": "Bearer x"})).status == 401
        assert (await c.get("/api/me", headers=h(DRIVER, token="999:WRONG-TEST-ONLY"))).status == 401
        assert (await c.get("/api/me", headers=h(DRIVER, age=4000))).status == 401
        assert (await c.get("/api/me", headers=h(DRIVER, age=-600))).status == 401
        me = await (await c.get("/api/me", headers=h(DRIVER))).json()
        assert me["name"] == "Jasur Karimov" and me["roles"] == {"workshop": None, "workshop_name": "", "admin": False}
        assert (await (await c.get("/api/me", headers=h(MASTER))).json())["roles"]["workshop"] == 1
        assert (await c.get("/api/nothing", headers=h(DRIVER))).status == 404


async def test_the_story_over_http_and_who_sees_what():
    async with api() as (c, svc, clock, h, spy):
        v = await (await c.post("/api/cars", json={"car": COBALT}, headers=h(DRIVER))).json()
        cid = v["car"]["id"]
        assert v["statuses"][0]["id"] in ("motor_moyi", "moy_filtri")
        for path in (f"/api/cars/{cid}", f"/api/cars/{cid}/records", f"/api/cars/{cid}/stats", f"/api/cars/{cid}/shares"):
            assert (await c.get(path, headers=h(STRANGER))).status == 404, path
        clock.skip(days=5)
        r = await c.post(f"/api/cars/{cid}/km", json={"km": 87_160}, headers=h(DRIVER))
        assert (await r.json())["view"]["fc"]["rate"] == 52_000
        r = await c.post(f"/api/cars/{cid}/km", json={"km": 87_000}, headers=h(DRIVER))
        assert r.status == 400 and (await r.json())["error"] == "odo_back"
        assert (await c.post("/api/ws/open", json={"code": await code_of(svc, cid)}, headers=h(DRIVER))).status == 404
        opened = await (await c.post("/api/ws/open", json={"code": await code_of(svc, cid)}, headers=h(MASTER))).json()
        assert "code" not in opened["car"] and "owner" not in opened["car"]
        assert (await c.get(f"/api/ws/cars/{cid}", headers=h(MASTER2))).status == 404
        r = await c.post(f"/api/ws/cars/{cid}/records", json={"record": {**OIL, "km": 87_200}}, headers=h(MASTER))
        rid = (await r.json())["records"][0]["id"]
        assert spy.notes[-1]["type"] == "confirm"
        assert (await c.post(f"/api/records/{rid}/decide", json={"yes": True}, headers=h(STRANGER))).status == 404
        rec = await (await c.post(f"/api/records/{rid}/decide", json={"yes": True}, headers=h(DRIVER))).json()
        assert rec["verified"] and spy.notes[-1] == {"type": "decided", "to": MASTER, "record_id": rid, "yes": True, "car_id": cid}
        await c.post(f"/api/cars/{NEXIA}/csv", json={}, headers=h(DRIVER))
        assert spy.docs[-1][0] == DRIVER and spy.docs[-1][2].decode("utf-8-sig").startswith("Sana,")


async def test_the_public_passport_call():
    async with api(passport_rate=5) as (c, _, _clock, h, _):
        made = await (await c.post(f"/api/cars/{NEXIA}/shares", json={"days": 30}, headers=h(DRIVER))).json()
        p = await (await c.post("/api/passport", json={"token": made["token"]})).json()
        assert p["car"]["title"] == "Chevrolet Nexia 3 2019" and p["check"]["ok"] and p["owner"] is None
        assert "labour" not in json.dumps(p) and "Jasur" not in json.dumps(p)
        bad = await c.post("/api/passport", json={"token": made["token"][:-1] + "A"})
        assert bad.status == 410 and (await bad.json())["error"] == "link_gone"
        await c.post(f"/api/cars/{NEXIA}/shares/{made['id']}/revoke", json={}, headers=h(DRIVER))
        codes = [(await c.post("/api/passport", json={"token": made["token"]})).status for _ in range(4)]
        assert codes == [410, 410, 410, 429], "one answer for forged and revoked, then rate-limited per address"


async def test_strict_input_body_cap_rate_limit_and_headers():
    async with api(rate=8) as (c, _, _clock, h, _):
        bad = await c.post("/api/cars", data="{not json", headers=h(DRIVER))
        assert bad.status == 400
        big = await c.post("/api/cars", data="x" * 20_000, headers=h(DRIVER))
        assert big.status == 413
        r = await c.post("/api/cars", json={"car": {**COBALT, "plate": "<script>"}}, headers=h(DRIVER))
        assert (await r.json())["error"] == "plate"
        r = await c.post(f"/api/cars/{NEXIA}/items/motor_moyi", json={"km": "1e3"}, headers=h(DRIVER))
        assert (await r.json())["error"] == "interval"
        statuses = [(await c.get("/api/me", headers=h(DRIVER))).status for _ in range(6)]
        assert statuses[-1] == 429
        page = await c.get("/webapp/index.html")
        assert page.status == 200 and "frame-ancestors" in page.headers["Content-Security-Policy"]
        assert page.headers["X-Content-Type-Options"] == "nosniff"
        assert (await c.get("/shared/data/plan.json")).status == 200
        assert (await c.get("/webapp/../avtoservis/config.py")).status in (403, 404)
