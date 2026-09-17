from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.news.intelligence.models import ImpactDirection, MarketRelevance
from app.news.persistence import NewsArticleNotFoundError

from .application import EventApplicationService
from .persistence import EventNotFoundError, EventPersistenceService
from .schemas import MarketEventResponse, to_event_response
from .types import EventCatalyst, EventType

router = APIRouter(
    prefix="/events",
    tags=["events"],
)

DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_db_session),
]

_persistence_service = EventPersistenceService()
_application_service = EventApplicationService()


@router.get(
    "",
    response_model=tuple[MarketEventResponse, ...],
    status_code=status.HTTP_200_OK,
    summary="List persisted market events",
)
async def list_events(
    session: DatabaseSession,
    event_type: EventType | None = None,
    catalyst: EventCatalyst | None = None,
    market_relevance: MarketRelevance | None = None,
    impact_direction: ImpactDirection | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 50,
) -> tuple[MarketEventResponse, ...]:
    """Return persisted market events with optional metadata filters."""

    try:
        events = await _persistence_service.list(
            session,
            event_type=event_type.value if event_type else None,
            catalyst=catalyst.value if catalyst else None,
            market_relevance=(market_relevance.value if market_relevance else None),
            impact_direction=(impact_direction.value if impact_direction else None),
            start_at=start_at,
            end_at=end_at,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return tuple(to_event_response(event) for event in events)


@router.post(
    "/from-news/{article_id}",
    response_model=MarketEventResponse,
    status_code=status.HTTP_200_OK,
    summary="Detect and persist an event from news",
)
async def detect_event_from_news(
    article_id: UUID,
    session: DatabaseSession,
) -> MarketEventResponse:
    """Run the News → News Intelligence → Event pipeline for one persisted article."""

    try:
        event = await _application_service.detect_from_article(
            session,
            article_id,
        )
    except NewsArticleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return to_event_response(event)


@router.get(
    "/{event_id}",
    response_model=MarketEventResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a persisted market event",
)
async def get_event(
    event_id: UUID,
    session: DatabaseSession,
) -> MarketEventResponse:
    """Return one persisted market event."""

    try:
        event = await _persistence_service.get(
            session,
            event_id,
        )
    except EventNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return to_event_response(event)
