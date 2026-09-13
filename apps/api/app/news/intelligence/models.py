from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MarketRelevance(StrEnum):
    """Market relevance classification for a news article."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Sentiment(StrEnum):
    """General directional sentiment of the article."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class ImpactDirection(StrEnum):
    """Potential market-impact direction."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    UNCERTAIN = "uncertain"


class NewsIntelligence(BaseModel):
    """Structured intelligence derived from a normalized news article."""

    model_config = ConfigDict(frozen=True)

    article_id: UUID
    market_relevance: MarketRelevance
    sentiment: Sentiment
    impact_direction: ImpactDirection
    confidence: float = Field(ge=0.0, le=1.0)
    topics: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()
    affected_sectors: tuple[str, ...] = ()
    catalyst: str | None = None
    rationale: str
