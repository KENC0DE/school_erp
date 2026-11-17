"""Detached Ed25519 signatures for heartbeats, audit batches and support tokens."""

from __future__ import annotations

import base64
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from erp_shared.audit import canonical_json


def _private(private_pem: str) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Not an Ed25519 private key")
    return key


def _public(public_pem: str) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(public_pem.encode())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("Not an Ed25519 public key")
    return key


def message_for(payload: dict[str, Any]) -> bytes:
    body = {key: value for key, value in payload.items() if key != "signature"}
    return canonical_json(body).encode()


def sign_detached(private_pem: str, payload: dict[str, Any]) -> str:
    signature = _private(private_pem).sign(message_for(payload))
    return base64.b64encode(signature).decode()


def verify_detached(public_pem: str, payload: dict[str, Any], signature: str) -> bool:
    try:
        _public(public_pem).verify(base64.b64decode(signature), message_for(payload))
        return True
    except (InvalidSignature, ValueError):
        return False
