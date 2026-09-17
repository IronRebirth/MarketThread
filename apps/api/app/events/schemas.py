from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.events.models import MarketEvent
from app.events.types import EventCatalyst, EventType
from app.news.intelligence.models import ImpactDirection, MarketRelevance


class MarketEventResponse(BaseModel):
    """Public API representation of a persisted market event."""

    model_config = ConfigDict(frozen=True)

    event_id: UUID
    event_type: EventType
    title: str
    summary: str
    catalyst: EventCatalyst
    market_relevance: MarketRelevance
    impact_direction: ImpactDirection
    affected_entities: tuple[str, ...]
    affected_sectors: tuple[str, ...]
    source_article_ids: tuple[UUID, ...]
    first_seen_at: datetime
    last_seen_at: datetime
    confidence: float = Field(ge=0.0, le=1.0)


def to_event_response(event: MarketEvent) -> MarketEventResponse:
    """Convert a domain event into the public API representation."""

    return MarketEventResponse(
        event_id=event.event_id,
        event_type=event.event_type,
        title=event.title,
        summary=event.summary,
        catalyst=event.catalyst,
        market_relevance=event.market_relevance,
        impact_direction=event.impact_direction,
        affected_entities=event.affected_entities,
        affected_sectors=event.affected_sectors,
        source_article_ids=event.source_article_ids,
        first_seen_at=event.first_seen_at,
        last_seen_at=event.last_seen_at,
        confidence=event.confidence,
    )
