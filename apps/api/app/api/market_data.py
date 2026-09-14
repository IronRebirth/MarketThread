from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.market_data.ingestion import MarketDataIngestionService
from app.market_data.models import (
    Instrument,
    MarketDataIngestionRequest,
    MarketDataIngestionResult,
)
from app.market_data.persistence import MarketDataPersistenceService
from app.market_data.providers.errors import MarketDataProviderError
from app.market_data.providers.factory import create_market_data_provider
from app.market_data.repository import MarketDataRepository
from app.market_data.service import MarketDataService

router = APIRouter(
    prefix="/market-data",
    tags=["market-data"],
)


def get_market_data_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MarketDataService:
    """Create the database-first market-data service."""

    settings = get_settings()
    repository = MarketDataRepository(session)

    provider = None

    try:
        provider = create_market_data_provider(settings)
    except MarketDataProviderError:
        provider = None

    return MarketDataService(
        provider=provider,
        repository=repository,
    )


def get_market_data_ingestion_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MarketDataIngestionService:
    """Create the market-data ingestion service."""

    settings = get_settings()

    try:
        provider = create_market_data_provider(settings)
    except MarketDataProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market-data provider is not configured.",
        ) from exc

    persistence = MarketDataPersistenceService(session)

    return MarketDataIngestionService(
        provider=provider,
        persistence=persistence,
    )


MarketDataServiceDependency = Annotated[
    MarketDataService,
    Depends(get_market_data_service),
]

MarketDataIngestionServiceDependency = Annotated[
    MarketDataIngestionService,
    Depends(get_market_data_ingestion_service),
]


@router.get(
    "/instruments/{symbol}",
    response_model=Instrument,
)
async def get_instrument(
    symbol: str,
    service: MarketDataServiceDependency,
) -> Instrument:
    """Return an instrument using database-first retrieval."""

    try:
        instrument = await service.get_instrument(symbol)
    except MarketDataProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market-data is unavailable.",
        ) from exc

    if instrument is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instrument not found.",
        )

    return instrument


@router.post(
    "/ingest/{symbol}",
    response_model=MarketDataIngestionResult,
    status_code=status.HTTP_200_OK,
)
async def ingest_market_data(
    symbol: str,
    request: MarketDataIngestionRequest,
    service: MarketDataIngestionServiceDependency,
) -> MarketDataIngestionResult:
    """Fetch and persist normalized market data for an instrument."""

    try:
        result = await service.ingest(
            symbol=symbol,
            start=request.start,
            end=request.end,
            include_quote=request.include_quote,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except MarketDataProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market-data provider request failed.",
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instrument not found.",
        )

    return result
