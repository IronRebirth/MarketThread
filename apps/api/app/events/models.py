from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.events.types import EventCatalyst, EventType
from app.news.intelligence.models import ImpactDirection, MarketRelevance


class MarketEvent(BaseModel):
    """Normalized market event derived from news intelligence."""

    model_config = ConfigDict(frozen=True)

    event_id: UUID
    event_type: EventType
    title: str = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1)
    catalyst: EventCatalyst
    market_relevance: MarketRelevance
    impact_direction: ImpactDirection
    affected_entities: tuple[str, ...] = ()
    affected_sectors: tuple[str, ...] = ()
    source_article_ids: tuple[UUID, ...] = ()
    first_seen_at: datetime
    last_seen_at: datetime
    confidence: float = Field(ge=0.0, le=1.0)
