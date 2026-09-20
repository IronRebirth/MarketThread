from collections import defaultdict
from threading import Lock
from time import monotonic
from typing import Final

from fastapi import HTTPException, Request, status


class FixedWindowRateLimiter:
    """Process-local fixed-window limiter for security-sensitive endpoints."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._lock = Lock()
        self._windows: dict[tuple[str, str], tuple[float, int]] = defaultdict(
            lambda: (0.0, 0),
        )

    def check(self, request: Request, scope: str) -> None:
        key = (scope, self._client_key(request))
        now = monotonic()

        with self._lock:
            window_started, count = self._windows[key]

            if now - window_started >= self.window_seconds:
                window_started = now
                count = 0

            if count >= self.limit:
                retry_after = max(
                    1,
                    int(self.window_seconds - (now - window_started)),
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                    headers={"Retry-After": str(retry_after)},
                )

            self._windows[key] = (window_started, count + 1)

    @staticmethod
    def _client_key(request: Request) -> str:
        client = request.client
        return client.host if client is not None else "unknown"


AUTH_LOGIN_LIMITER: Final = FixedWindowRateLimiter(
    limit=10,
    window_seconds=60,
)
AUTH_REGISTER_LIMITER: Final = FixedWindowRateLimiter(
    limit=5,
    window_seconds=600,
)
