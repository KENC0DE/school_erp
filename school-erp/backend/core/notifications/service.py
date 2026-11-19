"""Notification templates, rendering, delivery and the in-app centre (P1-23)."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from app.errors import Conflict, NotFound, ValidationFailed
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.api.concurrency import apply_row_version
from core.audit.service import record
from core.auth.models import User
from core.auth.principal import Principal
from core.db.soft_delete import actor_uuid, mark_restored, soft_delete
from core.events.service import create_job, emit
from core.i18n.service import merged_namespace
from core.notifications.adapters import EmailAdapter, PushAdapter, SMSAdapter
from core.notifications.models import DeliveryLog, Notification, NotificationTemplate

logger = logging.getLogger("erp.notifications")

CHANNELS = ("in_app", "email", "push", "sms", "telegram")
EXTERNAL_CHANNELS = {"email", "push", "sms", "telegram"}
CATEGORIES = ("general", "system", "academic", "attendance", "finance", "communication")
KEY_RE = re.compile(r"^[a-z][a-z0-9_.-]{1,79}$")
TRANSLATION_KEY_RE = re.compile(r"^[a-z][a-zA-Z0-9_.-]{1,199}$")
VARIABLE_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")

DEFAULT_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "key": "account.welcome",
        "name": "Welcome message",
        "description": "Sent when an account is created or handed over.",
        "category": "system",
        "title_key": "notifications.welcome.title",
        "body_key": "notifications.welcome.body",
        "default_channels": ["in_app", "email"],
    },
    {
        "key": "academics.results_published",
        "name": "Results published",
        "description": "Tells a student or guardian that results are available.",
        "category": "academic",
        "title_key": "notifications.results.title",
        "body_key": "notifications.results.body",
        "default_channels": ["in_app", "push"],
    },
    {
        "key": "finance.invoice_overdue",
        "name": "Invoice overdue",
        "description": "Reminder that an invoice has passed its due date.",
        "category": "finance",
        "title_key": "notifications.overdue.title",
        "body_key": "notifications.overdue.body",
        "default_channels": ["in_app", "email", "sms"],
    },
    {
        "key": "assessment.entry_reminder",
        "name": "Mark entry reminder",
        "description": "Reminds a teacher that marks are overdue for a class.",
        "category": "academic",
        "namespace": "assessment",
        "module": "assessment",
        "title_key": "notifications.entry_reminder.title",
        "body_key": "notifications.entry_reminder.body",
        "default_channels": ["in_app"],
    },
)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _template_view(row: NotificationTemplate) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "key": row.key,
        "name": row.name,
        "description": row.description,
        "category": row.category,
        "namespace": row.namespace,
        "title_key": row.title_key,
        "body_key": row.body_key,
        "default_channels": list(row.default_channels or []),
        "is_active": row.is_active,
        "is_system": row.is_system,
        "module": row.module,
        "row_version": row.row_version,
    }


def _notification_view(row: Notification) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "template_key": row.template_key,
        "category": row.category,
        "title": row.title,
        "body": row.body,
        "params": row.params or {},
        "link": row.link,
        "channels": list(row.channels or []),
        "read": row.read_at is not None,
        "read_at": _iso(row.read_at),
        "created_at": _iso(row.created_at),
    }


def mask_recipient(channel: str, value: str | None) -> str | None:
    """Never return a full email address, phone number or device token."""
    if not value:
        return None
    if channel == "email" and "@" in value:
        local, domain = value.split("@", 1)
        return f"{local[:1]}***@{domain}"
    if channel == "sms":
        digits = re.sub(r"\D", "", value)
        return f"***{digits[-4:]}" if digits else "***"
    return f"***{value[-4:]}" if len(value) > 4 else "***"


def _delivery_view(row: DeliveryLog) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "notification_id": str(row.notification_id),
        "user_id": str(row.user_id),
        "template_key": row.template_key,
        "channel": row.channel,
        "recipient": mask_recipient(row.channel, row.recipient),
        "status": row.status,
        "attempts": row.attempts,
        "error": row.error,
        "provider": row.provider,
        "sent_at": _iso(row.sent_at),
        "created_at": _iso(row.created_at),
    }


def _validate_channels(channels: list[str]) -> list[str]:
    if not isinstance(channels, list) or not channels:
        raise ValidationFailed(
            "Choose at least one delivery channel",
            message_key="error.notification.invalid_channels",
            details={"allowed": list(CHANNELS)},
        )
    seen: list[str] = []
    for channel in channels:
        if channel not in CHANNELS:
            raise ValidationFailed(
                "That delivery channel is not supported",
                message_key="error.notification.invalid_channels",
                details={"channel": channel, "allowed": list(CHANNELS)},
            )
        if channel not in seen:
            seen.append(channel)
    return seen


def _validate_template(
    *,
    key: str,
    title_key: str,
    body_key: str,
    category: str,
    namespace: str,
    channels: list[str],
) -> list[str]:
    if not KEY_RE.match(key):
        raise ValidationFailed(
            "Template keys are lowercase letters, digits, dots, dashes and underscores",
            message_key="error.notification.invalid_template",
            details={"field": "key", "value": key},
        )
    if category not in CATEGORIES:
        raise ValidationFailed(
            "Choose a known notification category",
            message_key="error.notification.invalid_template",
            details={"field": "category", "value": category, "allowed": list(CATEGORIES)},
        )
    for field, value in (("title_key", title_key), ("body_key", body_key), ("namespace", namespace)):
        if not TRANSLATION_KEY_RE.match(value):
            raise ValidationFailed(
                "Use a translation key, not literal message text",
                message_key="error.notification.invalid_template",
                details={"field": field, "value": value},
            )
    return _validate_channels(channels)


async def ensure_default_templates(session: AsyncSession) -> list[NotificationTemplate]:
    """Create the shipped templates without overwriting local edits."""
    created: list[NotificationTemplate] = []
    for spec in DEFAULT_TEMPLATES:
        row = (
            await session.execute(
                select(NotificationTemplate)
                .where(NotificationTemplate.key == spec["key"])
                .execution_options(include_deleted=True)
            )
        ).scalar_one_or_none()
        if row is None:
            row = NotificationTemplate(
                key=spec["key"],
                name=spec["name"],
                description=spec["description"],
                category=spec["category"],
                namespace=spec.get("namespace", "core"),
                title_key=spec["title_key"],
                body_key=spec["body_key"],
                default_channels=list(spec["default_channels"]),
                is_active=True,
                is_system=True,
                module=spec.get("module", "core"),
            )
            session.add(row)
            created.append(row)
        elif row.deleted_at is not None:
            mark_restored(row)
            row.is_active = True
            row.is_system = True
        else:
            row.is_system = True
    await session.flush()
    return created


async def list_templates(session: AsyncSession, *, category: str | None = None) -> list[dict]:
    stmt = select(NotificationTemplate).order_by(NotificationTemplate.key)
    if category:
        stmt = stmt.where(NotificationTemplate.category == category)
    rows = (await session.execute(stmt)).scalars().all()
    return [_template_view(row) for row in rows]


async def get_template(session: AsyncSession, template_id: str) -> NotificationTemplate:
    try:
        identifier = uuid.UUID(template_id)
    except ValueError as exc:
        raise NotFound("No notification template with that id") from exc
    row = await session.get(NotificationTemplate, identifier)
    if row is None or row.deleted_at is not None:
        raise NotFound("No notification template with that id")
    return row


async def get_template_by_key(session: AsyncSession, key: str) -> NotificationTemplate:
    row = (
        await session.execute(select(NotificationTemplate).where(NotificationTemplate.key == key))
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "No notification template with that key",
            message_key="error.notification.template_not_found",
            details={"template": key},
        )
    return row


async def create_template(
    session: AsyncSession,
    principal: Principal,
    *,
    key: str,
    name: str,
    title_key: str,
    body_key: str,
    description: str | None = None,
    category: str = "general",
    namespace: str = "core",
    channels: list[str] | None = None,
    module: str = "core",
) -> dict:
    chosen = _validate_template(
        key=key,
        title_key=title_key,
        body_key=body_key,
        category=category,
        namespace=namespace,
        channels=channels if channels is not None else ["in_app"],
    )
    existing = (
        await session.execute(
            select(NotificationTemplate)
            .where(NotificationTemplate.key == key)
            .execution_options(include_deleted=True)
        )
    ).scalar_one_or_none()
    if existing is not None and existing.deleted_at is None:
        raise Conflict(
            "A notification template with that key already exists",
            message_key="error.notification.duplicate_template",
            details={"key": key},
        )
    if existing is not None:
        mark_restored(existing)
        existing.name = name
        existing.description = description
        existing.category = category
        existing.namespace = namespace
        existing.title_key = title_key
        existing.body_key = body_key
        existing.default_channels = chosen
        existing.is_active = True
        existing.is_system = False
        existing.module = module
        existing.updated_by = actor_uuid(principal)
        row = existing
    else:
        row = NotificationTemplate(
            key=key,
            name=name,
            description=description,
            category=category,
            namespace=namespace,
            title_key=title_key,
            body_key=body_key,
            default_channels=chosen,
            is_active=True,
            is_system=False,
            module=module,
            created_by=actor_uuid(principal),
            updated_by=actor_uuid(principal),
        )
        session.add(row)
    await session.flush()
    await record(
        session,
        action="notification.template_create",
        module="core",
        entity_type="notification_template",
        entity_id=str(row.id),
        after=_template_view(row),
        actor=principal,
        via=principal.via,
    )
    await session.commit()
    await session.refresh(row)
    return _template_view(row)


async def update_template(
    session: AsyncSession,
    principal: Principal,
    template_id: str,
    *,
    row_version: int,
    values: dict[str, Any],
) -> dict:
    row = await get_template(session, template_id)
    before = _template_view(row)
    if "default_channels" in values and values["default_channels"] is not None:
        values["default_channels"] = _validate_channels(list(values["default_channels"]))
    if "category" in values and values["category"] is not None:
        if values["category"] not in CATEGORIES:
            raise ValidationFailed(
                "Choose a known notification category",
                message_key="error.notification.invalid_template",
                details={"field": "category", "value": values["category"]},
            )
    for field in ("title_key", "body_key", "namespace"):
        if values.get(field) is not None and not TRANSLATION_KEY_RE.match(str(values[field])):
            raise ValidationFailed(
                "Use a translation key, not literal message text",
                message_key="error.notification.invalid_template",
                details={"field": field, "value": values[field]},
            )
    if values.get("key") is not None and values["key"] != row.key:
        raise ValidationFailed(
            "A template key cannot be renamed",
            message_key="error.notification.invalid_template",
            details={"field": "key"},
        )
    changes = apply_row_version(
        row,
        row_version,
        values,
        allowed={
            "name",
            "description",
            "category",
            "namespace",
            "title_key",
            "body_key",
            "default_channels",
            "is_active",
        },
        current_state=before,
    )
    if not changes:
        raise ValidationFailed("No template fields were supplied", message_key="error.validation")
    row.updated_by = actor_uuid(principal)
    await session.flush()
    after = _template_view(row)
    await record(
        session,
        action="notification.template_update",
        module="core",
        entity_type="notification_template",
        entity_id=str(row.id),
        before=before,
        after=after,
        actor=principal,
        via=principal.via,
    )
    await session.commit()
    await session.refresh(row)
    return _template_view(row)


async def delete_template(session: AsyncSession, principal: Principal, template_id: str) -> dict:
    row = await get_template(session, template_id)
    if row.is_system:
        raise ValidationFailed(
            "Shipped notification templates cannot be deleted",
            message_key="error.notification.system_template",
            details={"template": row.key},
        )
    deleted = await soft_delete(
        session,
        row,
        action="notification.template_delete",
        module="core",
        actor=principal,
        via=principal.via,
        entity_type="notification_template",
    )
    await session.commit()
    return {"id": template_id, "deleted": deleted}


def render_message(template: str, params: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        value = params.get(match.group(1))
        return "" if value is None else str(value)

    return VARIABLE_RE.sub(replace, template)


async def _rendered(
    session: AsyncSession,
    template: NotificationTemplate,
    locale: str,
    params: dict[str, Any],
) -> tuple[str, str]:
    bundle = await merged_namespace(session, locale, template.namespace)
    title = bundle.get(template.title_key, template.title_key)
    body = bundle.get(template.body_key, template.body_key)
    return render_message(title, params), render_message(body, params)


def _recipient_for(channel: str, user: User) -> tuple[str | None, str | None, str]:
    """Return (recipient, skip reason, provider) for one channel."""
    if channel == "in_app":
        return str(user.id), None, "in_app"
    if channel == "email":
        return user.email, None if user.email else "No email address on file", "smtp"
    if channel == "sms":
        return user.phone, None if user.phone else "No phone number on file", "sms"
    if channel == "push":
        return str(user.id), None, "controller"
    return None, "Telegram is not configured", "telegram"


async def send_notification(
    session: AsyncSession,
    *,
    user_id: str | uuid.UUID,
    template_key: str,
    params: dict[str, Any] | None = None,
    channels: list[str] | None = None,
    link: str | None = None,
    actor: Principal | None = None,
    module: str = "core",
) -> dict[str, Any]:
    """Create one in-app notification and queue its other channels."""
    template = await get_template_by_key(session, template_key)
    if not template.is_active:
        raise ValidationFailed(
            "That notification template is inactive",
            message_key="error.notification.inactive_template",
            details={"template": template_key},
        )
    try:
        identifier = uuid.UUID(str(user_id))
    except ValueError as exc:
        raise NotFound("No such user", message_key="error.user.not_found") from exc
    user = await session.get(User, identifier)
    if user is None or not user.is_active:
        raise NotFound("No such user", message_key="error.user.not_found")
    chosen = _validate_channels(list(channels if channels is not None else template.default_channels))
    values = params or {}
    title, body = await _rendered(session, template, user.locale or "en", values)
    notification = Notification(
        user_id=user.id,
        template_key=template.key,
        category=template.category,
        title=title,
        body=body,
        params=values,
        link=link,
        channels=chosen,
    )
    session.add(notification)
    await session.flush()
    now = datetime.now(UTC)
    for channel in chosen:
        recipient, skip_reason, provider = _recipient_for(channel, user)
        session.add(
            DeliveryLog(
                notification_id=notification.id,
                user_id=user.id,
                template_key=template.key,
                channel=channel,
                recipient=recipient,
                status=("sent" if channel == "in_app" else "skipped" if skip_reason else "queued"),
                provider=provider,
                error=skip_reason,
                sent_at=now if channel == "in_app" else None,
            )
        )
    await record(
        session,
        action="notification.send",
        module=module,
        entity_type="notification",
        entity_id=str(notification.id),
        after={
            "template": template.key,
            "recipient_id": str(user.id),
            "channels": chosen,
            "category": template.category,
        },
        actor=actor,
        via=actor.via if actor else "automation",
    )
    await emit(
        session,
        "notification.created",
        {
            "notification_id": str(notification.id),
            "user_id": str(user.id),
            "template": template.key,
            "channels": chosen,
        },
        actor_id=actor.actor_id if actor else None,
    )
    job_id: str | None = None
    if EXTERNAL_CHANNELS.intersection(chosen):
        job = await create_job(
            session,
            "notifications.delivery",
            {"notification_id": str(notification.id)},
            created_by=actor.actor_id if actor else None,
        )
        job_id = str(job.id)
    await session.commit()
    await session.refresh(notification)
    result = _notification_view(notification)
    result["job_id"] = job_id
    return result


async def send_to_users(
    session: AsyncSession,
    *,
    user_ids: list[str],
    template_key: str,
    params: dict[str, Any] | None = None,
    channels: list[str] | None = None,
    link: str | None = None,
    actor: Principal | None = None,
) -> dict[str, Any]:
    if not user_ids:
        raise ValidationFailed("Choose at least one recipient", message_key="error.validation")
    if len(user_ids) > 500:
        raise ValidationFailed(
            "Send to at most 500 recipients at a time",
            message_key="error.notification.too_many_recipients",
            details={"count": len(user_ids), "maximum": 500},
        )
    sent = []
    for user_id in user_ids:
        sent.append(
            await send_notification(
                session,
                user_id=user_id,
                template_key=template_key,
                params=params,
                channels=channels,
                link=link,
                actor=actor,
            )
        )
    return {"items": sent, "count": len(sent)}


async def list_for_user(
    session: AsyncSession,
    user_id: str,
    *,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    try:
        identifier = uuid.UUID(user_id)
    except ValueError:
        return {"items": [], "unread": 0, "next_offset": None}
    stmt = select(Notification).where(Notification.user_id == identifier)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    rows = (
        (
            await session.execute(
                stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
                .offset(max(0, offset))
                .limit(max(1, min(limit, 200)))
            )
        )
        .scalars()
        .all()
    )
    unread = (
        await session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == identifier, Notification.read_at.is_(None))
        )
    ).scalar_one()
    next_offset = offset + len(rows) if len(rows) == min(limit, 200) else None
    return {
        "items": [_notification_view(row) for row in rows],
        "unread": int(unread),
        "next_offset": next_offset,
    }


async def unread_count(session: AsyncSession, user_id: str) -> dict[str, int]:
    try:
        identifier = uuid.UUID(user_id)
    except ValueError:
        return {"unread": 0}
    count = (
        await session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == identifier, Notification.read_at.is_(None))
        )
    ).scalar_one()
    return {"unread": int(count)}


async def get_own_notification(session: AsyncSession, user_id: str, notification_id: str) -> Notification:
    try:
        identifier = uuid.UUID(notification_id)
        owner = uuid.UUID(user_id)
    except ValueError as exc:
        raise NotFound("No such notification", message_key="error.notification.not_found") from exc
    row = await session.get(Notification, identifier)
    if row is None or row.user_id != owner:
        # Do not reveal that another user's notification exists.
        raise NotFound("No such notification", message_key="error.notification.not_found")
    return row


async def mark_read(session: AsyncSession, principal: Principal, notification_id: str) -> dict[str, Any]:
    row = await get_own_notification(session, principal.actor_id, notification_id)
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        await record(
            session,
            action="notification.read",
            module="core",
            entity_type="notification",
            entity_id=str(row.id),
            after={"read": True},
            actor=principal,
            via=principal.via,
        )
        await session.commit()
        await session.refresh(row)
    return _notification_view(row)


async def mark_all_read(session: AsyncSession, principal: Principal) -> dict[str, Any]:
    try:
        owner = uuid.UUID(principal.actor_id)
    except ValueError:
        return {"updated": 0}
    rows = (
        (
            await session.execute(
                select(Notification).where(Notification.user_id == owner, Notification.read_at.is_(None))
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    for row in rows:
        row.read_at = now
    if rows:
        await record(
            session,
            action="notification.read_all",
            module="core",
            entity_type="notification",
            after={"updated": len(rows)},
            actor=principal,
            via=principal.via,
        )
        await session.commit()
    return {"updated": len(rows)}


async def list_deliveries(
    session: AsyncSession,
    *,
    notification_id: str | None = None,
    template_key: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    stmt = select(DeliveryLog).order_by(DeliveryLog.created_at.desc()).limit(max(1, min(limit, 500)))
    if notification_id:
        try:
            stmt = stmt.where(DeliveryLog.notification_id == uuid.UUID(notification_id))
        except ValueError:
            return []
    if template_key:
        stmt = stmt.where(DeliveryLog.template_key == template_key)
    if status:
        stmt = stmt.where(DeliveryLog.status == status)
    rows = (await session.execute(stmt)).scalars().all()
    return [_delivery_view(row) for row in rows]


async def reset_failed_deliveries(
    session: AsyncSession,
    notification_id: str,
) -> int:
    """Return a notification's failed channels to the queue (P1-25 retry).

    ``deliver_notification`` only touches ``queued`` logs, so retrying a failed
    delivery job must first move its failures back to ``queued``. Skipped
    channels are left alone: they were skipped for a reason (no recipient or no
    adapter) and retrying them would only skip them again. The caller owns the
    transaction.
    """
    try:
        identifier = uuid.UUID(str(notification_id))
    except ValueError as exc:
        raise NotFound("No such notification", message_key="error.notification.not_found") from exc
    logs = (
        (
            await session.execute(
                select(DeliveryLog).where(
                    DeliveryLog.notification_id == identifier,
                    DeliveryLog.status == "failed",
                )
            )
        )
        .scalars()
        .all()
    )
    for log in logs:
        log.status = "queued"
        log.error = None
        log.sent_at = None
    await session.flush()
    return len(logs)


async def deliver_notification(
    session: AsyncSession,
    notification_id: str,
    *,
    mailer: EmailAdapter | None = None,
    sms: SMSAdapter | None = None,
    push: PushAdapter | None = None,
) -> dict[str, Any]:
    """Send every queued channel of a notification and record the outcome."""
    try:
        identifier = uuid.UUID(notification_id)
    except ValueError as exc:
        raise NotFound("No such notification", message_key="error.notification.not_found") from exc
    notification = await session.get(Notification, identifier)
    if notification is None:
        raise NotFound("No such notification", message_key="error.notification.not_found")
    user = await session.get(User, notification.user_id)
    logs = (
        (
            await session.execute(
                select(DeliveryLog).where(
                    DeliveryLog.notification_id == identifier,
                    DeliveryLog.status == "queued",
                )
            )
        )
        .scalars()
        .all()
    )
    summary: dict[str, str] = {}
    for log in logs:
        log.attempts += 1
        try:
            if log.channel == "email":
                if mailer is None:
                    break
                await mailer.send(
                    to=log.recipient or "",
                    subject=notification.title,
                    body=notification.body,
                )
            elif log.channel == "sms":
                if sms is None:
                    break
                await sms.send(
                    to=log.recipient or "",
                    body=f"{notification.title}: {notification.body}",
                )
            elif log.channel == "push":
                if push is None or user is None:
                    break
                await push.send(
                    user_id=str(log.recipient or notification.user_id),
                    title=notification.title,
                    body=notification.body,
                    data={
                        "link": notification.link,
                        "notification_id": str(notification.id),
                    },
                )
            else:
                log.status = "skipped"
                log.error = "No adapter for this channel"
                summary[log.channel] = log.status
                continue
            log.status = "sent"
            log.sent_at = datetime.now(UTC)
            log.error = None
            summary[log.channel] = "sent"
        except Exception as exc:  # noqa: BLE001 - delivery failures are logged, not raised
            logger.warning("notification %s %s failed: %s", notification.id, log.channel, exc)
            log.status = "failed"
            log.error = str(exc)[:500]
            summary[log.channel] = "failed"
    await session.commit()
    return {"notification_id": str(identifier), "channels": summary}


__all__ = [
    "CHANNELS",
    "DEFAULT_TEMPLATES",
    "create_template",
    "delete_template",
    "deliver_notification",
    "ensure_default_templates",
    "get_own_notification",
    "get_template",
    "get_template_by_key",
    "list_deliveries",
    "list_for_user",
    "list_templates",
    "mark_all_read",
    "mark_read",
    "reset_failed_deliveries",
    "send_notification",
    "send_to_users",
    "unread_count",
    "update_template",
]
