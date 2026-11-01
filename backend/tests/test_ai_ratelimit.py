"""Tests for AI rate limiter."""
from app.ai.ratelimit import RateLimiter


def test_rate_limiter_allows_under_limit():
    rl = RateLimiter(max_requests=3, window_seconds=60)
    assert rl.check("user-1")[0] is True
    assert rl.check("user-1")[0] is True
    assert rl.check("user-1")[0] is True


def test_rate_limiter_blocks_over_limit():
    rl = RateLimiter(max_requests=2, window_seconds=60)
    assert rl.check("user-1")[0] is True
    assert rl.check("user-1")[0] is True
    allowed, retry_after = rl.check("user-1")
    assert allowed is False
    assert retry_after > 0


def test_rate_limiter_per_user_isolation():
    rl = RateLimiter(max_requests=1, window_seconds=60)
    assert rl.check("user-1")[0] is True
    assert rl.check("user-2")[0] is True
    assert rl.check("user-1")[0] is False


def test_rate_limiter_reset():
    rl = RateLimiter(max_requests=1, window_seconds=60)
    assert rl.check("user-1")[0] is True
    assert rl.check("user-1")[0] is False
    rl.reset("user-1")
    assert rl.check("user-1")[0] is True

