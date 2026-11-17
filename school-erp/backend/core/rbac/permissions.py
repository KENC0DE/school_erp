from __future__ import annotations

from core.modules.manifest import Perm

CORE_PERMISSIONS = [
    Perm("users.view", "core.perm.users.view"),
    Perm("users.manage", "core.perm.users.manage"),
    Perm("roles.view", "core.perm.roles.view"),
    Perm("roles.manage", "core.perm.roles.manage"),
    Perm("modules.view", "core.perm.modules.view"),
    Perm("modules.manage", "core.perm.modules.manage"),
    Perm("audit.activity.view", "core.perm.audit.activity.view"),
    Perm("audit.activity.view_admin_actions", "core.perm.audit.activity.view_admin_actions"),
    Perm("audit.verify", "core.perm.audit.verify"),
    Perm("i18n.view", "core.perm.i18n.view"),
    Perm("i18n.manage", "core.perm.i18n.manage"),
    Perm("themes.view", "core.perm.themes.view"),
    Perm("themes.manage", "core.perm.themes.manage"),
    Perm("settings.view", "core.perm.settings.view"),
    Perm("settings.manage", "core.perm.settings.manage"),
    Perm("jobs.view", "core.perm.jobs.view"),
    Perm("ai.use", "core.perm.ai.use"),
]
