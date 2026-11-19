"""Per-process sliding-window rate limits (ARCH §5.2).

Production will move this to Redis when the shared cache lands; the interface is
deliberately tiny so callers do not care. Limits are per worker process, which
is enough to blunt online guessing behind a single instance today.
"""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from app.errors import RateLimited


@dataclass
class SlidingWindowLimiter:
    clock: Callable[[], float] = time.monotonic
    hits: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def hit(self, key: str, *, limit: int, window_seconds: int) -> None:
        """Record one attempt, raising ``429 RATE_LIMITED`` past the limit."""
        if limit <= 0:
            return
        now = self.clock()
        window = max(1, window_seconds)
        bucket = [stamp for stamp in self.hits[key] if now - stamp < window]
        if len(bucket) >= limit:
            retry_after = max(1, int(window - (now - bucket[0])) + 1)
            self.hits[key] = bucket
            raise RateLimited(
                "Too many attempts. Try again shortly.",
                message_key="error.rate_limited",
                details={"retry_after": retry_after},
            )
        bucket.append(now)
        self.hits[key] = bucket

    def reset(self) -> None:
        self.hits.clear()


login_limiter = SlidingWindowLimiter()
reset_limiter = SlidingWindowLimiter()


def reset_all() -> None:
    login_limiter.reset()
    reset_limiter.reset()


__all__ = ["SlidingWindowLimiter", "login_limiter", "reset_all", "reset_limiter"]
