"""Signed school directory records (ARCH §8.9, P0-16b)."""

from __future__ import annotations

import time
from typing import Any

from erp_shared.license import LicenseError, verify_payload

DIRECTORY_FIELDS = (
    "instance_id",
    "name",
    "api_base_url",
    "logo_url",
    "status",
    "min_app_version",
)


class DirectoryVerificationError(ValueError):
    pass


def verify_directory_record(record: dict[str, Any], trusted_keys: dict[str, str]) -> dict[str, Any]:
    """Verify a signed directory record against an embedded key set.

    The app must use the returned claims, not the outer fields, so an attacker
    cannot swap the server address while keeping a valid signature.
    """
    kid = record.get("kid")
    signature = record.get("signature")
    if not kid or not signature:
        raise DirectoryVerificationError("Record is not signed")
    public_key = trusted_keys.get(kid)
    if public_key is None:
        raise DirectoryVerificationError(f"Unknown signing key {kid!r}")
    try:
        claims = verify_payload(signature, public_key, expected_kid=kid)
    except LicenseError as exc:
        raise DirectoryVerificationError(f"Signature is invalid: {exc}") from exc
    if claims.get("exp") and claims["exp"] < int(time.time()):
        raise DirectoryVerificationError("Directory record has expired")
    for field in DIRECTORY_FIELDS:
        if record.get(field) != claims.get(field):
            raise DirectoryVerificationError(f"Signed value for {field} does not match the record")
    return claims
