from datetime import timedelta
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentUser
from app.api.market_data import get_market_data_service
from app.db.session import get_db_session
from app.market_data.service import MarketDataService
from app.portfolio.allocation_explanations import (
    PortfolioAllocationExplanationService,
)
from app.portfolio.allocation_explanations_schemas import (
    PortfolioAllocationExplanationCurrencyResponse,
    PortfolioAllocationExplanationItemResponse,
    PortfolioAllocationExplanationsResponse,
)
from app.portfolio.persistence import PortfolioPersistenceService
from app.portfolio.schemas import PortfolioPositionResponse, PortfolioResponse

router = APIRouter(
    prefix="/portfolios",
    tags=["portfolio allocation explanations"],
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
) -> PortfolioAllocationExplanationsResponse:
    """Convert allocation explanations into an API response."""

    items = tuple(
        PortfolioAllocationExplanationItemResponse(
            position=_to_position_response(item.position),
            currency=item.currency,
            position_count=item.position_count,
            quality=item.quality,
            status=item.status,
            current_market_value=item.current_market_value,
            current_weight=item.current_weight,
            minimum_weight=item.minimum_weight,
            target_weight=item.target_weight,
            maximum_weight=item.maximum_weight,
            constraint_violation_count=item.constraint_violation_count,
            violated_constraints=item.violated_constraints,
            explanation=item.explanation,
            notes=item.notes,
        )
        for item in analysis.items
    )

    currencies = tuple(
        PortfolioAllocationExplanationCurrencyResponse(
            currency=item.currency,
            position_count=item.position_count,
            quality=item.quality,
            explanation_count=item.explanation_count,
            outside_range_count=item.outside_range_count,
            violation_count=item.violation_count,
            explanation=item.explanation,
        )
        for item in analysis.currencies
    )

    return PortfolioAllocationExplanationsResponse(
        portfolio=_to_portfolio_response(analysis.portfolio),
        assessed_at=analysis.assessed_at,
        maximum_quote_age_seconds=analysis.maximum_quote_age_seconds,
        range_tolerance=analysis.range_tolerance,
        maximum_position_weight=analysis.maximum_position_weight,
        maximum_asset_class_weight=analysis.maximum_asset_class_weight,
        quality=analysis.quality,
        explanation_count=analysis.explanation_count,
        outside_range_count=analysis.outside_range_count,
        violation_count=analysis.violation_count,
        currencies=currencies,
        items=items,
        methodology=analysis.methodology,
        notes=analysis.notes,
    )


@router.get(
    "/{portfolio_id}/allocation-explanations",
    response_model=PortfolioAllocationExplanationsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_portfolio_allocation_explanations(
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
    range_tolerance: Annotated[
        Decimal,
        Query(
            gt=0,
            le=1,
            description="Relative tolerance around the reference allocation.",
        ),
    ] = Decimal("0.25"),
    maximum_position_weight: Annotated[
        Decimal,
        Query(
            gt=0,
            le=1,
            description="Maximum allowed position weight within a currency.",
        ),
    ] = Decimal("0.35"),
    maximum_asset_class_weight: Annotated[
        Decimal,
        Query(
            gt=0,
            le=1,
            description=("Maximum allowed asset-class weight within a currency."),
        ),
    ] = Decimal("0.60"),
) -> PortfolioAllocationExplanationsResponse:
    """Explain current allocation state for a user-owned portfolio."""

    service = PortfolioAllocationExplanationService(
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
            range_tolerance=range_tolerance,
            maximum_position_weight=maximum_position_weight,
            maximum_asset_class_weight=maximum_asset_class_weight,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found.",
        ) from None

    return _to_response(analysis)
