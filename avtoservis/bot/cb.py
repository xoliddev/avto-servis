"""Callback data is ``<prefix>:<fields>`` with digits only for ids and ``[a-z_]`` for item names, matched by strict
regexes in the handlers; anything else falls through to the "stale button" answer. Nothing in callback data is trusted
for authorization: the service re-checks every action against the caller's Telegram id. demo/bot.js speaks the same."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup

N = r"(\d{1,9})"
W = r"([a-z0-9_]{1,24})"


class Flow(StatesGroup):
    add_name = State()
    add_year = State()
    add_odo = State()
    add_plate = State()
    add_oil = State()
    km = State()
    expires = State()
    log_items = State()
    log_km = State()
    log_labour = State()
    log_parts = State()
    log_shop = State()
    log_photo = State()
    ws_code = State()
    ws_items = State()
    ws_km = State()
    ws_labour = State()
    ws_parts = State()
    join_name = State()
    join_address = State()
