from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Principal:
    actor_id: str
    actor_type: str = "user"
    via: str = "web"
    on_behalf_of: str | None = None
    display_name: str = ""
    email: str | None = None
    locale: str = "en"
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)
    scopes: dict[str, set[str]] = field(default_factory=dict)
    is_controller: bool = False
    read_only: bool = False
    reason: str | None = None
    session_id: str | None = None
    must_enroll_2fa: bool = False

    def can(self, permission: str, scope: str | None = None) -> bool:
        matching = {
            granted
            for granted in self.permissions
            if granted == "*" or permission_matches(granted, permission)
        }
        if not matching:
            return False
        if scope is None or "*" in matching:
            return True
        allowed = set().union(*(self.scopes.get(granted, set()) for granted in matching))
        return "all" in allowed or scope in allowed

    @property
    def user_id(self) -> str:
        return self.actor_id


def permission_matches(granted: str, permission: str) -> bool:
    if granted == permission or granted == "*":
        return True
    if granted.endswith(".*"):
        prefix = granted[:-2]
        return permission == prefix or permission.startswith(f"{prefix}.")
    return False


# Retained for the existing internal imports (rbac service, tests).
_permission_matches = permission_matches
