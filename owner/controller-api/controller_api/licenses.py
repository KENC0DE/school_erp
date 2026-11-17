from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from erp_shared.license import sign_license
from sqlalchemy.ext.asyncio import AsyncSession

from controller_api.keys import KeyMaterial
from controller_api.models import LicenseRecord, School
from controller_api.settings import ControllerSettings

LICENSABLE_MODULES = [
    "academics",
    "students",
    "admissions",
    "staff",
    "attendance",
    "assessment",
    "timetable",
    "fees",
    "documents",
    "communication",
    "portals",
    "ai",
    "automation",
    "sample",
]


def build_license_claims(school: School, settings: ControllerSettings) -> dict:
    now = int(time.time())
    valid_until = now + settings.license_valid_days * 86400
    grace_until = valid_until + settings.license_grace_days * 86400
    return {
        "instance_id": school.id,
        "plan": school.plan,
        "modules": list(school.modules or []),
        "limits": {"students": 3000, "staff": 300, "storage_gb": 50},
        "status": school.status,
        "iat": now,
        "exp": grace_until,
        "valid_until": valid_until,
        "school_code": school.school_code,
    }


async def issue_license(
    session: AsyncSession, school: School, key: KeyMaterial, settings: ControllerSettings
) -> str:
    claims = build_license_claims(school, settings)
    token = sign_license(key.private_pem, claims, kid=key.kid, expires_in=None)
    session.add(
        LicenseRecord(
            school_id=school.id,
            token=token,
            status=school.status,
            modules=list(school.modules or []),
            valid_until=datetime.fromtimestamp(claims["valid_until"], tz=UTC),
        )
    )
    await session.flush()
    return token


def next_renewal(settings: ControllerSettings) -> datetime:
    return datetime.now(UTC) + timedelta(days=settings.license_valid_days)
