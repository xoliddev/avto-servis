"""Money is a whole number of so'm. Floats are never used for money."""

from __future__ import annotations


def div_round(a: int, b: int) -> int:
    """a / b rounded half up, whole numbers only (b > 0). The JS port gives the same for every safe integer."""
    return (2 * a + b) // (2 * b)


def ceil_div(a: int, b: int) -> int:
    return -(-a // b)


def group(n: int) -> str:
    """180000 -> "180 000"."""
    sign = "-" if n < 0 else ""
    s = str(abs(n))
    parts = []
    while s:
        parts.append(s[-3:])
        s = s[:-3]
    return sign + " ".join(reversed(parts))


def split(total: int, n: int) -> list[int]:
    """Share ``total`` between ``n`` parts as evenly as whole so'm allow; the first parts get the remainder."""
    if n <= 0:
        return []
    base, rest = divmod(total, n)
    return [base + (1 if i < rest else 0) for i in range(n)]
