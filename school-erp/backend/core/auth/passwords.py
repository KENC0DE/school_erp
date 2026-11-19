"""Password policy (ARCH §5.2)."""

from __future__ import annotations

from app.errors import ValidationFailed

MIN_LENGTH = 12


def validate_password(password: str) -> None:
    """Raise ``422 WEAK_PASSWORD`` describing every unmet rule."""
    problems: list[str] = []
    if len(password) < MIN_LENGTH:
        problems.append("too_short")
    if not any(character.isalpha() for character in password):
        problems.append("missing_letter")
    if not any(character.isdigit() for character in password):
        problems.append("missing_digit")
    if problems:
        raise ValidationFailed(
            "The password does not meet the policy",
            code="WEAK_PASSWORD",
            message_key="error.weak_password",
            details={"min_length": MIN_LENGTH, "problems": problems},
        )


__all__ = ["MIN_LENGTH", "validate_password"]
