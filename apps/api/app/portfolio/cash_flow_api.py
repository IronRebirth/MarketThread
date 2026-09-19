from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentUser
from app.db.session import get_db_session
from app.portfolio.application import PortfolioNotFound
from app.portfolio.cash_flow_application import (
    PortfolioCashFlowApplicationService,
    PortfolioCashFlowQueryError,
)
from app.portfolio.cash_flow_persistence import (
    PortfolioCashFlowPersistenceService,
)
from app.portfolio.cash_flow_schemas import (
    PortfolioCashFlowCreateRequest,
    PortfolioCashFlowResponse,
)

DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_db_session),
]

router = APIRouter(
    tags=["portfolio cash flows"],
)


def get_portfolio_cash_flow_service(
    session: DatabaseSession,
) -> PortfolioCashFlowApplicationService:
    """Create the cash-flow application service for a request."""

    return PortfolioCashFlowApplicationService(
        persistence=PortfolioCashFlowPersistenceService(session),
    )


PortfolioCashFlowServiceDependency = Annotated[
    PortfolioCashFlowApplicationService,
    Depends(get_portfolio_cash_flow_service),
]


def _to_cash_flow_response(
    event,
) -> PortfolioCashFlowResponse:
    """Convert a persisted cash-flow record to an API response."""

    return PortfolioCashFlowResponse(
        sequence_id=event.sequence_id,
        cash_flow_id=event.id,
        portfolio_id=event.portfolio_id,
        currency=event.currency,
        amount=event.amount,
        event_type=event.event_type,
        effective_at=event.effective_at,
        recorded_at=event.recorded_at,
    )


@router.post(
    "/{portfolio_id}/cash-flows",
    response_model=PortfolioCashFlowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_portfolio_cash_flow(
    portfolio_id: UUID,
    payload: PortfolioCashFlowCreateRequest,
    current_user: CurrentUser,
    service: PortfolioCashFlowServiceDependency,
) -> PortfolioCashFlowResponse:
    """Append an external deposit or withdrawal to a portfolio."""

    try:
        event = await service.create(
            user_id=current_user.id,
            portfolio_id=portfolio_id,
            currency=payload.currency,
            amount=payload.amount,
            event_type=payload.event_type,
            effective_at=payload.effective_at,
        )
    except PortfolioNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found.",
        ) from None

    return _to_cash_flow_response(event)


@router.get(
    "/{portfolio_id}/cash-flows",
    response_model=list[PortfolioCashFlowResponse],
    status_code=status.HTTP_200_OK,
)
async def list_portfolio_cash_flows(
    portfolio_id: UUID,
    current_user: CurrentUser,
    service: PortfolioCashFlowServiceDependency,
    start_at: Annotated[
        datetime | None,
        Query(
            description="Inclusive start of the effective-time window.",
        ),
    ] = None,
    end_at: Annotated[
        datetime | None,
        Query(
            description="Inclusive end of the effective-time window.",
        ),
    ] = None,
    limit: Annotated[
        int,
        Query(
            gt=0,
            le=500,
            description="Maximum number of cash-flow events to return.",
        ),
    ] = 200,
) -> list[PortfolioCashFlowResponse]:
    """Return chronological external cash-flow history."""

    try:
        events = await service.list_for_user(
            user_id=current_user.id,
            portfolio_id=portfolio_id,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
        )
    except PortfolioNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found.",
        ) from None
    except PortfolioCashFlowQueryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from None

    return [_to_cash_flow_response(event) for event in events]
