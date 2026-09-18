from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentUser
from app.db.models.instrument import Instrument
from app.db.session import get_db_session
from app.portfolio.application import (
    PortfolioApplicationService,
    PortfolioInstrumentNotFound,
    PortfolioNameConflict,
    PortfolioNotFound,
    PortfolioPositionNotFound,
)
from app.portfolio.persistence import PortfolioPersistenceService
from app.portfolio.schemas import (
    PortfolioCreateRequest,
    PortfolioDetailResponse,
    PortfolioPositionResponse,
    PortfolioPositionUpsertRequest,
    PortfolioResponse,
)

router = APIRouter(
    prefix="/portfolios",
    tags=["portfolios"],
)

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_portfolio_service(
    session: DatabaseSession,
) -> PortfolioApplicationService:
    """Create the portfolio application service for a request."""

    return PortfolioApplicationService(
        persistence=PortfolioPersistenceService(session),
    )


PortfolioServiceDependency = Annotated[
    PortfolioApplicationService,
    Depends(get_portfolio_service),
]


async def _build_position_response(
    position,
    session: AsyncSession,
) -> PortfolioPositionResponse:
    """Resolve canonical instrument metadata for a persisted position."""

    instrument = await session.get(
        Instrument,
        position.instrument_id,
    )

    if instrument is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Portfolio position references a missing instrument.",
        )

    return PortfolioPositionResponse(
        position_id=position.id,
        portfolio_id=position.portfolio_id,
        instrument_id=position.instrument_id,
        quantity=position.quantity,
        average_cost=position.average_cost,
        created_at=position.created_at,
        updated_at=position.updated_at,
        symbol=instrument.symbol,
        name=instrument.name,
        exchange=instrument.exchange,
        asset_class=instrument.asset_class,
        currency=instrument.currency,
        is_active=instrument.is_active,
    )


@router.post(
    "",
    response_model=PortfolioResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_portfolio(
    payload: PortfolioCreateRequest,
    current_user: CurrentUser,
    service: PortfolioServiceDependency,
) -> PortfolioResponse:
    """Create a portfolio for the authenticated user."""

    try:
        portfolio = await service.create(
            user_id=current_user.id,
            name=payload.name,
        )
    except PortfolioNameConflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A portfolio with this name already exists.",
        ) from None

    return PortfolioResponse(
        portfolio_id=portfolio.id,
        name=portfolio.name,
        created_at=portfolio.created_at,
        updated_at=portfolio.updated_at,
        position_count=0,
    )


@router.get(
    "",
    response_model=list[PortfolioResponse],
    status_code=status.HTTP_200_OK,
)
async def list_portfolios(
    current_user: CurrentUser,
    service: PortfolioServiceDependency,
) -> list[PortfolioResponse]:
    """List portfolios owned by the authenticated user."""

    rows = await service.list_for_user(current_user.id)

    return [
        PortfolioResponse(
            portfolio_id=portfolio.id,
            name=portfolio.name,
            created_at=portfolio.created_at,
            updated_at=portfolio.updated_at,
            position_count=position_count,
        )
        for portfolio, position_count in rows
    ]


@router.get(
    "/{portfolio_id}",
    response_model=PortfolioDetailResponse,
    status_code=status.HTTP_200_OK,
)
async def get_portfolio(
    portfolio_id: UUID,
    current_user: CurrentUser,
    service: PortfolioServiceDependency,
    session: DatabaseSession,
) -> PortfolioDetailResponse:
    """Return a portfolio and its current positions."""

    try:
        portfolio, position_count, positions = await service.get_detail_for_user(
            current_user.id,
            portfolio_id,
        )
    except PortfolioNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found.",
        ) from None

    position_response_list = [
        await _build_position_response(position, session) for position in positions
    ]
    position_responses = tuple(position_response_list)

    return PortfolioDetailResponse(
        portfolio_id=portfolio.id,
        name=portfolio.name,
        created_at=portfolio.created_at,
        updated_at=portfolio.updated_at,
        position_count=position_count,
        positions=position_responses,
    )


@router.put(
    "/{portfolio_id}/positions/{instrument_id}",
    response_model=PortfolioPositionResponse,
    status_code=status.HTTP_200_OK,
)
async def upsert_portfolio_position(
    portfolio_id: UUID,
    instrument_id: UUID,
    payload: PortfolioPositionUpsertRequest,
    current_user: CurrentUser,
    service: PortfolioServiceDependency,
    session: DatabaseSession,
) -> PortfolioPositionResponse:
    """Create or replace the current position for an instrument."""

    try:
        position, _created = await service.upsert_position(
            user_id=current_user.id,
            portfolio_id=portfolio_id,
            instrument_id=instrument_id,
            quantity=payload.quantity,
            average_cost=payload.average_cost,
        )
    except PortfolioNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found.",
        ) from None
    except PortfolioInstrumentNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active instrument not found.",
        ) from None

    return await _build_position_response(
        position,
        session,
    )


@router.delete(
    "/{portfolio_id}/positions/{position_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_portfolio_position(
    portfolio_id: UUID,
    position_id: UUID,
    current_user: CurrentUser,
    service: PortfolioServiceDependency,
) -> None:
    """Delete a current position from a portfolio."""

    try:
        await service.delete_position(
            user_id=current_user.id,
            portfolio_id=portfolio_id,
            position_id=position_id,
        )
    except PortfolioPositionNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio position not found.",
        ) from None


@router.delete(
    "/{portfolio_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_portfolio(
    portfolio_id: UUID,
    current_user: CurrentUser,
    service: PortfolioServiceDependency,
) -> None:
    """Delete a portfolio and its current positions."""

    try:
        await service.delete(
            user_id=current_user.id,
            portfolio_id=portfolio_id,
        )
    except PortfolioNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found.",
        ) from None
