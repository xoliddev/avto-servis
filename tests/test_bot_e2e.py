"""The real aiogram handlers against a mocked Bot API: a driver adds a Cobalt by buttons, sends the odometer, gets
the reminder and answers it with one tap, the workshop opens the car by its code and records the oil change, the
driver confirms; self-logging with a receipt photo, history, stats, CSV; the passport link and its deep link; forged
buttons; joining as a workshop."""

from __future__ import annotations

from .helpers import ADMIN, DRIVER, MASTER, NEXIA, STRANGER, Clock, code_of, service_env
from .tg_sim import TgSim


async def test_add_a_car_by_buttons_reminder_workshop_and_confirm():
    clock = Clock(1_795_000_000_000 + 2 * 3_600_000)
    async with service_env(clock) as (svc, _):
        tg = TgSim(svc)
        await tg.say(DRIVER, "/start")
        assert "Avto Servis" in tg.last(DRIVER) and "Chevrolet Nexia 3 2019 · 01 A 254 JK" in tg.last(DRIVER)
        await tg.tap(DRIVER, "➕ Mashina qo'shish")
        await tg.tap(DRIVER, "Chevrolet Cobalt")
        await tg.tap(DRIVER, "2021")
        await tg.tap(DRIVER, "Metan")
        await tg.tap(DRIVER, "🙋 Shaxsiy")
        await tg.say(DRIVER, "86 900")
        await tg.say(DRIVER, "01a123bc")
        await tg.say(DRIVER, "80900")
        text = tg.last(DRIVER)
        assert "Mashina qo'shildi" in text and "<b>Motor moyi</b>: 800 km qoldi — taxminan" in text and "(18 kundan keyin)" in text
        cid = (await svc.my_cars(DRIVER))[-1]["id"]
        clock.skip(days=5)
        await tg.tap(DRIVER, "📍 Kilometr yuborish")
        await tg.say(DRIVER, "87160")
        assert "Qabul qilindi: 87 160 km" in tg.last(DRIVER) and "kuniga ~52 km" in tg.last(DRIVER)
        await tg.say(DRIVER, "87029")
        clock.skip(days=2)
        await tg.notifier.send(await svc.tick())
        remind = next(x for x in tg.texts(DRIVER) if x.startswith("🔔 <b>Chevrolet Cobalt 2021"))
        assert "<b>Motor moyi</b>: 436 km qoldi" in remind and "<b>Moy filtri</b>: 436 km qoldi" in remind
        await tg.tap(DRIVER, "✅ ≈ 87 264 km — to'g'ri")
        assert "Qabul qilindi: 87 264 km" in tg.last(DRIVER)
        await tg.tap(DRIVER, "📍 Kilometr yuborish")
        await tg.say(DRIVER, "87029")
        assert any("Spidometr orqaga ketmaydi" in x for x in tg.texts(DRIVER)), "a lower reading is refused"
        await tg.say(MASTER, "/start")
        await tg.tap(MASTER, "🔧 Servis paneli")
        await tg.tap(MASTER, "🔎 Mashinani kod bilan ochish")
        await tg.say(MASTER, (await code_of(svc, cid)).lower())
        assert "Chevrolet Cobalt 2021</b> · 01 A 123 BC" in tg.last(MASTER) and "Jasur" not in tg.last(MASTER)
        await tg.tap(MASTER, "➕ Xizmatni yozish")
        await tg.tap(MASTER, "▫️ Motor moyi")
        await tg.tap(MASTER, "▫️ Moy filtri")
        await tg.tap(MASTER, "Davom etish")
        await tg.say(MASTER, "87290")
        await tg.say(MASTER, "60 000")
        await tg.say(MASTER, "405000")
        assert "Egasiga yuborildi" in tg.last(MASTER)
        ask = tg.texts(DRIVER)[-1]
        assert "<b>Turbo Servis</b> xizmatni yozdi" in ask and "Jami: <b>465 000 so'm</b>" in ask and "Tasdiqlaysizmi?" in ask
        await tg.tap(DRIVER, "✅ Tasdiqlayman + eslatma yuborsin")
        assert "Tasdiqlandi" in tg.last(DRIVER) and "Motor moyi" not in tg.last(DRIVER), "the oil left the top of the list"
        await tg.tap(DRIVER, "📋 Reja")
        assert "<b>Motor moyi</b>: 6 800 km qoldi" in tg.last(DRIVER)
        assert "Egasi tasdiqladi" in tg.texts(MASTER)[-1]
        await tg.tap(DRIVER, "🧾 Tarix")
        assert "✅ Servis tasdiqlagan: Turbo Servis" in tg.last(DRIVER)


async def test_self_log_with_photo_stats_csv_and_the_plan():
    async with service_env() as (svc, _):
        tg = TgSim(svc)
        await tg.say(DRIVER, "/start")
        await tg.tap(DRIVER, "🚗 Chevrolet Nexia 3 2019")
        await tg.tap(DRIVER, "➕ Xizmat yozish")
        await tg.tap(DRIVER, "▫️ Salon filtri")
        await tg.tap(DRIVER, "Davom etish")
        odo = (await svc.car_view(DRIVER, NEXIA))["car"]["odo"]
        await tg.tap(DRIVER, f"{odo:,} km".replace(",", " "))
        await tg.tap(DRIVER, "0 so'm")
        await tg.say(DRIVER, "55000")
        await tg.say(DRIVER, "O'zim")
        await tg.send_photo(DRIVER)
        assert "Yozib qo'yildi" in tg.last(DRIVER)
        await tg.tap(DRIVER, "🧾 Tarix")
        assert "✍️ O'zi yozgan" in tg.last(DRIVER) and "Salon filtri" in tg.last(DRIVER)
        await tg.tap(DRIVER, "🧾 Chek")
        assert tg.session.photos[DRIVER][-1][0] == "AgACAgIAAxkBAAIBtest"
        await tg.tap(DRIVER, "📥 CSV fayl")
        csv = tg.session.documents[DRIVER][-1].decode("utf-8-sig")
        assert csv.startswith("Sana,Km,Xizmatlar") and "Servis tasdiqlagan" in csv and "O'zi yozgan" in csv
        await tg.tap_data(DRIVER, f"e:{NEXIA}")
        assert "1 km uchun" in tg.last(DRIVER) and "Eng ko'p pul ketgan" in tg.last(DRIVER)
        await tg.tap_data(DRIVER, f"i:{NEXIA}:osago")
        await tg.tap(DRIVER, "📅 Muddatini kiritish")
        await tg.say(DRIVER, "31.12.2027")
        assert "Saqlandi" in tg.last(DRIVER) and "31-dekabr" in tg.last(DRIVER)


async def test_passport_link_deep_link_and_revoke():
    async with service_env() as (svc, _):
        tg = TgSim(svc)
        await tg.tap_data(DRIVER, f"g:{NEXIA}")
        await tg.tap(DRIVER, "➕ Havola: 30 kun")
        made = tg.last(DRIVER)
        assert "https://garaj.example/webapp/#p=" in made and "https://t.me/avto_test_bot?start=p_" in made
        tok = made.split("start=p_")[1][:32]
        await tg.say(STRANGER, f"/start p_{tok}")
        card = tg.last(STRANGER)
        assert "Servis pasporti: Chevrolet Nexia 3 2019" in card and "✅ Spidometr ketma-ket" in card and "Jasur" not in card
        await tg.tap(DRIVER, "🚫 #")
        await tg.say(STRANGER, f"/start p_{tok}")
        assert "endi amal qilmaydi" in tg.last(STRANGER)


async def test_forged_buttons_and_other_people_are_refused():
    async with service_env() as (svc, _):
        tg = TgSim(svc)
        for data in (f"c:{NEXIA}", f"h:{NEXIA}", f"g:{NEXIA}", f"gn:{NEXIA}:30:0", "w:home", "x:link", f"ok:1:y", "zz:1", f"wc:{NEXIA}"):
            await tg.tap_data(STRANGER, data)
        alerts = tg.alerts()
        assert len(alerts) == 9 and all("Topilmadi" in a or "eskirgan" in a for a in alerts), alerts
        await tg.say(STRANGER, "/start c_ABCDEFGH")
        assert "servis ustalari uchun" in tg.last(STRANGER)


async def test_join_as_a_workshop_and_admin_screen():
    async with service_env() as (svc, _):
        tg = TgSim(svc)
        await tg.say(ADMIN, "/start")
        await tg.tap(ADMIN, "🛡 Admin")
        assert "Mashinalar: 7" in tg.last(ADMIN)
        await tg.tap(ADMIN, "🔗 Yangi servis")
        link = tg.last(ADMIN).split("start=w_")[1][:22]
        await tg.say(5555, f"/start w_{link}")
        await tg.say(5555, "Usta Avto")
        await tg.say(5555, "Olmazor 5")
        assert "Servis ochildi" in tg.last(5555) and "Usta Avto" in tg.last(5555)
        await tg.say(STRANGER, f"/start w_{link}")
        assert any("allaqachon ishlatilgan" in x for x in tg.texts(STRANGER))
