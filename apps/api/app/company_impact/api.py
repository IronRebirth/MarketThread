from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.company_impact import CompanyImpactRecord
from app.db.session import get_db_session
from app.events.persistence import EventNotFoundError

from .application import CompanyImpactApplicationService
from .models import CompanyImpactDirection, ImpactType
from .persistence import (
    CompanyImpactNotFoundError,
    CompanyImpactPersistenceService,
)
from .schemas import CompanyImpactResponse, to_company_impact_response

router = APIRouter(
    prefix="/company-impacts",
    tags=["company-impacts"],
)

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]

_persistence_service = CompanyImpactPersistenceService()
_application_service = CompanyImpactApplicationService()


@router.get(
    "",
    response_model=tuple[CompanyImpactResponse, ...],
    status_code=status.HTTP_200_OK,
    summary="List persisted company impacts",
)
async def list_company_impacts(
    session: DatabaseSession,
    event_id: UUID | None = None,
    company_name: str | None = None,
    ticker: str | None = None,
    impact_type: ImpactType | None = None,
    direction: CompanyImpactDirection | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> tuple[CompanyImpactResponse, ...]:
    try:
        impacts = await _persistence_service.list(
            session,
            event_id=event_id,
            company_name=company_name,
            ticker=ticker,
            impact_type=impact_type.value if impact_type else None,
            direction=direction.value if direction else None,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    responses: list[CompanyImpactResponse] = []

    for impact in impacts:
        impact_id = await _find_impact_id(
            session,
            impact,
        )
        responses.append(
            to_company_impact_response(
                impact,
                impact_id,
            ),
        )

    return tuple(responses)


@router.post(
    "/from-event/{event_id}",
    response_model=tuple[CompanyImpactResponse, ...],
    status_code=status.HTTP_201_CREATED,
    summary="Analyze and persist company impacts from a market event",
)
async def analyze_company_impacts_from_event(
    event_id: UUID,
    session: DatabaseSession,
) -> tuple[CompanyImpactResponse, ...]:
    try:
        impacts = await _application_service.analyze_from_event(
            session,
            event_id,
        )
    except EventNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    responses: list[CompanyImpactResponse] = []

    for impact in impacts:
        impact_id = await _find_impact_id(
            session,
            impact,
        )
        responses.append(
            to_company_impact_response(
                impact,
                impact_id,
            ),
        )

    return tuple(responses)


@router.get(
    "/{impact_id}",
    response_model=CompanyImpactResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a persisted company impact",
)
async def get_company_impact(
    impact_id: UUID,
    session: DatabaseSession,
) -> CompanyImpactResponse:
    try:
        impact = await _persistence_service.get(
            session,
            impact_id,
        )
    except CompanyImpactNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return to_company_impact_response(
        impact,
        impact_id,
    )


async def _find_impact_id(
    session: DatabaseSession,
    impact,
) -> UUID:
    impact_id = await session.scalar(
        select(CompanyImpactRecord.id).where(
            CompanyImpactRecord.event_id == impact.event_id,
            CompanyImpactRecord.company_name == impact.company_name,
            CompanyImpactRecord.impact_type == impact.impact_type.value,
        ),
    )

    if impact_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Persisted company impact could not be resolved.",
        )

    return impact_id
