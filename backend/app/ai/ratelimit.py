"""In-memory per-user rate limiter (sliding window, no persistence).

Default: 20 requests per 60 seconds per user_id.
Configuration via Settings.ai_rate_limit_per_minute and Settings.ai_rate_limit_window_seconds.
Thread-safe enough for single-process FastAPI (GIL protects the list operations).
"""
from __future__ import annotations
import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, max_requests: int = 20, window_seconds: int = 60):
        self._max = max_requests
        self._window = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def check(self, user_id: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds).

        Evicts expired timestamps; adds the new request if under the limit.
        """
        now = time.monotonic()
        cutoff = now - self._window
        bucket = self._buckets[user_id]
        # Evict old timestamps
        self._buckets[user_id] = [t for t in bucket if t > cutoff]
        bucket = self._buckets[user_id]

        if len(bucket) >= self._max:
            oldest = bucket[0]
            retry_after = int(self._window - (now - oldest)) + 1
            return False, retry_after

        bucket.append(now)
        return True, 0

    def reset(self, user_id: str) -> None:
        """Reset rate limit for a user (test helper)."""
        self._buckets.pop(user_id, None)

