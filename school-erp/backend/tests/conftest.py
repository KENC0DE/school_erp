from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from app.main import create_app
from app.settings import Settings
from core.auth.models import User
from core.auth.rate_limit import reset_all as reset_auth_limits
from core.auth.security import hash_password
from core.bootstrap import bootstrap
from core.rbac.models import Role, RolePermission, UserRole
from sqlalchemy import select

DEV_PASSWORD = "DevPass#2026"


def make_settings(tmp_path, **overrides) -> Settings:
    values = {
        "app_env": "test",
        "dev_mode": True,
        "database_url": f"sqlite+aiosqlite:///{tmp_path}/test.db",
        "auto_create_schema": False,
        "secret_key": "test-secret-key-0123456789abcdef0123",
        "refresh_secret": "test-refresh-key-0123456789abcdef",
        "storage_dir": f"{tmp_path}/storage",
        "public_base_url": "http://testserver",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
async def app(tmp_path):
    reset_auth_limits()
    application = create_app(make_settings(tmp_path))
    await application.state.db.create_all()
    await bootstrap(application)
    yield application
    await application.state.db.dispose()
    reset_auth_limits()


@pytest.fixture
async def client(app) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def create_role(app, key: str, permissions: list[tuple[str, str]], *, system: bool = False) -> Role:
    """Create a role or replace the permissions of an existing one.

    Bootstrap now seeds the shipped defaults (including ``super_admin``), so
    fixtures must upsert instead of inserting blindly.
    """
    async with app.state.db.session() as session:
        role = (await session.execute(select(Role).where(Role.key == key))).scalar_one_or_none()
        if role is None:
            role = Role(key=key, name=key.replace("_", " ").title(), is_system=system)
            session.add(role)
            await session.flush()
        else:
            role.name = key.replace("_", " ").title()
            role.is_system = system
            role.is_active = True
            for row in (
                (await session.execute(select(RolePermission).where(RolePermission.role_id == role.id)))
                .scalars()
                .all()
            ):
                await session.delete(row)
            await session.flush()
        for permission, scope in permissions:
            session.add(RolePermission(role_id=role.id, permission=permission, scope=scope))
        await session.commit()
        return role


async def create_user(
    app,
    email: str,
    *,
    display_name: str | None = None,
    roles: list[str] | None = None,
    password: str = DEV_PASSWORD,
) -> User:
    async with app.state.db.session() as session:
        user = User(
            email=email.lower(),
            display_name=display_name or email.split("@")[0].title(),
            password_hash=hash_password(password),
            locale="en",
        )
        session.add(user)
        await session.flush()
        for key in roles or []:
            role = (await session.execute(select(Role).where(Role.key == key))).scalar_one()
            session.add(UserRole(user_id=user.id, role_id=role.id))
        await session.commit()
        return user


async def login(client: httpx.AsyncClient, email: str, password: str = DEV_PASSWORD) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seeded(app):
    await create_role(app, "super_admin", [("*", "all")], system=True)
    await create_role(app, "limited", [("sample.notes.view", "all"), ("ai.use", "all")])
    await create_role(
        app,
        "sample_manager",
        [
            ("sample.notes.view", "all"),
            ("sample.notes.create", "all"),
            ("ai.use", "all"),
            ("users.view", "all"),
        ],
    )
    await create_role(
        app,
        "auditor",
        [
            ("audit.activity.view", "all"),
            ("audit.verify", "all"),
            ("jobs.view", "all"),
            ("ai.use", "all"),
            ("modules.manage", "all"),
            ("modules.view", "all"),
            ("roles.view", "all"),
        ],
    )
    await create_user(app, "superadmin@demo.school", display_name="Super Admin", roles=["super_admin"])
    await create_user(app, "limited@demo.school", display_name="Limited User", roles=["limited"])
    await create_user(app, "manager@demo.school", display_name="Sample Manager", roles=["sample_manager"])
    await create_user(app, "auditor@demo.school", display_name="Auditor", roles=["auditor"])
    return {"password": DEV_PASSWORD}


@pytest.fixture
async def superadmin_headers(client, seeded):
    return await login(client, "superadmin@demo.school")


@pytest.fixture
async def limited_headers(client, seeded):
    return await login(client, "limited@demo.school")


@pytest.fixture
async def manager_headers(client, seeded):
    return await login(client, "manager@demo.school")


@pytest.fixture
async def auditor_headers(client, seeded):
    return await login(client, "auditor@demo.school")


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}.{uuid.uuid4().hex[:8]}@demo.school"
