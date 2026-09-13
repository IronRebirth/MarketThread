from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from app.news.models import NewsArticle


class NewsProvider(Protocol):
    """Interface implemented by external news providers."""

    name: str

    async def search(
        self,
        query: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Sequence[NewsArticle]:
        """Search for normalized news articles."""

    async def latest(
        self,
        limit: int = 50,
    ) -> Sequence[NewsArticle]:
        """Return the latest normalized news articles."""
