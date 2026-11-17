"""Canonical theme tokens, validation and generated client forms (P1-21).

The JSON stored in ``themes.tokens`` is the source of truth for every client.
Web gets CSS custom properties and mobile gets a typed React Native object from
the same token map, so an imported theme can never drift between platforms.
"""

from __future__ import annotations

from typing import Any

from core.themes.colors import pair_contrast, to_rn_color

LIGHT = {
    "background": "oklch(1 0 0)",
    "foreground": "oklch(0.145 0 0)",
    "card": "oklch(1 0 0)",
    "card-foreground": "oklch(0.145 0 0)",
    "popover": "oklch(1 0 0)",
    "popover-foreground": "oklch(0.145 0 0)",
    "primary": "oklch(0.45 0.13 160)",
    "primary-foreground": "oklch(0.985 0 0)",
    "secondary": "oklch(0.97 0 0)",
    "secondary-foreground": "oklch(0.205 0 0)",
    "muted": "oklch(0.97 0 0)",
    "muted-foreground": "oklch(0.53 0 0)",
    "accent": "oklch(0.95 0.04 85)",
    "accent-foreground": "oklch(0.205 0 0)",
    "destructive": "oklch(0.577 0.245 27.325)",
    "destructive-foreground": "oklch(0.985 0 0)",
    "border": "oklch(0.922 0 0)",
    "input": "oklch(0.922 0 0)",
    "ring": "oklch(0.45 0.13 160)",
    "chart-1": "oklch(0.646 0.222 41.116)",
    "chart-2": "oklch(0.6 0.118 184.704)",
    "chart-3": "oklch(0.398 0.07 227.392)",
    "chart-4": "oklch(0.828 0.189 84.429)",
    "chart-5": "oklch(0.769 0.188 70.08)",
    "sidebar": "oklch(0.985 0 0)",
    "sidebar-foreground": "oklch(0.145 0 0)",
    "sidebar-primary": "oklch(0.45 0.13 160)",
    "sidebar-primary-foreground": "oklch(0.985 0 0)",
    "sidebar-accent": "oklch(0.97 0 0)",
    "sidebar-accent-foreground": "oklch(0.205 0 0)",
    "sidebar-border": "oklch(0.922 0 0)",
    "sidebar-ring": "oklch(0.708 0 0)",
    "radius": "0.625rem",
    "font-sans": "Inter, 'Noto Sans Ethiopic', system-ui, sans-serif",
    "font-ethiopic": "'Noto Sans Ethiopic', sans-serif",
}

DARK = {
    "background": "oklch(0.145 0 0)",
    "foreground": "oklch(0.985 0 0)",
    "card": "oklch(0.205 0 0)",
    "card-foreground": "oklch(0.985 0 0)",
    "popover": "oklch(0.205 0 0)",
    "popover-foreground": "oklch(0.985 0 0)",
    "primary": "oklch(0.62 0.13 160)",
    "primary-foreground": "oklch(0.145 0 0)",
    "secondary": "oklch(0.269 0 0)",
    "secondary-foreground": "oklch(0.985 0 0)",
    "muted": "oklch(0.269 0 0)",
    "muted-foreground": "oklch(0.708 0 0)",
    "accent": "oklch(0.3 0.04 85)",
    "accent-foreground": "oklch(0.985 0 0)",
    "destructive": "oklch(0.577 0.245 27.325)",
    "destructive-foreground": "oklch(0.985 0 0)",
    "border": "oklch(1 0 0 / 12%)",
    "input": "oklch(1 0 0 / 18%)",
    "ring": "oklch(0.62 0.13 160)",
    "chart-1": "oklch(0.488 0.243 264.376)",
    "chart-2": "oklch(0.696 0.17 162.48)",
    "chart-3": "oklch(0.769 0.188 70.08)",
    "chart-4": "oklch(0.627 0.265 303.9)",
    "chart-5": "oklch(0.645 0.246 16.439)",
    "sidebar": "oklch(0.205 0 0)",
    "sidebar-foreground": "oklch(0.985 0 0)",
    "sidebar-primary": "oklch(0.62 0.13 160)",
    "sidebar-primary-foreground": "oklch(0.145 0 0)",
    "sidebar-accent": "oklch(0.269 0 0)",
    "sidebar-accent-foreground": "oklch(0.985 0 0)",
    "sidebar-border": "oklch(1 0 0 / 12%)",
    "sidebar-ring": "oklch(0.556 0 0)",
    "radius": "0.625rem",
    "font-sans": "Inter, 'Noto Sans Ethiopic', system-ui, sans-serif",
    "font-ethiopic": "'Noto Sans Ethiopic', sans-serif",
}

REQUIRED_TOKENS = tuple(LIGHT)
NON_COLOR_TOKENS = {"radius", "font-sans", "font-ethiopic"}
COLOR_TOKENS = tuple(token for token in REQUIRED_TOKENS if token not in NON_COLOR_TOKENS)

# Key text pairs that must remain readable; WCAG 2.2 AA for normal text.
CONTRAST_PAIRS: tuple[tuple[str, str, float], ...] = (
    ("background", "foreground", 4.5),
    ("card", "card-foreground", 4.5),
    ("popover", "popover-foreground", 4.5),
    ("primary", "primary-foreground", 4.5),
    ("secondary", "secondary-foreground", 4.5),
    ("muted", "muted-foreground", 4.5),
    ("accent", "accent-foreground", 4.5),
    ("destructive", "destructive-foreground", 4.5),
    ("sidebar", "sidebar-foreground", 4.5),
    ("sidebar-primary", "sidebar-primary-foreground", 4.5),
    ("sidebar-accent", "sidebar-accent-foreground", 4.5),
)

DEFAULT_THEME: dict[str, Any] = {
    "key": "default",
    "name": "Default",
    "tokens": {"light": dict(LIGHT), "dark": dict(DARK)},
}


def _issue(code: str, message: str, *, mode: str | None = None, **extra: Any) -> dict[str, Any]:
    return {"code": code, "mode": mode, "message": message, **extra}


def _valid_css_length(value: str) -> bool:
    text = value.strip().lower()
    if text == "0":
        return True
    for unit in ("rem", "em", "px", "pt", "%"):
        if text.endswith(unit):
            try:
                float(text[: -len(unit)])
                return True
            except ValueError:
                return False
    return False


def contrast_report(tokens: dict) -> list[dict[str, Any]]:
    """Every checked pair with its measured ratio, whether it passes or not."""
    report: list[dict[str, Any]] = []
    if not isinstance(tokens, dict):
        return report
    for mode in ("light", "dark"):
        variant = tokens.get(mode)
        if not isinstance(variant, dict):
            continue
        for foreground, background, minimum in CONTRAST_PAIRS:
            fg = variant.get(foreground)
            bg = variant.get(background)
            if not isinstance(fg, str) or not isinstance(bg, str):
                continue
            result = pair_contrast(fg, bg, minimum=minimum)
            if result is None:
                continue
            report.append(
                {
                    "mode": mode,
                    "foreground_token": foreground,
                    "background_token": background,
                    "foreground": fg,
                    "background": bg,
                    "ratio": result.ratio,
                    "minimum": minimum,
                    "passes": result.passes,
                    "message": result.message(mode),
                }
            )
    return report


def validate_tokens(tokens: Any) -> list[dict[str, Any]]:
    """Return every problem that prevents a theme from being stored.

    An empty list means the theme is safe to use. Messages are complete
    sentences so the Theme Manager can show a clear reason without translating
    backend internals.
    """
    if not isinstance(tokens, dict):
        return [_issue("invalid_tokens", "Theme tokens must be an object.")]
    issues: list[dict[str, Any]] = []
    for mode in ("light", "dark"):
        variant = tokens.get(mode)
        if not isinstance(variant, dict):
            issues.append(
                _issue(
                    "missing_mode",
                    f"Theme is missing the '{mode}' variant; both light and dark are required.",
                    mode=mode,
                )
            )
            continue
        for token in REQUIRED_TOKENS:
            value = variant.get(token)
            if not isinstance(value, str) or value.strip() == "":
                issues.append(
                    _issue(
                        "missing_token",
                        f"The {mode} variant is missing the '{token}' token.",
                        mode=mode,
                        token=token,
                    )
                )
        for token, value in variant.items():
            if not isinstance(value, str):
                issues.append(
                    _issue(
                        "invalid_value",
                        f"The {mode} variant token '{token}' must be a string.",
                        mode=mode,
                        token=token,
                    )
                )
        radius = variant.get("radius")
        if isinstance(radius, str) and radius.strip() and not _valid_css_length(radius):
            issues.append(
                _issue(
                    "invalid_radius",
                    f"The {mode} radius '{radius}' is not a CSS length such as 0.625rem or 10px.",
                    mode=mode,
                    token="radius",
                )
            )
        for token in COLOR_TOKENS:
            value = variant.get(token)
            if not isinstance(value, str) or not value.strip():
                continue
            if value.strip().lower().startswith("var("):
                issues.append(
                    _issue(
                        "unresolved_variable",
                        f"The {mode} token '{token}' still points at another CSS variable; "
                        "paste resolved colour values.",
                        mode=mode,
                        token=token,
                    )
                )
                continue
            from core.themes.colors import parse_color

            if parse_color(value) is None:
                issues.append(
                    _issue(
                        "invalid_color",
                        f"The {mode} token '{token}' is not a colour this app can read: {value}.",
                        mode=mode,
                        token=token,
                    )
                )
    for pair in contrast_report(tokens):
        if not pair["passes"]:
            issues.append(
                _issue(
                    "contrast",
                    pair["message"],
                    mode=pair["mode"],
                    tokens=[pair["foreground_token"], pair["background_token"]],
                    ratio=pair["ratio"],
                    minimum=pair["minimum"],
                    foreground=pair["foreground"],
                    background=pair["background"],
                )
            )
    return issues


def theme_is_valid(tokens: Any) -> bool:
    return not validate_tokens(tokens)


def css_variables(tokens: dict) -> dict[str, str]:
    return {f"--{key}": value for key, value in tokens.items()}


def css_block(tokens: dict) -> str:
    return "\n".join(f"  {key}: {value};" for key, value in css_variables(tokens).items())


def to_mobile_theme(tokens: dict, mode: str) -> dict[str, Any]:
    variant = tokens.get(mode) if isinstance(tokens, dict) else None
    if not isinstance(variant, dict):
        variant = DEFAULT_THEME["tokens"][mode if mode in ("light", "dark") else "light"]
    colors: dict[str, str] = {}
    for token, value in variant.items():
        converted = to_rn_color(value) if isinstance(value, str) else None
        colors[token] = converted or str(value)
    radius_text = str(variant.get("radius", "0.625rem"))
    try:
        radius = float(radius_text.removesuffix("rem").removesuffix("px")) * 16
    except ValueError:
        radius = 10.0
    return {
        "mode": mode,
        "colors": colors,
        "radius": radius,
        "fonts": {
            "sans": variant.get("font-sans", LIGHT["font-sans"]),
            "ethiopic": variant.get("font-ethiopic", LIGHT["font-ethiopic"]),
        },
    }


__all__ = [
    "COLOR_TOKENS",
    "CONTRAST_PAIRS",
    "DARK",
    "DEFAULT_THEME",
    "LIGHT",
    "NON_COLOR_TOKENS",
    "REQUIRED_TOKENS",
    "contrast_report",
    "css_block",
    "css_variables",
    "theme_is_valid",
    "to_mobile_theme",
    "validate_tokens",
]
