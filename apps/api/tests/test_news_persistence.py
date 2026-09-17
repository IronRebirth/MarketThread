from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, select

from app.db.models.news import NewsArticle as NewsArticleRecord
from app.db.models.news import NewsSource as NewsSourceRecord
from app.news.models import NewsArticle
from app.news.persistence import (
    NewsArticleNotFoundError,
    NewsPersistenceService,
)

persistence_service = NewsPersistenceService()


def build_article(
    *,
    title: str,
    published_at: datetime,
    url: str,
    source_domain: str,
) -> NewsArticle:
    """Build a test article with isolated source metadata."""

    return NewsArticle(
        id=uuid4(),
        source_id=uuid4(),
        source_name="Example Test News",
        source_domain=source_domain,
        title=title,
        url=url,
        summary="Market-relevant test article.",
        author="Test Reporter",
        published_at=published_at,
        discovered_at=published_at,
        content_hash=uuid4().hex + uuid4().hex,
        language="en",
    )


async def cleanup_articles(
    db_session,
    content_hashes: list[str],
) -> None:
    """Delete test articles and their unreferenced source records safely."""

    result = await db_session.execute(
        select(NewsArticleRecord.source_id).where(
            NewsArticleRecord.content_hash.in_(content_hashes),
        ),
    )
    source_ids = set(result.scalars().all())

    await db_session.execute(
        delete(NewsArticleRecord).where(
            NewsArticleRecord.content_hash.in_(content_hashes),
        ),
    )

    await db_session.flush()

    for source_id in source_ids:
        remaining_article_id = await db_session.scalar(
            select(NewsArticleRecord.id)
            .where(
                NewsArticleRecord.source_id == source_id,
            )
            .limit(1)
        )

        if remaining_article_id is None:
            await db_session.execute(
                delete(NewsSourceRecord).where(
                    NewsSourceRecord.id == source_id,
                ),
            )

    await db_session.commit()


async def test_persist_many_is_idempotent_and_listable(db_session) -> None:
    """Persist the same article twice and retrieve it without duplication."""

    timestamp = datetime(
        2027,
        9,
        17,
        10,
        0,
        tzinfo=UTC,
    )
    source_domain = f"test-{uuid4().hex}.example.com"
    query_token = f"policy-{uuid4().hex[:8]}"

    article = build_article(
        title=f"Central bank changes {query_token} guidance",
        published_at=timestamp,
        url=f"https://{source_domain}/articles/policy",
        source_domain=source_domain,
    )

    try:
        first = await persistence_service.persist_many(
            db_session,
            [article],
        )

        second = await persistence_service.persist_many(
            db_session,
            [article],
        )

        assert len(first) == 1
        assert len(second) == 1
        assert second[0].id == first[0].id

        records = await persistence_service.list(
            db_session,
            query=query_token,
            start_at=datetime(
                2027,
                9,
                17,
                9,
                0,
                tzinfo=UTC,
            ),
            end_at=datetime(
                2027,
                9,
                17,
                11,
                0,
                tzinfo=UTC,
            ),
        )

        assert len(records) == 1
        assert records[0].id == article.id
        assert records[0].source_name == "Example Test News"
        assert records[0].source_domain == source_domain

        stored_id = await db_session.scalar(
            select(NewsArticleRecord.id).where(
                NewsArticleRecord.content_hash == article.content_hash,
            ),
        )

        assert stored_id == first[0].id
    finally:
        await cleanup_articles(
            db_session,
            [article.content_hash],
        )


async def test_persisted_news_can_be_filtered_by_time(db_session) -> None:
    """Return only persisted articles inside the requested time range."""

    source_domain = f"test-{uuid4().hex}.example.com"

    early = build_article(
        title="Early market report",
        published_at=datetime(
            2027,
            9,
            16,
            10,
            0,
            tzinfo=UTC,
        ),
        url=f"https://{source_domain}/articles/early",
        source_domain=source_domain,
    )
    late = build_article(
        title="Late market report",
        published_at=datetime(
            2027,
            9,
            17,
            10,
            0,
            tzinfo=UTC,
        ),
        url=f"https://{source_domain}/articles/late",
        source_domain=source_domain,
    )

    try:
        await persistence_service.persist_many(
            db_session,
            [early, late],
        )

        records = await persistence_service.list(
            db_session,
            start_at=datetime(
                2027,
                9,
                17,
                0,
                0,
                tzinfo=UTC,
            ),
            end_at=datetime(
                2027,
                9,
                18,
                0,
                0,
                tzinfo=UTC,
            ),
        )

        assert len(records) == 1
        assert records[0].id == late.id
    finally:
        await cleanup_articles(
            db_session,
            [early.content_hash, late.content_hash],
        )


async def test_invalid_persistence_range_is_rejected(db_session) -> None:
    """Reject a persistence query with a reversed time range."""

    start = datetime(
        2027,
        9,
        18,
        tzinfo=UTC,
    )
    end = datetime(
        2027,
        9,
        17,
        tzinfo=UTC,
    )

    try:
        await persistence_service.list(
            db_session,
            start_at=start,
            end_at=end,
        )
    except ValueError as exc:
        assert str(exc) == "start_at must be earlier than end_at"
    else:
        raise AssertionError("Expected invalid time range to be rejected.")


async def test_missing_article_raises_domain_error(db_session) -> None:
    """Raise a domain error when a requested article does not exist."""

    try:
        await persistence_service.get(
            db_session,
            uuid4(),
        )
    except NewsArticleNotFoundError as exc:
        assert "News article" in str(exc)
    else:
        raise AssertionError("Expected NewsArticleNotFoundError.")
