"""ETB money helpers. Amounts are integer santim everywhere (ARCH §5.9)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

SANTIM_PER_BIRR = 100
CURRENCY = "ETB"


class MoneyError(ValueError):
    pass


def parse(value: str | int | Decimal) -> int:
    """Parse '1,250.50', 'ETB 10', 1250.5 or 125050 into santim."""
    if isinstance(value, bool):
        raise MoneyError("Booleans are not money")
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal):
        return _to_santim(value)
    text = str(value).strip().replace(",", "").replace("_", "")
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
    return int((amount * SANTIM_PER_BIRR).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_santim(amount: int, *, locale: str = "en", with_currency: bool = True) -> str:
    if not isinstance(amount, int):
        raise MoneyError("Amount must be integer santim")
    sign = "-" if amount < 0 else ""
    whole, part = divmod(abs(amount), SANTIM_PER_BIRR)
    grouped = f"{whole:,}"
    body = f"{sign}{grouped}.{part:02d}"
    if not with_currency:
        return body
    return f"ብር {body}" if locale == "am" else f"ETB {body}"


def allocate(amount: int, weights: list[int]) -> list[int]:
    """Split `amount` by weights without losing or inventing a santim."""
    if not weights:
        raise MoneyError("At least one weight is required")
    if any(w < 0 for w in weights):
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
    return [sign * s for s in shares]


def add(*amounts: int) -> int:
    return sum(amounts)


def subtract(a: int, b: int) -> int:
    return a - b
