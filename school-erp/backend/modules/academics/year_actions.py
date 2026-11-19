"""Action-registry entry points for academic years and terms."""

from __future__ import annotations

import uuid

from core.actions.registry import ActionContext, action

from modules.academics import years
from modules.academics.schemas import TermUpdate, YearCreate, YearList, YearOut, YearUpdate


async def _commit(ctx: ActionContext) -> None:
    await ctx.session.commit()


@action(
    key="academics.years.list",
    module="academics",
    permission="academics.view",
    risk="read",
    describe="List academic years with their terms",
    output=YearList,
)
async def list_years(ctx: ActionContext, payload: dict | None = None) -> YearList:
    data = payload or {}
    return await years.list_years(ctx.session, status=data.get("status"))


@action(
    key="academics.years.get",
    module="academics",
    permission="academics.view",
    risk="read",
    describe="Read one academic year and its terms",
    output=YearOut,
)
async def get_year(ctx: ActionContext, payload: dict) -> YearOut:
    return await years.get_year(ctx.session, uuid.UUID(str(payload["year_id"])))


@action(
    key="academics.years.create",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Create an academic year and its terms",
    input=YearCreate,
    output=YearOut,
)
async def create_year(ctx: ActionContext, payload: dict) -> YearOut:
    data = YearCreate.model_validate(payload)
    result = await years.create_year(ctx.session, ctx.principal, data, via=ctx.via)
    await _commit(ctx)
    return result


@action(
    key="academics.years.update",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Edit an academic year using optimistic concurrency",
    input=YearUpdate,
    output=YearOut,
)
async def update_year(ctx: ActionContext, payload: dict) -> YearOut:
    data = YearUpdate.model_validate(payload)
    result = await years.update_year(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["year_id"])),
        data,
        via=ctx.via,
        reason=payload.get("reason"),
    )
    await _commit(ctx)
    return result


@action(
    key="academics.years.delete",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Soft-delete a draft academic year (reversible)",
    output=YearOut,
)
async def delete_year(ctx: ActionContext, payload: dict) -> YearOut:
    result = await years.delete_year(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["year_id"])),
        row_version=payload.get("row_version"),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return result


@action(
    key="academics.years.restore",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Restore a soft-deleted academic year",
    output=YearOut,
)
async def restore_year(ctx: ActionContext, payload: dict) -> YearOut:
    result = await years.restore_year(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["year_id"])),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return result


@action(
    key="academics.years.open",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Open an academic year, making it the current year",
    output=YearOut,
)
async def open_year(ctx: ActionContext, payload: dict) -> YearOut:
    result = await years.open_year(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["year_id"])),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return result


@action(
    key="academics.years.close",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Close an academic year and any open term inside it",
    output=YearOut,
)
async def close_year(ctx: ActionContext, payload: dict) -> YearOut:
    result = await years.close_year(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["year_id"])),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return result


@action(
    key="academics.terms.update",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Edit a term's name or dates",
    input=TermUpdate,
    output=YearOut,
)
async def update_term(ctx: ActionContext, payload: dict) -> YearOut:
    data = TermUpdate.model_validate(payload)
    result = await years.update_term(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["year_id"])),
        uuid.UUID(str(payload["term_id"])),
        data,
        via=ctx.via,
        reason=payload.get("reason"),
    )
    await _commit(ctx)
    return result


@action(
    key="academics.terms.open",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Open one term inside an open academic year",
    output=YearOut,
)
async def open_term(ctx: ActionContext, payload: dict) -> YearOut:
    result = await years.open_term(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["year_id"])),
        uuid.UUID(str(payload["term_id"])),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return result


@action(
    key="academics.terms.close",
    module="academics",
    permission="academics.manage",
    risk="write",
    describe="Close an open term",
    output=YearOut,
)
async def close_term(ctx: ActionContext, payload: dict) -> YearOut:
    result = await years.close_term(
        ctx.session,
        ctx.principal,
        uuid.UUID(str(payload["year_id"])),
        uuid.UUID(str(payload["term_id"])),
        reason=payload.get("reason"),
        via=ctx.via,
    )
    await _commit(ctx)
    return result


__all__ = [
    "close_term",
    "close_year",
    "create_year",
    "delete_year",
    "get_year",
    "list_years",
    "open_term",
    "open_year",
    "restore_year",
    "update_term",
    "update_year",
]
