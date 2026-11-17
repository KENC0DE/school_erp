"""Translation editor API (P1-18).

Registered before the public ``/i18n/{locale}/{namespace}`` bundle route so
``/i18n/editor/...`` is not captured as a locale/namespace pair.
"""

from __future__ import annotations

from core.auth.deps import require
from core.auth.principal import Principal
from core.db.deps import get_session
from core.i18n.editor import (
    all_namespaces,
    export_entries,
    import_entries,
    list_entries,
    reset_entry,
    set_entry,
    stats,
)
from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/i18n/editor", tags=["i18n-editor"])


class EntryUpdate(BaseModel):
    value: str = Field(min_length=1, max_length=4000)
    status: str = Field(default="approved", max_length=20)


class ImportRequest(BaseModel):
    namespace: str = Field(min_length=1, max_length=60)
    locale: str = Field(min_length=2, max_length=8)
    format: str = Field(pattern="^(csv|json)$")
    content: str
    status: str = Field(default="approved", max_length=20)
    dry_run: bool = False


@router.get("/namespaces", dependencies=[Depends(require("i18n.view"))])
async def editor_namespaces(session: AsyncSession = Depends(get_session)) -> dict:
    return {"items": await all_namespaces(session)}


@router.get("/entries", dependencies=[Depends(require("i18n.view"))])
async def editor_entries(
    locale: str = Query(default="am", min_length=2, max_length=8),
    namespace: str | None = Query(default=None, max_length=60),
    q: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None, max_length=20),
    layer: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await list_entries(
        session,
        locale=locale,
        namespace=namespace,
        q=q,
        status=status,
        layer=layer,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", dependencies=[Depends(require("i18n.view"))])
async def editor_stats(
    locale: str = Query(default="am", min_length=2, max_length=8),
    namespace: str | None = Query(default=None, max_length=60),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await stats(session, locale=locale, namespace=namespace)


@router.put(
    "/entries/{namespace}/{key}/{locale}",
    dependencies=[Depends(require("i18n.manage"))],
)
async def update_entry(
    namespace: str,
    key: str,
    locale: str,
    payload: EntryUpdate,
    principal: Principal = Depends(require("i18n.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await set_entry(
        session,
        principal,
        namespace,
        key,
        locale,
        payload.value,
        status=payload.status,
        via=principal.via,
    )


@router.post(
    "/entries/{namespace}/{key}/{locale}/reset",
    dependencies=[Depends(require("i18n.manage"))],
)
async def reset_translation(
    namespace: str,
    key: str,
    locale: str,
    principal: Principal = Depends(require("i18n.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await reset_entry(
        session, principal, namespace, key, locale, via=principal.via
    )


@router.post("/import", dependencies=[Depends(require("i18n.manage"))])
async def import_translations(
    payload: ImportRequest,
    principal: Principal = Depends(require("i18n.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await import_entries(
        session,
        principal,
        namespace=payload.namespace,
        locale=payload.locale,
        fmt=payload.format,
        content=payload.content,
        status=payload.status,
        dry_run=payload.dry_run,
        via=principal.via,
    )


@router.get("/export", dependencies=[Depends(require("i18n.view"))])
async def export_translations(
    locale: str = Query(default="am", min_length=2, max_length=8),
    namespace: str | None = Query(default=None, max_length=60),
    format: str = Query(default="json", pattern="^(csv|json)$"),
    session: AsyncSession = Depends(get_session),
) -> Response:
    body, filename, media_type = await export_entries(
        session, locale=locale, namespace=namespace, fmt=format
    )
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
