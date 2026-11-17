"""Request/response models for RBAC management (P1-05)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PermissionGrant(BaseModel):
    permission: str = Field(min_length=1, max_length=120)
    scope: str = Field(default="all", min_length=1, max_length=40)


class RoleCreate(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,59}$")
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    require_totp: bool = False
    permissions: list[PermissionGrant] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    require_totp: bool | None = None


class RolePermissionSet(BaseModel):
    permissions: list[PermissionGrant]

    @field_validator("permissions")
    @classmethod
    def no_duplicates(cls, value: list[PermissionGrant]) -> list[PermissionGrant]:
        seen = {(item.permission, item.scope) for item in value}
        if len(seen) != len(value):
            raise ValueError("Duplicate permission/scope pairs")
        return value


class RoleAssignment(BaseModel):
    role_id: str


class OverrideCreate(BaseModel):
    permission: str = Field(min_length=1, max_length=120)
    scope: str = Field(default="all", min_length=1, max_length=40)
    effect: Literal["grant", "deny"] = "grant"
    expires_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=500)


__all__ = [
    "OverrideCreate",
    "PermissionGrant",
    "RoleAssignment",
    "RoleCreate",
    "RolePermissionSet",
    "RoleUpdate",
]
