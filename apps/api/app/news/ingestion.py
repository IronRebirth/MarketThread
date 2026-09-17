from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.news.models import NewsArticle
from app.news.persistence import NewsPersistenceService
from app.news.providers.base import NewsProvider
from app.news.service import NewsService


class NewsIngestionService:
    """Retrieve normalized news and persist the resulting snapshots."""

    def __init__(
        self,
        provider: NewsProvider,
        persistence: NewsPersistenceService,
    ) -> None:
        self._news_service = NewsService(provider)
        self._persistence = persistence

    async def search(
        self,
        session: AsyncSession,
        query: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> tuple[NewsArticle, ...]:
        """Search the provider and persist the normalized results."""

        articles: Sequence[NewsArticle] = await self._news_service.search(
            query,
            start=start,
            end=end,
        )

        return await self._persistence.persist_many(
            session,
            articles,
        )

    async def latest(
        self,
        session: AsyncSession,
        limit: int = 50,
    ) -> tuple[NewsArticle, ...]:
        """Retrieve latest provider articles and persist the snapshots."""

        articles: Sequence[NewsArticle] = await self._news_service.latest(
            limit=limit,
        )

        return await self._persistence.persist_many(
            session,
            articles,
        )
