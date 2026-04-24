import unittest

from app.services.rate_limit_service import SlidingWindowRateLimiter


class TestRateLimiter(unittest.TestCase):
    def test_rate_limiter_blocks_after_limit(self) -> None:
        limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60)
        first = limiter.check("user-1")
        second = limiter.check("user-1")
        third = limiter.check("user-1")

        self.assertTrue(first.allowed)
        self.assertTrue(second.allowed)
        self.assertFalse(third.allowed)
        self.assertGreater(third.retry_after_seconds, 0)

    def test_rate_limiter_isolation_between_keys(self) -> None:
        limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60)
        first_user = limiter.check("user-a")
        second_user = limiter.check("user-b")

        self.assertTrue(first_user.allowed)
        self.assertTrue(second_user.allowed)


if __name__ == "__main__":
    unittest.main()
