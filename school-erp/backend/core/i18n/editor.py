"""Translation editor services (ARCH §5.6, P1-18).

The editor works on effective rows, one per ``(namespace, key, locale)``:

* English (``en``) is the source column.
* The target column is the most specific layer (``default < central < school``)
  for the requested locale. A key with no row in the target locale is
  ``missing`` even though the runtime falls back to English.
* Writes from the school app always create a ``school`` layer override, so a
  bundled default is never mutated and the change can be reverted by resetting
  the key (which copies the underlying default back into the override row).
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.errors import Conflict, NotFound, ValidationFailed
from core.audit.service import record
from core.auth.principal import Principal
from core.db.base import uuid7
from core.db.soft_delete import actor_uuid, mark_deleted, mark_restored
from core.i18n.models import TranslationEntry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

LAYERS = ("default", "central", "school")
LAYER_RANK = {layer: index for index, layer in enumerate(LAYERS)}
STATUSES = ("approved", "needs_review")
EDITABLE_LAYER = "school"
MAX_VALUE_LENGTH = 4000
MAX_IMPORT_ENTRIES = 2000


def _effective(rows: list[TranslationEntry]) -> TranslationEntry | None:
    chosen: TranslationEntry | None = None
    for row in rows:
        if chosen is None or LAYER_RANK.get(row.layer, 0) >= LAYER_RANK.get(chosen.layer, 0):
            chosen = row
    return chosen


def _entry_view(
    namespace: str,
    key: str,
    source_row: TranslationEntry | None,
    target_row: TranslationEntry | None,
) -> dict[str, Any]:
    return {
        "namespace": namespace,
        "key": key,
        "source": source_row.value if source_row else "",
        "value": target_row.value if target_row else "",
        "status": target_row.status if target_row else "missing",
        "source_kind": target_row.source if target_row else None,
        "layer": target_row.layer if target_row else None,
        "updated_at": (
            target_row.updated_at.isoformat()
            if target_row is not None and target_row.updated_at
            else None
        ),
    }


def _raw_view(row: TranslationEntry | None) -> dict | None:
    if row is None:
        return None
    return {
        "namespace": row.namespace,
        "key": row.key,
        "locale": row.locale,
        "value": row.value,
        "status": row.status,
        "source": row.source,
        "layer": row.layer,
    }


async def _namespace_rows(
    session: AsyncSession,
    namespaces: list[str] | None,
    locales: tuple[str, ...],
) -> list[TranslationEntry]:
    stmt = select(TranslationEntry).where(TranslationEntry.locale.in_(locales))
    if namespaces:
        stmt = stmt.where(TranslationEntry.namespace.in_(namespaces))
    return list((await session.execute(stmt)).scalars().all())


def _group(
    rows: list[TranslationEntry],
) -> dict[tuple[str, str], dict[str, list[TranslationEntry]]]:
    grouped: dict[tuple[str, str], dict[str, list[TranslationEntry]]] = {}
    for row in rows:
        bucket = grouped.setdefault((row.namespace, row.key), {})
        bucket.setdefault(row.locale, []).append(row)
    return grouped


async def all_namespaces(session: AsyncSession) -> list[str]:
    rows = (await session.execute(select(TranslationEntry.namespace).distinct())).scalars()
    namespaces = {str(value) for value in rows}
    namespaces.add("core")
    return sorted(namespaces)


async def list_entries(
    session: AsyncSession,
    *,
    locale: str,
    namespace: str | None = None,
    q: str | None = None,
    status: str | None = None,
    layer: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    if locale not in {"en", "am"}:
        raise ValidationFailed(
            "Unknown locale", message_key="error.i18n.locale", details={"locale": locale}
        )
    if status is not None and status not in STATUSES + ("missing",):
        raise ValidationFailed(
            "Unknown translation status",
            message_key="error.i18n.status",
            details={"status": status},
        )
    if layer is not None and layer not in LAYERS:
        raise ValidationFailed(
            "Unknown translation layer",
            message_key="error.i18n.layer",
            details={"layer": layer},
        )

    rows = await _namespace_rows(
        session,
        [namespace] if namespace else None,
        ("en",) if locale == "en" else ("en", locale),
    )
    grouped = _group(rows)
    needle = q.casefold().strip() if q else ""

    items: list[dict[str, Any]] = []
    for (entry_namespace, key), bucket in grouped.items():
        source = _effective(bucket.get("en", []))
        target = _effective(bucket.get(locale, [])) if locale != "en" else source
        view = _entry_view(entry_namespace, key, source, target)
        if needle and not any(
            needle in str(value).casefold()
            for value in (view["namespace"], view["key"], view["source"], view["value"])
        ):
            continue
        if status and view["status"] != status:
            continue
        if layer and view["layer"] != layer:
            continue
        items.append(view)

    items.sort(key=lambda item: (item["namespace"], item["key"]))
    total = len(items)
    return {
        "items": items[offset : offset + limit],
        "total": total,
        "next_cursor": None,
        "limit": limit,
        "offset": offset,
    }


async def stats(
    session: AsyncSession,
    *,
    locale: str,
    namespace: str | None = None,
) -> dict[str, Any]:
    listing = await list_entries(
        session, locale=locale, namespace=namespace, limit=10**9, offset=0
    )
    items = listing["items"]
    return {
        "total": len(items),
        "missing": sum(1 for item in items if item["status"] == "missing"),
        "needs_review": sum(1 for item in items if item["status"] == "needs_review"),
        "overrides": sum(1 for item in items if item["layer"] == EDITABLE_LAYER),
    }


async def _default_keys(session: AsyncSession, namespace: str) -> set[str]:
    rows = (
        await session.execute(
            select(TranslationEntry.key).where(
                TranslationEntry.namespace == namespace,
                TranslationEntry.layer == "default",
            )
        )
    ).scalars()
    return {str(key) for key in rows}


async def _effective_en(
    session: AsyncSession, namespace: str, key: str
) -> TranslationEntry | None:
    rows = list(
        (
            await session.execute(
                select(TranslationEntry).where(
                    TranslationEntry.namespace == namespace,
                    TranslationEntry.key == key,
                    TranslationEntry.locale == "en",
                )
            )
        )
        .scalars()
        .all()
    )
    return _effective(rows)


async def _default_row(
    session: AsyncSession, namespace: str, key: str, locale: str
) -> TranslationEntry | None:
    rows = list(
        (
            await session.execute(
                select(TranslationEntry).where(
                    TranslationEntry.namespace == namespace,
                    TranslationEntry.key == key,
                    TranslationEntry.locale == locale,
                    TranslationEntry.layer != EDITABLE_LAYER,
                )
            )
        )
        .scalars()
        .all()
    )
    return _effective(rows)


def _validate_value(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValidationFailed(
            "A translation cannot be empty", message_key="error.i18n.empty"
        )
    if len(cleaned) > MAX_VALUE_LENGTH:
        raise ValidationFailed(
            "The translation is too long",
            message_key="error.i18n.too_long",
            details={"max": MAX_VALUE_LENGTH},
        )
    return cleaned


def _validate_status(status: str) -> str:
    if status not in STATUSES:
        raise ValidationFailed(
            "Unknown translation status",
            message_key="error.i18n.status",
            details={"status": status},
        )
    return status


async def _apply_entry(
    session: AsyncSession,
    principal: Principal,
    namespace: str,
    key: str,
    locale: str,
    value: str,
    status: str,
    *,
    via: str | None = None,
) -> tuple[TranslationEntry, bool]:
    """Create or update the school override. Returns (row, changed)."""
    cleaned = _validate_value(value)
    status = _validate_status(status)
    keys = await _default_keys(session, namespace)
    if key not in keys:
        raise NotFound(
            "No translation key by that name",
            message_key="error.i18n.unknown_key",
            details={"namespace": namespace, "key": key},
        )
    row = (
        await session.execute(
            select(TranslationEntry)
            .where(
                TranslationEntry.namespace == namespace,
                TranslationEntry.key == key,
                TranslationEntry.locale == locale,
                TranslationEntry.layer == EDITABLE_LAYER,
            )
            .execution_options(include_deleted=True)
        )
    ).scalar_one_or_none()
    was_deleted = row is not None and row.deleted_at is not None
    if was_deleted:
        mark_restored(row, actor=principal)
    changed = was_deleted or row is None or row.value != cleaned or row.status != status
    if row is None:
        row = TranslationEntry(
            namespace=namespace,
            key=key,
            locale=locale,
            value=cleaned,
            status=status,
            source="human",
            layer=EDITABLE_LAYER,
        )
        session.add(row)
    else:
        row.value = cleaned
        row.status = status
        row.source = "human"
    row.updated_by = actor_uuid(principal)
    await session.flush()
    await session.refresh(row)
    return row, changed


async def set_entry(
    session: AsyncSession,
    principal: Principal,
    namespace: str,
    key: str,
    locale: str,
    value: str,
    *,
    status: str = "approved",
    via: str | None = None,
) -> dict[str, Any]:
    before_row = (
        await session.execute(
            select(TranslationEntry)
            .where(
                TranslationEntry.namespace == namespace,
                TranslationEntry.key == key,
                TranslationEntry.locale == locale,
                TranslationEntry.layer == EDITABLE_LAYER,
            )
            .execution_options(include_deleted=True)
        )
    ).scalar_one_or_none()
    before = _raw_view(before_row)
    row, changed = await _apply_entry(
        session, principal, namespace, key, locale, value, status, via=via
    )
    if changed:
        await record(
            session,
            action="i18n.update" if before is not None else "i18n.create",
            module="core",
            entity_type="translation_entry",
            entity_id=f"{namespace}:{key}:{locale}",
            before=before,
            after=_raw_view(row),
            actor=principal,
            via=via,
        )
    view = _entry_view(
        namespace,
        key,
        await _effective_en(session, namespace, key),
        row,
    )
    await session.commit()
    return view


async def reset_entry(
    session: AsyncSession,
    principal: Principal,
    namespace: str,
    key: str,
    locale: str,
    *,
    via: str | None = None,
) -> dict[str, Any]:
    row = (
        await session.execute(
            select(TranslationEntry).where(
                TranslationEntry.namespace == namespace,
                TranslationEntry.key == key,
                TranslationEntry.locale == locale,
                TranslationEntry.layer == EDITABLE_LAYER,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(
            "There is no school override for this key",
            message_key="error.i18n.no_override",
        )
    base = await _default_row(session, namespace, key, locale)
    if base is None:
        raise Conflict(
            "There is no shipped translation to fall back to",
            message_key="error.i18n.no_default",
        )
    before = _raw_view(row)
    mark_deleted(row, actor=principal)
    await session.flush()
    await record(
        session,
        action="i18n.reset",
        module="core",
        entity_type="translation_entry",
        entity_id=f"{namespace}:{key}:{locale}",
        before=before,
        after=_raw_view(base),
        actor=principal,
        via=via,
    )
    view = _entry_view(
        namespace,
        key,
        await _effective_en(session, namespace, key),
        base,
    )
    await session.commit()
    return view


def parse_import(content: str, fmt: str) -> dict[str, str]:
    if fmt == "json":
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValidationFailed(
                "The JSON file is not valid", message_key="error.i18n.import_json"
            ) from exc
        if not isinstance(parsed, dict):
            raise ValidationFailed(
                "The JSON file must map keys to text",
                message_key="error.i18n.import_json",
            )
        entries = {str(key): str(value) for key, value in parsed.items()}
    elif fmt == "csv":
        text = content.lstrip("\ufeff")
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None or "key" not in reader.fieldnames:
            raise ValidationFailed(
                "The CSV needs a key column", message_key="error.i18n.import_csv"
            )
        value_column = "value" if "value" in reader.fieldnames else "translation"
        if value_column not in reader.fieldnames:
            raise ValidationFailed(
                "The CSV needs a value column", message_key="error.i18n.import_csv"
            )
        entries = {}
        for row in reader:
            key = (row.get("key") or "").strip()
            if not key:
                continue
            entries[key] = (row.get(value_column) or "").strip()
    else:
        raise ValidationFailed(
            "Import format must be csv or json",
            message_key="error.i18n.import_format",
            details={"format": fmt},
        )
    if not entries:
        raise ValidationFailed(
            "The file contains no translations", message_key="error.i18n.import_empty"
        )
    if len(entries) > MAX_IMPORT_ENTRIES:
        raise ValidationFailed(
            "Too many translations in one import",
            message_key="error.i18n.import_too_large",
            details={"max": MAX_IMPORT_ENTRIES},
        )
    return entries


async def import_entries(
    session: AsyncSession,
    principal: Principal,
    *,
    namespace: str,
    locale: str,
    fmt: str,
    content: str,
    status: str = "approved",
    dry_run: bool = False,
    via: str | None = None,
) -> dict[str, Any]:
    if locale not in {"en", "am"}:
        raise ValidationFailed(
            "Unknown locale", message_key="error.i18n.locale", details={"locale": locale}
        )
    entries = parse_import(content, fmt)
    known = await _default_keys(session, namespace)
    unknown = sorted(key for key in entries if key not in known)
    if unknown:
        raise ValidationFailed(
            "The file has keys that are not in this module",
            message_key="error.i18n.import_unknown",
            details={"keys": unknown},
        )
    for value in entries.values():
        _validate_value(value)
    _validate_status(status)

    if dry_run:
        return {"imported": 0, "would_import": len(entries), "keys": sorted(entries)}

    changed_keys: list[str] = []
    for key, value in sorted(entries.items()):
        _, changed = await _apply_entry(
            session, principal, namespace, key, locale, value, status, via=via
        )
        if changed:
            changed_keys.append(key)
    if changed_keys:
        await record(
            session,
            action="i18n.import",
            module="core",
            entity_type="translation_batch",
            entity_id=f"{namespace}:{locale}",
            after={
                "namespace": namespace,
                "locale": locale,
                "format": fmt,
                "status": status,
                "count": len(changed_keys),
                "keys": changed_keys,
            },
            actor=principal,
            via=via,
        )
    await session.commit()
    return {
        "imported": len(changed_keys),
        "unchanged": len(entries) - len(changed_keys),
        "keys": changed_keys,
    }


async def export_entries(
    session: AsyncSession,
    *,
    locale: str,
    namespace: str | None = None,
    fmt: str = "json",
) -> tuple[str, str, str]:
    listing = await list_entries(
        session, locale=locale, namespace=namespace, limit=10**9, offset=0
    )
    items = listing["items"]
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    base = f"translations-{locale}-{namespace or 'all'}-{stamp}"
    if fmt == "json":
        body = json.dumps({item["key"]: item["value"] for item in items}, ensure_ascii=False, indent=2)
        return body + "\n", f"{base}.json", "application/json"
    if fmt == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["key", "value", "source", "status", "layer"])
        for item in items:
            writer.writerow(
                [item["key"], item["value"], item["source"], item["status"], item["layer"] or ""]
            )
        return buffer.getvalue(), f"{base}.csv", "text/csv"
    raise ValidationFailed(
        "Export format must be csv or json",
        message_key="error.i18n.export_format",
        details={"format": fmt},
    )


__all__ = [
    "LAYERS",
    "STATUSES",
    "all_namespaces",
    "export_entries",
    "import_entries",
    "list_entries",
    "parse_import",
    "reset_entry",
    "set_entry",
    "stats",
]


# Keep uuid7 importable for tests that build rows directly.
def new_entry_id() -> uuid.UUID:
    return uuid7()
