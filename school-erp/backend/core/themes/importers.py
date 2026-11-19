"""Theme importers: CSS paste, JSON upload and registry URLs (P1-21).

Parsing is deliberately strict about the two modes and the required token set,
but it accepts the common shapes emitted by shadcn/ui, tweakcn and registry
items so a school can paste what those tools produce without hand editing.
"""

from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx
from app.errors import ValidationFailed

_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.DOTALL)
_DECLARATION = re.compile(r"(--[A-Za-z0-9_-]+|[A-Za-z0-9_-]+)\s*:\s*([^;]+)")

# Values that are not standalone colours; still required, validated separately.
_NON_COLOR_PREFIXES = ("font-", "radius", "spacing", "shadow", "tracking", "text-", "leading-")


@dataclass
class ImportedTheme:
    key: str
    name: str
    tokens: dict[str, dict[str, str]]
    source: str
    source_url: str | None = None
    warnings: list[str] = field(default_factory=list)


def _normalize_key(token: str) -> str:
    name = token.strip()
    if name.startswith("--"):
        name = name[2:]
    if name.startswith("color-"):
        name = name[len("color-") :]
    return name


def _normalize_variant(values: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_key, raw_value in values.items():
        key = _normalize_key(str(raw_key))
        if not key:
            continue
        if isinstance(raw_value, (int, float)):
            raw_value = str(raw_value)
        if not isinstance(raw_value, str):
            continue
        normalized[key] = raw_value.strip()
    return normalized


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug or "imported")[:60]


def parse_css(content: str) -> ImportedTheme:
    css = _COMMENT.sub("", content)
    light: dict[str, str] = {}
    dark: dict[str, str] = {}
    shared: dict[str, str] = {}
    for selector, body in _RULE.findall(css):
        declarations = _normalize_variant(
            {match.group(1): match.group(2) for match in _DECLARATION.finditer(body)}
        )
        if not declarations:
            continue
        selector_text = selector.strip().lower()
        is_dark = ".dark" in selector_text or 'data-theme="dark"' in selector_text
        is_dark = is_dark or "data-theme=dark" in selector_text
        is_light = ":root" in selector_text or selector_text in {"html", "body", ":host"}
        if is_dark:
            dark.update(declarations)
        elif is_light:
            light.update(declarations)
        elif selector_text.startswith("@theme"):
            for key, value in declarations.items():
                if not value.strip().lower().startswith("var("):
                    shared.setdefault(key, value)
    for key, value in shared.items():
        light.setdefault(key, value)
        dark.setdefault(key, value)
    tokens = {mode: values for mode, values in (("light", light), ("dark", dark)) if values}
    name = "Pasted theme"
    return ImportedTheme(
        key=_slug(name),
        name=name,
        tokens=tokens,
        source="css",
        warnings=_shape_warnings(light, dark),
    )


def _shape_warnings(light: dict[str, str], dark: dict[str, str]) -> list[str]:
    warnings: list[str] = []
    if not light:
        warnings.append("No :root light block was found in the pasted CSS.")
    if not dark:
        warnings.append("No .dark block was found in the pasted CSS.")
    return warnings


def _extract_css_vars(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
    css_vars = data.get("cssVars")
    if isinstance(css_vars, dict):
        theme = css_vars.get("theme") if isinstance(css_vars.get("theme"), dict) else {}
        light = css_vars.get("light") if isinstance(css_vars.get("light"), dict) else {}
        dark = css_vars.get("dark") if isinstance(css_vars.get("dark"), dict) else {}
        return theme, light, dark
    return None


def parse_json(content: str) -> ImportedTheme:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValidationFailed(
            "The uploaded file is not valid JSON",
            message_key="error.theme.invalid_json",
            details={"position": exc.pos},
        ) from exc
    if isinstance(data, list):
        data = next((item for item in data if isinstance(item, dict)), None)
        if data is None:
            raise ValidationFailed(
                "The uploaded JSON does not contain a theme",
                message_key="error.theme.invalid_json",
            )
    if not isinstance(data, dict):
        raise ValidationFailed(
            "The uploaded JSON must be a theme object",
            message_key="error.theme.invalid_json",
        )
    if isinstance(data.get("items"), list):
        # A registry index, not a registry item: use the first theme entry.
        item = next(
            (
                entry
                for entry in data["items"]
                if isinstance(entry, dict) and entry.get("type", "").endswith("theme")
            ),
            None,
        )
        if item is None:
            item = next(
                (entry for entry in data["items"] if isinstance(entry, dict) and "cssVars" in entry), None
            )
        if item is None:
            raise ValidationFailed(
                "The registry index does not list a theme",
                message_key="error.theme.invalid_json",
            )
        data = item

    extracted = _extract_css_vars(data)
    if extracted is not None:
        shared, light_raw, dark_raw = extracted
        light = {**_normalize_variant(shared), **_normalize_variant(light_raw)}
        dark = {**_normalize_variant(shared), **_normalize_variant(dark_raw)}
    elif isinstance(data.get("tokens"), dict):
        tokens = data["tokens"]
        light = _normalize_variant(tokens.get("light", {})) if isinstance(tokens.get("light"), dict) else {}
        dark = _normalize_variant(tokens.get("dark", {})) if isinstance(tokens.get("dark"), dict) else {}
    elif isinstance(data.get("light"), dict) or isinstance(data.get("dark"), dict):
        light = _normalize_variant(data.get("light", {}))
        dark = _normalize_variant(data.get("dark", {}))
    elif isinstance(data.get("theme"), dict) and isinstance(data["theme"].get("tokens"), dict):
        tokens = data["theme"]["tokens"]
        light = _normalize_variant(tokens.get("light", {}))
        dark = _normalize_variant(tokens.get("dark", {}))
        data = {**data["theme"], **{key: value for key, value in data.items() if key != "theme"}}
    else:
        # A flat token map is a single mode; refuse rather than guessing which
        # mode the author meant.
        raise ValidationFailed(
            "The JSON must contain both 'light' and 'dark' token sets",
            message_key="error.theme.missing_modes",
        )

    name = str(data.get("name") or data.get("title") or data.get("slug") or "Imported theme")
    key = str(data.get("key") or data.get("slug") or _slug(name))
    return ImportedTheme(
        key=_slug(key),
        name=name[:120],
        tokens={mode: values for mode, values in (("light", light), ("dark", dark)) if values},
        source="json",
        warnings=_shape_warnings(light, dark),
    )


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValidationFailed(
            "The registry URL must be an http(s) URL",
            message_key="error.theme.invalid_registry_url",
            details={"url": url},
        )
    host = parsed.hostname.lower()
    if host in {"localhost"} or host.endswith(".local"):
        raise ValidationFailed(
            "The registry URL points at a local address",
            message_key="error.theme.invalid_registry_url",
            details={"url": url},
        )
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
        raise ValidationFailed(
            "The registry URL points at a private address",
            message_key="error.theme.invalid_registry_url",
            details={"url": url},
        )


async def fetch_registry(url: str, *, client: httpx.AsyncClient | None = None) -> str:
    _validate_url(url)
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=10.0, follow_redirects=True)
    try:
        response = await http.get(url, headers={"Accept": "application/json"})
    except httpx.HTTPError as exc:
        raise ValidationFailed(
            "The registry could not be reached",
            message_key="error.theme.registry_unreachable",
            details={"url": url},
        ) from exc
    finally:
        if owns_client:
            await http.aclose()
    if response.status_code != 200:
        raise ValidationFailed(
            "The registry returned an error",
            message_key="error.theme.registry_unreachable",
            details={"url": url, "status": response.status_code},
        )
    return response.text


async def import_payload(
    fmt: str,
    content: str,
    *,
    name: str | None = None,
    key: str | None = None,
    registry_client: httpx.AsyncClient | None = None,
) -> ImportedTheme:
    if fmt == "css":
        theme = parse_css(content)
    elif fmt == "json":
        theme = parse_json(content)
    elif fmt == "registry":
        theme = parse_json(await fetch_registry(content.strip(), client=registry_client))
        theme.source = "registry"
        theme.source_url = content.strip()
        theme.key = _slug(theme.key or theme.name)
    else:
        raise ValidationFailed(
            "Theme format must be css, json or registry",
            message_key="error.theme.invalid_format",
            details={"format": fmt},
        )
    if name:
        theme.name = name.strip()[:120]
        if not key:
            theme.key = _slug(theme.name)
    if key:
        theme.key = _slug(key)
    return theme


__all__ = [
    "ImportedTheme",
    "fetch_registry",
    "import_payload",
    "parse_css",
    "parse_json",
]
