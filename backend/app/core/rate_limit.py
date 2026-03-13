import time
from dataclasses import dataclass

from app.core.config import get_settings


@dataclass
class RateLimitEntry:
    count: int
    reset_at_ms: int


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_at_ms: int


store: dict[str, RateLimitEntry] = {}


def check_rate_limit(key: str) -> RateLimitResult:
    cfg = get_settings()
    now = int(time.time() * 1000)
    window_ms = cfg.RATE_LIMIT_WINDOW_MS
    max_requests = cfg.RATE_LIMIT_MAX_REQUESTS

    current = store.get(key)
    if not current or now > current.reset_at_ms:
        current = RateLimitEntry(count=0, reset_at_ms=now + window_ms)
        store[key] = current

    current.count += 1
    remaining = max(0, max_requests - current.count)

    return RateLimitResult(
        allowed=current.count <= max_requests,
        remaining=remaining,
        reset_at_ms=current.reset_at_ms,
    )


def rate_limit_headers(result: RateLimitResult) -> dict[str, str]:
    cfg = get_settings()
    return {
        "X-RateLimit-Limit": str(cfg.RATE_LIMIT_MAX_REQUESTS),
        "X-RateLimit-Remaining": str(result.remaining),
        "X-RateLimit-Reset": str((result.reset_at_ms + 999) // 1000),
    }

