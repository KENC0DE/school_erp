"""Action-registry entry points for admissions.

Routers and the AI layer share these functions so permissions, validation and
audit entries stay identical. Payloads are JSON objects; the router maps path
parameters into the same keys.
"""

from __future__ import annotations

import uuid

from core.actions.registry import ActionContext, action

from modules.admissions import service
from modules.admissions.schemas import (
    AdmissionFormOut,
    ApplicationCreate,
    ApplicationCreateOut,
    ApplicationList,
    ApplicationOut,
    ApplicationPreview,
    ApplicationQuery,
    ApplicationUpdate,
    ConversionInput,
    ConversionOut,
    ConversionPreview,
    DecisionInput,
    DecisionOut,
)


def _application_id(payload: dict) -> uuid.UUID:
    return uuid.UUID(str(payload["application_id"]))


def _body(payload: dict, *path_keys: str) -> dict:
    """Drop router path parameters before validating an action payload."""
    return {key: value for key, value in payload.items() if key not in path_keys}


@action(
    key="admissions.search",
    module="admissions",
    permission="admissions.view",
    risk="read",
    describe="Search admission applications by name, number, status and placement",
    input=ApplicationQuery,
    output=ApplicationList,
)
async def search_applications(ctx: ActionContext, payload: dict | None = None) -> ApplicationList:
    query = ApplicationQuery.model_validate(payload or {})
    return await service.list_applications(ctx.session, query)


@action(
    key="admissions.get",
    module="admissions",
    permission="admissions.view",
    risk="read",
    describe="Read one application with its guardians and decision history",
    output=ApplicationOut,
)
async def get_application(ctx: ActionContext, payload: dict) -> ApplicationOut:
    return await service.get_application(ctx.session, ctx.principal, _application_id(payload))


@action(
    key="admissions.form",
    module="admissions",
    permission="admissions.view",
    risk="read",
    describe="Read the application form fields and entrance-test settings",
    output=AdmissionFormOut,
)
async def form_view(ctx: ActionContext, payload: dict | None = None) -> AdmissionFormOut:
    return await service.form_view(ctx.session, ctx.principal)


async def preview_application(ctx: ActionContext, payload: dict) -> ApplicationPreview:
    data = ApplicationCreate.model_validate(_body(payload, "application_id"))
    return await service.preview_application(ctx.session, data)


@action(
    key="admissions.preview",
    module="admissions",
    permission="admissions.manage",
    risk="read",
    describe="Preview the next number, duplicate warnings and form totals without writing",
    input=ApplicationCreate,
    output=ApplicationPreview,
)
async def preview_application_action(ctx: ActionContext, payload: dict) -> ApplicationPreview:
    return await preview_application(ctx, payload)


@action(
    key="admissions.create",
    module="admissions",
    permission="admissions.manage",
    risk="write",
    describe="Take an application for a person, with guardians and custom fields",
    input=ApplicationCreate,
    output=ApplicationCreateOut,
    preview=preview_application,
)
async def create_application(ctx: ActionContext, payload: dict) -> ApplicationCreateOut:
    data = ApplicationCreate.model_validate(_body(payload, "application_id"))
    row, warnings = await service.create_application(ctx.session, ctx.principal, data, via=ctx.via)
    view = await service.application_view(ctx.session, row, locale=ctx.principal.locale)
    return ApplicationCreateOut(**view.model_dump(), duplicate_warnings=warnings)


@action(
    key="admissions.update",
    module="admissions",
    permission="admissions.manage",
    risk="write",
    describe="Edit an open application's person, placement or custom fields",
    input=ApplicationUpdate,
    output=ApplicationOut,
)
async def update_application(ctx: ActionContext, payload: dict) -> ApplicationOut:
    data = ApplicationUpdate.model_validate(_body(payload, "application_id"))
    return await service.update_application(
        ctx.session, ctx.principal, _application_id(payload), data, via=ctx.via
    )


@action(
    key="admissions.decide",
    module="admissions",
    permission="admissions.decide",
    risk="write",
    describe="Move an application through review, test, offer, acceptance or rejection",
    input=DecisionInput,
    output=DecisionOut,
)
async def decide_application(ctx: ActionContext, payload: dict) -> DecisionOut:
    data = DecisionInput.model_validate(_body(payload, "application_id"))
    return await service.decide_application(
        ctx.session, ctx.principal, _application_id(payload), data, via=ctx.via
    )


@action(
    key="admissions.conversion_preview",
    module="admissions",
    permission="admissions.decide",
    risk="read",
    describe="Preview the student number, placement and guardian accounts of a conversion",
    output=ConversionPreview,
)
async def preview_conversion(ctx: ActionContext, payload: dict) -> ConversionPreview:
    return await service.preview_conversion(ctx.session, _application_id(payload))


async def conversion_preview(ctx: ActionContext, payload: dict) -> ConversionPreview:
    return await service.preview_conversion(ctx.session, _application_id(payload))


@action(
    key="admissions.convert",
    module="admissions",
    permission="admissions.decide",
    risk="write",
    describe="Convert an accepted application into a student, enrollment and guardian accounts",
    input=ConversionInput,
    output=ConversionOut,
    preview=conversion_preview,
)
async def convert_application(ctx: ActionContext, payload: dict) -> ConversionOut:
    data = ConversionInput.model_validate(_body(payload, "application_id"))
    return await service.convert_application(
        ctx.session,
        ctx.principal,
        _application_id(payload),
        data,
        request=ctx.request,
        app_settings=ctx.settings,
        via=ctx.via,
    )


@action(
    key="admissions.delete",
    module="admissions",
    permission="admissions.manage",
    risk="destructive",
    describe="Soft-delete an unconverted application (restorable, audited)",
)
async def delete_application(ctx: ActionContext, payload: dict) -> dict:
    return await service.delete_application(
        ctx.session,
        ctx.principal,
        _application_id(payload),
        row_version=payload.get("row_version"),
        reason=payload.get("reason"),
        via=ctx.via,
    )


@action(
    key="admissions.restore",
    module="admissions",
    permission="admissions.manage",
    risk="write",
    describe="Restore a soft-deleted application",
    output=ApplicationOut,
)
async def restore_application(ctx: ActionContext, payload: dict) -> ApplicationOut:
    return await service.restore_application(
        ctx.session,
        ctx.principal,
        _application_id(payload),
        reason=payload.get("reason"),
        via=ctx.via,
    )


__all__ = [
    "convert_application",
    "create_application",
    "decide_application",
    "delete_application",
    "form_view",
    "get_application",
    "preview_application",
    "preview_conversion",
    "restore_application",
    "search_applications",
    "update_application",
]
