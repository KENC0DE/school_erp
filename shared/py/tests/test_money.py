from __future__ import annotations

from decimal import Decimal

import pytest
from erp_shared.money import (
    CURRENCY,
    MAX_SANTIM,
    SANTIM_PER_BIRR,
    MoneyError,
    add,
    allocate,
    format_santim,
    parse,
    subtract,
)


def test_parse_accepts_formats():
    assert parse("1,250.50") == 125050
    assert parse("ETB 10") == 1000
    assert parse("ብር 9.99") == 999
    assert parse("Br 10") == 1000
    assert parse(" 1 250.5 ") == 125050
    assert parse(1250) == 1250
    assert parse(Decimal("12.5")) == 1250
    assert parse("0.005") == 1


def test_parse_rejects_garbage():
    with pytest.raises(MoneyError):
        parse("not money")
    with pytest.raises(MoneyError):
        parse("")
    with pytest.raises(MoneyError):
        parse("1.2.3")
    with pytest.raises(MoneyError):
        parse(True)
    with pytest.raises(MoneyError):
        parse(Decimal("NaN"))
    with pytest.raises(MoneyError):
        parse(Decimal("Infinity"))


def test_parse_rounds_half_up_on_decimal_text():
    assert parse("1.005") == 101
    assert parse("1.004") == 100
    assert parse("1.004999") == 100
    assert parse("-1.005") == -101
    assert parse("1,250.999") == 125100


def test_large_amounts_stay_within_bigint():
    assert parse("9,000,000,000.00") == 900_000_000_000
    assert format_santim(900_000_000_000) == "ETB 9,000,000,000.00"
    assert format_santim(MAX_SANTIM) == "ETB 92,233,720,368,547,758.07"
    assert add(MAX_SANTIM - 1, 1) == MAX_SANTIM
    with pytest.raises(MoneyError):
        add(MAX_SANTIM, 1)
    with pytest.raises(MoneyError):
        parse("92,233,720,368,547,758.08")
    with pytest.raises(MoneyError):
        format_santim(MAX_SANTIM + 1)


def test_format_is_locale_aware():
    assert format_santim(125050) == "ETB 1,250.50"
    assert format_santim(125050, locale="am") == "ብር 1,250.50"
    assert format_santim(125050, with_currency=False) == "1,250.50"
    assert format_santim(-5) == "ETB -0.05"
    assert format_santim(-125050, locale="am") == "ብር -1,250.50"
    assert CURRENCY == "ETB"
    assert SANTIM_PER_BIRR == 100


def test_add_and_subtract():
    assert add(100, 250, -50) == 300
    assert add() == 0
    assert subtract(1000, 999) == 1
    assert subtract(0, 500) == -500
    with pytest.raises(MoneyError):
        add(1.5, 1)
    with pytest.raises(MoneyError):
        add(True)
    with pytest.raises(MoneyError):
        subtract(0, 0.25)


def test_allocate_never_loses_a_santim():
    shares = allocate(100, [1, 1, 1])
    assert sum(shares) == 100
    assert sorted(shares) == [33, 33, 34]

    shares = allocate(1001, [2, 3, 5])
    assert sum(shares) == 1001

    shares = allocate(0, [1, 2])
    assert shares == [0, 0]

    assert allocate(10, [1, 2, 3]) == [1, 3, 6]
    assert allocate(1, [5, 5]) == [1, 0]
    assert allocate(7, [1]) == [7]


def test_allocate_handles_negative_amounts_symmetrically():
    shares = allocate(-101, [1, 1, 1])
    assert shares == [-34, -34, -33]
    assert sum(shares) == -101
    assert allocate(-10, [1, 2, 3]) == [-1, -3, -6]


def test_allocate_rejects_bad_weights():
    with pytest.raises(MoneyError):
        allocate(100, [])
    with pytest.raises(MoneyError):
        allocate(100, [0, 0])
    with pytest.raises(MoneyError):
        allocate(100, [-1, 2])
    with pytest.raises(MoneyError):
        allocate(1.5, [1, 1])
