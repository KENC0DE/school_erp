from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from controller_api.deps import CPPrincipal, current_user, get_session
from controller_api.errors import unauthorized
from controller_api.models import CPUser
from controller_api.security import create_token, verify_password

router = APIRouter(prefix="/controller/v1", tags=["controller-auth"])


class LoginRequest(BaseModel):
    # `.local` demo accounts are reserved names, so EmailStr would reject them.
    email: str = Field(min_length=3, max_length=320)
    password: str


@router.post("/auth/login")
async def login(
    payload: LoginRequest, request: Request, session: AsyncSession = Depends(get_session)
) -> dict:
    user = (
        await session.execute(select(CPUser).where(CPUser.email == payload.email.lower()))
    ).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise unauthorized("Email or password is incorrect")
    token = create_token(request.app.state.settings, user.id, user.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "display_name": user.display_name, "role": user.role},
    }


@router.get("/auth/me")
async def me(principal: CPPrincipal = Depends(current_user)) -> dict:
    return {
        "id": principal.id,
        "email": principal.email,
        "display_name": principal.display_name,
        "role": principal.role,
    }
