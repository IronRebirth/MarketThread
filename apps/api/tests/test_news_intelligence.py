from datetime import UTC, datetime
from uuid import uuid4

from app.news.intelligence.models import (
    ImpactDirection,
    MarketRelevance,
    Sentiment,
)
from app.news.intelligence.service import NewsIntelligenceService
from app.news.models import NewsArticle


def make_article(
    title: str,
    summary: str | None = None,
) -> NewsArticle:
    """Build a normalized article for intelligence tests."""

    now = datetime.now(UTC)

    return NewsArticle(
        id=uuid4(),
        source_id=uuid4(),
        title=title,
        url="https://example.com/article",
        summary=summary,
        published_at=now,
        discovered_at=now,
        content_hash="a" * 64,
        language="en",
    )


def test_positive_high_relevance_news() -> None:
    article = make_article(
        "Central bank approves interest rate cut after strong earnings",
    )

    intelligence = NewsIntelligenceService().analyze(article)

    assert intelligence.market_relevance == MarketRelevance.HIGH
    assert intelligence.sentiment == Sentiment.POSITIVE
    assert intelligence.impact_direction == ImpactDirection.POSITIVE
    assert intelligence.confidence > 0.5
    assert "monetary policy" in intelligence.topics
    assert intelligence.catalyst == "monetary_policy"


def test_negative_geopolitical_news() -> None:
    article = make_article(
        "New sanctions announced amid war escalation",
    )

    intelligence = NewsIntelligenceService().analyze(article)

    assert intelligence.market_relevance == MarketRelevance.HIGH
    assert intelligence.sentiment == Sentiment.NEGATIVE
    assert intelligence.impact_direction == ImpactDirection.NEGATIVE
    assert intelligence.catalyst == "geopolitical"


def test_neutral_low_relevance_news() -> None:
    article = make_article(
        "Technology conference opens in Singapore",
    )

    intelligence = NewsIntelligenceService().analyze(article)

    assert intelligence.market_relevance == MarketRelevance.LOW
    assert intelligence.sentiment == Sentiment.NEUTRAL
    assert intelligence.impact_direction == ImpactDirection.UNCERTAIN
    assert intelligence.confidence <= 0.65


def test_intelligence_is_linked_to_article() -> None:
    article = make_article(
        "Company reports strong profit growth",
    )

    intelligence = NewsIntelligenceService().analyze(article)

    assert intelligence.article_id == article.id


def test_word_matching_does_not_match_substrings() -> None:
    article = make_article(
        "Central bank reports strong earnings",
    )

    intelligence = NewsIntelligenceService().analyze(article)

    assert intelligence.sentiment == Sentiment.POSITIVE


def test_extracts_company_and_sector_information() -> None:
    article = make_article(
        "Apple reports strong iPhone growth as semiconductor demand rises",
    )

    intelligence = NewsIntelligenceService().analyze(article)

    assert intelligence.entities == ("Apple",)
    assert intelligence.affected_sectors == ("Technology",)
