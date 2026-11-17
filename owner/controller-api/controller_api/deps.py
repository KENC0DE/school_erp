from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from controller_api.db import Database
from controller_api.models import CPUser
from controller_api.security import decode_token


class CPPrincipal:
    def __init__(self, user: CPUser) -> None:
        self.user = user
        self.id = user.id
        self.role = user.role
        self.email = user.email
        self.display_name = user.display_name

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"

    def can_write(self) -> bool:
        return self.role in {"owner", "support"}


def get_db(request: Request) -> Database:
    return request.app.state.db


async def get_session(request: Request):
    database: Database = request.app.state.db
    async with database.session() as session:
        yield session


async def current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CPPrincipal:
    from controller_api.errors import unauthorized

    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise unauthorized("Authentication required")
    token = header[7:].strip()
    try:
        claims = decode_token(request.app.state.settings, token)
    except Exception as exc:
        raise unauthorized("Invalid token") from exc
    user = await session.get(CPUser, claims["sub"])
    if user is None or not user.is_active:
        raise unauthorized("User is not active")
    return CPPrincipal(user)
