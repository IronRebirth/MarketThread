from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.news.intelligence.models import (
    ImpactDirection,
    MarketRelevance,
    Sentiment,
)
from app.news.models import NewsArticle


class NewsIntelligenceResponse(BaseModel):
    """API representation of article intelligence."""

    model_config = ConfigDict(from_attributes=True)

    article_id: UUID
    market_relevance: MarketRelevance
    sentiment: Sentiment
    impact_direction: ImpactDirection
    confidence: float = Field(ge=0.0, le=1.0)
    topics: tuple[str, ...]
    entities: tuple[str, ...]
    affected_sectors: tuple[str, ...]
    catalyst: str | None
    rationale: str


class NewsArticleResponse(BaseModel):
    """API representation of a normalized news article."""

    model_config = ConfigDict(from_attributes=True)

    article_id: UUID
    source_id: UUID
    source_name: str
    source_domain: str
    title: str
    url: HttpUrl
    summary: str | None
    author: str | None
    published_at: datetime
    discovered_at: datetime
    language: str


class NewsFeedItemResponse(BaseModel):
    """Combined article and deterministic intelligence response."""

    article: NewsArticleResponse
    intelligence: NewsIntelligenceResponse


def to_news_feed_item(
    article: NewsArticle,
    intelligence: NewsIntelligenceResponse,
) -> NewsFeedItemResponse:
    """Convert normalized article data into the public API response."""

    source_name = article.source_name

    if not source_name:
        raise ValueError("News article source name is required for API responses.")

    source_domain = article.source_domain

    if not source_domain:
        raise ValueError("News article source domain is required for API responses.")

    return NewsFeedItemResponse(
        article=NewsArticleResponse(
            article_id=article.id,
            source_id=article.source_id,
            source_name=source_name,
            source_domain=source_domain,
            title=article.title,
            url=article.url,
            summary=article.summary,
            author=article.author,
            published_at=article.published_at,
            discovered_at=article.discovered_at,
            language=article.language,
        ),
        intelligence=intelligence,
    )
