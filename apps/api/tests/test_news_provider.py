from datetime import UTC, datetime

import httpx
import pytest

from app.news.providers.errors import (
    NewsProviderError,
    NewsProviderInvalidResponseError,
    NewsProviderUnavailableError,
)
from app.news.providers.http import HttpNewsProvider


def build_provider(
    handler,
) -> tuple[HttpNewsProvider, httpx.AsyncClient]:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(
        transport=transport,
        base_url="https://newsapi.test",
    )

    return (
        HttpNewsProvider(
            base_url="https://newsapi.test",
            api_key="test-key",
            client=client,
        ),
        client,
    )


def article_payload() -> dict[str, object]:
    return {
        "source": {
            "id": "test-source",
            "name": "Example News",
        },
        "author": "Reporter",
        "title": "Central bank announces a major policy change",
        "description": "Markets are reviewing the policy decision.",
        "url": "https://example.com/articles/policy-change",
        "publishedAt": "2026-09-17T10:15:00Z",
    }


@pytest.mark.asyncio
async def test_search_normalizes_newsapi_article() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Api-Key"] == "test-key"
        assert request.url.path == "/v2/everything"

        params = request.url.params

        assert params["q"] == "central bank"
        assert params["language"] == "en"
        assert params["sortBy"] == "publishedAt"
        assert params["pageSize"] == "100"
        assert params["from"] == "2026-09-16T00:00:00Z"
        assert params["to"] == "2026-09-17T00:00:00Z"

        return httpx.Response(
            200,
            json={
                "status": "ok",
                "totalResults": 1,
                "articles": [article_payload()],
            },
        )

    provider, client = build_provider(handler)

    try:
        articles = await provider.search(
            "central bank",
            start=datetime(2026, 9, 16, tzinfo=UTC),
            end=datetime(2026, 9, 17, tzinfo=UTC),
        )
    finally:
        await client.aclose()

    assert len(articles) == 1

    article = articles[0]

    assert article.title == "Central bank announces a major policy change"
    assert article.source_name == "Example News"
    assert article.source_domain == "example.com"
    assert article.language == "en"
    assert article.published_at == datetime(
        2026,
        9,
        17,
        10,
        15,
        tzinfo=UTC,
    )
    assert len(article.content_hash) == 64


@pytest.mark.asyncio
async def test_latest_uses_market_focused_query_and_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        params = request.url.params

        assert params["q"] == "market OR stocks OR finance OR economy"
        assert params["sortBy"] == "publishedAt"
        assert params["pageSize"] == "2"

        return httpx.Response(
            200,
            json={
                "status": "ok",
                "totalResults": 2,
                "articles": [
                    article_payload(),
                    {
                        **article_payload(),
                        "url": "https://example.com/articles/second",
                        "title": "Markets react to fresh economic data",
                    },
                ],
            },
        )

    provider, client = build_provider(handler)

    try:
        articles = await provider.latest(limit=2)
    finally:
        await client.aclose()

    assert len(articles) == 2


@pytest.mark.asyncio
async def test_provider_api_error_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={
                "status": "error",
                "code": "apiKeyInvalid",
                "message": "Your API key is invalid.",
            },
        )

    provider, client = build_provider(handler)

    try:
        with pytest.raises(NewsProviderError, match="HTTP 401"):
            await provider.latest()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_provider_unavailable_error_is_raised_for_upstream_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            json={
                "status": "error",
                "message": "Service unavailable",
            },
        )

    provider, client = build_provider(handler)

    try:
        with pytest.raises(
            NewsProviderUnavailableError,
            match="News provider is unavailable",
        ):
            await provider.latest()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_invalid_json_raises_invalid_response_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"not-json",
        )

    provider, client = build_provider(handler)

    try:
        with pytest.raises(
            NewsProviderInvalidResponseError,
            match="invalid JSON",
        ):
            await provider.latest()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_unsuccessful_payload_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "error",
                "code": "rateLimited",
                "message": "Too many requests",
            },
        )

    provider, client = build_provider(handler)

    try:
        with pytest.raises(NewsProviderError, match="Too many requests"):
            await provider.latest()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_invalid_article_payload_raises_invalid_response_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "articles": [
                    {
                        "source": {
                            "id": "test-source",
                            "name": "Example News",
                        },
                        "title": "",
                        "url": "https://example.com/article",
                        "publishedAt": "2026-09-17T10:15:00Z",
                    },
                ],
            },
        )

    provider, client = build_provider(handler)

    try:
        with pytest.raises(
            NewsProviderInvalidResponseError,
            match="valid title",
        ):
            await provider.latest()
    finally:
        await client.aclose()
