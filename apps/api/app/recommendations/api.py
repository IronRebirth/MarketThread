from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.market_impact.persistence import MarketImpactNotFoundError
from app.signals.persistence import SignalNotFoundError

from .application import (
    RecommendationApplicationService,
    RecommendationDataConsistencyError,
    RecommendationMarketImpactRequiredError,
)
from .models import RecommendationState
from .persistence import (
    RecommendationNotFoundError,
    RecommendationPersistenceService,
)

router = APIRouter(
    prefix="/recommendations",
    tags=["recommendations"],
)

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]

_persistence_service = RecommendationPersistenceService()
_application_service = RecommendationApplicationService()


class RecommendationResponse(BaseModel):
    """Persisted recommendation response."""

    model_config = ConfigDict(from_attributes=True)

    recommendation_id: UUID
    signal_id: UUID
    created_at: datetime
    event_id: UUID
    company_name: str
    ticker: str | None
    state: str
    signal_direction: str
    confidence_score: float
    risk_score: float
    confidence_level: str
    risk_level: str
    time_horizon: str
    supporting_factors: tuple[str, ...]
    contradicting_factors: tuple[str, ...]
    assumptions: tuple[str, ...]
    invalidation_conditions: tuple[str, ...]
    evidence_article_ids: tuple[UUID, ...]
    rationale: str


@router.post(
    "/from-signal/{signal_id}",
    response_model=RecommendationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate and persist a recommendation from a signal",
)
async def create_recommendation_from_signal(
    signal_id: UUID,
    session: DatabaseSession,
) -> RecommendationResponse:
    try:
        record = await _application_service.generate_from_signal(
            session,
            signal_id,
        )
    except SignalNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except MarketImpactNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except RecommendationMarketImpactRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except RecommendationDataConsistencyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return _to_response(record)


@router.get(
    "",
    response_model=tuple[RecommendationResponse, ...],
    status_code=status.HTTP_200_OK,
    summary="List persisted recommendations",
)
async def list_recommendations(
    session: DatabaseSession,
    signal_id: UUID | None = None,
    company_name: str | None = None,
    ticker: str | None = None,
    state: RecommendationState | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=100),
) -> tuple[RecommendationResponse, ...]:
    try:
        records = await _persistence_service.list(
            session,
            signal_id=signal_id,
            company_name=company_name,
            ticker=ticker,
            state=state.value if state is not None else None,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return tuple(_to_response(record) for record in records)


@router.get(
    "/{recommendation_id}",
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a persisted recommendation",
)
async def get_recommendation(
    recommendation_id: UUID,
    session: DatabaseSession,
) -> RecommendationResponse:
    try:
        record = await _persistence_service.get(
            session,
            recommendation_id,
        )
    except RecommendationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return _to_response(record)


def _to_response(record) -> RecommendationResponse:
    return RecommendationResponse(
        recommendation_id=record.id,
        signal_id=record.signal_id,
        created_at=record.created_at,
        event_id=record.event_id,
        company_name=record.company_name,
        ticker=record.ticker,
        state=record.state,
        signal_direction=record.signal_direction,
        confidence_score=record.confidence_score,
        risk_score=record.risk_score,
        confidence_level=record.confidence_level,
        risk_level=record.risk_level,
        time_horizon=record.time_horizon,
        supporting_factors=tuple(record.supporting_factors),
        contradicting_factors=tuple(record.contradicting_factors),
        assumptions=tuple(record.assumptions),
        invalidation_conditions=tuple(record.invalidation_conditions),
        evidence_article_ids=tuple(
            UUID(article_id) for article_id in record.evidence_article_ids
        ),
        rationale=record.rationale,
    )
