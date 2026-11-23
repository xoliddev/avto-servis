"""The Mini App API (signed initData, see web.py). The user always comes from the verified initData; ids in the URL
are only looked up among that user's own cars (or, for a workshop, the cars it was given), so anyone else's id
answers "not_found"."""

from __future__ import annotations

from aiohttp import web

from .bot.handlers_log import csv_text
from .web import body, num

ID = r"{id:\d{1,9}}"
ITEM = r"{item:[a-z_]{1,24}}"


def add_routes(r: web.UrlDispatcher, svc, me_key, notify, notifier) -> None:
    def ok(data) -> web.Response:
        return web.json_response(data)

    async def me(request):
        uid = request[me_key]
        user = await svc.user(uid)
        return ok({"id": uid, "name": user["name"], "lang": user["lang"], "roles": await svc.roles(uid), "now": svc.now(),
                   "today": svc.today()})

    async def lang(request):
        return ok({"lang": await svc.set_lang(request[me_key], (await body(request)).get("lang"))})

    async def cars(request):
        return ok({"items": await svc.my_cars(request[me_key])})

    async def add_car(request):
        return ok(await svc.add_car(request[me_key], (await body(request)).get("car")))

    async def car(request):
        return ok(await svc.car_view(request[me_key], num(request)))

    async def reading(request):
        d = await body(request)
        return ok(await svc.add_reading(request[me_key], num(request), d.get("km"), d.get("confirm") is True))

    async def item(request):
        return ok(await svc.set_item(request[me_key], num(request), request.match_info["item"], await body(request)))

    async def code(request):
        return ok(await svc.rotate_code(request[me_key], num(request)))

    async def shop(request):
        d = await body(request)
        return ok(await svc.set_shop(request[me_key], num(request), num(request, "wid"), d.get("allow"), d.get("remove") is True))

    async def history(request):
        return ok({"items": await svc.history(request[me_key], num(request))})

    async def add_record(request):
        return ok(await svc.add_record(request[me_key], num(request), (await body(request)).get("record")))

    async def decide(request):
        d = await body(request)
        rec, notes = await svc.decide(request[me_key], num(request), d.get("yes"), d.get("allow") is True)
        await notify(notes)
        return ok(rec)

    async def receipt(request):
        file_id = await svc.photo(request[me_key], num(request))
        if file_id and notifier is not None:
            await notifier.bot.send_photo(request[me_key], file_id)
        return ok({"sent": bool(file_id)})

    async def stats(request):
        return ok(await svc.stats(request[me_key], num(request)))

    async def export(request):
        uid = request[me_key]
        car_row, recs = await svc.export_rows(uid, num(request))
        if notifier is not None:
            await notifier.document(uid, f"avtoservis-{car_row['id']}.csv", csv_text((await svc.user(uid))["lang"], recs).encode(),
                                    svc.title(car_row))
        return ok({"sent": True, "n": len(recs)})

    async def shares(request):
        return ok({"items": await svc.shares(request[me_key], num(request))})

    async def share(request):
        d = await body(request)
        return ok(await svc.share(request[me_key], num(request), d.get("days"), d.get("show_owner", False)))

    async def revoke(request):
        return ok({"items": await svc.revoke(request[me_key], num(request), num(request, "sid"))})

    async def passport(request):
        return ok(await svc.passport((await body(request)).get("token")))

    async def ws_home(request):
        return ok(await svc.ws_home(request[me_key]))

    async def ws_open(request):
        return ok(await svc.open_car(request[me_key], (await body(request)).get("code")))

    async def ws_car(request):
        return ok(await svc.ws_car(request[me_key], num(request)))

    async def ws_record(request):
        view, notes = await svc.ws_record(request[me_key], num(request), (await body(request)).get("record"))
        await notify(notes)
        return ok(view)

    async def ws_invite(request):
        view, notes = await svc.ws_invite(request[me_key], num(request), (await body(request)).get("item"))
        await notify(notes)
        return ok(view)

    r.add_get("/api/me", me)
    r.add_post("/api/lang", lang)
    r.add_get("/api/cars", cars)
    r.add_post("/api/cars", add_car)
    r.add_get(f"/api/cars/{ID}", car)
    r.add_post(f"/api/cars/{ID}/km", reading)
    r.add_post(f"/api/cars/{ID}/items/{ITEM}", item)
    r.add_post(f"/api/cars/{ID}/code", code)
    r.add_post(f"/api/cars/{ID}/shops/{{wid:\\d{{1,9}}}}", shop)
    r.add_get(f"/api/cars/{ID}/records", history)
    r.add_post(f"/api/cars/{ID}/records", add_record)
    r.add_get(f"/api/cars/{ID}/stats", stats)
    r.add_post(f"/api/cars/{ID}/csv", export)
    r.add_get(f"/api/cars/{ID}/shares", shares)
    r.add_post(f"/api/cars/{ID}/shares", share)
    r.add_post(f"/api/cars/{ID}/shares/{{sid:\\d{{1,9}}}}/revoke", revoke)
    r.add_post(f"/api/records/{ID}/decide", decide)
    r.add_post(f"/api/records/{ID}/receipt", receipt)
    r.add_post("/api/passport", passport)
    r.add_get("/api/ws", ws_home)
    r.add_post("/api/ws/open", ws_open)
    r.add_get(f"/api/ws/cars/{ID}", ws_car)
    r.add_post(f"/api/ws/cars/{ID}/records", ws_record)
    r.add_post(f"/api/ws/cars/{ID}/invite", ws_invite)
