from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from app.db.models.fundamental_snapshot import FundamentalSnapshot
from app.db.models.instrument import Instrument
from app.db.models.news import NewsArticle, NewsSource
from app.research.models import ResearchQuery
from app.research.retrieval import ResearchContextService


@pytest.mark.asyncio
async def test_research_context_respects_as_of_cutoff(db_session) -> None:
    instrument = Instrument(
        id=uuid4(),
        symbol="CUTOFF",
        name="Cutoff Test Corp",
        exchange="TEST",
        asset_class="equity",
        currency="USD",
        is_active=True,
    )
    source = NewsSource(
        id=uuid4(),
        name="Test Source",
        domain=f"cutoff-{uuid4().hex}.example",
    )
    now = datetime.now(UTC)

    db_session.add_all([instrument, source])
    await db_session.flush()

    db_session.add_all(
        [
            NewsArticle(
                id=uuid4(),
                source_id=source.id,
                title="Visible event for CUTOFF",
                url="https://example.com/visible",
                summary="Visible CUTOFF research",
                published_at=now - timedelta(days=2),
                discovered_at=now - timedelta(days=2),
                content_hash=uuid4().hex + uuid4().hex,
                language="en",
            ),
            NewsArticle(
                id=uuid4(),
                source_id=source.id,
                title="Future event for CUTOFF",
                url="https://example.com/future",
                summary="Future CUTOFF research",
                published_at=now + timedelta(days=2),
                discovered_at=now + timedelta(days=2),
                content_hash=uuid4().hex + uuid4().hex,
                language="en",
            ),
            FundamentalSnapshot(
                id=uuid4(),
                instrument_id=instrument.id,
                period_end=date.today(),
                source="test",
                revenue_growth="0.10",
            ),
        ],
    )
    await db_session.commit()

    context = await ResearchContextService(db_session).build(
        ResearchQuery(
            question="CUTOFF",
            as_of=now,
            limit=10,
        ),
        user_id=uuid4(),
    )

    assert all(article.published_at <= now for article in context.articles)
    assert all(
        fundamental.period_end <= now.date() for fundamental in context.fundamentals
    )


@pytest.mark.asyncio
async def test_research_context_returns_explicit_limitations_when_empty(
    db_session,
) -> None:
    context = await ResearchContextService(db_session).build(
        ResearchQuery(
            question="NONEXISTENT-COMPANY",
            as_of=datetime.now(UTC),
        ),
        user_id=uuid4(),
    )

    assert context.instruments == ()
    assert context.articles == ()
    assert context.events == ()
    assert context.signals == ()
    assert context.limitations
