from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.news.models import NewsArticle
from app.news.service import NewsService


class FakeNewsProvider:
    """Deterministic provider used to test the news service."""

    name = "test-provider"

    def __init__(self) -> None:
        now = datetime.now(UTC)

        self.article = NewsArticle(
            id=uuid4(),
            source_id=uuid4(),
            title="Global markets react to major economic development",
            url="https://example.com/articles/market-event",
            summary="Example market-moving article.",
            published_at=now,
            discovered_at=now,
            content_hash="a" * 64,
            language="en",
        )

    async def search(
        self,
        query: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Sequence[NewsArticle]:
        if query.lower() in self.article.title.lower():
            return [self.article]

        return []

    async def latest(
        self,
        limit: int = 50,
    ) -> Sequence[NewsArticle]:
        return [self.article][:limit]


@pytest.mark.asyncio
async def test_search_normalizes_query() -> None:
    provider = FakeNewsProvider()
    service = NewsService(provider)

    articles = await service.search("  GLOBAL MARKETS  ")

    assert len(articles) == 1
    assert articles[0].title.startswith("Global markets")


@pytest.mark.asyncio
async def test_search_returns_empty_for_blank_query() -> None:
    provider = FakeNewsProvider()
    service = NewsService(provider)

    articles = await service.search("   ")

    assert articles == []


@pytest.mark.asyncio
async def test_search_rejects_invalid_range() -> None:
    provider = FakeNewsProvider()
    service = NewsService(provider)

    timestamp = datetime(2026, 1, 1, tzinfo=UTC)

    with pytest.raises(ValueError, match="start must be earlier than end"):
        await service.search(
            "markets",
            start=timestamp,
            end=timestamp,
        )


@pytest.mark.asyncio
async def test_latest_enforces_limit() -> None:
    provider = FakeNewsProvider()
    service = NewsService(provider)

    articles = await service.latest(limit=1)

    assert len(articles) == 1


@pytest.mark.asyncio
async def test_latest_rejects_invalid_limit() -> None:
    provider = FakeNewsProvider()
    service = NewsService(provider)

    with pytest.raises(ValueError, match="between 1 and 100"):
        await service.latest(limit=101)
