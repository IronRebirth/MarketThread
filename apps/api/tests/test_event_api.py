from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete

from app.db.models.event import EventRecord
from app.db.models.news import NewsArticle as NewsArticleRecord
from app.db.models.news import NewsSource as NewsSourceRecord


async def create_news_article(db_session):
    """Create one isolated persisted article for event API tests."""

    source = NewsSourceRecord(
        id=uuid4(),
        name="Example Event News",
        domain=f"events-{uuid4().hex}.example.com",
    )
    db_session.add(source)
    await db_session.flush()

    timestamp = datetime(
        2027,
        9,
        18,
        12,
        0,
        tzinfo=UTC,
    )

    article = NewsArticleRecord(
        id=uuid4(),
        source_id=source.id,
        title="Central bank approves interest rate cut",
        url=f"https://{source.domain}/rate-cut",
        summary="Policymakers reduce rates to support economic growth.",
        author="Test Reporter",
        published_at=timestamp,
        discovered_at=timestamp,
        content_hash=uuid4().hex + uuid4().hex,
        language="en",
    )

    db_session.add(article)
    await db_session.commit()
    await db_session.refresh(article)

    return article, source


async def cleanup_news_article(
    db_session,
    article_id,
    source_id,
    event_id,
) -> None:
    """Remove the event, article, and source created by the test."""

    await db_session.execute(
        delete(EventRecord).where(
            EventRecord.id == event_id,
        ),
    )
    await db_session.execute(
        delete(NewsArticleRecord).where(
            NewsArticleRecord.id == article_id,
        ),
    )
    await db_session.execute(
        delete(NewsSourceRecord).where(
            NewsSourceRecord.id == source_id,
        ),
    )
    await db_session.commit()


async def test_detect_event_from_persisted_news(
    client,
    db_session,
) -> None:
    """Run the persisted News → Intelligence → Event pipeline."""

    article, source = await create_news_article(db_session)
    event_id = None

    try:
        response = await client.post(
            f"/events/from-news/{article.id}",
        )

        assert response.status_code == 200

        payload = response.json()

        assert payload["event_id"]
        assert payload["event_type"] == "monetary_policy"
        assert payload["catalyst"] == "rate_cut"
        assert payload["market_relevance"] == "high"
        assert payload["impact_direction"] == "positive"
        assert payload["source_article_ids"] == [str(article.id)]

        event_id = payload["event_id"]

        get_response = await client.get(
            f"/events/{event_id}",
        )

        assert get_response.status_code == 200
        assert get_response.json() == payload

        list_response = await client.get(
            "/events",
            params={
                "event_type": "monetary_policy",
                "catalyst": "rate_cut",
            },
        )

        assert list_response.status_code == 200

        listed_ids = {item["event_id"] for item in list_response.json()}

        assert event_id in listed_ids
    finally:
        if event_id is not None:
            await cleanup_news_article(
                db_session,
                article.id,
                source.id,
                event_id,
            )


async def test_detect_event_from_missing_news_returns_404(
    client,
) -> None:
    """Return 404 when the source article does not exist."""

    response = await client.post(
        f"/events/from-news/{uuid4()}",
    )

    assert response.status_code == 404


async def test_event_list_rejects_reversed_time_range(
    client,
) -> None:
    """Reject an invalid event-list time range."""

    response = await client.get(
        "/events",
        params={
            "start_at": "2027-09-19T00:00:00Z",
            "end_at": "2027-09-18T00:00:00Z",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "start_at must be earlier than end_at"
