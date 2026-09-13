from datetime import UTC, datetime
from uuid import uuid4

from app.events.models import MarketEvent
from app.events.service import EventIntelligenceService
from app.events.types import EventCatalyst, EventType
from app.news.intelligence.models import (
    ImpactDirection,
    MarketRelevance,
    NewsIntelligence,
    Sentiment,
)
from app.news.models import NewsArticle


def make_article(
    title: str,
    summary: str | None = None,
) -> NewsArticle:
    """Create a normalized article for event tests."""

    timestamp = datetime.now(UTC)

    return NewsArticle(
        id=uuid4(),
        source_id=uuid4(),
        external_id=None,
        url="https://example.com/news",
        title=title,
        summary=summary,
        content_hash=uuid4().hex,
        author=None,
        language="en",
        published_at=timestamp,
        discovered_at=timestamp,
    )


def make_intelligence(article: NewsArticle) -> NewsIntelligence:
    """Create article intelligence for event tests."""

    return NewsIntelligence(
        article_id=article.id,
        market_relevance=MarketRelevance.HIGH,
        sentiment=Sentiment.POSITIVE,
        impact_direction=ImpactDirection.POSITIVE,
        confidence=0.82,
        topics=("monetary policy",),
        entities=("Apple",),
        affected_sectors=("Technology",),
        catalyst="monetary_policy",
        rationale="Strong market-relevant catalyst detected.",
    )


def test_detects_rate_cut_event() -> None:
    article = make_article(
        "Central bank approves interest rate cut",
        "Policymakers reduce rates to support economic growth.",
    )
    intelligence = make_intelligence(article)

    event = EventIntelligenceService().detect(
        article,
        intelligence,
    )

    assert isinstance(event, MarketEvent)
    assert event.event_type == EventType.MONETARY_POLICY
    assert event.catalyst == EventCatalyst.RATE_CUT
    assert event.market_relevance == MarketRelevance.HIGH
    assert event.impact_direction == ImpactDirection.POSITIVE
    assert event.affected_entities == ("Apple",)
    assert event.affected_sectors == ("Technology",)
    assert event.source_article_ids == (article.id,)
    assert event.confidence == 0.82


def test_detects_tariff_event() -> None:
    article = make_article(
        "Government announces new semiconductor tariffs",
    )
    intelligence = make_intelligence(article)

    event = EventIntelligenceService().detect(
        article,
        intelligence,
    )

    assert event.event_type == EventType.TRADE_POLICY
    assert event.catalyst == EventCatalyst.TARIFF


def test_detects_corporate_acquisition() -> None:
    article = make_article(
        "Microsoft announces acquisition of software company",
    )
    intelligence = make_intelligence(article)

    event = EventIntelligenceService().detect(
        article,
        intelligence,
    )

    assert event.event_type == EventType.CORPORATE_ACTION
    assert event.catalyst == EventCatalyst.ACQUISITION


def test_detects_corporate_merger() -> None:
    article = make_article(
        "Microsoft and another company announce a merger",
    )
    intelligence = make_intelligence(article)

    event = EventIntelligenceService().detect(
        article,
        intelligence,
    )

    assert event.event_type == EventType.CORPORATE_ACTION
    assert event.catalyst == EventCatalyst.MERGER


def test_unknown_event_falls_back_to_other() -> None:
    article = make_article(
        "Company opens a new regional office",
    )
    intelligence = make_intelligence(article)

    event = EventIntelligenceService().detect(
        article,
        intelligence,
    )

    assert event.event_type == EventType.OTHER
    assert event.catalyst == EventCatalyst.OTHER
