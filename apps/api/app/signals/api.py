from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.market_impact.persistence import MarketImpactNotFoundError

from .application import (
    SignalApplicationService,
    SignalInstrumentNotFoundError,
    SignalInstrumentResolutionError,
)
from .models import MarketSignal
from .persistence import SignalNotFoundError, SignalPersistenceService

router = APIRouter(
    prefix="/signals",
    tags=["signals"],
)

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]

_persistence_service = SignalPersistenceService()
_application_service = SignalApplicationService()


class SignalCreateRequest(MarketSignal):
    """Market signal plus the historical context required for persistence."""

    instrument_id: UUID
    created_at: datetime


class SignalResponse(BaseModel):
    """Persisted market signal response."""

    model_config = ConfigDict(from_attributes=True)

    signal_id: UUID
    market_impact_id: UUID | None
    instrument_id: UUID
    created_at: datetime
    event_id: UUID
    company_name: str
    ticker: str | None
    direction: str
    strength: str
    opportunity: str
    confidence: float
    risk_score: float
    time_horizon: str
    supporting_factors: tuple[str, ...]
    contradicting_factors: tuple[str, ...]
    evidence_article_ids: tuple[UUID, ...]
    invalidation_conditions: tuple[str, ...]
    rationale: str


@router.post(
    "",
    response_model=SignalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Persist a market signal",
)
async def create_signal(
    request: SignalCreateRequest,
    session: DatabaseSession,
) -> SignalResponse:
    record = await _persistence_service.create(
        session,
        signal=request,
        instrument_id=request.instrument_id,
        created_at=request.created_at,
    )

    return _to_response(record)


@router.post(
    "/from-market-impact/{market_impact_id}",
    response_model=SignalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate and persist a signal from a market impact",
)
async def create_signal_from_market_impact(
    market_impact_id: UUID,
    session: DatabaseSession,
) -> SignalResponse:
    try:
        record = await _application_service.generate_from_market_impact(
            session,
            market_impact_id,
        )
    except MarketImpactNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except SignalInstrumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except SignalInstrumentResolutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return _to_response(record)


@router.get(
    "",
    response_model=tuple[SignalResponse, ...],
    status_code=status.HTTP_200_OK,
    summary="List persisted market signals",
)
async def list_signals(
    session: DatabaseSession,
    instrument_id: UUID | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> tuple[SignalResponse, ...]:
    records = await _persistence_service.list(
        session,
        instrument_id=instrument_id,
        start_at=start_at,
        end_at=end_at,
        limit=limit,
    )

    return tuple(_to_response(record) for record in records)


@router.get(
    "/{signal_id}",
    response_model=SignalResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a persisted market signal",
)
async def get_signal(
    signal_id: UUID,
    session: DatabaseSession,
) -> SignalResponse:
    try:
        record = await _persistence_service.get(
            session,
            signal_id,
        )
    except SignalNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return _to_response(record)


def _to_response(record) -> SignalResponse:
    return SignalResponse(
        signal_id=record.id,
        market_impact_id=record.market_impact_id,
        instrument_id=record.instrument_id,
        created_at=record.created_at,
        event_id=record.event_id,
        company_name=record.company_name,
        ticker=record.ticker,
        direction=record.direction,
        strength=record.strength,
        opportunity=record.opportunity,
        confidence=record.confidence,
        risk_score=record.risk_score,
        time_horizon=record.time_horizon,
        supporting_factors=tuple(record.supporting_factors),
        contradicting_factors=tuple(record.contradicting_factors),
        evidence_article_ids=tuple(
            UUID(article_id) for article_id in record.evidence_article_ids
        ),
        invalidation_conditions=tuple(record.invalidation_conditions),
        rationale=record.rationale,
    )
