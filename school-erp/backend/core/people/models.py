"""Shared person and three-part name model (ARCH §5.8, P1-13)."""

from __future__ import annotations

import re
import unicodedata
import uuid

from sqlalchemy import JSON, Date, Index, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import BusinessModel

# Ethiopic homophone series: variants that sound the same are folded so search
# and duplicate detection treat them equally. Kept deliberately small and
# documented rather than attempting full transliteration.
GEEZ_FOLD = {
    "ሃ": "ሀ",
    "ሐ": "ሀ",
    "ሓ": "ሀ",
    "ኻ": "ሀ",
    "ኀ": "ሀ",
    "ኃ": "ሀ",
    "ሡ": "ሱ",
    "ሢ": "ሲ",
    "ሣ": "ሳ",
    "ሤ": "ሴ",
    "ሥ": "ስ",
    "ሦ": "ሶ",
    "ሧ": "ሷ",
    "ሠ": "ሰ",
    "ረ": "ረ",
    "ሹ": "ሹ",
    "ሺ": "ሺ",
    "ሻ": "ሻ",
    "ሼ": "ሼ",
    "ሽ": "ሽ",
    "ሾ": "ሾ",
    "ሿ": "ሿ",
    "ቈ": "ቀ",
    "ቊ": "ቀ",
    "ቋ": "ቃ",
    "ቌ": "ቄ",
    "ቍ": "ቅ",
    "ኋ": "ኋ",
    "ኈ": "ኈ",
    "ኊ": "ኈ",
    "ኍ": "ኍ",
    "ዐ": "አ",
    "ዓ": "አ",
    "ዑ": "ኡ",
    "ዒ": "ኢ",
    "ጸ": "ጸ",
    "ፀ": "ጸ",
    "ፁ": "ጹ",
    "ፂ": "ጺ",
    "ፃ": "ጻ",
    "ፄ": "ጼ",
    "ፅ": "ጽ",
    "ፆ": "ጾ",
    "ኰ": "ከ",
    "ኲ": "ከ",
    "ኳ": "ካ",
    "ኴ": "ኬ",
    "ኵ": "ክ",
    "ጒ": "ገ",
    "ጔ": "ጌ",
    "ጕ": "ግ",
    "ቐ": "ቀ",
    "ቑ": "ቁ",
    "ቒ": "ቂ",
    "ቓ": "ቃ",
    "ቔ": "ቄ",
    "ቕ": "ቅ",
    "ቖ": "ቆ",
}

LATIN_FOLD = str.maketrans({"ä": "a", "á": "a", "é": "e", "è": "e", "í": "i", "ó": "o", "ú": "u"})


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKC", value).strip().lower()
    folded = "".join(GEEZ_FOLD.get(char, char) for char in decomposed)
    folded = folded.translate(LATIN_FOLD)
    folded = re.sub(r"[^\w\u1200-\u137f]+", " ", folded, flags=re.UNICODE)
    return re.sub(r"\s+", " ", folded).strip()


def normalize_phone(value: str | None) -> str:
    if not value:
        return ""
    digits = re.sub(r"\D", "", value)
    if digits.startswith("251") and len(digits) == 12:
        digits = "0" + digits[3:]
    return digits


class Person(BusinessModel):
    __tablename__ = "persons"
    __table_args__ = (
        Index(
            "ix_persons_search_name",
            "search_name",
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_persons_dob", "date_of_birth"),
    )

    given_name_en: Mapped[str | None] = mapped_column(String(120))
    father_name_en: Mapped[str | None] = mapped_column(String(120))
    grandfather_name_en: Mapped[str | None] = mapped_column(String(120))
    given_name_am: Mapped[str | None] = mapped_column(String(120))
    father_name_am: Mapped[str | None] = mapped_column(String(120))
    grandfather_name_am: Mapped[str | None] = mapped_column(String(120))
    mother_name_en: Mapped[str | None] = mapped_column(String(120))
    mother_name_am: Mapped[str | None] = mapped_column(String(120))
    baptismal_name: Mapped[str | None] = mapped_column(String(120))
    nickname: Mapped[str | None] = mapped_column(String(120))
    search_name: Mapped[str] = mapped_column(Text, default="", nullable=False)

    sex: Mapped[str | None] = mapped_column(String(20))
    date_of_birth: Mapped[object | None] = mapped_column(Date)
    place_of_birth: Mapped[str | None] = mapped_column(String(200))
    nationality: Mapped[str | None] = mapped_column(String(80))
    phone: Mapped[str | None] = mapped_column(String(32), index=True)
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    address: Mapped[str | None] = mapped_column(Text)
    photo_file_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    custom: Mapped[dict | None] = mapped_column(JSON)


EN_PARTS = ("given_name_en", "father_name_en", "grandfather_name_en")
AM_PARTS = ("given_name_am", "father_name_am", "grandfather_name_am")


def validate_name_parts(person: Person) -> None:
    latin = [getattr(person, key) for key in EN_PARTS]
    geez = [getattr(person, key) for key in AM_PARTS]
    if not any(latin) and not any(geez):
        raise ValueError("At least one name script is required")
    if any(latin) and not all(latin):
        raise ValueError("Latin names need all three parts: given, father and grandfather")
    if any(geez) and not all(geez):
        raise ValueError("Amharic names need all three parts: given, father and grandfather")


def _parts(person: Person, locale: str) -> list[str]:
    primary = AM_PARTS if locale.startswith("am") else EN_PARTS
    fallback = EN_PARTS if primary is AM_PARTS else AM_PARTS
    values = [getattr(person, key) for key in primary]
    if all(values):
        return values
    mixed = [
        getattr(person, key) or getattr(person, other_key)
        for key, other_key in zip(primary, fallback, strict=True)
    ]
    if all(mixed):
        return mixed
    return list(values if any(values) else [getattr(person, key) for key in fallback])


def full_name(person: Person, locale: str = "en") -> str:
    return " ".join(part for part in _parts(person, locale) if part)


def short_name(person: Person, locale: str = "en") -> str:
    return " ".join(part for part in _parts(person, locale)[:2] if part)


def build_search_name(person: Person) -> str:
    chunks = [
        *[getattr(person, key) for key in EN_PARTS],
        *[getattr(person, key) for key in AM_PARTS],
        person.mother_name_en,
        person.mother_name_am,
        person.nickname,
        person.baptismal_name,
        person.phone,
        normalize_phone(person.phone),
        person.email,
    ]
    seen = [normalize_name(chunk) for chunk in chunks if chunk]
    return " ".join(dict.fromkeys(seen))


__all__ = [
    "AM_PARTS",
    "EN_PARTS",
    "GEEZ_FOLD",
    "Person",
    "build_search_name",
    "full_name",
    "normalize_name",
    "normalize_phone",
    "short_name",
    "validate_name_parts",
]
