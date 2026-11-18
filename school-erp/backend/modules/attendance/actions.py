"""Action-registry entry points for attendance."""

from __future__ import annotations

import uuid

from core.actions.registry import ActionContext, action

from modules.attendance import service
from modules.attendance.schemas import (
    BulkRecordsInput,
    RecordUpdate,
    SessionCreate,
    SessionDetail,
    SessionList,
    SessionQuery,
    SessionUpdate,
)


def _id(payload: dict, key: str) -> uuid.UUID:
    return uuid.UUID(str(payload[key]))


def _body(payload: dict, *path_keys: str) -> dict:
    return {key: value for key, value in payload.items() if key not in path_keys}


@action(
    key="attendance.sessions.search",
    module="attendance",
    permission="attendance.view",
    risk="read",
    describe="List attendance registers",
    input=SessionQuery,
    output=SessionList,
)
async def search_sessions(ctx: ActionContext, payload: dict | None = None) -> SessionList:
    query = SessionQuery.model_validate(payload or {})
    return await service.list_sessions(ctx.session, ctx.principal, query)


@action(
    key="attendance.sessions.get",
    module="attendance",
    permission="attendance.view",
    risk="read",
    describe="Read one register with its roster and entries",
    output=SessionDetail,
)
async def get_session(ctx: ActionContext, payload: dict) -> SessionDetail:
    return await service.get_session(ctx.session, ctx.principal, _id(payload, "session_id"))


@action(
    key="attendance.sessions.create",
    module="attendance",
    permission="attendance.record",
    risk="write",
    describe="Open an attendance register and mark everyone present",
    input=SessionCreate,
    output=SessionDetail,
)
async def create_session(ctx: ActionContext, payload: dict) -> SessionDetail:
    data = SessionCreate.model_validate(_body(payload, "session_id"))
    return await service.create_session(ctx.session, ctx.principal, data, via=ctx.via)


@action(
    key="attendance.sessions.update",
    module="attendance",
    permission="attendance.record",
    risk="write",
    describe="Change a register's notes",
    input=SessionUpdate,
    output=SessionDetail,
)
async def update_session(ctx: ActionContext, payload: dict) -> SessionDetail:
    data = SessionUpdate.model_validate(_body(payload, "session_id"))
    return await service.update_session(
        ctx.session, ctx.principal, _id(payload, "session_id"), data, via=ctx.via
    )


@action(
    key="attendance.sessions.submit",
    module="attendance",
    permission="attendance.record",
    risk="write",
    describe="Submit a register for review",
    output=SessionDetail,
)
async def submit_session(ctx: ActionContext, payload: dict) -> SessionDetail:
    return await service.submit_session(ctx.session, ctx.principal, _id(payload, "session_id"), via=ctx.via)


@action(
    key="attendance.sessions.lock",
    module="attendance",
    permission="attendance.manage",
    risk="write",
    describe="Lock a register against further entry",
    output=SessionDetail,
)
async def lock_session(ctx: ActionContext, payload: dict) -> SessionDetail:
    return await service.lock_session(ctx.session, ctx.principal, _id(payload, "session_id"), via=ctx.via)


@action(
    key="attendance.sessions.reopen",
    module="attendance",
    permission="attendance.manage",
    risk="write",
    describe="Reopen a closed register",
    output=SessionDetail,
)
async def reopen_session(ctx: ActionContext, payload: dict) -> SessionDetail:
    return await service.reopen_session(ctx.session, ctx.principal, _id(payload, "session_id"), via=ctx.via)


@action(
    key="attendance.sessions.delete",
    module="attendance",
    permission="attendance.manage",
    risk="write",
    describe="Remove an attendance register",
    output=dict,
)
async def delete_session(ctx: ActionContext, payload: dict) -> dict:
    return await service.delete_session(
        ctx.session,
        ctx.principal,
        _id(payload, "session_id"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


@action(
    key="attendance.records.upsert",
    module="attendance",
    permission="attendance.record",
    risk="write",
    describe="Record attendance for one or more students",
    input=BulkRecordsInput,
    output=SessionDetail,
)
async def upsert_records(ctx: ActionContext, payload: dict) -> SessionDetail:
    data = BulkRecordsInput.model_validate(_body(payload, "session_id"))
    return await service.upsert_records(
        ctx.session, ctx.principal, _id(payload, "session_id"), data, via=ctx.via
    )


@action(
    key="attendance.records.update",
    module="attendance",
    permission="attendance.record",
    risk="write",
    describe="Correct one student's attendance entry",
    input=RecordUpdate,
    output=SessionDetail,
)
async def update_record(ctx: ActionContext, payload: dict) -> SessionDetail:
    data = RecordUpdate.model_validate(_body(payload, "session_id", "record_id"))
    return await service.update_record(
        ctx.session,
        ctx.principal,
        _id(payload, "session_id"),
        _id(payload, "record_id"),
        data,
        via=ctx.via,
    )


__all__ = [
    "create_session",
    "delete_session",
    "get_session",
    "lock_session",
    "reopen_session",
    "search_sessions",
    "submit_session",
    "update_record",
    "update_session",
    "upsert_records",
]
