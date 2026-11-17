"""Request/response models for authentication (P1-04)."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: str | None = Field(None, max_length=10)
    recovery_code: str | None = Field(None, max_length=20)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    locale: str
    roles: list[str]
    permissions: list[str]
    must_change_password: bool = False
    totp_enabled: bool = False
    must_enroll_2fa: bool = False


class LoginResponse(BaseModel):
    tokens: TokenPair
    user: UserOut


class WebSessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=6, max_length=200)
    new_password: str = Field(min_length=1, max_length=200)


class TOTPEnrollResponse(BaseModel):
    secret: str
    otpauth_uri: str
    issuer: str


class TOTPConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=10)


class TOTPConfirmResponse(BaseModel):
    enabled: bool = True
    recovery_codes: list[str]


class TOTPDisableRequest(BaseModel):
    password: str


__all__ = [
    "ForgotPasswordRequest",
    "LoginRequest",
    "LoginResponse",
    "RefreshRequest",
    "ResetPasswordRequest",
    "TOTPConfirmRequest",
    "TOTPConfirmResponse",
    "TOTPDisableRequest",
    "TOTPEnrollResponse",
    "TokenPair",
    "UserOut",
    "WebSessionResponse",
]
