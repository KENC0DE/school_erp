"""Theme Manager service: import, availability, previews and user choice (P1-21)."""

from __future__ import annotations

import uuid
from typing import Any

from app.errors import NotFound, ValidationFailed, VersionRequired
from core.api.concurrency import apply_row_version
from core.audit.service import record
from core.auth.models import User
from core.auth.principal import Principal
from core.db.soft_delete import actor_uuid, mark_restored, soft_delete
from core.themes.importers import ImportedTheme
from core.themes.models import Theme
from core.themes.tokens import (
    DEFAULT_THEME,
    LIGHT,
    contrast_report,
    css_block,
    css_variables,
    theme_is_valid,
    to_mobile_theme,
    validate_tokens,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _raw_view(row: Theme | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "key": row.key,
        "name": row.name,
        "description": row.description,
        "is_default": row.is_default,
        "is_active": row.is_active,
        "is_builtin": row.is_builtin,
        "source": row.source,
        "source_url": row.source_url,
        "row_version": row.row_version,
    }


def _summary(row: Theme) -> dict[str, Any]:
    return {
        "key": row.key,
        "name": row.name,
        "description": row.description,
        "is_default": row.is_default,
        "is_active": row.is_active,
        "is_builtin": row.is_builtin,
        "source": row.source,
        "source_url": row.source_url,
        "row_version": row.row_version,
        "valid": theme_is_valid(row.tokens),
    }


def _active_view(
    key: str,
    name: str,
    tokens: dict,
    *,
    source: str,
    mode: str | None = None,
    user_theme_key: str | None = None,
    fallback: bool = False,
    reason: list[dict] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "name": name,
        "tokens": tokens,
        "source": source,
        "mode": mode,
        "user_theme_key": user_theme_key,
        "fallback": fallback,
        "reason": reason or [],
    }


def _builtin_active(*, fallback: bool = False, reason: list[dict] | None = None) -> dict[str, Any]:
    return _active_view(
        DEFAULT_THEME["key"],
        DEFAULT_THEME["name"],
        DEFAULT_THEME["tokens"],
        source="builtin",
        fallback=fallback,
        reason=reason,
    )


async def _get_by_key(session: AsyncSession, key: str, *, include_deleted: bool = False) -> Theme | None:
    stmt = select(Theme).where(Theme.key == key)
    if include_deleted:
        stmt = stmt.execution_options(include_deleted=True)
    return (await session.execute(stmt)).scalar_one_or_none()


async def _default_row(session: AsyncSession) -> Theme | None:
    """The school default even when its tokens are broken.

    Returning the broken row lets ``active_theme`` explain why it fell back
    instead of silently replacing the school's choice.
    """
    return (
        await session.execute(
            select(Theme)
            .where(Theme.is_default.is_(True), Theme.is_active.is_(True))
            .order_by(Theme.key)
            .limit(1)
        )
    ).scalar_one_or_none()


async def active_theme(
    session: AsyncSession,
    user: User | None = None,
) -> dict[str, Any]:
    """Resolve the theme for a request, falling back to the shipped default.

    A stored theme that is missing tokens, corrupt or fails a contrast check is
    never served. The caller receives the builtin default plus the validation
    reason so the Theme Manager can explain what broke.
    """
    if user is not None and user.theme_key:
        chosen = await _get_by_key(session, user.theme_key)
        if chosen is not None and chosen.is_active:
            issues = validate_tokens(chosen.tokens)
            if not issues:
                return _active_view(
                    chosen.key,
                    chosen.name,
                    chosen.tokens,
                    source="user",
                    mode=user.theme_mode,
                    user_theme_key=chosen.key,
                )
            return _builtin_active(fallback=True, reason=issues)
    row = await _default_row(session)
    if row is None:
        return _builtin_active(
            fallback=True,
            reason=[{"code": "no_default", "message": "No school default theme is available."}],
        )
    issues = validate_tokens(row.tokens)
    if issues:
        return _builtin_active(fallback=True, reason=issues)
    return _active_view(
        row.key,
        row.name,
        row.tokens,
        source="instance",
        mode=user.theme_mode if user is not None else None,
        user_theme_key=user.theme_key if user is not None else None,
    )


async def mobile_theme(session: AsyncSession, user: User | None, mode: str) -> dict[str, Any]:
    active = await active_theme(session, user)
    chosen_mode = mode if mode in ("light", "dark") else (user.theme_mode if user else "light")
    return {
        "key": active["key"],
        "name": active["name"],
        "source": active["source"],
        "fallback": active["fallback"],
        "fallback_reason": active["reason"],
        "theme": to_mobile_theme(active["tokens"], chosen_mode),
    }


async def list_themes(session: AsyncSession, *, available_only: bool = False) -> list[dict[str, Any]]:
    stmt = select(Theme).where(Theme.deleted_at.is_(None)).order_by(Theme.is_default.desc(), Theme.name)
    if available_only:
        stmt = stmt.where(Theme.is_active.is_(True))
    rows = list((await session.execute(stmt)).scalars().all())
    return [_summary(row) for row in rows]


async def available_themes(session: AsyncSession) -> list[dict[str, Any]]:
    items = await list_themes(session, available_only=True)
    if not any(item["key"] == DEFAULT_THEME["key"] for item in items):
        items.insert(
            0,
            {
                "key": DEFAULT_THEME["key"],
                "name": DEFAULT_THEME["name"],
                "description": None,
                "is_default": True,
                "is_active": True,
                "is_builtin": True,
                "source": "builtin",
                "source_url": None,
                "row_version": None,
                "valid": True,
            },
        )
    # Broken themes are listed to admins but cannot be chosen by end users.
    return [item for item in items if item["valid"]]


async def theme_detail(session: AsyncSession, key: str) -> dict[str, Any]:
    row = await _get_by_key(session, key)
    if row is None:
        if key == DEFAULT_THEME["key"]:
            return {
                **_summary_dict_from_tokens(
                    DEFAULT_THEME["key"], DEFAULT_THEME["name"], DEFAULT_THEME["tokens"]
                ),
                "tokens": DEFAULT_THEME["tokens"],
                "issues": [],
                "contrast": contrast_report(DEFAULT_THEME["tokens"]),
                "css": {
                    "light": css_block(DEFAULT_THEME["tokens"]["light"]),
                    "dark": css_block(DEFAULT_THEME["tokens"]["dark"]),
                },
                "mobile": {
                    mode: to_mobile_theme(DEFAULT_THEME["tokens"], mode) for mode in ("light", "dark")
                },
            }
        raise NotFound("No theme by that name", message_key="error.theme.not_found")
    return {
        **_summary(row),
        "tokens": row.tokens,
        "issues": validate_tokens(row.tokens),
        "contrast": contrast_report(row.tokens),
        "css": {
            "light": css_block(row.tokens.get("light", {})),
            "dark": css_block(row.tokens.get("dark", {})),
        },
        "mobile": {mode: to_mobile_theme(row.tokens, mode) for mode in ("light", "dark")},
    }


def _summary_dict_from_tokens(key: str, name: str, tokens: dict) -> dict[str, Any]:
    return {
        "key": key,
        "name": name,
        "description": None,
        "is_default": True,
        "is_active": True,
        "is_builtin": True,
        "source": "builtin",
        "source_url": None,
        "row_version": None,
        "valid": theme_is_valid(tokens),
    }


def validate_import(theme: ImportedTheme) -> list[dict[str, Any]]:
    return validate_tokens(theme.tokens)


def preview_import(theme: ImportedTheme) -> dict[str, Any]:
    issues = validate_import(theme)
    valid = not issues
    tokens = theme.tokens
    return {
        "valid": valid,
        "key": theme.key,
        "name": theme.name,
        "source": theme.source,
        "source_url": theme.source_url,
        "warnings": theme.warnings,
        "issues": issues,
        "contrast": contrast_report(tokens),
        "tokens": tokens,
        "css": {
            "light": css_block(tokens.get("light", {})),
            "dark": css_block(tokens.get("dark", {})),
        },
        "mobile": {mode: to_mobile_theme(tokens, mode) for mode in ("light", "dark")},
        "fallback": None
        if valid
        else _active_view(
            DEFAULT_THEME["key"],
            DEFAULT_THEME["name"],
            DEFAULT_THEME["tokens"],
            source="builtin",
            fallback=True,
            reason=issues,
        ),
    }


def _reject_invalid(theme: ImportedTheme) -> None:
    issues = validate_import(theme)
    if issues:
        raise ValidationFailed(
            "The theme did not pass validation; nothing was saved",
            message_key="error.theme.invalid",
            details={"issues": issues},
        )


async def import_theme(
    session: AsyncSession,
    principal: Principal,
    theme: ImportedTheme,
    *,
    description: str | None = None,
    is_active: bool = True,
) -> dict[str, Any]:
    _reject_invalid(theme)
    row = await _get_by_key(session, theme.key, include_deleted=True)
    if row is not None and row.deleted_at is None and row.is_builtin:
        raise ValidationFailed(
            "The builtin default theme cannot be replaced",
            message_key="error.theme.builtin_required",
            details={"theme_key": theme.key},
        )
    before = _raw_view(row if row is not None and row.deleted_at is None else None)
    if row is None:
        row = Theme(
            key=theme.key,
            name=theme.name,
            description=description,
            tokens=theme.tokens,
            is_default=False,
            is_active=is_active,
            is_builtin=False,
            source=theme.source,
            source_url=theme.source_url,
        )
        row.created_by = actor_uuid(principal)
        row.updated_by = actor_uuid(principal)
        session.add(row)
    else:
        if row.deleted_at is not None:
            mark_restored(row, actor=principal)
        row.name = theme.name
        row.description = description if description is not None else row.description
        row.tokens = theme.tokens
        row.is_active = is_active
        row.is_builtin = False
        row.source = theme.source
        row.source_url = theme.source_url
        row.updated_by = actor_uuid(principal)
        row.row_version = (row.row_version or 0) + 1
    await session.flush()
    await session.refresh(row)
    await record(
        session,
        action="theme.import",
        module="core",
        entity_type="theme",
        entity_id=row.key,
        before=before,
        after=_raw_view(row),
        actor=principal,
        via=principal.via,
    )
    await session.commit()
    return await theme_detail(session, row.key)


async def update_theme(
    session: AsyncSession,
    principal: Principal,
    key: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    row = await _get_by_key(session, key)
    if row is None:
        raise NotFound("No theme by that name", message_key="error.theme.not_found")
    version = payload.get("row_version")
    if version is None:
        raise VersionRequired("row_version is required for this update", details={"field": "row_version"})
    values = {
        field: payload[field]
        for field in ("name", "description", "is_active", "is_default")
        if field in payload
    }
    if values.get("is_default") is True:
        values["is_active"] = True
    if row.is_builtin and values.get("is_active") is False:
        raise ValidationFailed(
            "The builtin default theme cannot be made unavailable",
            message_key="error.theme.builtin_required",
        )
    if row.is_default and values.get("is_active") is False:
        raise ValidationFailed(
            "Choose another default theme before making this one unavailable",
            message_key="error.theme.default_must_be_available",
        )
    before = _raw_view(row)
    changes = apply_row_version(
        row, int(version), values, allowed={"name", "description", "is_active", "is_default"}
    )
    if not changes:
        raise ValidationFailed("No theme fields were supplied", message_key="error.validation")
    if changes.get("is_default") is True:
        others = (
            await session.execute(select(Theme).where(Theme.is_default.is_(True), Theme.key != row.key))
        ).scalars()
        for other in others:
            other.is_default = False
            other.row_version = (other.row_version or 0) + 1
    row.updated_by = actor_uuid(principal)
    await session.flush()
    await session.refresh(row)
    await record(
        session,
        action="theme.update",
        module="core",
        entity_type="theme",
        entity_id=row.key,
        before=before,
        after=_raw_view(row),
        actor=principal,
        via=principal.via,
    )
    await session.commit()
    return await theme_detail(session, row.key)


async def set_default_theme(
    session: AsyncSession, principal: Principal, key: str, *, commit: bool = True
) -> dict[str, Any]:
    row = await _get_by_key(session, key)
    if row is None:
        raise NotFound("No theme by that name", message_key="error.theme.not_found")
    if not theme_is_valid(row.tokens):
        raise ValidationFailed(
            "A broken theme cannot become the school default",
            message_key="error.theme.invalid",
            details={"issues": validate_tokens(row.tokens)},
        )
    before = _raw_view(row)
    others = (
        await session.execute(select(Theme).where(Theme.is_default.is_(True), Theme.key != row.key))
    ).scalars()
    for other in others:
        other.is_default = False
        other.row_version = (other.row_version or 0) + 1
    row.is_default = True
    row.is_active = True
    row.row_version = (row.row_version or 0) + 1
    row.updated_by = actor_uuid(principal)
    await session.flush()
    await session.refresh(row)
    await record(
        session,
        action="theme.default",
        module="core",
        entity_type="theme",
        entity_id=row.key,
        before=before,
        after=_raw_view(row),
        actor=principal,
        via=principal.via,
    )
    if commit:
        await session.commit()
    return await theme_detail(session, row.key)


async def delete_theme(session: AsyncSession, principal: Principal, key: str) -> dict[str, Any]:
    row = await _get_by_key(session, key)
    if row is None:
        raise NotFound("No theme by that name", message_key="error.theme.not_found")
    if row.is_builtin:
        raise ValidationFailed(
            "The builtin default theme cannot be deleted",
            message_key="error.theme.builtin_required",
        )
    if row.is_default:
        builtin = await _get_by_key(session, DEFAULT_THEME["key"])
        if builtin is not None:
            builtin.is_default = True
            builtin.is_active = True
            builtin.row_version = (builtin.row_version or 0) + 1
    deleted = await soft_delete(
        session,
        row,
        action="theme.delete",
        module="core",
        actor=principal,
        via=principal.via,
        entity_type="theme",
    )
    await session.commit()
    return {"key": key, "deleted": deleted}


async def set_user_preference(
    session: AsyncSession,
    principal: Principal,
    *,
    theme_key: str | None,
    mode: str,
) -> dict[str, Any]:
    if mode not in {"light", "dark"}:
        raise ValidationFailed(
            "Theme mode must be light or dark",
            message_key="error.theme.invalid_mode",
            details={"mode": mode},
        )
    user_id = uuid.UUID(principal.actor_id)
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound("User not found", message_key="error.not_found")
    if theme_key is not None:
        row = await _get_by_key(session, theme_key)
        if row is None or not row.is_active:
            raise ValidationFailed(
                "That theme is not available to this school",
                message_key="error.theme.not_available",
                details={"theme_key": theme_key},
            )
        if not theme_is_valid(row.tokens):
            raise ValidationFailed(
                "That theme is broken and cannot be selected",
                message_key="error.theme.invalid",
                details={"issues": validate_tokens(row.tokens)},
            )
    before = {"theme_key": user.theme_key, "theme_mode": user.theme_mode}
    user.theme_key = theme_key
    user.theme_mode = mode
    after = {"theme_key": user.theme_key, "theme_mode": user.theme_mode}
    await record(
        session,
        action="user.theme_preference",
        module="core",
        entity_type="user",
        entity_id=str(user.id),
        before=before,
        after=after,
        actor=principal,
        via=principal.via,
    )
    await session.commit()
    active = await active_theme(session, user)
    return {
        "theme_key": user.theme_key,
        "theme_mode": user.theme_mode,
        "theme": active,
    }


async def ensure_default_theme(session: AsyncSession) -> Theme:
    row = await _get_by_key(session, DEFAULT_THEME["key"], include_deleted=True)
    if row is None:
        row = Theme(
            key=DEFAULT_THEME["key"],
            name=DEFAULT_THEME["name"],
            description="The theme shipped with the app and always available as a fallback.",
            tokens=DEFAULT_THEME["tokens"],
            is_default=True,
            is_active=True,
            is_builtin=True,
            source="builtin",
        )
        session.add(row)
        await session.flush()
    elif row.deleted_at is not None:
        mark_restored(row)
        row.is_builtin = True
        row.is_active = True
        await session.flush()
    elif not row.is_builtin or not row.is_active:
        row.is_builtin = True
        row.is_active = True
        await session.flush()
    elif (
        not row.is_default
        and not (
            await session.execute(select(Theme).where(Theme.is_default.is_(True)).limit(1))
        ).scalar_one_or_none()
    ):
        row.is_default = True
        await session.flush()
    return row


__all__ = [
    "DEFAULT_THEME",
    "LIGHT",
    "active_theme",
    "available_themes",
    "css_variables",
    "delete_theme",
    "ensure_default_theme",
    "import_theme",
    "list_themes",
    "mobile_theme",
    "preview_import",
    "set_default_theme",
    "set_user_preference",
    "theme_detail",
    "update_theme",
    "validate_import",
]
