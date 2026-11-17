"""Colour parsing and WCAG contrast checks for imported themes (P1-21).

Themes may be authored in any of the CSS colour spaces that tweakcn and
shadcn/ui registries emit. The manager stores the strings the author wrote
(so a round-trip keeps the theme readable and editable) and this module is the
single place that turns them into sRGB for validation, previews and the React
Native theme object.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

RGB = tuple[float, float, float]
RGBA = tuple[float, float, float, float]

_NAMED = {
    "black": (0.0, 0.0, 0.0),
    "white": (1.0, 1.0, 1.0),
    "transparent": None,
}

_FUNC = re.compile(r"^([a-z]+)\((.*)\)$", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class ContrastResult:
    foreground: str
    background: str
    ratio: float
    minimum: float
    passes: bool

    def message(self, mode: str) -> str:
        return (
            f"{mode.title()} theme: '{self.foreground}' on '{self.background}' has a "
            f"contrast ratio of {self.ratio:.2f}:1; it must be at least "
            f"{self.minimum:.1f}:1."
        )


def _number(value: str, *, percent_scale: float = 1.0) -> float:
    text = value.strip()
    if text.endswith("%"):
        return float(text[:-1]) / 100.0 * percent_scale
    return float(text)


def _alpha(value: str | None) -> float:
    if value is None or value == "":
        return 1.0
    parsed = _number(value)
    return min(1.0, max(0.0, parsed))


def _split_components(body: str) -> tuple[list[str], float]:
    text = body.replace(",", " ")
    if "/" in text:
        main, alpha_text = text.split("/", 1)
        return main.split(), _alpha(alpha_text.strip())
    parts = text.split()
    # rgba(0, 0, 0, 0.5) / hsla(0, 0%, 0%, 0.5) keep alpha as a fourth part.
    if len(parts) == 4:
        return parts[:3], _alpha(parts[3])
    return parts, 1.0


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def _hue(value: str) -> float:
    text = value.strip().lower()
    if text.endswith("turn"):
        return float(text[:-4]) * 360.0
    if text.endswith("rad"):
        return math.degrees(float(text[:-3]))
    if text.endswith("grad"):
        return float(text[:-4]) * 0.9
    if text.endswith("deg"):
        text = text[:-3]
    return float(text)


def _hex(value: str) -> RGBA | None:
    text = value[1:]
    if len(text) in (3, 4):
        text = "".join(ch * 2 for ch in text)
    if len(text) not in (6, 8):
        return None
    try:
        channels = [int(text[index : index + 2], 16) / 255.0 for index in range(0, len(text), 2)]
    except ValueError:
        return None
    if len(channels) == 3:
        channels.append(1.0)
    return (channels[0], channels[1], channels[2], channels[3])


def _hsl_to_rgb(hue: float, saturation: float, lightness: float) -> RGB:
    hue = (hue % 360.0) / 360.0

    def hue_to_channel(p: float, q: float, t: float) -> float:
        t = t % 1.0
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    if saturation == 0:
        return (lightness, lightness, lightness)
    q = lightness * (1 + saturation) if lightness < 0.5 else lightness + saturation - lightness * saturation
    p = 2 * lightness - q
    return (
        hue_to_channel(p, q, hue + 1 / 3),
        hue_to_channel(p, q, hue),
        hue_to_channel(p, q, hue - 1 / 3),
    )


def _linear_to_srgb(channel: float) -> float:
    channel = _clamp(channel)
    if channel <= 0.0031308:
        return 12.92 * channel
    return 1.055 * channel ** (1 / 2.4) - 0.055


def _oklch_to_rgb(lightness: float, chroma: float, hue: float) -> RGB:
    radians = math.radians(hue)
    a = chroma * math.cos(radians)
    b = chroma * math.sin(radians)
    l_ = lightness + 0.3963377774 * a + 0.2158037573 * b
    m_ = lightness - 0.1055613458 * a - 0.0638541728 * b
    s_ = lightness - 0.0894841775 * a - 1.291485548 * b
    ll, mm, ss = l_**3, m_**3, s_**3
    red = 4.0767416621 * ll - 3.3077115913 * mm + 0.2309699292 * ss
    green = -1.2684380046 * ll + 2.6097574011 * mm - 0.3413193965 * ss
    blue = -0.0041960863 * ll - 0.7034186147 * mm + 1.707614701 * ss
    return (_linear_to_srgb(red), _linear_to_srgb(green), _linear_to_srgb(blue))


def parse_color(value: str) -> RGBA | None:
    """Parse hex, rgb(), hsl() or oklch() into non-linear sRGB + alpha."""
    text = value.strip()
    lowered = text.lower()
    if lowered in _NAMED:
        named = _NAMED[lowered]
        if named is None:
            return (0.0, 0.0, 0.0, 0.0)
        return (*named, 1.0)
    if lowered.startswith("#"):
        return _hex(lowered)
    match = _FUNC.match(lowered)
    if not match:
        return None
    name, body = match.group(1), match.group(2)
    try:
        parts, alpha = _split_components(body)
        if name in {"rgb", "rgba"}:
            if len(parts) != 3:
                return None
            channels = [
                float(part.strip()[:-1]) / 100.0
                if part.strip().endswith("%")
                else float(part.strip()) / 255.0
                for part in parts
            ]
            return (_clamp(channels[0]), _clamp(channels[1]), _clamp(channels[2]), alpha)
        if name in {"hsl", "hsla"}:
            if len(parts) != 3:
                return None
            hue = _hue(parts[0])
            saturation = _number(parts[1], percent_scale=1.0)
            lightness = _number(parts[2], percent_scale=1.0)
            if parts[1].strip().endswith("%"):
                saturation = float(parts[1].strip()[:-1]) / 100.0
            if parts[2].strip().endswith("%"):
                lightness = float(parts[2].strip()[:-1]) / 100.0
            return (*_hsl_to_rgb(hue, _clamp(saturation), _clamp(lightness)), alpha)
        if name == "oklch":
            if len(parts) != 3:
                return None
            lightness = _number(parts[0], percent_scale=1.0)
            if parts[0].strip().endswith("%"):
                lightness = float(parts[0].strip()[:-1]) / 100.0
            chroma = _number(parts[1], percent_scale=1.0)
            if parts[1].strip().endswith("%"):
                chroma = float(parts[1].strip()[:-1]) / 100.0 * 0.4
            hue = _hue(parts[2])
            return (*_oklch_to_rgb(_clamp(lightness), max(0.0, chroma), hue), alpha)
    except (TypeError, ValueError):
        return None
    return None


def composite(foreground: RGBA, background: RGBA) -> RGBA:
    alpha = foreground[3] + background[3] * (1 - foreground[3])
    if alpha <= 0:
        return (0.0, 0.0, 0.0, 0.0)
    return (
        (foreground[0] * foreground[3] + background[0] * background[3] * (1 - foreground[3])) / alpha,
        (foreground[1] * foreground[3] + background[1] * background[3] * (1 - foreground[3])) / alpha,
        (foreground[2] * foreground[3] + background[2] * background[3] * (1 - foreground[3])) / alpha,
        alpha,
    )


def _luminance(channels: RGB) -> float:
    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(_clamp(channel)) for channel in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: RGBA, background: RGBA) -> float:
    # Theme token backgrounds are usually opaque; if one has alpha assume the
    # page underneath is white for light tokens and black for dark tokens. The
    # caller passes an already composited background where that matters.
    base = background if background[3] >= 0.999 else composite(background, (1.0, 1.0, 1.0, 1.0))
    text = composite(foreground, base)
    lighter, darker = sorted((_luminance(text[:3]), _luminance(base[:3])), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def pair_contrast(foreground: str, background: str, *, minimum: float) -> ContrastResult | None:
    fg = parse_color(foreground)
    bg = parse_color(background)
    if fg is None or bg is None:
        return None
    ratio = contrast_ratio(fg, bg)
    return ContrastResult(
        foreground=foreground,
        background=background,
        ratio=round(ratio, 2),
        minimum=minimum,
        passes=ratio + 1e-9 >= minimum,
    )


def to_rn_color(value: str) -> str | None:
    """Convert a CSS colour to a string React Native can render."""
    parsed = parse_color(value)
    if parsed is None:
        return None
    red, green, blue, alpha = parsed
    red_byte = round(_clamp(red) * 255)
    green_byte = round(_clamp(green) * 255)
    blue_byte = round(_clamp(blue) * 255)
    if alpha >= 0.999:
        return f"#{red_byte:02x}{green_byte:02x}{blue_byte:02x}"
    return f"rgba({red_byte}, {green_byte}, {blue_byte}, {round(alpha, 3)})"


__all__ = [
    "ContrastResult",
    "composite",
    "contrast_ratio",
    "pair_contrast",
    "parse_color",
    "to_rn_color",
]
