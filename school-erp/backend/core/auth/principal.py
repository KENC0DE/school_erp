from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Principal:
    actor_id: str
    actor_type: str = "user"
    via: str = "web"
    display_name: str = ""
    email: str | None = None
    locale: str = "en"
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)
    scopes: dict[str, set[str]] = field(default_factory=dict)
    is_controller: bool = False
    read_only: bool = False
    reason: str | None = None

    def can(self, permission: str) -> bool:
        if "*" in self.permissions or permission in self.permissions:
            return True
        prefix = permission.rsplit(".", 1)[0]
        return f"{prefix}.*" in self.permissions

    @property
    def user_id(self) -> str:
        return self.actor_id
