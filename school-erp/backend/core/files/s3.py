"""Minimal AWS Signature V4 query presigner for S3-compatible storage.

Only the query-string form is needed: the API hands a short-lived URL to the
browser or mobile client, which then talks to the bucket directly. Keeping
this dependency-free avoids shipping a full AWS SDK just to sign two URLs.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote, urlencode, urlparse

ALGORITHM = "AWS4-HMAC-SHA256"
UNSIGNED_PAYLOAD = "UNSIGNED-PAYLOAD"
MAX_EXPIRES = 604_800


@dataclass(frozen=True)
class S3Config:
    endpoint: str
    region: str
    bucket: str
    access_key: str
    secret_key: str
    path_style: bool = True


def _hmac(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode(), hashlib.sha256).digest()


def _location(config: S3Config, key: str) -> tuple[str, str]:
    """Return (host, canonical path), handling path- and virtual-host style."""
    parsed = urlparse(config.endpoint)
    endpoint_path = parsed.path.rstrip("/")
    object_path = quote(key.lstrip("/"), safe="/-_.~")
    if config.path_style:
        bucket = quote(config.bucket, safe="-_.~")
        return parsed.netloc, f"{endpoint_path}/{bucket}/{object_path}"
    return f"{config.bucket}.{parsed.netloc}", f"{endpoint_path}/{object_path}"


def presign(
    config: S3Config,
    method: str,
    key: str,
    *,
    expires_in: int = 600,
    now: datetime | None = None,
) -> str:
    """Return a presigned URL for one object and method."""
    if not 1 <= expires_in <= MAX_EXPIRES:
        raise ValueError(f"expires_in must be between 1 and {MAX_EXPIRES} seconds")
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    stamp = moment.strftime("%Y%m%dT%H%M%SZ")
    date = moment.strftime("%Y%m%d")
    scope = f"{date}/{config.region}/s3/aws4_request"
    parsed = urlparse(config.endpoint)
    host, uri = _location(config, key)
    if not parsed.netloc:
        raise ValueError("The S3 endpoint needs a host")
    params = {
        "X-Amz-Algorithm": ALGORITHM,
        "X-Amz-Credential": f"{config.access_key}/{scope}",
        "X-Amz-Date": stamp,
        "X-Amz-Expires": str(expires_in),
        "X-Amz-SignedHeaders": "host",
    }
    query = urlencode(sorted(params.items()), quote_via=quote)
    canonical_request = "\n".join(
        [
            method.upper(),
            uri,
            query,
            f"host:{host}\n",
            "host",
            UNSIGNED_PAYLOAD,
        ]
    )
    string_to_sign = "\n".join(
        [
            ALGORITHM,
            stamp,
            scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ]
    )
    signing_key = _hmac(
        _hmac(_hmac(_hmac(("AWS4" + config.secret_key).encode(), date), config.region), "s3"),
        "aws4_request",
    )
    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    return f"{parsed.scheme}://{host}{uri}?{query}&X-Amz-Signature={signature}"


__all__ = ["MAX_EXPIRES", "S3Config", "presign"]
