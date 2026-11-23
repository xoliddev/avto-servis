"""SQLite storage (aiosqlite, WAL). Parameterised SQL only. Times are UTC milliseconds, dates Tashkent day numbers.

The rules that must never break are written into the schema too, so even a bug in the service cannot break them:
odometer values stay within range, money is never negative, only a workshop's record can wait for the owner's
"Tasdiqlaysizmi?", a car code and a passport nonce are unique, and a reminder or an invitation key exists once.
"""

from __future__ import annotations

import asyncio
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, lang TEXT NOT NULL DEFAULT 'uz' CHECK (lang IN ('uz', 'ru')),
  phone TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS workshops (
  id INTEGER PRIMARY KEY AUTOINCREMENT, owner INTEGER NOT NULL UNIQUE REFERENCES users(id), name TEXT NOT NULL,
  district TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '', blocked INTEGER NOT NULL DEFAULT 0 CHECK (blocked IN (0, 1)),
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS cars (
  id INTEGER PRIMARY KEY AUTOINCREMENT, owner INTEGER NOT NULL REFERENCES users(id), model TEXT NOT NULL,
  name TEXT NOT NULL DEFAULT '', year INTEGER NOT NULL CHECK (year BETWEEN 1985 AND 2100),
  fuel TEXT NOT NULL CHECK (fuel IN ('benzin', 'metan', 'propan', 'gibrid', 'elektr')),
  usage TEXT NOT NULL CHECK (usage IN ('shaxsiy', 'taksi')), plate TEXT NOT NULL DEFAULT '',
  code TEXT NOT NULL UNIQUE CHECK (length(code) = 8), created_day INTEGER NOT NULL, created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS cars_owner ON cars(owner);
CREATE TABLE IF NOT EXISTS readings (
  id INTEGER PRIMARY KEY AUTOINCREMENT, car_id INTEGER NOT NULL REFERENCES cars(id), day INTEGER NOT NULL,
  km INTEGER NOT NULL CHECK (km BETWEEN 0 AND 2000000), at INTEGER NOT NULL, jump INTEGER NOT NULL DEFAULT 0 CHECK (jump IN (0, 1))
);
CREATE INDEX IF NOT EXISTS readings_car ON readings(car_id, day);
CREATE TABLE IF NOT EXISTS car_items (
  car_id INTEGER NOT NULL REFERENCES cars(id), item TEXT NOT NULL, last_km INTEGER CHECK (last_km IS NULL OR last_km >= 0),
  last_day INTEGER, guess INTEGER NOT NULL DEFAULT 1 CHECK (guess IN (0, 1)), km INTEGER CHECK (km IS NULL OR km BETWEEN 500 AND 200000),
  months INTEGER CHECK (months IS NULL OR months BETWEEN 1 AND 120), off INTEGER NOT NULL DEFAULT 0 CHECK (off IN (0, 1)),
  PRIMARY KEY (car_id, item)
);
CREATE TABLE IF NOT EXISTS records (
  id INTEGER PRIMARY KEY AUTOINCREMENT, car_id INTEGER NOT NULL REFERENCES cars(id), day INTEGER NOT NULL,
  km INTEGER NOT NULL CHECK (km BETWEEN 0 AND 2000000), items TEXT NOT NULL,
  labour INTEGER NOT NULL CHECK (labour BETWEEN 0 AND 50000000), parts INTEGER NOT NULL CHECK (parts BETWEEN 0 AND 50000000),
  shop TEXT NOT NULL DEFAULT '', workshop_id INTEGER REFERENCES workshops(id), by INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '',
  photo TEXT, status TEXT NOT NULL CHECK (status IN ('pending', 'ok', 'rejected')), created_at INTEGER NOT NULL, decided_at INTEGER,
  CHECK (status <> 'pending' OR workshop_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS records_car ON records(car_id, status, day);
CREATE INDEX IF NOT EXISTS records_workshop ON records(workshop_id, created_at);
CREATE TABLE IF NOT EXISTS access (
  car_id INTEGER NOT NULL REFERENCES cars(id), workshop_id INTEGER NOT NULL REFERENCES workshops(id),
  allow INTEGER NOT NULL DEFAULT 0 CHECK (allow IN (0, 1)), since_day INTEGER NOT NULL, at INTEGER NOT NULL,
  PRIMARY KEY (car_id, workshop_id)
);
CREATE INDEX IF NOT EXISTS access_workshop ON access(workshop_id);
CREATE TABLE IF NOT EXISTS shares (
  id INTEGER PRIMARY KEY AUTOINCREMENT, car_id INTEGER NOT NULL REFERENCES cars(id), nonce TEXT NOT NULL UNIQUE,
  show_owner INTEGER NOT NULL DEFAULT 0 CHECK (show_owner IN (0, 1)), created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL CHECK (expires_at > created_at), revoked_at INTEGER
);
CREATE INDEX IF NOT EXISTS shares_car ON shares(car_id);
CREATE TABLE IF NOT EXISTS reminders (car_id INTEGER NOT NULL, key TEXT NOT NULL, at INTEGER NOT NULL, PRIMARY KEY (car_id, key));
CREATE TABLE IF NOT EXISTS invites (
  workshop_id INTEGER NOT NULL, car_id INTEGER NOT NULL, item TEXT NOT NULL, cycle TEXT NOT NULL, at INTEGER NOT NULL,
  PRIMARY KEY (workshop_id, car_id, item, cycle)
);
CREATE TABLE IF NOT EXISTS links (token_hash TEXT PRIMARY KEY, made_by INTEGER NOT NULL, made_at INTEGER NOT NULL, used_by INTEGER);
"""


class Database:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self.conn = conn
        self.lock = asyncio.Lock()  # one transaction at a time on this connection

    @classmethod
    async def open(cls, path: str) -> Database:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(path, isolation_level=None)  # we issue BEGIN/COMMIT ourselves
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute("PRAGMA busy_timeout=5000")
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.executescript(SCHEMA)
        return cls(conn)

    async def close(self) -> None:
        await self.conn.close()

    @asynccontextmanager
    async def tx(self):
        """``BEGIN IMMEDIATE`` takes the write lock up front, so check-then-write sequences cannot interleave,
        neither between coroutines (asyncio lock) nor between processes (SQLite lock + busy_timeout)."""
        async with self.lock:
            for attempt in range(6):
                try:
                    await self.conn.execute("BEGIN IMMEDIATE")
                    break
                except sqlite3.OperationalError as err:
                    if "locked" not in str(err) or attempt == 5:
                        raise
                    await asyncio.sleep(0.05 * (attempt + 1))
            try:
                yield self.conn
            except BaseException:
                await self.conn.execute("ROLLBACK")
                raise
            await self.conn.execute("COMMIT")

    async def one(self, sql: str, args: tuple = ()) -> dict | None:
        async with self.conn.execute(sql, args) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def all(self, sql: str, args: tuple = ()) -> list[dict]:
        async with self.conn.execute(sql, args) as cur:
            return [dict(r) for r in await cur.fetchall()]
