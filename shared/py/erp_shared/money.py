"""ETB money helpers. Amounts are integer santim everywhere (ARCH §5.9).

Parsing goes through :class:`~decimal.Decimal` so half-santim values round
half-up on the decimal text instead of inheriting IEEE-754 float error.
``int`` inputs are already santim (the storage unit); strings and ``Decimal``
inputs are birr. Amounts are capped at the signed 64-bit BIGINT range.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

SANTIM_PER_BIRR = 100
CURRENCY = "ETB"
MAX_SANTIM = 2**63 - 1


class MoneyError(ValueError):
    pass


def _check_range(amount: int) -> int:
    if not -MAX_SANTIM - 1 <= amount <= MAX_SANTIM:
        raise MoneyError("Money amount is too large for a BIGINT")
    return amount


def parse(value: str | int | Decimal) -> int:
    """Parse '1,250.50', 'ETB 10', 1250.5 or 125050 into santim."""
    if isinstance(value, bool):
        raise MoneyError("Booleans are not money")
    if isinstance(value, int):
        return _check_range(value)
    if isinstance(value, Decimal):
        return _to_santim(value)
    text = "".join(str(value).split()).replace(",", "").replace("_", "")
    for prefix in ("ETB", "ብር", "Br"):
        if text.upper().startswith(prefix.upper()):
            text = text[len(prefix) :].strip()
    try:
        return _to_santim(Decimal(text))
    except InvalidOperation as exc:
        raise MoneyError(f"Cannot parse money value {value!r}") from exc


def _to_santim(amount: Decimal) -> int:
    if not amount.is_finite():
        raise MoneyError("Money must be finite")
    return _check_range(
        int((amount * SANTIM_PER_BIRR).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    )


def format_santim(amount: int, *, locale: str = "en", with_currency: bool = True) -> str:
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise MoneyError("Amount must be integer santim")
    _check_range(amount)
    sign = "-" if amount < 0 else ""
    whole, part = divmod(abs(amount), SANTIM_PER_BIRR)
    grouped = f"{whole:,}"
    body = f"{sign}{grouped}.{part:02d}"
    if not with_currency:
        return body
    return f"ብር {body}" if locale == "am" else f"ETB {body}"


def allocate(amount: int, weights: list[int]) -> list[int]:
    """Split `amount` by weights without losing or inventing a santim."""
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise MoneyError("Amount must be integer santim")
    _check_range(amount)
    if not weights:
        raise MoneyError("At least one weight is required")
    if any(weight < 0 for weight in weights):
        raise MoneyError("Weights cannot be negative")
    total = sum(weights)
    if total == 0:
        raise MoneyError("Weights cannot all be zero")
    sign = -1 if amount < 0 else 1
    remainder = abs(amount)
    shares: list[int] = []
    for weight in weights:
        share = abs(amount) * weight // total
        shares.append(share)
        remainder -= share
    # Distribute the leftover santim to the largest weights first (stable).
    order = sorted(range(len(weights)), key=lambda i: (-weights[i], i))
    for i in range(remainder):
        shares[order[i % len(order)]] += 1
    return [sign * share for share in shares]


def add(*amounts: int) -> int:
    total = 0
    for amount in amounts:
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise MoneyError("Amount must be integer santim")
        total = _check_range(total + amount)
    return total


def subtract(a: int, b: int) -> int:
    return add(a, -b)


__all__ = [
    "CURRENCY",
    "MAX_SANTIM",
    "MoneyError",
    "SANTIM_PER_BIRR",
    "add",
    "allocate",
    "format_santim",
    "parse",
    "subtract",
]
