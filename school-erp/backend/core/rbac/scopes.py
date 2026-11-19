"""Permission scopes (ARCH §5.3).

A scope narrows *where* a permission applies. ``all`` is the widest; every
module declares the scopes its permissions accept, and a role grant or a direct
override stores one of those values. Data-level resolvers (a teacher's sections,
a parent's children) arrive with the domain modules; this module only defines
the vocabulary and the containment rule.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import cycle guard for type checkers only
    from core.auth.principal import Principal

ALL = "all"
OWN_CLASS = "own_class"
ASSIGNED_SUBJECTS = "assigned_subjects"
DEPARTMENT = "department"
OWN_CHILDREN = "own_children"
SELF = "self"

# Ordered from widest to narrowest; kept for manifest authors and documentation.
KNOWN_SCOPES: tuple[str, ...] = (
    ALL,
    DEPARTMENT,
    ASSIGNED_SUBJECTS,
    OWN_CLASS,
    OWN_CHILDREN,
    SELF,
)


def scope_covers(granted: str, requested: str) -> bool:
    """True when holding ``granted`` satisfies a check for ``requested``."""
    return granted == ALL or granted == requested


def scopes_cover(granted: set[str], requested: str) -> bool:
    return any(scope_covers(scope, requested) for scope in granted)


def effective_scopes(principal: Principal, permission: str) -> set[str] | None:
    """Return the caller's scopes for one permission.

    ``None`` means unrestricted: the wildcard principal, or a permission that
    only ever matches through ``*``. An empty set means the caller holds the
    permission only through an exact grant with no scopes, which is treated as
    "no data" rather than "all data"; route guards use ``Principal.can`` for
    the permission check itself.
    """
    from core.auth.principal import permission_matches

    if "*" in principal.permissions:
        return None
    granted = {item for item in principal.permissions if permission_matches(item, permission)}
    if not granted:
        return set()
    scopes: set[str] = set()
    for item in granted:
        scopes |= principal.scopes.get(item, set())
    return scopes


__all__ = [
    "ALL",
    "ASSIGNED_SUBJECTS",
    "DEPARTMENT",
    "KNOWN_SCOPES",
    "OWN_CHILDREN",
    "OWN_CLASS",
    "SELF",
    "effective_scopes",
    "scope_covers",
    "scopes_cover",
]
