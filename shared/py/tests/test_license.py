from __future__ import annotations

import time

import pytest
from erp_shared.audit import compute_hash
from erp_shared.license import (
    LicenseError,
    generate_keypair,
    public_key_from_private,
    sign_license,
    sign_payload,
    verify_license,
    verify_payload,
)


def test_license_roundtrip_and_public_key_derivation():
    pair = generate_keypair()
    assert public_key_from_private(pair.private_key).strip() == pair.public_key.strip()
    token = sign_license(pair.private_key, {"instance_id": "abc", "modules": ["sample"]}, expires_in=60)
    claims = verify_license(token, pair.public_key, expected_kid="k1")
    assert claims["instance_id"] == "abc"
    assert claims["modules"] == ["sample"]


def test_tampered_license_is_rejected():
    pair = generate_keypair()
    token = sign_license(pair.private_key, {"instance_id": "abc"}, expires_in=60)
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload[:-2]}xx.{signature}"
    with pytest.raises(LicenseError) as exc:
        verify_license(tampered, pair.public_key)
    assert exc.value.code == "INVALID_LICENSE"


def test_expired_license_is_rejected():
    pair = generate_keypair()
    token = sign_license(pair.private_key, {"instance_id": "abc"}, expires_in=-10)
    with pytest.raises(LicenseError) as exc:
        verify_license(token, pair.public_key)
    assert exc.value.code == "LICENSE_EXPIRED"


def test_unknown_kid_is_rejected():
    pair = generate_keypair()
    token = sign_license(pair.private_key, {"instance_id": "abc"}, kid="old", expires_in=60)
    with pytest.raises(LicenseError) as exc:
        verify_license(token, pair.public_key, expected_kid="new")
    assert exc.value.code == "UNKNOWN_KID"


def test_wrong_key_is_rejected():
    first = generate_keypair()
    second = generate_keypair()
    token = sign_license(first.private_key, {"instance_id": "abc"}, expires_in=60)
    with pytest.raises(LicenseError):
        verify_license(token, second.public_key)


def test_payload_signature_roundtrip():
    pair = generate_keypair()
    token = sign_payload(
        pair.private_key, {"reason": "support", "iat": int(time.time()), "exp": int(time.time()) + 60}
    )
    claims = verify_payload(token, pair.public_key)
    assert claims["reason"] == "support"


def test_audit_hash_detects_field_change():
    entry = {"seq": 1, "action": "x", "before": {"a": 1}, "after": None}
    first = compute_hash(None, entry)
    changed = compute_hash(None, {**entry, "after": {"a": 2}})
    assert first != changed
    assert compute_hash(None, entry) == first
