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
from app.portfolio.persistence import PortfolioPersistenceService
from app.portfolio.risk_constraints import PortfolioRiskConstraintService
from app.portfolio.risk_constraints_schemas import (
    PortfolioRiskConstraintCurrencyResponse,
    PortfolioRiskConstraintResponse,
    PortfolioRiskConstraintsResponse,
)
from app.portfolio.schemas import PortfolioPositionResponse, PortfolioResponse

router = APIRouter(
    prefix="/portfolios",
    tags=["portfolio risk constraints"],
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
) -> PortfolioPositionResponse | None:
    """Convert a domain position into an API response."""

    if position is None:
        return None

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
) -> PortfolioRiskConstraintsResponse:
    """Convert domain risk constraints into an API response."""

    currencies = tuple(
        PortfolioRiskConstraintCurrencyResponse(
            currency=item.currency,
            position_count=item.position_count,
            quality=item.quality,
            current_market_value=item.current_market_value,
            constraint_count=item.constraint_count,
            violation_count=item.violation_count,
        )
        for item in analysis.currencies
    )

    constraints = tuple(
        PortfolioRiskConstraintResponse(
            constraint_id=item.constraint_id,
            kind=item.kind,
            scope=item.scope,
            currency=item.currency,
            subject=item.subject,
            position=_to_position_response(item.position),
            asset_class=item.asset_class,
            observed_weight=item.observed_weight,
            limit=item.limit,
            headroom=item.headroom,
            status=item.status,
            rationale=item.rationale,
        )
        for item in analysis.constraints
    )

    return PortfolioRiskConstraintsResponse(
        portfolio=_to_portfolio_response(analysis.portfolio),
        assessed_at=analysis.assessed_at,
        maximum_quote_age_seconds=analysis.maximum_quote_age_seconds,
        maximum_position_weight=analysis.maximum_position_weight,
        maximum_asset_class_weight=analysis.maximum_asset_class_weight,
        quality=analysis.quality,
        evaluated_constraint_count=analysis.evaluated_constraint_count,
        violation_count=analysis.violation_count,
        currencies=currencies,
        constraints=constraints,
        methodology=analysis.methodology,
        notes=analysis.notes,
    )


@router.get(
    "/{portfolio_id}/risk-constraints",
    response_model=PortfolioRiskConstraintsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_portfolio_risk_constraints(
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
    maximum_position_weight: Annotated[
        Decimal,
        Query(
            gt=0,
            le=1,
            description="Maximum allowed position weight within one currency.",
        ),
    ] = Decimal("0.35"),
    maximum_asset_class_weight: Annotated[
        Decimal,
        Query(
            gt=0,
            le=1,
            description=("Maximum allowed asset-class weight within one currency."),
        ),
    ] = Decimal("0.60"),
) -> PortfolioRiskConstraintsResponse:
    """Evaluate configured concentration constraints for a user-owned portfolio."""

    service = PortfolioRiskConstraintService(
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
            maximum_position_weight=maximum_position_weight,
            maximum_asset_class_weight=maximum_asset_class_weight,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None

    return _to_response(analysis)
