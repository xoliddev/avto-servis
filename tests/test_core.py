"""The pure core: the vectors are up to date, and the rules read the way the README says."""

from __future__ import annotations

import json
import subprocess
import sys

from avtoservis.core import cars, clock, forecast, odometer, plan, reminders, stats, token
from avtoservis.core.text import InputError

from .conftest import ROOT

TODAY = clock.local_day(1_795_000_000_000)


def load(name: str):
    with open(ROOT / "shared" / "data" / f"{name}.json", encoding="utf-8") as fh:
        return json.load(fh)


def test_vectors_are_up_to_date(tmp_path):
    before = (ROOT / "shared" / "test_vectors.json").read_bytes()
    subprocess.run([sys.executable, str(ROOT / "scripts" / "make_vectors.py")], check=True, capture_output=True)
    assert (ROOT / "shared" / "test_vectors.json").read_bytes() == before, "run python scripts/make_vectors.py"


def test_month_arithmetic_and_dates():
    jan31 = clock.days_from_civil(2027, 1, 31)
    assert clock.civil(clock.add_months(jan31, 1)) == (2027, 2, 28)
    assert clock.civil(clock.add_months(clock.days_from_civil(2027, 12, 15), 1)) == (2028, 1, 15), "across New Year"
    assert clock.parse_date("29.02.2028") == clock.days_from_civil(2028, 2, 29)
    assert clock.parse_date("29.02.2027") is None and clock.parse_date("12.11") is None


def test_weighted_median_ignores_one_odd_trip_and_the_fan_tightens():
    steady = [[TODAY - 7 * i, 50_000 - 7 * 50 * i] for i in range(6, -1, -1)]
    trip = [*steady[:-1], [TODAY, steady[-2][1] + 7 * 50 + 900]]  # a 900 km weekend in the newest week
    assert forecast.estimate(steady, 45)["rate"] == 50_000
    assert forecast.estimate(trip, 45)["rate"] == 50_000, "one trip does not move the median"
    one = forecast.estimate(steady[-1:], 45)
    two = forecast.estimate(steady[-2:], 45)
    many = forecast.estimate(steady, 45)
    widths = [f["hi"] - f["lo"] for f in (one, two, many)]
    assert one["rate"] == 45_000 and widths[0] > widths[1] > widths[2], widths


def test_metan_and_taxi_shorten_oil_and_calendar_items():
    oil = load("plan")["items"][0]
    assert plan.interval(oil, "benzin", "shaxsiy") == (8000, 6)
    assert plan.interval(oil, "metan", "shaxsiy") == (6800, 6)
    assert plan.interval(oil, "metan", "taksi") == (5400, 6)
    items = plan.items_for(load("plan"), cars.model(load("models"), "cobalt"), "metan", "shaxsiy")
    ids = [i["id"] for i in items]
    assert "metan_ballon" in ids and "grm_remni" in ids
    ev = plan.items_for(load("plan"), cars.model(load("models"), "byd_song"), "elektr", "shaxsiy")
    assert not {"motor_moyi", "svecha", "metan_ballon", "grm_remni"} & {i["id"] for i in ev}


def test_whichever_comes_first_and_the_sentence_numbers():
    cfg = load("plan")
    it = {"id": "motor_moyi", "km": 6800, "months": 6, "calendar": False, "season": None}
    fc = forecast.estimate([[TODAY - 5, 86_900], [TODAY, 87_160]], 45)
    st = plan.status(it, {"km": 80_900, "day": TODAY - 5, "guess": False}, fc, TODAY, cfg)
    assert (st["km_left"], st["days_left"], st["state"], st["basis"]) == (540, 11, "ok", "km")
    assert st["lo_day"] < st["due_day"] < st["hi_day"]
    slow = forecast.estimate([[TODAY - 30, 86_900], [TODAY, 87_000]], 45)
    st = plan.status(it, {"km": 86_000, "day": TODAY - 180, "guess": False}, slow, TODAY, cfg)
    assert st["basis"] == "date" and st["state"] == "soon", "six months come before 6 800 km"


def test_odometer_guard():
    try:
        odometer.check([TODAY - 2, 87_160], TODAY, 87_029, False, 1500)
        raise AssertionError("lower reading accepted")
    except InputError as err:
        assert err.code == "odo_back"
    assert odometer.check([TODAY - 2, 87_160], TODAY, 90_160, False, 1500) == (90_160, False)
    assert odometer.check([TODAY - 2, 87_160], TODAY, 90_161, False, 1500) == (90_161, True)
    assert odometer.check([TODAY - 2, 87_160], TODAY, 90_161, True, 1500) == (90_161, False)


def test_reminder_keys_once_per_cycle_and_weekly_when_late():
    st = {"id": "motor_moyi", "cycle": "80900:1", "state": "due", "days_left": -15}
    assert reminders.keys_for([st], TODAY, TODAY, {"ask_after_days": 14}) == [
        {"key": "motor_moyi:80900:1:late2", "item": "motor_moyi", "kind": "late"}]
    assert reminders.keys_for([{**st, "days_left": 0}], TODAY, TODAY - 14, {"ask_after_days": 14})[-1]["key"] == f"ask:{TODAY - 14}"
    assert reminders.quiet(21 * 60) and reminders.quiet(8 * 60 + 59) and not reminders.quiet(9 * 60)


def test_csv_neutralises_formulas_and_tokens_are_signed():
    assert stats.csv([["=HYPERLINK(1)", "a,b"]]) == "'=HYPERLINK(1),\"a,b\"\r\n"
    secret = token.secret_from("x")
    t = token.make(secret, bytes(12))
    assert len(t) == token.TOKEN_LEN and token.nonce_of(secret, t) == "00" * 12
    assert token.nonce_of(token.secret_from("y"), t) is None
