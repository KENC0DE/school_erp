"""P1-15: Ethiopian calendar conversion, formatting and round-trips."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from core.calendar.ethiopian import (
    days_in_month,
    format_dual,
    format_ethiopian,
    from_gregorian,
    is_leap_year,
    new_year,
    to_gregorian,
)


@pytest.mark.parametrize(
    ("ec", "gregorian"),
    [
        ((2016, 1, 1), date(2023, 9, 12)),  # Ethiopian New Year announcements
        ((2017, 1, 1), date(2024, 9, 11)),
        ((2015, 13, 6), date(2023, 9, 11)),  # Pagume 6 of a leap year
        ((2016, 13, 5), date(2024, 9, 10)),
        ((2017, 4, 29), date(2025, 1, 7)),  # Genna (Christmas)
        ((2017, 5, 11), date(2025, 1, 19)),  # Timkat
    ],
)
def test_authoritative_vectors(ec, gregorian):
    assert to_gregorian(*ec) == gregorian
    assert from_gregorian(gregorian) == ec


def test_leap_year_rule():
    assert is_leap_year(2015)
    assert not is_leap_year(2016)
    assert days_in_month(2015, 13) == 6
    assert days_in_month(2016, 13) == 5
    assert days_in_month(2016, 1) == 30
    assert days_in_month(2016, 14) == 0


def test_new_year_alternates_between_11_and_12_september():
    assert new_year(2015) == date(2022, 9, 11)
    assert new_year(2016) == date(2023, 9, 12)
    assert new_year(2017) == date(2024, 9, 11)
    assert new_year(2018) == date(2025, 9, 11)


def test_round_trip_over_more_than_one_hundred_years():
    current = to_gregorian(1900, 1, 1)
    end = to_gregorian(2010, 1, 1)
    while current < end:
        assert to_gregorian(*from_gregorian(current)) == current
        current += timedelta(days=37)
    assert current >= end


def test_invalid_dates_are_rejected():
    with pytest.raises(ValueError):
        to_gregorian(2016, 13, 6)  # Pagume has five days in 2016
    with pytest.raises(ValueError):
        to_gregorian(2016, 14, 1)


def test_formatting_in_both_scripts_and_dual_mode():
    value = date(2024, 9, 11)
    assert format_ethiopian(2017, 1, 1, "en") == "Meskerem 1, 2017"
    assert format_ethiopian(2017, 1, 1, "am") == "መስከረም 1፣ 2017"
    assert format_dual(value, "ethiopian") == "Meskerem 1, 2017"
    assert "Meskerem 1, 2017" in format_dual(value, "both")
    assert format_dual(value, "gregorian") == "11 Sep 2024"
