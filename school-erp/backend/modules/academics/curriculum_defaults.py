"""Shipped curriculum starter data (ARCH §9.1).

Every profile here is **starter data**, not an official syllabus: it is marked
``is_starter=True`` and ``is_verified=False`` until the school confirms it
against its own curriculum or an official source. The school may edit any
profile, duplicate it, or deactivate it; the bootstrap only creates what is
missing and never overwrites edits.

Later phases add the remaining parts of a bundle (mark structures, grade
scales, promotion rules, document templates) to the same profile rows.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class StarterSubject:
    code: str
    name: str
    name_am: str
    sort_order: int


@dataclass(frozen=True)
class StarterProfile:
    code: str
    name: str
    name_am: str
    description: str
    term_system: str
    sort_order: int
    levels: Mapping[str, tuple[str, ...]]


STARTER_SUBJECTS: tuple[StarterSubject, ...] = (
    StarterSubject("amharic", "Amharic", "አማርኛ", 0),
    StarterSubject("english", "English", "እንግሊዝኛ", 1),
    StarterSubject("mathematics", "Mathematics", "ሒሳብ", 2),
    StarterSubject("environmental_science", "Environmental Science", "የአካባቢ ሳይንስ", 3),
    StarterSubject("science", "Science", "ሳይንስ", 4),
    StarterSubject("social_studies", "Social Studies", "ማህበራዊ ጥናት", 5),
    StarterSubject("civics", "Civics and Ethical Education", "ስነ-ዜጋ እና ሥነ-ምግባር", 6),
    StarterSubject("physical_education", "Physical Education", "የአካል ስርዓተ ትምህርት", 7),
    StarterSubject("arts", "Arts", "ሥነ-ጥበብ", 8),
    StarterSubject("ict", "Information and Communication Technology", "አይሲቲ", 9),
    StarterSubject("biology", "Biology", "ባዮሎጂ", 10),
    StarterSubject("chemistry", "Chemistry", "ኬሚስትሪ", 11),
    StarterSubject("physics", "Physics", "ፊዚክስ", 12),
    StarterSubject("geography", "Geography", "ጂኦግራፊ", 13),
    StarterSubject("history", "History", "ታሪክ", 14),
    StarterSubject("foreign_language", "Foreign Language", "የውጭ ቋንቋ", 15),
    StarterSubject("music", "Music", "ሙዚቃ", 16),
)

_PRIMARY_LOWER = ("amharic", "english", "mathematics", "environmental_science", "arts", "physical_education")
_PRIMARY_MIDDLE = (
    "amharic",
    "english",
    "mathematics",
    "science",
    "social_studies",
    "civics",
    "arts",
    "physical_education",
)
_PRIMARY_UPPER = (
    "amharic",
    "english",
    "mathematics",
    "science",
    "social_studies",
    "civics",
    "ict",
    "physical_education",
)
_SECONDARY = (
    "amharic",
    "english",
    "mathematics",
    "biology",
    "chemistry",
    "physics",
    "geography",
    "history",
    "civics",
    "ict",
    "physical_education",
)
_PRIVATE_LOWER = (
    "english",
    "mathematics",
    "science",
    "social_studies",
    "amharic",
    "arts",
    "physical_education",
)
_PRIVATE_UPPER = (
    "english",
    "mathematics",
    "science",
    "social_studies",
    "amharic",
    "ict",
    "arts",
    "physical_education",
)
_PRIVATE_SECONDARY = (
    "english",
    "mathematics",
    "biology",
    "chemistry",
    "physics",
    "geography",
    "history",
    "amharic",
    "ict",
    "physical_education",
)
_INTL_EARLY = ("english", "mathematics", "arts", "physical_education", "music")
_INTL_PRIMARY = (
    "english",
    "mathematics",
    "science",
    "social_studies",
    "ict",
    "arts",
    "music",
    "physical_education",
    "foreign_language",
)
_INTL_MIDDLE = (
    "english",
    "mathematics",
    "science",
    "social_studies",
    "ict",
    "arts",
    "physical_education",
    "foreign_language",
)
_INTL_SECONDARY = (
    "english",
    "mathematics",
    "biology",
    "chemistry",
    "physics",
    "geography",
    "history",
    "ict",
    "physical_education",
    "foreign_language",
)

STARTER_PROFILES: tuple[StarterProfile, ...] = (
    StarterProfile(
        code="ethiopian_national",
        name="Ethiopian National",
        name_am="የኢትዮጵያ ብሔራዊ ሥርዓተ ትምህርት",
        description=(
            "Starter subjects by level following the Ethiopian national structure. "
            "Verify against the current official curriculum before enrolling students."
        ),
        term_system="semester",
        sort_order=0,
        levels={
            "g1": _PRIMARY_LOWER,
            "g2": _PRIMARY_LOWER,
            "g3": _PRIMARY_LOWER,
            "g4": _PRIMARY_LOWER,
            "g5": _PRIMARY_MIDDLE,
            "g6": _PRIMARY_MIDDLE,
            "g7": _PRIMARY_UPPER,
            "g8": _PRIMARY_UPPER,
            "g9": _SECONDARY,
            "g10": _SECONDARY,
            "g11": _SECONDARY,
            "g12": _SECONDARY,
        },
    ),
    StarterProfile(
        code="private_custom",
        name="Private: Custom",
        name_am="የግል፡ ብጁ",
        description=(
            "A neutral starting point for private schools. Duplicate it and adjust "
            "the subjects, credits and term system to match your own programme."
        ),
        term_system="semester",
        sort_order=1,
        levels={
            "g1": _PRIVATE_LOWER,
            "g2": _PRIVATE_LOWER,
            "g3": _PRIVATE_LOWER,
            "g4": _PRIVATE_LOWER,
            "g5": _PRIVATE_UPPER,
            "g6": _PRIVATE_UPPER,
            "g7": _PRIVATE_UPPER,
            "g8": _PRIVATE_UPPER,
            "g9": _PRIVATE_SECONDARY,
            "g10": _PRIVATE_SECONDARY,
            "g11": _PRIVATE_SECONDARY,
            "g12": _PRIVATE_SECONDARY,
        },
    ),
    StarterProfile(
        code="international_generic",
        name="International: Generic",
        name_am="ዓለም አቀፍ፡ አጠቃላይ",
        description=(
            "A generic international-style bundle with an early-years programme and "
            "a foreign language. Starter data only; verify against your accreditation."
        ),
        term_system="semester",
        sort_order=2,
        levels={
            "kg1": _INTL_EARLY,
            "kg2": _INTL_EARLY,
            "kg3": _INTL_EARLY,
            "g1": _INTL_PRIMARY,
            "g2": _INTL_PRIMARY,
            "g3": _INTL_PRIMARY,
            "g4": _INTL_PRIMARY,
            "g5": _INTL_PRIMARY,
            "g6": _INTL_MIDDLE,
            "g7": _INTL_MIDDLE,
            "g8": _INTL_MIDDLE,
            "g9": _INTL_SECONDARY,
            "g10": _INTL_SECONDARY,
            "g11": _INTL_SECONDARY,
            "g12": _INTL_SECONDARY,
        },
    ),
)


__all__ = ["STARTER_PROFILES", "STARTER_SUBJECTS", "StarterProfile", "StarterSubject"]
