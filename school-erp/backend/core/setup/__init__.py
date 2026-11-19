"""First-run instance setup (P1-24)."""

from core.setup.service import (
    AdminSetup,
    SchoolSetup,
    SetupRequest,
    complete_setup,
    setup_status,
    user_count,
)

__all__ = [
    "AdminSetup",
    "SchoolSetup",
    "SetupRequest",
    "complete_setup",
    "setup_status",
    "user_count",
]
