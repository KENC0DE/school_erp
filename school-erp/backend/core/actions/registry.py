from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from core.auth.principal import Principal
from sqlalchemy.ext.asyncio import AsyncSession

RISK_LEVELS = {"read", "write", "bulk", "destructive"}


@dataclass
class ActionContext:
    principal: Principal
    session: AsyncSession
    via: str = "api"
    request_id: str | None = None
    ai_session_id: str | None = None


@dataclass
class Action:
    key: str
    module: str
    permission: str
    risk: str
    handler: Callable[[ActionContext, Any], Awaitable[Any]]
    describe: str = ""
    input_schema: type | None = None
    output_schema: type | None = None
    preview: Callable[..., Awaitable[Any]] | None = None
    ai_forbidden: bool = False

    def to_tool(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "module": self.module,
            "description": self.describe,
            "risk": self.risk,
            "permission": self.permission,
            "input_schema": self.input_schema.__name__ if self.input_schema else None,
            "requires_confirmation": self.risk != "read",
        }


@dataclass
class ActionRegistry:
    actions: dict[str, Action] = field(default_factory=dict)

    def register(self, action: Action) -> Action:
        if action.key in self.actions:
            raise ValueError(f"Duplicate action {action.key}")
        if action.risk not in RISK_LEVELS:
            raise ValueError(f"Action {action.key} has invalid risk {action.risk}")
        if not action.permission:
            raise ValueError(f"Action {action.key} must declare a permission")
        self.actions[action.key] = action
        return action

    def get(self, key: str) -> Action | None:
        return self.actions.get(key)

    def all(self) -> list[Action]:
        return list(self.actions.values())

    def visible(self, principal: Principal, states: dict[str, dict], *, for_ai: bool = True) -> list[Action]:
        visible = []
        for action in self.actions.values():
            if action.ai_forbidden and for_ai:
                continue
            state = states.get(action.module)
            if state is not None and not state.get("available"):
                continue
            if principal.can(action.permission):
                visible.append(action)
        return sorted(visible, key=lambda a: a.key)


registry = ActionRegistry()


def action(
    *,
    key: str,
    module: str,
    permission: str,
    risk: str = "read",
    describe: str = "",
    input: type | None = None,
    output: type | None = None,
    preview: Callable[..., Awaitable[Any]] | None = None,
    ai_forbidden: bool = False,
) -> Callable[
    [Callable[[ActionContext, Any], Awaitable[Any]]], Callable[[ActionContext, Any], Awaitable[Any]]
]:
    def decorator(fn: Callable[[ActionContext, Any], Awaitable[Any]]):
        registry.register(
            Action(
                key=key,
                module=module,
                permission=permission,
                risk=risk,
                handler=fn,
                describe=describe,
                input_schema=input,
                output_schema=output,
                preview=preview,
                ai_forbidden=ai_forbidden,
            )
        )
        return fn

    return decorator
