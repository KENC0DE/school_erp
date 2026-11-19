"""Shared protocol schemas for the instance ↔ controller link (ARCH §8)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EnrollRequest(BaseModel):
    enrollment_token: str
    instance_public_key: str
    name: str
    app_version: str = "0.0.0"
    api_base_url: str = ""


class EnrollResponse(BaseModel):
    instance_id: str
    license_token: str
    controller_public_key: str
    heartbeat_seconds: int = 60


class LicenseClaims(BaseModel):
    instance_id: str
    plan: str = "standard"
    modules: list[str] = Field(default_factory=list)
    limits: dict[str, int] = Field(default_factory=dict)
    status: str = "active"
    valid_until: int | None = None
    issued_at: int | None = None


class HeartbeatRequest(BaseModel):
    instance_id: str
    app_version: str
    uptime_seconds: int = 0
    error_count: int = 0
    queue_depth: int = 0
    db_size_bytes: int = 0
    storage_used_bytes: int = 0
    student_count: int = 0
    staff_count: int = 0
    last_backup_at: datetime | None = None
    audit_chain_head: str | None = None
    audit_seq: int = 0
    signature: str = ""


class HeartbeatResponse(BaseModel):
    license_token: str
    heartbeat_seconds: int = 60
    commands: list[dict[str, Any]] = Field(default_factory=list)


class AuditEntryIn(BaseModel):
    seq: int
    entry: dict[str, Any]
    hash: str
    prev_hash: str | None = None


class AuditIngestRequest(BaseModel):
    instance_id: str
    entries: list[AuditEntryIn]
    chain_head: str
    signature: str = ""


class AuditIngestResponse(BaseModel):
    accepted: int
    vault_seq: int
    alerts: list[str] = Field(default_factory=list)


class DirectoryRecord(BaseModel):
    instance_id: str
    name: str
    api_base_url: str
    logo_url: str | None = None
    status: str
    min_app_version: str
    kid: str
    signature: str


class SupportTokenClaims(BaseModel):
    instance_id: str
    cp_user_id: str
    reason: str
    read_only: bool = False
    exp: int
