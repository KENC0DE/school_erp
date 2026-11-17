from __future__ import annotations

import pytest
from erp_shared.money import MoneyError, allocate, format_santim, parse


def test_parse_accepts_formats():
    assert parse("1,250.50") == 125050
    assert parse("ETB 10") == 1000
    assert parse("ብር 9.99") == 999
    assert parse(1250) == 1250
    assert parse("0.005") == 1


def test_parse_rejects_garbage():
    with pytest.raises(MoneyError):
        parse("not money")


def test_format_is_locale_aware():
    assert format_santim(125050) == "ETB 1,250.50"
    assert format_santim(125050, locale="am") == "ብር 1,250.50"
    assert format_santim(-5) == "ETB -0.05"


def test_allocate_never_loses_a_santim():
    shares = allocate(100, [1, 1, 1])
    assert sum(shares) == 100
    assert sorted(shares) == [33, 33, 34]

    shares = allocate(1001, [2, 3, 5])
    assert sum(shares) == 1001

    shares = allocate(0, [1, 2])
    assert shares == [0, 0]


def test_allocate_rejects_bad_weights():
    with pytest.raises(MoneyError):
        allocate(100, [])
    with pytest.raises(MoneyError):
        allocate(100, [0, 0])
