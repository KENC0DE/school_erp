from __future__ import annotations

import time

import pytest
from erp_shared.directory import DirectoryVerificationError, verify_directory_record
from erp_shared.license import generate_keypair, sign_payload


def make_record(pair, **overrides):
    record = {
        "instance_id": "inst-1",
        "name": "Demo Academy",
        "api_base_url": "https://demo.example",
        "logo_url": None,
        "status": "active",
        "min_app_version": "1.0.0",
        "kid": "k1",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    record.update(overrides)
    record["signature"] = sign_payload(pair.private_key, record, kid=record["kid"])
    return record


def test_valid_record_verifies():
    pair = generate_keypair()
    record = make_record(pair)
    claims = verify_directory_record(record, {"k1": pair.public_key})
    assert claims["api_base_url"] == "https://demo.example"


def test_tampered_server_address_is_rejected():
    pair = generate_keypair()
    record = make_record(pair)
    record["api_base_url"] = "https://evil.example"
    with pytest.raises(DirectoryVerificationError):
        verify_directory_record(record, {"k1": pair.public_key})


def test_wrong_key_is_rejected():
    pair = generate_keypair()
    other = generate_keypair()
    record = make_record(pair)
    with pytest.raises(DirectoryVerificationError):
        verify_directory_record(record, {"k1": other.public_key})


def test_kid_rotation_uses_the_matching_key():
    first = generate_keypair()
    second = generate_keypair()
    record = make_record(second, kid="k2")
    verify_directory_record(record, {"k1": first.public_key, "k2": second.public_key})
    with pytest.raises(DirectoryVerificationError):
        verify_directory_record(record, {"k1": first.public_key})


def test_expired_record_is_rejected():
    pair = generate_keypair()
    record = make_record(pair, exp=int(time.time()) - 5)
    with pytest.raises(DirectoryVerificationError):
        verify_directory_record(record, {"k1": pair.public_key})
