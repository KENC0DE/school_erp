"""Ed25519 license signing and verification (ARCH §8.2–8.3).

Kept provider-free: both the control plane and every school instance use this module,
so there is exactly one definition of a valid license.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

ALGORITHM = "EdDSA"


class LicenseError(Exception):
    """Raised when a license token is missing, malformed, tampered with or expired."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class KeyPair:
    private_key: str
    public_key: str


def generate_keypair() -> KeyPair:
    """Generate a fresh Ed25519 keypair in PEM form."""
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return KeyPair(private_key=private_pem, public_key=public_pem)


def public_key_from_private(private_pem: str) -> str:
    key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise LicenseError("BAD_KEY", "Not an Ed25519 private key")
    return (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )


def _load_private_key(private_pem: str) -> Ed25519PrivateKey:
    """PyJWT 2.15 does not convert PEM strings for EdDSA signing, only for
    verification; load the key object explicitly so both paths agree."""
    key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise LicenseError("BAD_KEY", "Not an Ed25519 private key")
    return key


def sign_license(
    private_pem: str,
    payload: dict[str, Any],
    *,
    kid: str = "k1",
    expires_in: int | None = None,
) -> str:
    """Sign a license payload as an EdDSA JWT."""
    claims = dict(payload)
    now = int(time.time())
    claims.setdefault("iat", now)
    if expires_in is not None:
        claims["exp"] = now + expires_in
    headers = {"kid": kid, "typ": "JWT"}
    return jwt.encode(claims, _load_private_key(private_pem), algorithm=ALGORITHM, headers=headers)


def verify_license(
    token: str,
    public_pem: str,
    *,
    leeway: int = 0,
    expected_kid: str | None = None,
    verify_aud: bool = True,
) -> dict[str, Any]:
    """Verify signature and expiry. Raises LicenseError with a stable code."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:  # pragma: no cover - defensive
        raise LicenseError("INVALID_LICENSE", "Malformed license token") from exc
    if expected_kid is not None and header.get("kid") != expected_kid:
        raise LicenseError("UNKNOWN_KID", f"Unknown signing key {header.get('kid')!r}")
    try:
        return jwt.decode(
            token,
            public_pem,
            algorithms=[ALGORITHM],
            leeway=leeway,
            options={"require": ["iat"], "verify_aud": verify_aud},
        )
    except jwt.ExpiredSignatureError as exc:
        raise LicenseError("LICENSE_EXPIRED", "License has expired") from exc
    except jwt.PyJWTError as exc:
        raise LicenseError("INVALID_LICENSE", "License signature is invalid") from exc


def sign_payload(private_pem: str, payload: dict[str, Any], *, kid: str = "k1") -> str:
    """Sign an arbitrary short-lived assertion (directory record, support token)."""
    return jwt.encode(payload, _load_private_key(private_pem), algorithm=ALGORITHM, headers={"kid": kid})


def verify_payload(
    token: str,
    public_pem: str,
    *,
    leeway: int = 0,
    expected_kid: str | None = None,
) -> dict[str, Any]:
    # Assertion tokens carry an `aud` claim for the caller to check; PyJWT's
    # audience validation needs an expected value, so it is disabled here.
    return verify_license(token, public_pem, leeway=leeway, expected_kid=expected_kid, verify_aud=False)


def load_public_key(public_pem: str) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(public_pem.encode())
    if not isinstance(key, Ed25519PublicKey):
        raise LicenseError("BAD_KEY", "Not an Ed25519 public key")
    return key
