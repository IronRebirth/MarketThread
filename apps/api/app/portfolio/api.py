from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentUser
from app.api.market_data import get_market_data_service
from app.db.models.instrument import Instrument
from app.db.session import get_db_session
from app.market_data.service import MarketDataService
from app.portfolio.application import (
    PortfolioApplicationService,
    PortfolioInstrumentNotFound,
    PortfolioNameConflict,
    PortfolioNotFound,
    PortfolioPositionNotFound,
)
from app.portfolio.exposure import PortfolioExposureService
from app.portfolio.exposure_schemas import (
    PortfolioAssetClassExposureResponse,
    PortfolioCurrencyExposureResponse,
    PortfolioExposureResponse,
    PortfolioPositionExposureResponse,
)
from app.portfolio.persistence import PortfolioPersistenceService
from app.portfolio.risk_indicators import PortfolioRiskIndicatorService
from app.portfolio.risk_indicators_schemas import (
    PortfolioRiskIndicatorResponse,
    PortfolioRiskIndicatorsResponse,
)
from app.portfolio.schemas import (
    PortfolioCreateRequest,
    PortfolioCurrencyValuationResponse,
    PortfolioDetailResponse,
    PortfolioPositionResponse,
    PortfolioPositionUpsertRequest,
    PortfolioPositionValuationResponse,
    PortfolioQuoteQualityResponse,
    PortfolioQuoteResponse,
    PortfolioResponse,
    PortfolioValuationResponse,
)
from app.portfolio.valuation import PortfolioValuationService

router = APIRouter(
    prefix="/portfolios",
    tags=["portfolios"],
)

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
MarketDataServiceDependency = Annotated[
    MarketDataService,
    Depends(get_market_data_service),
]


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


def _to_portfolio_response(
    portfolio,
    position_count: int,
) -> PortfolioResponse:
    """Convert a persisted portfolio to an API response."""

    return PortfolioResponse(
        portfolio_id=portfolio.id,
        name=portfolio.name,
        created_at=portfolio.created_at,
        updated_at=portfolio.updated_at,
        position_count=position_count,
    )


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


def _to_position_valuation_response(
    valuation,
) -> PortfolioPositionValuationResponse:
    """Convert a domain position valuation to an API response."""

    position = valuation.position

    position_response = PortfolioPositionResponse(
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

    quote_response = (
        PortfolioQuoteResponse(
            instrument_id=valuation.quote.instrument_id,
            timestamp=valuation.quote.timestamp,
            price=valuation.quote.price,
            bid=valuation.quote.bid,
            ask=valuation.quote.ask,
            volume=valuation.quote.volume,
            source=valuation.quote.source,
        )
        if valuation.quote is not None
        else None
    )

    quote_quality = PortfolioQuoteQualityResponse(
        status=valuation.quote_quality.status,
        observed_at=valuation.quote_quality.observed_at,
        assessed_at=valuation.quote_quality.assessed_at,
        age_seconds=valuation.quote_quality.age_seconds,
        maximum_age_seconds=valuation.quote_quality.maximum_age_seconds,
        source=valuation.quote_quality.source,
    )

    return PortfolioPositionValuationResponse(
        position=position_response,
        cost_basis=valuation.cost_basis,
        quote=quote_response,
        quote_quality=quote_quality,
        market_value=valuation.market_value,
        unrealized_pnl=valuation.unrealized_pnl,
        unrealized_pnl_percent=valuation.unrealized_pnl_percent,
    )


def _to_valuation_response(
    valuation,
) -> PortfolioValuationResponse:
    """Convert a domain portfolio valuation to an API response."""

    portfolio_response = PortfolioResponse(
        portfolio_id=valuation.portfolio.portfolio_id,
        name=valuation.portfolio.name,
        created_at=valuation.portfolio.created_at,
        updated_at=valuation.portfolio.updated_at,
        position_count=valuation.portfolio.position_count,
    )

    positions = tuple(
        _to_position_valuation_response(position) for position in valuation.positions
    )

    currencies = tuple(
        PortfolioCurrencyValuationResponse(
            currency=currency.currency,
            position_count=currency.position_count,
            quality=currency.quality,
            cost_basis=currency.cost_basis,
            market_value=currency.market_value,
            unrealized_pnl=currency.unrealized_pnl,
        )
        for currency in valuation.currencies
    )

    return PortfolioValuationResponse(
        portfolio=portfolio_response,
        assessed_at=valuation.assessed_at,
        maximum_quote_age_seconds=valuation.maximum_quote_age_seconds,
        quality=valuation.quality,
        positions=positions,
        currencies=currencies,
    )


def _to_exposure_response(
    exposure,
) -> PortfolioExposureResponse:
    """Convert portfolio exposure domain data into an API response."""

    portfolio_response = PortfolioResponse(
        portfolio_id=exposure.portfolio.portfolio_id,
        name=exposure.portfolio.name,
        created_at=exposure.portfolio.created_at,
        updated_at=exposure.portfolio.updated_at,
        position_count=exposure.portfolio.position_count,
    )

    positions = tuple(
        PortfolioPositionExposureResponse(
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
            cost_basis=item.cost_basis,
            market_value=item.market_value,
            market_value_weight=item.market_value_weight,
            quality=item.quality,
        )
        for item in exposure.positions
    )

    currencies = tuple(
        PortfolioCurrencyExposureResponse(
            currency=item.currency,
            position_count=item.position_count,
            quality=item.quality,
            cost_basis=item.cost_basis,
            market_value=item.market_value,
        )
        for item in exposure.currencies
    )

    asset_classes = tuple(
        PortfolioAssetClassExposureResponse(
            currency=item.currency,
            asset_class=item.asset_class,
            position_count=item.position_count,
            quality=item.quality,
            cost_basis=item.cost_basis,
            market_value=item.market_value,
            market_value_weight=item.market_value_weight,
        )
        for item in exposure.asset_classes
    )

    return PortfolioExposureResponse(
        portfolio=portfolio_response,
        assessed_at=exposure.assessed_at,
        maximum_quote_age_seconds=exposure.maximum_quote_age_seconds,
        quality=exposure.quality,
        currencies=currencies,
        asset_classes=asset_classes,
        positions=positions,
    )


def _to_risk_indicators_response(
    analysis,
) -> PortfolioRiskIndicatorsResponse:
    """Convert risk observations into an API response."""

    portfolio_response = PortfolioResponse(
        portfolio_id=analysis.portfolio.portfolio_id,
        name=analysis.portfolio.name,
        created_at=analysis.portfolio.created_at,
        updated_at=analysis.portfolio.updated_at,
        position_count=analysis.portfolio.position_count,
    )

    indicators = tuple(
        PortfolioRiskIndicatorResponse(
            kind=indicator.kind,
            level=indicator.level,
            currency=indicator.currency,
            title=indicator.title,
            rationale=indicator.rationale,
            position_count=indicator.position_count,
            asset_class=indicator.asset_class,
        )
        for indicator in analysis.indicators
    )

    return PortfolioRiskIndicatorsResponse(
        portfolio=portfolio_response,
        assessed_at=analysis.assessed_at,
        maximum_quote_age_seconds=analysis.maximum_quote_age_seconds,
        quality=analysis.quality,
        indicators=indicators,
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

    return _to_portfolio_response(
        portfolio,
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
        _to_portfolio_response(
            portfolio,
            position_count,
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


@router.get(
    "/{portfolio_id}/valuation",
    response_model=PortfolioValuationResponse,
    status_code=status.HTTP_200_OK,
)
async def get_portfolio_valuation(
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
) -> PortfolioValuationResponse:
    """Return a quality-aware valuation from persisted positions and quotes."""

    valuation_service = PortfolioValuationService(
        persistence=PortfolioPersistenceService(session),
        market_data=market_data,
    )

    try:
        valuation = await valuation_service.build(
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

    return _to_valuation_response(valuation)


@router.get(
    "/{portfolio_id}/exposure",
    response_model=PortfolioExposureResponse,
    status_code=status.HTTP_200_OK,
)
async def get_portfolio_exposure(
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
) -> PortfolioExposureResponse:
    """Return quality-aware portfolio exposure and concentration metrics."""

    exposure_service = PortfolioExposureService(
        persistence=PortfolioPersistenceService(session),
        market_data=market_data,
    )

    try:
        exposure = await exposure_service.build(
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

    return _to_exposure_response(exposure)


@router.get(
    "/{portfolio_id}/risk-indicators",
    response_model=PortfolioRiskIndicatorsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_portfolio_risk_indicators(
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
) -> PortfolioRiskIndicatorsResponse:
    """Return deterministic portfolio risk observations."""

    service = PortfolioRiskIndicatorService(
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

    return _to_risk_indicators_response(analysis)


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
