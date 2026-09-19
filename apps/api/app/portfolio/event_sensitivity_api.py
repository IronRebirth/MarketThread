from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentUser
from app.db.session import get_db_session
from app.portfolio.persistence import PortfolioPersistenceService

from .event_sensitivity import PortfolioEventSensitivityService
from .event_sensitivity_schemas import (
    PortfolioEventSensitivityItemResponse,
    PortfolioEventSensitivityResponse,
)
from .schemas import PortfolioPositionResponse, PortfolioResponse

router = APIRouter(
    prefix="/portfolios",
    tags=["portfolios"],
)

DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_db_session),
]


def _to_response(
    analysis,
) -> PortfolioEventSensitivityResponse:
    """Convert domain event sensitivity into an API response."""

    portfolio_response = PortfolioResponse(
        portfolio_id=analysis.portfolio.portfolio_id,
        name=analysis.portfolio.name,
        created_at=analysis.portfolio.created_at,
        updated_at=analysis.portfolio.updated_at,
        position_count=analysis.portfolio.position_count,
    )

    items = tuple(
        PortfolioEventSensitivityItemResponse(
            position=PortfolioPositionResponse(
                position_id=item.position.position_id,
                portfolio_id=item.position.portfolio_id,
                instrument_id=item.position.instrument_id,
                quantity=item.position.quantity,
                average_cost=item.position.average_cost,
                created_at=item.position.created_at,
                updated_at=item.position.updated_at,
                symbol=item.position.symbol,
                name=item.position.name,
                exchange=item.position.exchange,
                asset_class=item.position.asset_class,
                currency=item.position.currency,
                is_active=item.position.is_active,
            ),
            market_impact_id=item.market_impact_id,
            company_impact_id=item.company_impact_id,
            event_id=item.event_id,
            company_name=item.company_name,
            ticker=item.ticker,
            impact_type=item.impact_type,
            direction=item.direction,
            factor=item.factor,
            time_horizon=item.time_horizon,
            confidence=item.confidence,
            event_type=item.event_type,
            title=item.title,
            summary=item.summary,
            catalyst=item.catalyst,
            market_relevance=item.market_relevance,
            event_impact_direction=item.event_impact_direction,
            affected_entities=item.affected_entities,
            affected_sectors=item.affected_sectors,
            first_seen_at=item.first_seen_at,
            last_seen_at=item.last_seen_at,
            event_confidence=item.event_confidence,
            source_article_ids=item.source_article_ids,
            rationale=item.rationale,
        )
        for item in analysis.items
    )

    return PortfolioEventSensitivityResponse(
        portfolio=portfolio_response,
        assessed_at=analysis.assessed_at,
        position_count=analysis.position_count,
        matched_position_count=analysis.matched_position_count,
        unmatched_position_count=analysis.unmatched_position_count,
        event_count=analysis.event_count,
        impact_count=analysis.impact_count,
        returned_impact_count=analysis.returned_impact_count,
        quality=analysis.quality,
        unmatched_symbols=analysis.unmatched_symbols,
        methodology=analysis.methodology,
        notes=analysis.notes,
        items=items,
    )


@router.get(
    "/{portfolio_id}/event-sensitivity",
    response_model=PortfolioEventSensitivityResponse,
    status_code=status.HTTP_200_OK,
)
async def get_portfolio_event_sensitivity(
    portfolio_id: UUID,
    current_user: CurrentUser,
    session: DatabaseSession,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Maximum number of matching impact records to return.",
        ),
    ] = 100,
) -> PortfolioEventSensitivityResponse:
    """Return persisted event sensitivity for the authenticated user's portfolio."""

    service = PortfolioEventSensitivityService(
        persistence=PortfolioPersistenceService(session),
    )

    try:
        analysis = await service.build(
            user_id=current_user.id,
            portfolio_id=portfolio_id,
            limit=limit,
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
