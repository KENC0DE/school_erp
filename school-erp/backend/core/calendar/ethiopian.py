"""Ethiopian (Amete Mihret) <-> Gregorian conversion.

JDN = 1723856 + 365*year + year//4 + 30*month + day - 31.
Ethiopian year Y is leap when Y % 4 == 3 (Pagume has six days).

Validated against published new-year announcements (1 Meskerem 2016 =
12 Sep 2023, 1 Meskerem 2017 = 11 Sep 2024) and the movable feasts Genna and
Timkat (7/8 and 19/20 January depending on the preceding leap year).
"""

from __future__ import annotations

from datetime import date, timedelta

ETHIOPIAN_EPOCH_JDN = 1723856
GREGORIAN_ORDINAL_OFFSET = 1721425

ETHIOPIAN_MONTHS_AM = (
    "መስከረም",
    "ጥቅምት",
    "ኅዳር",
    "ታኅሣሥ",
    "ጥር",
    "የካቲት",
    "መጋቢት",
    "ሚያዝያ",
    "ግንቦት",
    "ሰኔ",
    "ሐምሌ",
    "ነሐሴ",
    "ጳጉሜ",
)
ETHIOPIAN_MONTHS_EN = (
    "Meskerem",
    "Tikimt",
    "Hidar",
    "Tahsas",
    "Tir",
    "Yekatit",
    "Megabit",
    "Miazia",
    "Ginbot",
    "Sene",
    "Hamle",
    "Nehase",
    "Pagume",
)


def is_leap_year(year: int) -> bool:
    return year % 4 == 3


def days_in_month(year: int, month: int) -> int:
    if month < 1 or month > 13:
        return 0
    if month == 13:
        return 6 if is_leap_year(year) else 5
    return 30


def to_jdn(year: int, month: int, day: int) -> int:
    if not 1 <= month <= 13:
        raise ValueError("Ethiopian month must be 1..13")
    if not 1 <= day <= days_in_month(year, month):
        raise ValueError("Day is outside the Ethiopian month")
    return ETHIOPIAN_EPOCH_JDN + 365 * year + year // 4 + 30 * month + day - 31


def from_jdn(jdn: int) -> tuple[int, int, int]:
    offset = jdn - ETHIOPIAN_EPOCH_JDN
    cycle, remainder = divmod(offset, 1461)
    n = remainder % 365 + 365 * (remainder // 1460)
    year = 4 * cycle + remainder // 365 - remainder // 1460
    return year, n // 30 + 1, n % 30 + 1


def to_gregorian(year: int, month: int, day: int) -> date:
    return date.fromordinal(to_jdn(year, month, day) - GREGORIAN_ORDINAL_OFFSET)


def from_gregorian(value: date) -> tuple[int, int, int]:
    return from_jdn(value.toordinal() + GREGORIAN_ORDINAL_OFFSET)


def format_ethiopian(year: int, month: int, day: int, locale: str = "en") -> str:
    months = ETHIOPIAN_MONTHS_AM if locale.startswith("am") else ETHIOPIAN_MONTHS_EN
    if not 1 <= month <= 13:
        return f"{day}/{month}/{year}"
    if locale.startswith("am"):
        return f"{months[month - 1]} {day}፣ {year}"
    return f"{months[month - 1]} {day}, {year}"


def format_dual(value: date, preference: str = "both", locale: str = "en") -> str:
    year, month, day = from_gregorian(value)
    gregorian = value.strftime("%d %b %Y")
    ethiopian = format_ethiopian(year, month, day, locale)
    if preference == "gregorian":
        return gregorian
    if preference == "ethiopian":
        return ethiopian
    return f"{ethiopian} ({gregorian})"


def new_year(year: int) -> date:
    return to_gregorian(year, 1, 1)


def add_days(value: date, days: int) -> date:
    return value + timedelta(days=days)


__all__ = [
    "ETHIOPIAN_MONTHS_AM",
    "ETHIOPIAN_MONTHS_EN",
    "add_days",
    "days_in_month",
    "format_dual",
    "format_ethiopian",
    "from_gregorian",
    "from_jdn",
    "is_leap_year",
    "new_year",
    "to_gregorian",
    "to_jdn",
]
