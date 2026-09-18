from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentUser
from app.api.market_data import get_market_data_service
from app.db.session import get_db_session
from app.market_data.service import MarketDataService
from app.portfolio.persistence import PortfolioPersistenceService
from app.portfolio.risk_metrics import PortfolioRiskMetricsService
from app.portfolio.risk_metrics_schemas import (
    PortfolioCurrencyRiskMetricsResponse,
    PortfolioRiskMetricsResponse,
)
from app.portfolio.schemas import PortfolioResponse

router = APIRouter(
    prefix="/portfolios",
    tags=["portfolio-risk"],
)

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
MarketDataServiceDependency = Annotated[
    MarketDataService,
    Depends(get_market_data_service),
]


def _to_response(
    analysis,
) -> PortfolioRiskMetricsResponse:
    """Convert domain risk metrics into an API response."""

    portfolio = analysis.portfolio

    portfolio_response = PortfolioResponse(
        portfolio_id=portfolio.portfolio_id,
        name=portfolio.name,
        created_at=portfolio.created_at,
        updated_at=portfolio.updated_at,
        position_count=portfolio.position_count,
    )

    currencies = tuple(
        PortfolioCurrencyRiskMetricsResponse(
            currency=item.currency,
            position_count=item.position_count,
            quality=item.quality,
            first_observed_on=item.first_observed_on,
            last_observed_on=item.last_observed_on,
            observation_count=item.observation_count,
            return_count=item.return_count,
            annualized_volatility=item.annualized_volatility,
            maximum_drawdown=item.maximum_drawdown,
            drawdown_peak_on=item.drawdown_peak_on,
            drawdown_trough_on=item.drawdown_trough_on,
            sources=item.sources,
            notes=item.notes,
        )
        for item in analysis.currencies
    )

    return PortfolioRiskMetricsResponse(
        portfolio=portfolio_response,
        assessed_at=analysis.assessed_at,
        lookback_start=analysis.lookback_start,
        lookback_end=analysis.lookback_end,
        lookback_days=analysis.lookback_days,
        annualization_factor=analysis.annualization_factor,
        position_count=analysis.position_count,
        quality=analysis.quality,
        methodology=analysis.methodology,
        currencies=currencies,
    )


@router.get(
    "/{portfolio_id}/risk-metrics",
    response_model=PortfolioRiskMetricsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_portfolio_risk_metrics(
    portfolio_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    market_data: MarketDataServiceDependency,
    lookback_days: Annotated[
        int,
        Query(
            gt=0,
            le=3650,
            description="Historical lookback window in calendar days.",
        ),
    ] = 365,
) -> PortfolioRiskMetricsResponse:
    """Return historical volatility and drawdown for current portfolio holdings."""

    service = PortfolioRiskMetricsService(
        persistence=PortfolioPersistenceService(session),
        market_data=market_data,
    )

    try:
        analysis = await service.build(
            user_id=current_user.id,
            portfolio_id=portfolio_id,
            lookback_days=lookback_days,
        )
    except ValueError as exc:
        if str(exc) == "Portfolio not found.":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found.",
            ) from None

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from None

    return _to_response(analysis)
