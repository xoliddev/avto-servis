"""Spending: per month, per plan item (a record's cost shared evenly between its items) and so'm per km; CSV export."""

from __future__ import annotations

from .clock import civil
from .money import div_round, split


def spending(records: list[dict], months: int, today: int) -> dict:
    """``records``: confirmed ones, each {day, km, items, labour, parts}. The last ``months`` calendar months."""
    y, m, _ = civil(today)
    keys = []
    for k in range(months - 1, -1, -1):
        idx = y * 12 + (m - 1) - k
        keys.append((idx // 12, idx % 12 + 1))
    per_month = {key: 0 for key in keys}
    per_item: dict[str, int] = {}
    total = labour = parts = 0
    for r in records:
        cost = r["labour"] + r["parts"]
        total += cost
        labour += r["labour"]
        parts += r["parts"]
        yy, mm, _ = civil(r["day"])
        if (yy, mm) in per_month:
            per_month[(yy, mm)] += cost
        for item, share in zip(r["items"], split(cost, len(r["items"])), strict=True):
            per_item[item] = per_item.get(item, 0) + share
    items = sorted(per_item.items(), key=lambda kv: (-kv[1], kv[0]))
    return {"months": [{"y": yy, "m": mm, "total": per_month[(yy, mm)]} for yy, mm in keys],
            "items": [{"id": k, "total": v} for k, v in items], "total": total, "labour": labour, "parts": parts,
            "n": len(records)}


def per_km(total: int, km_driven: int) -> int | None:
    """So'm per km, rounded; None until the car has driven at least 100 km."""
    return div_round(total, km_driven) if km_driven >= 100 else None


def _cell(value: object) -> str:
    s = str(value)
    if s[:1] in ("=", "+", "-", "@", "\t", "\r"):
        s = "'" + s  # no formulas when the file is opened in a spreadsheet
    return '"' + s.replace('"', '""') + '"' if any(c in s for c in ',"\n;') else s


def csv(rows: list[list]) -> str:
    """Rows of cells -> CSV text (comma separated, CRLF, formulas neutralised)."""
    return "".join(",".join(_cell(c) for c in row) + "\r\n" for row in rows)
