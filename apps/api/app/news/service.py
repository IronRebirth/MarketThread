from collections.abc import Sequence
from datetime import datetime

from app.news.models import NewsArticle
from app.news.providers.base import NewsProvider


class NewsService:
    """Coordinate normalized news retrieval."""

    def __init__(self, provider: NewsProvider) -> None:
        self.provider = provider

    async def search(
        self,
        query: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Sequence[NewsArticle]:
        """Search for normalized news articles."""

        normalized_query = query.strip()

        if not normalized_query:
            return []

        if start is not None and end is not None and start >= end:
            raise ValueError("start must be earlier than end")

        return await self.provider.search(
            normalized_query,
            start=start,
            end=end,
        )

    async def latest(
        self,
        limit: int = 50,
    ) -> Sequence[NewsArticle]:
        """Return the latest normalized news articles."""

        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        return await self.provider.latest(limit=limit)
