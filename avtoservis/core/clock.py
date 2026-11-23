"""Tashkent time with whole numbers only (UTC+5 all year: Uzbekistan has no daylight saving time since 1992).

Times are UTC milliseconds. Calendar dates come from Howard Hinnant's days -> civil algorithm, so the Python
server and the JS demo agree on "tomorrow 10:00" on any day, also across month ends and New Year.
"""

from __future__ import annotations

TZ_OFFSET_MS = 5 * 3_600_000
DAY_MS = 86_400_000
HOUR_MS = 3_600_000
MIN_MS = 60_000


def local_day(ms: int) -> int:
    """Days since 1970-01-01 in Tashkent."""
    return (ms + TZ_OFFSET_MS) // DAY_MS


def local_minute(ms: int) -> int:
    """Minute of the day in Tashkent (0..1439)."""
    return ((ms + TZ_OFFSET_MS) % DAY_MS) // MIN_MS


def weekday(day: int) -> int:
    """0 = Monday ... 6 = Sunday (1970-01-01 was a Thursday)."""
    return (day + 3) % 7


def civil(day: int) -> tuple[int, int, int]:
    """Days since epoch -> (year, month 1..12, day 1..31)."""
    z = day + 719_468
    era = z // 146_097
    doe = z - era * 146_097
    yoe = (doe - doe // 1460 + doe // 36_524 - doe // 146_096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    return (y + 1 if m <= 2 else y), m, d


def at_local(day: int, minute: int) -> int:
    """Tashkent day number + minute of day -> UTC milliseconds."""
    return day * DAY_MS + minute * MIN_MS - TZ_OFFSET_MS


def hhmm(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


def days_from_civil(y: int, m: int, d: int) -> int:
    """(year, month, day) -> days since 1970-01-01 (the inverse of ``civil``)."""
    y = y - 1 if m <= 2 else y
    era = y // 400
    yoe = y - era * 400
    doy = (153 * (m - 3 if m > 2 else m + 9) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146_097 + doe - 719_468


def month_len(y: int, m: int) -> int:
    if m == 2:
        return 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28
    return 30 if m in (4, 6, 9, 11) else 31


def add_months(day: int, months: int) -> int:
    """The same day of the month ``months`` later (31 January + 1 month = 28/29 February)."""
    y, m, d = civil(day)
    k = y * 12 + (m - 1) + months
    y2, m2 = k // 12, k % 12 + 1
    return days_from_civil(y2, m2, min(d, month_len(y2, m2)))


def parse_date(text: object) -> int | None:
    """ "12.11.2026", "12/11/2026" or "12.11.26" -> day number, or None."""
    if not isinstance(text, str) or len(text) > 12:
        return None
    parts = text.strip().replace("/", ".").replace("-", ".").split(".")
    if len(parts) != 3 or not all(p.isascii() and p.isdigit() and 0 < len(p) <= 4 for p in parts):
        return None
    d, m, y = (int(p) for p in parts)
    if y < 100:
        y += 2000
    if not (1990 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= month_len(y, m)):
        return None
    return days_from_civil(y, m, d)
