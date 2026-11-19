"""The actor and channel vocabulary stored on every audit entry (ARCH §5.4)."""

from __future__ import annotations

ACTOR_TYPES = ("user", "ai", "controller", "automation", "system")
VIA_CHANNELS = ("web", "mobile", "api", "ai", "controller", "automation")

# Channels a client may declare about itself. Privileged channels (ai,
# controller, automation) are server-derived and can never be claimed by a
# request header.
CLIENT_VIA_CHANNELS = ("web", "mobile", "api")

__all__ = ["ACTOR_TYPES", "CLIENT_VIA_CHANNELS", "VIA_CHANNELS"]
