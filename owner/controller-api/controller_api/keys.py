from __future__ import annotations

from dataclasses import dataclass

from erp_shared.license import generate_keypair, public_key_from_private
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from controller_api.models import SigningKey
from controller_api.settings import ControllerSettings


@dataclass
class KeyMaterial:
    kid: str
    private_pem: str
    public_pem: str


async def _ensure(
    session: AsyncSession,
    settings: ControllerSettings,
    *,
    key_type: str,
    kid: str,
    private_pem: str,
    public_pem: str,
) -> KeyMaterial:
    row = (
        (
            await session.execute(
                select(SigningKey).where(SigningKey.key_type == key_type, SigningKey.active.is_(True))
            )
        )
        .scalars()
        .first()
    )
    if row is not None:
        return KeyMaterial(kid=row.kid, private_pem=row.private_pem, public_pem=row.public_pem)
    if not private_pem:
        pair = generate_keypair()
        private_pem, public_pem = pair.private_key, pair.public_key
    elif not public_pem:
        public_pem = public_key_from_private(private_pem)
    session.add(
        SigningKey(key_type=key_type, kid=kid, private_pem=private_pem, public_pem=public_pem, active=True)
    )
    await session.flush()
    return KeyMaterial(kid=kid, private_pem=private_pem, public_pem=public_pem)


async def ensure_signing_keys(
    session: AsyncSession, settings: ControllerSettings
) -> tuple[KeyMaterial, KeyMaterial]:
    license_key = await _ensure(
        session,
        settings,
        key_type="license",
        kid=settings.license_kid,
        private_pem=settings.license_private_key,
        public_pem=settings.license_public_key,
    )
    directory_key = await _ensure(
        session,
        settings,
        key_type="directory",
        kid=settings.directory_kid,
        private_pem=settings.directory_private_key,
        public_pem=settings.directory_public_key,
    )
    return license_key, directory_key


async def directory_key_set(session: AsyncSession) -> list[SigningKey]:
    rows = (
        (await session.execute(select(SigningKey).where(SigningKey.key_type == "directory"))).scalars().all()
    )
    return list(rows)
