"""P1-04: lockout, 2FA, password reset, sessions and web cookies."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from core.auth.models import User
from core.auth.totp import code_at
from sqlalchemy import select

from tests.conftest import DEV_PASSWORD, create_role, create_user

PASSWORD = "DevPass#2026"


async def _login(client, email: str, password: str = DEV_PASSWORD, **extra):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password, **extra})


def _bearer(response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['tokens']['access_token']}"}


async def test_failed_logins_lock_the_account_and_expire(client, seeded, app):
    response = await _login(client, "superadmin@demo.school", "wrong")
    assert response.status_code == 401

    for _ in range(4):
        assert (await _login(client, "superadmin@demo.school", "wrong")).status_code == 401

    locked = await _login(client, "superadmin@demo.school", PASSWORD)
    assert locked.status_code == 423
    assert locked.json()["error"]["code"] == "ACCOUNT_LOCKED"
    assert locked.json()["error"]["message_key"] == "error.account_locked"
    assert "locked_until" in locked.json()["error"]["details"]

    # Expire the lock: a correct password works again and the counter resets.
    async with app.state.db.session() as session:
        user = (
            await session.execute(select(User).where(User.email == "superadmin@demo.school"))
        ).scalar_one()
        user.locked_until = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()

    assert (await _login(client, "superadmin@demo.school", PASSWORD)).status_code == 200


async def test_login_attempts_are_rate_limited_per_ip(client, seeded, app):
    app.state.settings.login_rate_limit = 2
    assert (await _login(client, "nobody1@demo.school")).status_code == 401
    assert (await _login(client, "nobody2@demo.school")).status_code == 401
    limited = await _login(client, "nobody3@demo.school")
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    assert limited.json()["error"]["details"]["retry_after"] >= 1


async def test_totp_enrollment_and_login(client, seeded):
    login = await _login(client, "superadmin@demo.school")
    headers = _bearer(login)

    enroll = await client.post("/api/v1/auth/2fa/enroll", headers=headers)
    assert enroll.status_code == 200, enroll.text
    secret = enroll.json()["secret"]
    assert enroll.json()["otpauth_uri"].startswith("otpauth://totp/")

    bad = await client.post("/api/v1/auth/2fa/confirm", json={"code": "000000"}, headers=headers)
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "TOTP_INVALID"

    confirm = await client.post("/api/v1/auth/2fa/confirm", json={"code": code_at(secret)}, headers=headers)
    assert confirm.status_code == 200, confirm.text
    recovery = confirm.json()["recovery_codes"]
    assert len(recovery) == 10

    missing = await _login(client, "superadmin@demo.school")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "TOTP_REQUIRED"

    wrong = await _login(client, "superadmin@demo.school", totp_code="000000")
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "TOTP_INVALID"

    good = await _login(client, "superadmin@demo.school", totp_code=code_at(secret))
    assert good.status_code == 200
    assert good.json()["user"]["totp_enabled"] is True

    recovered = await _login(client, "superadmin@demo.school", recovery_code=recovery[0])
    assert recovered.status_code == 200

    # Recovery codes are single use.
    again = await _login(client, "superadmin@demo.school", recovery_code=recovery[0])
    assert again.status_code == 401
    assert again.json()["error"]["code"] == "TOTP_INVALID"


async def test_role_can_force_2fa_enrollment(client, app):
    await create_role(app, "strict", [("users.view", "all")], system=False)
    async with app.state.db.session() as session:
        from core.rbac.models import Role

        role = (await session.execute(select(Role).where(Role.key == "strict"))).scalar_one()
        role.require_totp = True
        await session.commit()
    await create_user(app, "strict@demo.school", display_name="Strict User", roles=["strict"])

    login = await _login(client, "strict@demo.school")
    assert login.status_code == 200
    assert login.json()["user"]["must_enroll_2fa"] is True
    headers = _bearer(login)

    blocked = await client.get("/api/v1/auth/users", headers=headers)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "TOTP_ENROLLMENT_REQUIRED"

    enroll = await client.post("/api/v1/auth/2fa/enroll", headers=headers)
    assert enroll.status_code == 200
    confirm = await client.post(
        "/api/v1/auth/2fa/confirm",
        json={"code": code_at(enroll.json()["secret"])},
        headers=headers,
    )
    assert confirm.status_code == 200

    relogin = await _login(
        client,
        "strict@demo.school",
        totp_code=code_at(enroll.json()["secret"]),
    )
    allowed = await client.get("/api/v1/auth/users", headers=_bearer(relogin))
    assert allowed.status_code == 200


async def test_password_reset_by_email_invalidates_sessions(client, app, seeded):
    await create_user(app, "reset@demo.school", display_name="Reset User", roles=["limited"])
    before = await _login(client, "reset@demo.school")
    old_refresh = before.json()["tokens"]["refresh_token"]

    unknown = await client.post("/api/v1/auth/forgot-password", json={"email": "ghost@demo.school"})
    assert unknown.status_code == 200
    assert app.state.mailer.outbox == []

    requested = await client.post("/api/v1/auth/forgot-password", json={"email": "reset@demo.school"})
    assert requested.status_code == 200
    assert len(app.state.mailer.outbox) == 1
    body = app.state.mailer.outbox[0].body
    token = body.split("token=")[1].splitlines()[0]

    weak = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "short"},
    )
    assert weak.status_code == 422
    assert weak.json()["error"]["code"] == "WEAK_PASSWORD"

    reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "NewStrongPass#2026"},
    )
    assert reset.status_code == 200, reset.text

    assert (await _login(client, "reset@demo.school", PASSWORD)).status_code == 401
    assert (await _login(client, "reset@demo.school", "NewStrongPass#2026")).status_code == 200

    reused = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "AnotherStrong#2026"},
    )
    assert reused.status_code == 401

    refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert refresh.status_code == 401


async def test_password_reset_by_sms_code(client, app, seeded):
    await create_user(app, "sms@demo.school", display_name="SMS User", roles=["limited"])
    async with app.state.db.session() as session:
        user = (await session.execute(select(User).where(User.email == "sms@demo.school"))).scalar_one()
        user.phone = "+251911000000"
        await session.commit()

    requested = await client.post("/api/v1/auth/forgot-password", json={"email": "sms@demo.school"})
    assert requested.status_code == 200
    assert len(app.state.sms.outbox) == 1
    sms_body = app.state.sms.outbox[0].body
    code = re.search(r"code is (\d{6})", sms_body)
    assert code is not None

    reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": code.group(1), "new_password": "SmsResetPass#2026"},
    )
    assert reset.status_code == 200, reset.text
    assert (await _login(client, "sms@demo.school", "SmsResetPass#2026")).status_code == 200

    reused = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": code.group(1), "new_password": "SmsResetPass#2027"},
    )
    assert reused.status_code == 401


async def test_session_list_and_revoke(client, seeded):
    first = await _login(client, "limited@demo.school")
    second = await _login(client, "limited@demo.school")
    headers = _bearer(second)

    listing = await client.get("/api/v1/auth/sessions", headers=headers)
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert len(items) == 2
    current = [item for item in items if item["current"]]
    assert len(current) == 1

    other = next(item for item in items if not item["current"])
    revoked = await client.delete(f"/api/v1/auth/sessions/{other['id']}", headers=headers)
    assert revoked.status_code == 200

    stale = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first.json()["tokens"]["refresh_token"]},
    )
    assert stale.status_code == 401

    remaining = await client.get("/api/v1/auth/sessions", headers=headers)
    assert len(remaining.json()["items"]) == 1

    cleared = await client.delete("/api/v1/auth/sessions", headers=headers)
    assert cleared.status_code == 200
    assert cleared.json()["revoked"] == 0


async def test_web_cookie_session_requires_csrf(client, seeded):
    login = await client.post(
        "/api/v1/auth/web/login",
        json={"email": "superadmin@demo.school", "password": PASSWORD},
    )
    assert login.status_code == 200, login.text
    refresh_cookie = login.cookies.get("erp_refresh")
    csrf = login.cookies.get("erp_csrf")
    assert refresh_cookie and csrf
    assert "httponly" in login.headers["set-cookie"].lower()

    no_csrf = await client.post("/api/v1/auth/web/refresh")
    assert no_csrf.status_code == 403
    assert no_csrf.json()["error"]["code"] == "CSRF_FAILED"

    refreshed = await client.post("/api/v1/auth/web/refresh", headers={"X-CSRF-Token": csrf})
    assert refreshed.status_code == 200, refreshed.text
    rotated = refreshed.cookies.get("erp_csrf")
    assert rotated and rotated != csrf
    rotated_refresh = refreshed.cookies.get("erp_refresh")
    assert rotated_refresh

    stale = await client.post("/api/v1/auth/web/refresh", headers={"X-CSRF-Token": csrf})
    assert stale.status_code == 403

    access = refreshed.json()["access_token"]
    logout = await client.post(
        "/api/v1/auth/web/logout",
        headers={"Authorization": f"Bearer {access}", "X-CSRF-Token": rotated},
    )
    assert logout.status_code == 200

    after = await client.post("/api/v1/auth/refresh", json={"refresh_token": rotated_refresh})
    assert after.status_code == 401
