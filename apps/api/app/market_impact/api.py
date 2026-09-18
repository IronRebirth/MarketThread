from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.market_impact import MarketImpactRecord
from app.db.session import get_db_session
from app.events.persistence import EventNotFoundError

from .application import MarketImpactApplicationService
from .models import (
    CompanyImpactDirection,
    ImpactFactor,
    ImpactType,
    TimeHorizon,
)
from .persistence import (
    MarketImpactNotFoundError,
    MarketImpactPersistenceService,
)
from .schemas import MarketImpactResponse, to_market_impact_response

router = APIRouter(
    prefix="/market-impacts",
    tags=["market-impacts"],
)

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]

_persistence_service = MarketImpactPersistenceService()
_application_service = MarketImpactApplicationService()


@router.get(
    "",
    response_model=tuple[MarketImpactResponse, ...],
    status_code=status.HTTP_200_OK,
    summary="List persisted market impacts",
)
async def list_market_impacts(
    session: DatabaseSession,
    event_id: UUID | None = None,
    company_name: str | None = None,
    impact_type: ImpactType | None = None,
    direction: CompanyImpactDirection | None = None,
    factor: ImpactFactor | None = None,
    time_horizon: TimeHorizon | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> tuple[MarketImpactResponse, ...]:
    try:
        impacts = await _persistence_service.list(
            session,
            event_id=event_id,
            company_name=company_name,
            impact_type=impact_type.value if impact_type else None,
            direction=direction.value if direction else None,
            factor=factor.value if factor else None,
            time_horizon=time_horizon.value if time_horizon else None,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    responses: list[MarketImpactResponse] = []

    for impact_id, impact in impacts:
        responses.append(
            to_market_impact_response(
                impact,
                impact_id,
                await _find_company_impact_id(
                    session,
                    impact_id,
                ),
            ),
        )

    return tuple(responses)


@router.post(
    "/from-event/{event_id}",
    response_model=tuple[MarketImpactResponse, ...],
    status_code=status.HTTP_201_CREATED,
    summary="Analyze and persist market impacts from an event",
)
async def analyze_market_impacts_from_event(
    event_id: UUID,
    session: DatabaseSession,
) -> tuple[MarketImpactResponse, ...]:
    try:
        results = await _application_service.analyze_from_event(
            session,
            event_id,
        )
    except EventNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    responses: list[MarketImpactResponse] = []

    for company_impact_id, impact in results:
        impact_id = await _find_market_impact_id(
            session,
            company_impact_id,
        )

        responses.append(
            to_market_impact_response(
                impact,
                impact_id,
                company_impact_id,
            ),
        )

    return tuple(responses)


@router.get(
    "/{impact_id}",
    response_model=MarketImpactResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a persisted market impact",
)
async def get_market_impact(
    impact_id: UUID,
    session: DatabaseSession,
) -> MarketImpactResponse:
    try:
        impact = await _persistence_service.get(
            session,
            impact_id,
        )
    except MarketImpactNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    company_impact_id = await _find_company_impact_id(
        session,
        impact_id,
    )

    return to_market_impact_response(
        impact,
        impact_id,
        company_impact_id,
    )


async def _find_company_impact_id(
    session: DatabaseSession,
    impact_id: UUID,
) -> UUID:
    company_impact_id = await session.scalar(
        select(MarketImpactRecord.company_impact_id).where(
            MarketImpactRecord.id == impact_id,
        ),
    )

    if company_impact_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Persisted company impact reference could not be resolved.",
        )

    return company_impact_id


async def _find_market_impact_id(
    session: DatabaseSession,
    company_impact_id: UUID,
) -> UUID:
    impact_id = await session.scalar(
        select(MarketImpactRecord.id).where(
            MarketImpactRecord.company_impact_id == company_impact_id,
        ),
    )

    if impact_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Persisted market impact could not be resolved.",
        )

    return impact_id
