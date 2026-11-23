"""The odometer guard and the passport's consistency check.

* A reading lower than the last one is refused: an odometer does not go back.
* A jump of more than ``jump_km_per_day`` (1 500 km) per day since the last reading asks the owner to confirm.
* A service record dated in the past must fit between the readings around it.
"""

from __future__ import annotations

import itertools

from .cars import MAX_KM
from .text import InputError, whole


def check(last: list | None, day: int, km: object, confirmed: bool, jump_per_day: int) -> tuple[int, bool]:
    """-> (km, needs_confirm). Raises ``odo`` (not a number) or ``odo_back`` (lower than ``last``)."""
    n = whole(km, 0, MAX_KM, "odo")
    if last is None:
        return n, False
    if n < last[1]:
        raise InputError("odo_back")
    days = max(1, day - last[0])
    return n, n - last[1] > jump_per_day * days and not confirmed


def fits(points: list, day: int, km: int) -> None:
    """A past record at (day, km) must not be below an earlier reading or above a later one."""
    before = [k for d, k in points if d < day]
    after = [k for d, k in points if d > day]
    if (before and km < max(before)) or (after and km > min(after)):
        raise InputError("odo_order")


def consistency(points: list, jump_per_day: int) -> dict:
    """For the passport: did the odometer ever go back, how many big jumps, km per day on average."""
    back = sum(1 for a, b in itertools.pairwise(points) if b[1] < a[1])
    jumps = sum(1 for a, b in itertools.pairwise(points)
                if b[1] - a[1] > jump_per_day * max(1, b[0] - a[0]))
    span = points[-1][0] - points[0][0] if points else 0
    driven = points[-1][1] - points[0][1] if points else 0
    return {"ok": back == 0, "back": back, "jumps": jumps, "n": len(points), "first_day": points[0][0] if points else None,
            "last_day": points[-1][0] if points else None, "first_km": points[0][1] if points else None,
            "last_km": points[-1][1] if points else None, "per_day": driven // span if span > 0 else None}
