"""Custom field administration and validation endpoints (P1-17)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.deps import require
from core.auth.principal import Principal
from core.custom_fields.service import (
    create_definition,
    definition_view,
    definitions_for,
    delete_definition,
    get_definition,
    list_entity_types,
    update_definition,
    validate_entity_values,
)
from core.db.deps import get_session

router = APIRouter(prefix="/custom-fields", tags=["custom-fields"])


class DefinitionInput(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    label_key: str = Field(min_length=1, max_length=160)
    help_key: str | None = Field(default=None, max_length=160)
    field_type: str = Field(min_length=1, max_length=20)
    required: bool = False
    options: list[str] | None = None
    min_value: Any = None
    max_value: Any = None
    max_length: int | None = Field(default=None, ge=1)
    pattern: str | None = Field(default=None, max_length=200)
    visible_roles: list[str] | None = None
    active: bool = True
    order: int = 0
    group_key: str | None = Field(default=None, max_length=80)


class DefinitionUpdate(BaseModel):
    key: str | None = Field(default=None, min_length=1, max_length=80)
    label_key: str | None = Field(default=None, min_length=1, max_length=160)
    help_key: str | None = Field(default=None, max_length=160)
    field_type: str | None = Field(default=None, min_length=1, max_length=20)
    required: bool | None = None
    options: list[str] | None = None
    min_value: Any = None
    max_value: Any = None
    max_length: int | None = Field(default=None, ge=1)
    pattern: str | None = Field(default=None, max_length=200)
    visible_roles: list[str] | None = None
    active: bool | None = None
    order: int | None = None
    group_key: str | None = Field(default=None, max_length=80)


class ValuesInput(BaseModel):
    values: dict[str, Any]
    partial: bool = False


@router.get("/entity-types", dependencies=[Depends(require("custom_fields.view"))])
async def entity_types(session: AsyncSession = Depends(get_session)) -> dict:
    return {"items": await list_entity_types(session)}


@router.get("", dependencies=[Depends(require("custom_fields.view"))])
async def list_definitions(
    entity_type: str = Query(min_length=1, max_length=60),
    include_inactive: bool = Query(default=False),
    principal: Principal = Depends(require("custom_fields.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    rows = await definitions_for(
        session,
        entity_type,
        principal=principal,
        active_only=not include_inactive,
    )
    return {"items": [definition_view(row) for row in rows], "next_cursor": None}


@router.post("/{entity_type}", dependencies=[Depends(require("custom_fields.manage"))])
async def create_custom_field(
    entity_type: str,
    payload: DefinitionInput,
    principal: Principal = Depends(require("custom_fields.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    defn = await create_definition(
        session,
        principal,
        entity_type,
        payload.model_dump(),
        via=principal.via,
    )
    return definition_view(defn)


@router.patch("/{field_id}", dependencies=[Depends(require("custom_fields.manage"))])
async def update_custom_field(
    field_id: uuid.UUID,
    payload: DefinitionUpdate,
    principal: Principal = Depends(require("custom_fields.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    defn = await get_definition(session, field_id)
    updated = await update_definition(
        session,
        principal,
        defn.id,
        payload.model_dump(exclude_unset=True),
        via=principal.via,
    )
    return definition_view(updated)


@router.delete("/{field_id}", dependencies=[Depends(require("custom_fields.manage"))])
async def delete_custom_field(
    field_id: uuid.UUID,
    reason: str | None = Query(default=None, max_length=500),
    principal: Principal = Depends(require("custom_fields.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await delete_definition(session, principal, field_id, reason=reason, via=principal.via)
    return {"id": str(field_id), "deleted": True}


@router.post("/{entity_type}/validate", dependencies=[Depends(require("custom_fields.view"))])
async def validate_values(
    entity_type: str,
    payload: ValuesInput,
    principal: Principal = Depends(require("custom_fields.view")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    cleaned = await validate_entity_values(session, entity_type, payload.values, partial=payload.partial)
    return {"values": cleaned, "valid": True}
