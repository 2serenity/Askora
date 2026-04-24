from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic
import uuid

from redis import Redis

from app.core.config import settings


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int


class SlidingWindowRateLimiter:
    """In-process sliding-window limiter for interactive API protection."""

    def __init__(self, *, limit: int, window_seconds: int) -> None:
        self.limit = max(1, limit)
        self.window_seconds = max(1, window_seconds)
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> RateLimitDecision:
        now = monotonic()
        with self._lock:
            bucket = self._events[key]
            threshold = now - self.window_seconds
            while bucket and bucket[0] <= threshold:
                bucket.popleft()

            if len(bucket) >= self.limit:
                retry_after = max(1, int(self.window_seconds - (now - bucket[0])))
                return RateLimitDecision(
                    allowed=False,
                    limit=self.limit,
                    remaining=0,
                    retry_after_seconds=retry_after,
                )

            bucket.append(now)
            remaining = max(0, self.limit - len(bucket))
            return RateLimitDecision(
                allowed=True,
                limit=self.limit,
                remaining=remaining,
                retry_after_seconds=0,
            )


class RedisSlidingWindowRateLimiter:
    """Redis-backed sliding-window limiter with in-memory fallback."""

    def __init__(self, *, redis_url: str, limit: int, window_seconds: int) -> None:
        self.limit = max(1, limit)
        self.window_seconds = max(1, window_seconds)
        self.window_ms = self.window_seconds * 1000
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self._fallback = SlidingWindowRateLimiter(limit=self.limit, window_seconds=self.window_seconds)

    def check(self, key: str) -> RateLimitDecision:
        now_ms = self._now_ms()
        window_start = now_ms - self.window_ms
        bucket_key = f"ratelimit:{key}"
        event_id = f"{now_ms}:{uuid.uuid4().hex}"
        try:
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(bucket_key, 0, window_start)
            pipe.zcard(bucket_key)
            _, count = pipe.execute()
            count = int(count)
            if count >= self.limit:
                oldest = self.redis.zrange(bucket_key, 0, 0, withscores=True)
                retry_after = 1
                if oldest:
                    oldest_ms = int(oldest[0][1])
                    retry_after = max(1, math.ceil((oldest_ms + self.window_ms - now_ms) / 1000))
                return RateLimitDecision(
                    allowed=False,
                    limit=self.limit,
                    remaining=0,
                    retry_after_seconds=retry_after,
                )

            pipe = self.redis.pipeline()
            pipe.zadd(bucket_key, {event_id: now_ms})
            pipe.expire(bucket_key, self.window_seconds + 1)
            pipe.zcard(bucket_key)
            _, _, new_count = pipe.execute()
            remaining = max(0, self.limit - int(new_count))
            return RateLimitDecision(
                allowed=True,
                limit=self.limit,
                remaining=remaining,
                retry_after_seconds=0,
            )
        except Exception:
            return self._fallback.check(key)

    def _now_ms(self) -> int:
        return int(monotonic() * 1000)


query_rate_limiter = RedisSlidingWindowRateLimiter(
    redis_url=settings.redis_url,
    limit=settings.query_rate_limit_per_window,
    window_seconds=settings.query_rate_limit_window_seconds,
)
