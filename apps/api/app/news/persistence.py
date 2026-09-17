from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.news import (
    NewsArticle as NewsArticleRecord,
)
from app.db.models.news import (
    NewsSource as NewsSourceRecord,
)
from app.news.models import NewsArticle


class NewsPersistenceError(Exception):
    """Base error for news persistence failures."""


class NewsArticleNotFoundError(NewsPersistenceError):
    """Raised when a persisted news article does not exist."""


class NewsPersistenceService:
    """Persist normalized news articles and source metadata."""

    async def persist_many(
        self,
        session: AsyncSession,
        articles: Sequence[NewsArticle],
    ) -> tuple[NewsArticle, ...]:
        """Persist normalized articles idempotently."""

        if not articles:
            return ()

        persisted: list[NewsArticle] = []

        for article in articles:
            source = await self._get_or_create_source(
                session,
                article,
            )

            existing = await session.scalar(
                select(NewsArticleRecord).where(
                    NewsArticleRecord.content_hash == article.content_hash,
                ),
            )

            if existing is not None:
                persisted.append(
                    self._to_domain_article(
                        existing,
                        source,
                    ),
                )
                continue

            record = NewsArticleRecord(
                id=article.id,
                source_id=source.id,
                title=article.title,
                url=str(article.url),
                summary=article.summary,
                author=article.author,
                published_at=article.published_at,
                discovered_at=article.discovered_at,
                content_hash=article.content_hash,
                language=article.language,
            )

            session.add(record)

            persisted.append(
                article.model_copy(
                    update={
                        "source_id": source.id,
                        "source_name": source.name,
                        "source_domain": source.domain,
                    },
                ),
            )

        await session.commit()

        return tuple(persisted)

    async def get(
        self,
        session: AsyncSession,
        article_id: UUID,
    ) -> NewsArticle:
        """Retrieve a persisted article with source metadata."""

        statement = (
            select(NewsArticleRecord, NewsSourceRecord)
            .join(
                NewsSourceRecord,
                NewsSourceRecord.id == NewsArticleRecord.source_id,
            )
            .where(NewsArticleRecord.id == article_id)
        )

        result = await session.execute(statement)
        row = result.one_or_none()

        if row is None:
            raise NewsArticleNotFoundError(
                f"News article {article_id} was not found.",
            )

        article_record, source_record = row

        return self._to_domain_article(
            article_record,
            source_record,
        )

    async def list(
        self,
        session: AsyncSession,
        *,
        query: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        limit: int = 50,
    ) -> tuple[NewsArticle, ...]:
        """List persisted articles with optional search and time filters."""

        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        if start_at is not None and end_at is not None and start_at >= end_at:
            raise ValueError("start_at must be earlier than end_at")

        statement = select(NewsArticleRecord, NewsSourceRecord).join(
            NewsSourceRecord,
            NewsSourceRecord.id == NewsArticleRecord.source_id,
        )

        normalized_query = query.strip() if query else ""

        if normalized_query:
            pattern = f"%{normalized_query}%"

            statement = statement.where(
                or_(
                    NewsArticleRecord.title.ilike(pattern),
                    NewsArticleRecord.summary.ilike(pattern),
                ),
            )

        if start_at is not None:
            statement = statement.where(
                NewsArticleRecord.published_at >= start_at,
            )

        if end_at is not None:
            statement = statement.where(
                NewsArticleRecord.published_at < end_at,
            )

        statement = statement.order_by(
            NewsArticleRecord.published_at.desc(),
        ).limit(limit)

        result = await session.execute(statement)

        return tuple(
            self._to_domain_article(article_record, source_record)
            for article_record, source_record in result.all()
        )

    async def _get_or_create_source(
        self,
        session: AsyncSession,
        article: NewsArticle,
    ) -> NewsSourceRecord:
        """Resolve a source record using its normalized domain."""

        domain = article.source_domain or _extract_domain(str(article.url))

        if not domain:
            raise NewsPersistenceError(
                "News article source domain is required for persistence.",
            )

        source = await session.scalar(
            select(NewsSourceRecord).where(
                NewsSourceRecord.domain == domain,
            ),
        )

        if source is not None:
            return source

        source = NewsSourceRecord(
            id=article.source_id,
            name=article.source_name or domain,
            domain=domain,
        )

        session.add(source)

        await session.flush()

        return source

    @staticmethod
    def _to_domain_article(
        record: NewsArticleRecord,
        source: NewsSourceRecord,
    ) -> NewsArticle:
        """Convert database records into the normalized domain model."""

        return NewsArticle(
            id=record.id,
            source_id=source.id,
            source_name=source.name,
            source_domain=source.domain,
            title=record.title,
            url=record.url,
            summary=record.summary,
            author=record.author,
            published_at=record.published_at,
            discovered_at=record.discovered_at,
            content_hash=record.content_hash,
            language=record.language,
        )


def _extract_domain(url: str) -> str | None:
    """Extract a normalized hostname from an article URL."""

    from urllib.parse import urlparse

    try:
        hostname = urlparse(url).hostname
    except ValueError:
        return None

    if not hostname:
        return None

    normalized = hostname.lower().removeprefix("www.")

    return normalized or None
