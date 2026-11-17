from __future__ import annotations

from core.themes.models import Theme
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    "muted-foreground": "oklch(0.556 0 0)",
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
    "destructive": "oklch(0.704 0.191 22.216)",
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

REQUIRED_TOKENS = set(LIGHT)

DEFAULT_THEME = {
    "key": "default",
    "name": "Default",
    "tokens": {"light": LIGHT, "dark": DARK},
}


def validate_theme(tokens: dict) -> list[str]:
    problems: list[str] = []
    if not isinstance(tokens, dict):
        return ["Theme tokens must be an object"]
    for mode in ("light", "dark"):
        variant = tokens.get(mode)
        if not isinstance(variant, dict):
            problems.append(f"Theme is missing the '{mode}' variant")
            continue
        missing = REQUIRED_TOKENS - set(variant)
        if missing:
            problems.append(f"{mode} variant is missing tokens: {', '.join(sorted(missing))}")
    return problems


async def active_theme(session: AsyncSession) -> dict:
    row = (
        (
            await session.execute(
                select(Theme).where(Theme.is_active.is_(True)).order_by(Theme.is_default.desc(), Theme.key)
            )
        )
        .scalars()
        .first()
    )
    if row is None:
        return {**DEFAULT_THEME, "source": "builtin"}
    return {"key": row.key, "name": row.name, "tokens": row.tokens, "source": "instance"}


async def ensure_default_theme(session: AsyncSession) -> Theme:
    row = (await session.execute(select(Theme).where(Theme.key == "default"))).scalar_one_or_none()
    if row is None:
        row = Theme(
            key="default",
            name="Default",
            tokens=DEFAULT_THEME["tokens"],
            is_default=True,
            is_active=True,
            is_builtin=True,
        )
        session.add(row)
        await session.flush()
    return row
