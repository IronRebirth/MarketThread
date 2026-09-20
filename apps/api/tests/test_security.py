import pytest
from httpx import AsyncClient

from app.core.config import Settings
from app.security.rate_limit import FixedWindowRateLimiter


def test_jwt_secret_requires_at_least_32_characters() -> None:
    with pytest.raises(ValueError, match="32 characters"):
        Settings(jwt_secret_key="too-short")


async def test_security_headers_are_present(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]


def test_rate_limiter_rejects_requests_after_limit() -> None:
    from starlette.requests import Request

    scope = {
        "type": "http",
        "client": ("127.0.0.1", 12345),
        "headers": [],
        "method": "GET",
        "path": "/test",
        "query_string": b"",
        "scheme": "http",
        "server": ("test", 80),
    }
    request = Request(scope)
    limiter = FixedWindowRateLimiter(limit=1, window_seconds=60)

    limiter.check(request, "test")

    with pytest.raises(Exception) as exc_info:
        limiter.check(request, "test")

    assert exc_info.value.status_code == 429
