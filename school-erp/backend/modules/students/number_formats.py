"""Student-number format templates (ARCH §9.2).

A format is literal text plus two placeholders:

* ``{year}`` - the academic year's start year (four digits)
* ``{seq}`` / ``{seq:04d}`` - the sequence value, optionally zero-padded

Exactly one ``{seq}`` is required. The rendered number must fit the 40-character
column, so templates are bounded and checked again at render time as the
sequence grows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_NUMBER_LENGTH = 40
MAX_FORMAT_LENGTH = 40
MAX_SEQ_WIDTH = 39
_LITERAL_RE = re.compile(r"[A-Za-z0-9 _./#()\-]*")
_TOKEN_RE = re.compile(r"\{([^{}]*)\}")


@dataclass(frozen=True)
class NumberToken:
    """One resolved placeholder in a compiled format."""

    kind: str  # "year" | "seq"
    width: int = 0  # zero-padding width for seq (0 = no padding)


@dataclass(frozen=True)
class NumberFormat:
    """A validated format; literals and tokens are interleaved."""

    pieces: tuple[str | NumberToken, ...]

    def render(self, *, year: int, seq: int) -> str:
        rendered: list[str] = []
        for piece in self.pieces:
            if isinstance(piece, str):
                rendered.append(piece)
            elif piece.kind == "year":
                rendered.append(f"{year:04d}")
            elif piece.width:
                rendered.append(str(seq).zfill(piece.width))
            else:
                rendered.append(str(seq))
        value = "".join(rendered)
        if len(value) > MAX_NUMBER_LENGTH:
            raise ValueError(f"The generated student number is longer than {MAX_NUMBER_LENGTH} characters")
        return value


def _check_literal(piece: str) -> None:
    if not _LITERAL_RE.fullmatch(piece):
        raise ValueError("Use only letters, digits, spaces and - _ . / # ( ) outside placeholders")


def _seq_width(raw: str) -> int:
    if raw == "seq":
        return 0
    prefix = "seq:0"
    if raw.startswith(prefix) and raw.endswith("d"):
        digits = raw[len(prefix) : -1]
        if digits.isdigit():
            width = int(digits)
            if 1 <= width <= MAX_SEQ_WIDTH:
                return width
    raise ValueError("Use {seq} or a zero-padded width such as {seq:04d}")


def compile_format(template: str) -> NumberFormat:
    """Validate a template and return the pieces used to render it."""
    if not isinstance(template, str):
        raise ValueError("The student number format must be text")
    template = template.strip()
    if not 1 <= len(template) <= MAX_FORMAT_LENGTH:
        raise ValueError(f"The format must be between 1 and {MAX_FORMAT_LENGTH} characters")

    pieces: list[str | NumberToken] = []
    cursor = 0
    seq_count = 0
    year_count = 0
    for match in _TOKEN_RE.finditer(template):
        _check_literal(template[cursor : match.start()])
        pieces.append(template[cursor : match.start()])
        raw = match.group(1)
        if raw == "year":
            year_count += 1
            token = NumberToken("year")
        else:
            seq_count += 1
            token = NumberToken("seq", _seq_width(raw))
        pieces.append(token)
        cursor = match.end()
    _check_literal(template[cursor:])
    pieces.append(template[cursor:])

    if seq_count != 1:
        raise ValueError("The format must contain exactly one {seq} placeholder")
    if year_count > 1:
        raise ValueError("The format can contain at most one {year} placeholder")
    return NumberFormat(tuple(pieces))


def validate_number_format(template: str) -> str:
    """Validate a template and return it unchanged (for settings validators)."""
    compile_format(template)
    return template.strip()


def render_number(template: str, *, year: int, seq: int) -> str:
    """Render a validated template into a student number."""
    return compile_format(template).render(year=year, seq=seq)


__all__ = [
    "MAX_FORMAT_LENGTH",
    "MAX_NUMBER_LENGTH",
    "NumberFormat",
    "NumberToken",
    "compile_format",
    "render_number",
    "validate_number_format",
]
