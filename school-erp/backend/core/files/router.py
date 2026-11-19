from __future__ import annotations

from urllib.parse import quote

from app.errors import NotFound
from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.deps import authenticated, public_access, require
from core.auth.principal import Principal
from core.db.deps import get_session
from core.files.deps import get_app_settings, get_storage
from core.files.models import StoredFile
from core.files.service import (
    delete_file,
    get_file,
    list_files,
    signed_file_url,
    upload_file,
)
from core.files.storage import Storage

router = APIRouter(prefix="/files", tags=["files"])


@router.post("", status_code=201, dependencies=[Depends(require("files.upload"))])
async def upload(
    file: UploadFile = File(...),
    owner_entity_type: str | None = Form(default=None),
    owner_entity_id: str | None = Form(default=None),
    is_private: bool = Form(default=True),
    principal: Principal = Depends(require("files.upload")),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
    settings=Depends(get_app_settings),  # type: ignore[no-untyped-def]
) -> dict:
    data = await file.read(settings.storage_max_upload_bytes + 1)
    return await upload_file(
        session,
        principal,
        storage,
        settings,
        filename=file.filename,
        content_type=file.content_type,
        data=data,
        owner_entity_type=owner_entity_type or None,
        owner_entity_id=owner_entity_id or None,
        is_private=is_private,
    )


@router.get("", dependencies=[Depends(require("files.view"))])
async def list_files_endpoint(
    owner_entity_type: str | None = Query(default=None),
    owner_entity_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
    settings=Depends(get_app_settings),  # type: ignore[no-untyped-def]
) -> dict:
    items = await list_files(
        session,
        storage,
        settings,
        owner_entity_type=owner_entity_type,
        owner_entity_id=owner_entity_id,
        limit=limit,
    )
    return {"items": items}


@router.get("/content/{object_key:path}", dependencies=[Depends(public_access)])
async def content(
    object_key: str,
    expires: int = Query(...),
    signature: str = Query(...),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
) -> Response:
    # A soft-deleted file stops serving immediately, but links stay valid for
    # their short TTL otherwise.
    row = (
        await session.execute(
            select(StoredFile).where(
                or_(StoredFile.object_key == object_key, StoredFile.thumbnail_key == object_key)
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("No file for that link", message_key="error.file.not_found")
    storage.verify(object_key, expires, signature)
    data = await storage.get(object_key)
    name = "thumbnail.jpg" if object_key == row.thumbnail_key else row.original_name
    mime = "image/jpeg" if object_key == row.thumbnail_key else row.mime
    return Response(
        content=data,
        media_type=mime,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(name)}",
            "Cache-Control": "private, max-age=60",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{file_id}", dependencies=[Depends(authenticated)])
async def detail(
    file_id: str,
    principal: Principal = Depends(authenticated),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
    settings=Depends(get_app_settings),  # type: ignore[no-untyped-def]
) -> dict:
    return await get_file(session, principal, storage, settings, file_id)


@router.get("/{file_id}/url", dependencies=[Depends(authenticated)])
async def signed_url(
    file_id: str,
    thumbnail: bool = Query(default=False),
    expires_in: int | None = Query(default=None, ge=30, le=86_400),
    principal: Principal = Depends(authenticated),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
    settings=Depends(get_app_settings),  # type: ignore[no-untyped-def]
) -> dict:
    return await signed_file_url(
        session,
        principal,
        storage,
        settings,
        file_id,
        thumbnail=thumbnail,
        expires_in=expires_in,
    )


@router.delete("/{file_id}", dependencies=[Depends(authenticated)])
async def remove(
    file_id: str,
    principal: Principal = Depends(authenticated),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await delete_file(session, principal, file_id)
