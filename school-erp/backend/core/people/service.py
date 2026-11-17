"""Person services: create/update, search and duplicate detection (P1-13)."""

from __future__ import annotations

import difflib
import uuid
from datetime import date
from typing import Any

from app.errors import ValidationFailed
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit.service import record
from core.auth.principal import Principal
from core.custom_fields.service import merge_custom, validate_entity_values
from core.db.soft_delete import get_live
from core.people.models import (
    Person,
    build_search_name,
    full_name,
    normalize_name,
    normalize_phone,
    short_name,
    validate_name_parts,
)

FUZZY_THRESHOLD = 0.82


def _apply(person: Person, data: dict[str, Any]) -> None:
    for key in (
        "given_name_en",
        "father_name_en",
        "grandfather_name_en",
        "given_name_am",
        "father_name_am",
        "grandfather_name_am",
        "mother_name_en",
        "mother_name_am",
        "baptismal_name",
        "nickname",
        "sex",
        "date_of_birth",
        "place_of_birth",
        "nationality",
        "phone",
        "email",
        "address",
        "custom",
    ):
        if key in data:
            setattr(person, key, data[key])
    if isinstance(person.date_of_birth, str):
        person.date_of_birth = date.fromisoformat(person.date_of_birth)


def _name_triplet(person: Person) -> tuple[str, ...]:
    latin = tuple(
        normalize_name(getattr(person, key))
        for key in ("given_name_en", "father_name_en", "grandfather_name_en")
    )
    geez = tuple(
        normalize_name(getattr(person, key))
        for key in ("given_name_am", "father_name_am", "grandfather_name_am")
    )
    return latin, geez


def _levenshtein_ratio(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return difflib.SequenceMatcher(a=left, b=right).ratio()


def person_view(person: Person, locale: str = "en") -> dict[str, Any]:
    return {
        "id": str(person.id),
        "given_name_en": person.given_name_en,
        "father_name_en": person.father_name_en,
        "grandfather_name_en": person.grandfather_name_en,
        "given_name_am": person.given_name_am,
        "father_name_am": person.father_name_am,
        "grandfather_name_am": person.grandfather_name_am,
        "mother_name_en": person.mother_name_en,
        "mother_name_am": person.mother_name_am,
        "baptismal_name": person.baptismal_name,
        "nickname": person.nickname,
        "sex": person.sex,
        "date_of_birth": person.date_of_birth.isoformat() if person.date_of_birth else None,
        "place_of_birth": person.place_of_birth,
        "nationality": person.nationality,
        "phone": person.phone,
        "email": person.email,
        "address": person.address,
        "photo_file_id": str(person.photo_file_id) if person.photo_file_id else None,
        "custom": person.custom or {},
        "full_name": full_name(person, locale),
        "short_name": short_name(person, locale),
        "row_version": person.row_version,
    }


async def duplicate_warnings(
    session: AsyncSession,
    candidate: Person,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Exact triple-name + DOB matches, or phonetically similar + same DOB."""
    if candidate.date_of_birth is None:
        return []
    rows = list(
        (
            await session.execute(
                select(Person).where(
                    Person.deleted_at.is_(None),
                    Person.date_of_birth == candidate.date_of_birth,
                )
            )
        )
        .scalars()
        .all()
    )
    latin, geez = _name_triplet(candidate)
    warnings: list[dict[str, Any]] = []
    for row in rows:
        row_latin, row_geez = _name_triplet(row)
        latin_key = " ".join(latin).strip()
        row_latin_key = " ".join(row_latin).strip()
        geez_key = " ".join(geez).strip()
        row_geez_key = " ".join(row_geez).strip()
        exact = bool(latin_key and latin_key == row_latin_key) or bool(geez_key and geez_key == row_geez_key)
        similar = max(
            _levenshtein_ratio(latin_key, row_latin_key),
            _levenshtein_ratio(geez_key, row_geez_key),
        )
        if exact or similar >= FUZZY_THRESHOLD:
            warnings.append(
                {
                    "person": person_view(row),
                    "reason": "same_names_and_dob" if exact else "similar_name_and_dob",
                    "similarity": round(similar, 3),
                }
            )
        if len(warnings) >= limit:
            break
    return warnings


async def create_person(
    session: AsyncSession,
    principal: Principal | None,
    data: dict[str, Any],
    *,
    via: str | None = None,
    reason: str | None = None,
) -> tuple[Person, list[dict[str, Any]]]:
    person = Person()
    if data.get("custom") is not None:
        cleaned = await validate_entity_values(session, "person", data["custom"])
        data["custom"] = merge_custom(None, cleaned)
    _apply(person, data)
    try:
        validate_name_parts(person)
        if person.phone:
            person.phone = person.phone.strip()
        person.search_name = build_search_name(person)
    except ValueError as exc:
        raise ValidationFailed(str(exc), message_key="error.invalid_name") from exc
    warnings = await duplicate_warnings(session, person)

    session.add(person)
    await session.flush()
    await record(
        session,
        action="people.create",
        module="core",
        entity_type="person",
        entity_id=str(person.id),
        after=person_view(person),
        actor=principal,
        via=via,
        reason=reason,
    )
    await session.commit()
    return person, warnings


async def update_person(
    session: AsyncSession,
    principal: Principal | None,
    person_id: uuid.UUID,
    data: dict[str, Any],
    *,
    via: str | None = None,
) -> Person:
    person = await get_live(session, Person, person_id)
    before = person_view(person)
    if data.get("custom") is not None:
        cleaned = await validate_entity_values(session, "person", data["custom"], partial=True)
        data["custom"] = merge_custom(person.custom, cleaned)
    _apply(person, data)
    try:
        validate_name_parts(person)
    except ValueError as exc:
        raise ValidationFailed(str(exc), message_key="error.invalid_name") from exc
    person.search_name = build_search_name(person)
    person.row_version = (person.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action="people.update",
        module="core",
        entity_type="person",
        entity_id=str(person.id),
        before=before,
        after=person_view(person),
        actor=principal,
        via=via,
    )
    await session.commit()
    return person


async def search_people(
    session: AsyncSession,
    query: str,
    *,
    limit: int = 20,
    locale: str = "en",
) -> list[dict[str, Any]]:
    normalized = normalize_name(query)
    normalized_phone = normalize_phone(query)
    if not normalized and not normalized_phone:
        return []
    terms = normalized.split()
    stmt = select(Person).where(Person.deleted_at.is_(None))
    for term in terms:
        stmt = stmt.where(Person.search_name.like(f"%{term}%"))
    if normalized_phone:
        stmt = stmt.where(
            or_(Person.search_name.like(f"%{normalized}%"), Person.search_name.like(f"%{normalized_phone}%"))
        )
    rows = (
        (await session.execute(stmt.order_by(Person.given_name_en, Person.given_name_am).limit(limit)))
        .scalars()
        .all()
    )
    if not rows and normalized:
        # Fallback for typos and transliteration variants: rank every live person.
        candidates = (
            (await session.execute(select(Person).where(Person.deleted_at.is_(None)).limit(500)))
            .scalars()
            .all()
        )
        ranked = sorted(
            candidates,
            key=lambda person: _levenshtein_ratio(normalized, person.search_name),
            reverse=True,
        )
        rows = [person for person in ranked if _levenshtein_ratio(normalized, person.search_name) >= 0.55][
            :limit
        ]
    return [person_view(person, locale) for person in rows]


__all__ = [
    "FUZZY_THRESHOLD",
    "create_person",
    "duplicate_warnings",
    "person_view",
    "search_people",
    "update_person",
]
