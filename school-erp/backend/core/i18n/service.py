from __future__ import annotations

import asyncio
import json
from pathlib import Path

from core.i18n.models import TranslationEntry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

CORE_I18N_DIR = Path(__file__).resolve().parent
LAYERS = ("default", "central", "school")


def _read_bundles(registry=None) -> list[tuple[str, str, dict[str, str]]]:
    """Read every default bundle off the event loop (small, but blocking I/O)."""
    bundles: list[tuple[str, Path]] = []
    for locale in ("en", "am"):
        bundles.append(("core", CORE_I18N_DIR / f"{locale}.json"))
    if registry is not None:
        for manifest in registry.all():
            module_dir = Path(__file__).resolve().parents[2] / "modules" / manifest.key / "i18n"
            for locale in ("en", "am"):
                bundles.append((manifest.key, module_dir / f"{locale}.json"))

    loaded: list[tuple[str, str, dict[str, str]]] = []
    for namespace, path in bundles:
        if not path.exists():
            continue
        loaded.append((namespace, path.stem, json.loads(path.read_text(encoding="utf-8"))))
    return loaded


async def load_defaults(session: AsyncSession, registry=None) -> int:
    bundles = await asyncio.to_thread(_read_bundles, registry)

    inserted = 0
    for namespace, locale, data in bundles:
        for key, value in data.items():
            exists = (
                await session.execute(
                    select(TranslationEntry).where(
                        TranslationEntry.namespace == namespace,
                        TranslationEntry.key == key,
                        TranslationEntry.locale == locale,
                        TranslationEntry.layer == "default",
                    )
                )
            ).scalar_one_or_none()
            if exists is None:
                session.add(
                    TranslationEntry(
                        namespace=namespace,
                        key=key,
                        locale=locale,
                        value=value,
                        layer="default",
                        status="approved",
                        source="human",
                    )
                )
                inserted += 1
            elif exists.value != value:
                exists.value = value
    await session.flush()
    return inserted


async def merged_namespace(session: AsyncSession, locale: str, namespace: str) -> dict[str, str]:
    rows = (
        (
            await session.execute(
                select(TranslationEntry).where(
                    TranslationEntry.namespace == namespace,
                    TranslationEntry.locale.in_([locale, "en"]),
                    TranslationEntry.status.in_(["approved", "needs_review"]),
                )
            )
        )
        .scalars()
        .all()
    )
    # Most specific layer wins: default < central < school.
    layer_rank = {name: index for index, name in enumerate(LAYERS)}
    merged: dict[str, str] = {}
    by_key_locale: dict[tuple[str, str], TranslationEntry] = {}
    for row in rows:
        pair = (row.key, row.locale)
        current = by_key_locale.get(pair)
        if current is None or layer_rank.get(row.layer, 0) >= layer_rank.get(current.layer, 0):
            by_key_locale[pair] = row
    for (key, row_locale), row in by_key_locale.items():
        if row_locale == "en":
            merged.setdefault(key, row.value)
    for (key, row_locale), row in by_key_locale.items():
        if row_locale == locale:
            merged[key] = row.value
    return merged


async def namespaces_for(session: AsyncSession, locale: str) -> list[str]:
    rows = await session.execute(
        select(TranslationEntry.namespace).where(TranslationEntry.locale == locale).distinct()
    )
    namespaces = {row[0] for row in rows.all()}
    if "core" not in namespaces:
        namespaces.add("core")
    return sorted(namespaces)
