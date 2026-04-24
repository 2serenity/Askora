import unittest

from app.services.rate_limit_service import RedisSlidingWindowRateLimiter


class _FailingRedis:
    def pipeline(self):
        raise RuntimeError("redis unavailable")


class TestRedisRateLimiter(unittest.TestCase):
    def test_fallback_to_inmemory_when_redis_unavailable(self) -> None:
        limiter = RedisSlidingWindowRateLimiter(redis_url="redis://localhost:6399/0", limit=1, window_seconds=60)
        limiter.redis = _FailingRedis()  # type: ignore[assignment]

        first = limiter.check("user-1")
        second = limiter.check("user-1")
        self.assertTrue(first.allowed)
        self.assertFalse(second.allowed)


if __name__ == "__main__":
    unittest.main()
