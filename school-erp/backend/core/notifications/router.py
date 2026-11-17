"""Notification centre, templates, delivery logs and admin send (P1-23)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.deps import authenticated, require
from core.auth.principal import Principal
from core.db.deps import get_session
from core.notifications.service import (
    create_template,
    delete_template,
    deliver_notification,
    list_deliveries,
    list_for_user,
    list_templates,
    mark_all_read,
    mark_read,
    send_to_users,
    unread_count,
    update_template,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])

Channel = Literal["in_app", "email", "push", "sms", "telegram"]


class TemplateCreateRequest(BaseModel):
    key: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    category: str = Field(default="general", max_length=30)
    namespace: str = Field(default="core", max_length=60)
    title_key: str = Field(min_length=2, max_length=200)
    body_key: str = Field(min_length=2, max_length=200)
    default_channels: list[Channel] = Field(default_factory=lambda: ["in_app"])
    module: str = Field(default="core", max_length=60)


class TemplateUpdateRequest(BaseModel):
    row_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, max_length=30)
    namespace: str | None = Field(default=None, max_length=60)
    title_key: str | None = Field(default=None, min_length=2, max_length=200)
    body_key: str | None = Field(default=None, min_length=2, max_length=200)
    default_channels: list[Channel] | None = None
    is_active: bool | None = None


class SendRequest(BaseModel):
    user_ids: list[str] = Field(min_length=1, max_length=500)
    template_key: str = Field(min_length=2, max_length=80)
    params: dict[str, Any] = Field(default_factory=dict)
    channels: list[Channel] | None = None
    link: str | None = Field(default=None, max_length=300)


@router.get("", dependencies=[Depends(authenticated)])
async def inbox(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(authenticated),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await list_for_user(
        session,
        principal.actor_id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )


@router.get("/unread-count", dependencies=[Depends(authenticated)])
async def unread(
    principal: Principal = Depends(authenticated),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await unread_count(session, principal.actor_id)


@router.post("/read-all", dependencies=[Depends(authenticated)])
async def read_all(
    principal: Principal = Depends(authenticated),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await mark_all_read(session, principal)


@router.post("/{notification_id}/read", dependencies=[Depends(authenticated)])
async def read_one(
    notification_id: str,
    principal: Principal = Depends(authenticated),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await mark_read(session, principal, notification_id)


@router.get("/templates", dependencies=[Depends(require("notifications.view"))])
async def templates(
    category: str | None = Query(default=None, max_length=30),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"items": await list_templates(session, category=category)}


@router.post(
    "/templates",
    status_code=201,
    dependencies=[Depends(require("notifications.manage"))],
)
async def create(
    payload: TemplateCreateRequest,
    principal: Principal = Depends(require("notifications.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await create_template(
        session,
        principal,
        key=payload.key,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        namespace=payload.namespace,
        title_key=payload.title_key,
        body_key=payload.body_key,
        channels=list(payload.default_channels),
        module=payload.module,
    )


@router.put(
    "/templates/{template_id}",
    dependencies=[Depends(require("notifications.manage"))],
)
async def update(
    template_id: str,
    payload: TemplateUpdateRequest,
    principal: Principal = Depends(require("notifications.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    values = payload.model_dump(exclude_unset=True, exclude={"row_version"})
    values = {key: value for key, value in values.items() if value is not None}
    return await update_template(
        session,
        principal,
        template_id,
        row_version=payload.row_version,
        values=values,
    )


@router.delete(
    "/templates/{template_id}",
    dependencies=[Depends(require("notifications.manage"))],
)
async def remove(
    template_id: str,
    principal: Principal = Depends(require("notifications.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await delete_template(session, principal, template_id)


@router.get("/deliveries", dependencies=[Depends(require("notifications.view"))])
async def deliveries(
    notification_id: str | None = Query(default=None),
    template_key: str | None = Query(default=None, max_length=80),
    status: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {
        "items": await list_deliveries(
            session,
            notification_id=notification_id,
            template_key=template_key,
            status=status,
            limit=limit,
        )
    }


@router.post("/send", dependencies=[Depends(require("notifications.manage"))])
async def send(
    payload: SendRequest,
    principal: Principal = Depends(require("notifications.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await send_to_users(
        session,
        user_ids=payload.user_ids,
        template_key=payload.template_key,
        params=payload.params,
        channels=list(payload.channels) if payload.channels is not None else None,
        link=payload.link,
        actor=principal,
    )


@router.post(
    "/{notification_id}/deliver",
    dependencies=[Depends(require("notifications.manage"))],
)
async def deliver(
    notification_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await deliver_notification(
        session,
        notification_id,
        mailer=request.app.state.mailer,
        sms=request.app.state.sms,
        push=request.app.state.push,
    )
