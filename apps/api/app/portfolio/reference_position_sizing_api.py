from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentUser
from app.api.market_data import get_market_data_service
from app.db.session import get_db_session
from app.market_data.service import MarketDataService
from app.portfolio.persistence import PortfolioPersistenceService
from app.portfolio.reference_position_sizing import (
    PortfolioReferencePositionSizingService,
)
from app.portfolio.reference_position_sizing_schemas import (
    PortfolioPositionResponse,
    PortfolioReferenceCurrencySizingResponse,
    PortfolioReferencePositionSizingItemResponse,
    PortfolioReferencePositionSizingResponse,
    PortfolioResponse,
)

router = APIRouter(
    prefix="/portfolios",
    tags=["portfolio reference position sizing"],
)

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
MarketDataServiceDependency = Annotated[
    MarketDataService,
    Depends(get_market_data_service),
]


def _to_portfolio_response(
    portfolio,
) -> PortfolioResponse:
    """Convert a domain portfolio into an API response."""

    return PortfolioResponse(
        portfolio_id=portfolio.portfolio_id,
        name=portfolio.name,
        created_at=portfolio.created_at,
        updated_at=portfolio.updated_at,
        position_count=portfolio.position_count,
    )


def _to_position_response(
    position,
) -> PortfolioPositionResponse:
    """Convert a domain position into an API response."""

    return PortfolioPositionResponse(
        position_id=position.position_id,
        portfolio_id=position.portfolio_id,
        instrument_id=position.instrument_id,
        quantity=position.quantity,
        average_cost=position.average_cost,
        created_at=position.created_at,
        updated_at=position.updated_at,
        symbol=position.symbol,
        name=position.name,
        exchange=position.exchange,
        asset_class=position.asset_class,
        currency=position.currency,
        is_active=position.is_active,
    )


def _to_response(
    analysis,
) -> PortfolioReferencePositionSizingResponse:
    """Convert domain reference sizing into an API response."""

    positions = tuple(
        PortfolioReferencePositionSizingItemResponse(
            position=_to_position_response(item.position),
            currency=item.currency,
            position_count=item.position_count,
            quality=item.quality,
            current_market_value=item.current_market_value,
            current_weight=item.current_weight,
            reference_weight=item.reference_weight,
            reference_market_value=item.reference_market_value,
            reference_quantity=item.reference_quantity,
            quantity_delta=item.quantity_delta,
            quote_price=item.quote_price,
            notes=item.notes,
        )
        for item in analysis.positions
    )

    currencies = tuple(
        PortfolioReferenceCurrencySizingResponse(
            currency=item.currency,
            position_count=item.position_count,
            quality=item.quality,
            current_market_value=item.current_market_value,
            reference_weight=item.reference_weight,
            reference_market_value=item.reference_market_value,
        )
        for item in analysis.currencies
    )

    return PortfolioReferencePositionSizingResponse(
        portfolio=_to_portfolio_response(analysis.portfolio),
        assessed_at=analysis.assessed_at,
        maximum_quote_age_seconds=analysis.maximum_quote_age_seconds,
        quality=analysis.quality,
        positions=positions,
        currencies=currencies,
        methodology=analysis.methodology,
        notes=analysis.notes,
    )


@router.get(
    "/{portfolio_id}/reference-position-sizing",
    response_model=PortfolioReferencePositionSizingResponse,
    status_code=status.HTTP_200_OK,
)
async def get_reference_position_sizing(
    portfolio_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    market_data: MarketDataServiceDependency,
    maximum_age_seconds: Annotated[
        int,
        Query(
            gt=0,
            le=86400,
            description="Maximum accepted quote age in seconds.",
        ),
    ] = 900,
) -> PortfolioReferencePositionSizingResponse:
    """Return an equal-reference sizing baseline for a user-owned portfolio."""

    service = PortfolioReferencePositionSizingService(
        persistence=PortfolioPersistenceService(session),
        market_data=market_data,
    )

    try:
        analysis = await service.build(
            user_id=current_user.id,
            portfolio_id=portfolio_id,
            maximum_quote_age=timedelta(
                seconds=maximum_age_seconds,
            ),
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found.",
        ) from None

    return _to_response(analysis)
