from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.settings import Settings, get_settings
from core.modules.models import InstanceModule, LicenseState
from erp_shared.license import LicenseError, verify_license
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class LicenseStatus:
    ACTIVE = "active"
    GRACE = "grace"
    SUSPENDED = "suspended"
    UNKNOWN = "unknown"


async def get_license(session: AsyncSession) -> LicenseState | None:
    return await session.get(LicenseState, "current")


async def verified_license(session: AsyncSession, settings: Settings | None = None) -> dict | None:
    settings = settings or get_settings()
    state = await get_license(session)
    if state is None or not state.token:
        return None
    public_key = state.controller_public_key or settings.controller_public_key
    if not public_key:
        return None
    try:
        return verify_license(state.token, public_key)
    except LicenseError:
        return None


async def module_states(session: AsyncSession, registry, settings: Settings | None = None) -> dict[str, dict]:
    """The three gates for every module (ARCH §4.5)."""
    settings = settings or get_settings()
    state = await get_license(session)
    claims = await verified_license(session, settings)
    license_known = bool(state and state.token)
    licensed_modules = set(claims.get("modules", [])) if claims else set()
    suspended = bool(claims and claims.get("status") == "suspended")

    rows = await session.execute(select(InstanceModule))
    enabled_map = {row.module_key: row.enabled for row in rows.scalars().all()}

    result: dict[str, dict] = {}
    for manifest in registry.all():
        if manifest.core:
            licensed = True
        elif claims is None:
            licensed = not license_known
        else:
            licensed = manifest.key in licensed_modules and not suspended
        enabled = True if manifest.core else enabled_map.get(manifest.key, manifest.default_enabled)
        result[manifest.key] = {
            "licensed": licensed,
            "enabled": enabled,
            "available": licensed and enabled,
            "licensable": manifest.licensable,
            "default_enabled": manifest.default_enabled,
            "core": manifest.core,
            "name": manifest.name,
            "version": manifest.version,
            "depends_on": manifest.depends_on,
        }
    return result


async def ensure_module_rows(session: AsyncSession, registry) -> None:
    existing = {row.module_key for row in (await session.execute(select(InstanceModule))).scalars().all()}
    for manifest in registry.all():
        if manifest.core or manifest.key in existing:
            continue
        session.add(InstanceModule(module_key=manifest.key, enabled=manifest.default_enabled))
    await session.commit()


async def set_module_enabled(
    session: AsyncSession, registry, key: str, enabled: bool, actor_id: uuid.UUID | None
) -> InstanceModule:
    manifest = registry.get(key)
    if manifest is None:
        from app.errors import NotFound

        raise NotFound(f"Unknown module {key}")
    if manifest.core:
        from app.errors import Conflict

        raise Conflict("Core modules cannot be toggled")
    if enabled:
        states = await module_states(session, registry)
        for dependency in manifest.depends_on:
            if not states.get(dependency, {}).get("available", False):
                from app.errors import Conflict

                raise Conflict(
                    f"Module '{key}' requires '{dependency}' to be enabled first",
                    message_key="modules.dependency_disabled",
                    details={"dependency": dependency},
                )
        # Turning a module off must not silently break dependants.
    else:
        states = await module_states(session, registry)
        dependants = [
            other.key
            for other in registry.all()
            if key in other.depends_on and states.get(other.key, {}).get("enabled")
        ]
        if dependants:
            from app.errors import Conflict

            raise Conflict(
                "Disable dependent modules first",
                message_key="modules.dependants_enabled",
                details={"dependants": dependants},
            )

    row = await session.get(InstanceModule, key)
    if row is None:
        row = InstanceModule(module_key=key, enabled=enabled)
        session.add(row)
    else:
        row.enabled = enabled
        row.updated_at = datetime.now(UTC)
    try:
        row.updated_by = uuid.UUID(actor_id) if actor_id else None
    except (TypeError, ValueError):
        # Controller actors use non-UUID ids; the column only tracks real users.
        row.updated_by = None
    await session.flush()
    return row


async def apply_license(
    session: AsyncSession, token: str, controller_public_key: str | None, settings: Settings | None = None
) -> LicenseState:
    settings = settings or get_settings()
    public_key = controller_public_key or settings.controller_public_key
    claims = verify_license(token, public_key)
    state = await session.get(LicenseState, "current")
    if state is None:
        state = LicenseState(id="current")
        session.add(state)
    state.token = token
    state.instance_id = claims.get("instance_id")
    state.status = claims.get("status", "active")
    state.modules = list(claims.get("modules", []))
    state.plan = claims.get("plan")
    state.limits = claims.get("limits", {})
    state.issued_at = datetime.fromtimestamp(claims["iat"], tz=UTC) if claims.get("iat") else None
    if claims.get("exp"):
        state.valid_until = datetime.fromtimestamp(claims["exp"], tz=UTC)
    if controller_public_key:
        state.controller_public_key = controller_public_key
    state.applied_at = datetime.now(UTC)
    await session.flush()
    return state
