from __future__ import annotations

from collections import defaultdict
from threading import Lock


class MetricsService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._http_requests: dict[tuple[str, str, int], int] = defaultdict(int)
        self._http_latency_ms_sum: dict[tuple[str, str], float] = defaultdict(float)
        self._http_latency_ms_count: dict[tuple[str, str], int] = defaultdict(int)
        self._query_runs: dict[str, int] = defaultdict(int)
        self._query_blocked_reasons: dict[str, int] = defaultdict(int)
        self._rate_limit_blocks = 0

    def observe_http(self, *, method: str, path: str, status_code: int, duration_ms: float) -> None:
        key = (method.upper(), path, status_code)
        latency_key = (method.upper(), path)
        with self._lock:
            self._http_requests[key] += 1
            self._http_latency_ms_sum[latency_key] += duration_ms
            self._http_latency_ms_count[latency_key] += 1

    def observe_query_run(self, status: str) -> None:
        with self._lock:
            self._query_runs[status] += 1

    def observe_query_blocked_reason(self, reason: str) -> None:
        normalized = reason.strip()[:160] or "unknown"
        with self._lock:
            self._query_blocked_reasons[normalized] += 1

    def observe_rate_limit_block(self) -> None:
        with self._lock:
            self._rate_limit_blocks += 1

    def snapshot(self) -> dict:
        with self._lock:
            http_requests = [
                {"method": method, "path": path, "status_code": status, "count": count}
                for (method, path, status), count in sorted(self._http_requests.items())
            ]
            latency = []
            for key, total in sorted(self._http_latency_ms_sum.items()):
                method, path = key
                count = self._http_latency_ms_count.get(key, 0)
                avg = round(total / count, 2) if count else 0.0
                latency.append(
                    {
                        "method": method,
                        "path": path,
                        "avg_ms": avg,
                        "count": count,
                    }
                )
            query_runs = [{"status": status, "count": count} for status, count in sorted(self._query_runs.items())]
            blocked = [{"reason": reason, "count": count} for reason, count in sorted(self._query_blocked_reasons.items())]
            return {
                "http_requests_total": http_requests,
                "http_latency_avg_ms": latency,
                "query_runs_total": query_runs,
                "query_blocked_reasons_total": blocked,
                "rate_limit_block_total": self._rate_limit_blocks,
            }


metrics_service = MetricsService()
