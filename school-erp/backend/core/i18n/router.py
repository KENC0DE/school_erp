from __future__ import annotations

import hashlib
import json

from core.auth.deps import public_access
from core.db.deps import get_session
from core.i18n.service import merged_namespace, namespaces_for
from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/i18n", tags=["i18n"])

LOCALES = [
    {"code": "en", "name": "English", "script": "Latin", "direction": "ltr"},
    {"code": "am", "name": "አማርኛ", "script": "Ethiopic", "direction": "ltr"},
]


@router.get("/locales", dependencies=[Depends(public_access)])
async def locales() -> dict:
    return {"items": LOCALES}


@router.get("/{locale}/namespaces", dependencies=[Depends(public_access)])
async def namespaces(locale: str, session: AsyncSession = Depends(get_session)) -> dict:
    return {"items": await namespaces_for(session, locale)}


@router.get("/{locale}/{namespace}", dependencies=[Depends(public_access)])
async def bundle(
    locale: str,
    namespace: str,
    response: Response,
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
    session: AsyncSession = Depends(get_session),
) -> Response:
    if locale not in {item["code"] for item in LOCALES}:
        locale = "en"
    data = await merged_namespace(session, locale, namespace)
    body = json.dumps(
        {"locale": locale, "namespace": namespace, "messages": data}, ensure_ascii=False, sort_keys=True
    )
    etag = 'W/"' + hashlib.sha256(body.encode()).hexdigest()[:32] + '"'
    headers = {"ETag": etag, "Cache-Control": "no-cache"}
    if if_none_match == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="application/json", headers=headers)
