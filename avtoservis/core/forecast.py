"""How many kilometres a car drives a day, and when it reaches a given odometer value.

Readings are ``[day, km]`` pairs (Tashkent day numbers). The rate is in **metres per day**, whole numbers only, so the
Python server and the browser agree to the metre. It is a *weighted median* of the rates between readings: one odd
week (a trip to Samarkand, a week in the garage) moves it little, and newer intervals weigh more than old ones.
The forecast fan is the weighted 20th..80th percentile, never narrower than a margin that shrinks as readings grow.
"""

from __future__ import annotations

import itertools

from .money import ceil_div

MAX_INTERVALS = 12  # only the latest intervals count
WEIGHT_CAP_DAYS = 30  # a long gap is worth at most 30 days
DEFAULT_MARGIN = 45  # percent, when there is only one reading


def points(readings: list) -> list[list[int]]:
    """One point per day (the highest km of that day), oldest first."""
    best: dict[int, int] = {}
    for day, km in readings:
        best[day] = max(km, best.get(day, km))
    return [[d, best[d]] for d in sorted(best)]


def intervals(pts: list[list[int]]) -> list[tuple[int, int]]:
    """(rate in m/day, weight) between consecutive points; weight = days (capped) x recency rank."""
    pairs = list(itertools.pairwise(pts))[-MAX_INTERVALS:]
    out = []
    for i, (a, b) in enumerate(pairs):
        days = b[0] - a[0]
        out.append(((b[1] - a[1]) * 1000 // days, min(days, WEIGHT_CAP_DAYS) * (i + 1)))
    return out


def wquantile(iv: list[tuple[int, int]], num: int, den: int) -> int:
    """The smallest rate whose cumulative weight reaches num/den of the total."""
    ordered = sorted(iv)
    total = sum(w for _, w in ordered)
    cum = 0
    for rate, w in ordered:
        cum += w
        if cum * den >= total * num:
            return rate
    return ordered[-1][0]


def estimate(readings: list, default_km: int) -> dict:
    """{rate, lo, hi (m/day), n intervals, margin %, day, km of the last reading}; ``default_km`` a day if one reading."""
    pts = points(readings)
    iv = intervals(pts)
    if iv:
        rate, margin = wquantile(iv, 1, 2), max(8, 36 // len(iv))
        lo_q, hi_q = wquantile(iv, 1, 5), wquantile(iv, 4, 5)
    else:
        rate, margin = default_km * 1000, DEFAULT_MARGIN
        lo_q = hi_q = rate
    lo = min(lo_q, rate * (100 - margin) // 100)
    hi = max(hi_q, ceil_div(rate * (100 + margin), 100))
    day, km = pts[-1] if pts else (None, None)
    return {"rate": rate, "lo": lo, "hi": hi, "n": len(iv), "margin": margin, "day": day, "km": km}


def odo_on(fc: dict, day: int, rate: int | None = None) -> int:
    """Expected odometer on ``day`` (never below the last reading)."""
    r = fc["rate"] if rate is None else rate
    return fc["km"] + r * max(0, day - fc["day"]) // 1000


def day_for(fc: dict, km: int, rate: int | None = None) -> int | None:
    """The first day the odometer is expected to reach ``km``; None if the car does not move."""
    r = fc["rate"] if rate is None else rate
    if km <= fc["km"]:
        return fc["day"]
    if r <= 0:
        return None
    return fc["day"] + ceil_div((km - fc["km"]) * 1000, r)
