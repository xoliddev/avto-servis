# Changelog

## 1.0.2 — 2026-11-23

- The server answers `/webapp/` (the address the bot's Mini App button opens) with the Mini App page. Before, aiohttp's
  static route answered 403 for the folder itself, so a real deployment opened an error instead of the app.

## 1.0.1 — 2026-11-23

- The workshop screen labels its odometer "Spidometr, taxminan bugun": it is today's estimate, while the owner's card
  shows the last reading, so the two different numbers no longer look like a mismatch.
- Reminders ask for the current km only when they include a km-based item (not for OSAGO or texnik ko'rik alone).
- Spending by item explains that a record with several jobs is split between them equally.

## 1.0.0 — 2026-11-23

Daily portfolio challenge #6.

- Pure core with a JavaScript port checked by shared vectors: Tashkent calendar with month arithmetic, Uzbek-market
  models and plates, car codes, daily km as a weighted median with a forecast fan, the service plan (km and/or months,
  fuel and taxi adjusted, seasons, documents), the odometer guard, records, spending and CSV, reminder keys, signed
  Servis pasporti tokens, the seeded world.
- Service on SQLite (WAL, `BEGIN IMMEDIATE`): garage, readings, plan edits, self-logged and workshop records with the
  owner's confirmation, stats, workshops (open by code, clients due soon, one invitation per item, one-time join
  links), passport links (signed, expiring, revocable), reminders claimed exactly once.
- aiogram bot, buttons only, Uzbek and Russian; aiohttp API with initData HMAC and the public passport call.
- Mini App "Garaj": the car dashboard with the hand-drawn odometer chart, plan, history, spending, car code, passport
  links; the workshop panel; the buyer's passport page.
- Browser demo with three phones and a ten-step story; pytest, node tests and Playwright e2e; Docker (non-root,
  read-only), CI and GitHub Pages.
