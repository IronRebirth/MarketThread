from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.news.api import get_news_ingestion_service
from app.news.ingestion import NewsIngestionService
from app.news.models import NewsArticle
from app.news.persistence import NewsPersistenceService
from app.news.providers.base import NewsProvider


def build_article(
    *,
    title: str = "Central bank changes interest-rate guidance",
) -> NewsArticle:
    timestamp = datetime(
        2026,
        9,
        17,
        10,
        0,
        tzinfo=UTC,
    )

    return NewsArticle(
        id=uuid4(),
        source_id=uuid4(),
        source_name="Example News",
        source_domain="example.com",
        title=title,
        url=f"https://example.com/articles/{uuid4()}",
        summary="Markets respond to the policy decision.",
        author="Reporter",
        published_at=timestamp,
        discovered_at=timestamp,
        content_hash=uuid4().hex + uuid4().hex,
        language="en",
    )


class FakeNewsProvider(NewsProvider):
    name = "test-provider"

    async def search(
        self,
        query: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Sequence[NewsArticle]:
        return (
            build_article(
                title=f"{query.title()} markets react to policy change",
            ),
        )

    async def latest(
        self,
        limit: int = 50,
    ) -> Sequence[NewsArticle]:
        return (build_article(),)[:limit]


@pytest.mark.asyncio
async def test_news_search_returns_article_and_intelligence(
    client,
) -> None:
    fake_service = NewsIngestionService(
        provider=FakeNewsProvider(),
        persistence=NewsPersistenceService(),
    )

    async def override_news_service(
        session=None,
    ) -> NewsIngestionService:
        return fake_service

    app = client._transport.app
    app.dependency_overrides[get_news_ingestion_service] = override_news_service

    try:
        response = await client.get(
            "/news/search",
            params={"query": "central bank"},
        )
    finally:
        app.dependency_overrides.pop(
            get_news_ingestion_service,
            None,
        )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["article"]["title"].startswith("Central Bank")
    assert payload[0]["article"]["source_name"] == "Example News"
    assert (
        payload[0]["intelligence"]["article_id"] == payload[0]["article"]["article_id"]
    )
    assert payload[0]["intelligence"]["market_relevance"]


@pytest.mark.asyncio
async def test_news_search_rejects_reversed_time_range(
    client,
) -> None:
    fake_service = NewsIngestionService(
        provider=FakeNewsProvider(),
        persistence=NewsPersistenceService(),
    )

    async def override_news_service(
        session=None,
    ) -> NewsIngestionService:
        return fake_service

    app = client._transport.app
    app.dependency_overrides[get_news_ingestion_service] = override_news_service

    try:
        response = await client.get(
            "/news/search",
            params={
                "query": "markets",
                "start_at": "2026-09-18T00:00:00Z",
                "end_at": "2026-09-17T00:00:00Z",
            },
        )
    finally:
        app.dependency_overrides.pop(
            get_news_ingestion_service,
            None,
        )

    assert response.status_code == 422
    assert "start must be earlier than end" in response.json()["detail"]


@pytest.mark.asyncio
async def test_latest_news_returns_empty_collection_when_provider_returns_none(
    client,
) -> None:
    class EmptyNewsProvider(NewsProvider):
        name = "empty-provider"

        async def search(
            self,
            query: str,
            start: datetime | None = None,
            end: datetime | None = None,
        ) -> Sequence[NewsArticle]:
            return ()

        async def latest(
            self,
            limit: int = 50,
        ) -> Sequence[NewsArticle]:
            return ()

    fake_service = NewsIngestionService(
        provider=EmptyNewsProvider(),
        persistence=NewsPersistenceService(),
    )

    async def override_news_service(
        session=None,
    ) -> NewsIngestionService:
        return fake_service

    app = client._transport.app
    app.dependency_overrides[get_news_ingestion_service] = override_news_service

    try:
        response = await client.get(
            "/news/latest",
            params={"limit": 10},
        )
    finally:
        app.dependency_overrides.pop(
            get_news_ingestion_service,
            None,
        )

    assert response.status_code == 200
    assert response.json() == []
