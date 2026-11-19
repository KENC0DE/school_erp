"""Person search and maintenance endpoints (P1-13)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session
from core.db.soft_delete import get_live
from core.people.models import Person
from core.people.schemas import PersonInput
from core.people.service import create_person, person_view, search_people, update_person

router = APIRouter(prefix="/people", tags=["people"])


@router.get("/search", dependencies=[Depends(require("people.view"))])
async def people_search(
    q: str = Query(min_length=1, max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
    principal: Principal = Depends(require("people.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    items = await search_people(session, q, limit=limit, locale=principal.locale)
    return {"items": items, "next_cursor": None}


@router.post("", dependencies=[Depends(require("people.manage"))])
async def people_create(
    payload: PersonInput,
    principal: Principal = Depends(require("people.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    person, warnings = await create_person(session, principal, payload.model_dump(), via=principal.via)
    return {
        "person": person_view(person, principal.locale),
        "duplicate_warnings": warnings,
    }


@router.get("/{person_id}", dependencies=[Depends(require("people.view"))])
async def people_get(
    person_id: uuid.UUID,
    principal: Principal = Depends(require("people.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    person = await get_live(session, Person, person_id)
    return person_view(person, principal.locale)


@router.patch("/{person_id}", dependencies=[Depends(require("people.manage"))])
async def people_update(
    person_id: uuid.UUID,
    payload: PersonInput,
    principal: Principal = Depends(require("people.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    person = await update_person(
        session,
        principal,
        person_id,
        payload.model_dump(exclude_unset=True),
        via=principal.via,
    )
    return person_view(person, principal.locale)
