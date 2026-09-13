from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import get_settings
from app.market_data.models import Instrument
from app.market_data.providers.errors import (
    MarketDataProviderError,
)
from app.market_data.providers.factory import create_market_data_provider
from app.market_data.service import MarketDataService

router = APIRouter(
    prefix="/market-data",
    tags=["market-data"],
)


def get_market_data_service() -> MarketDataService:
    """Create the market-data service for the current application."""

    settings = get_settings()

    try:
        provider = create_market_data_provider(settings)
    except MarketDataProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market-data provider is not configured.",
        ) from exc

    return MarketDataService(provider)


MarketDataServiceDependency = Annotated[
    MarketDataService,
    Depends(get_market_data_service),
]


@router.get(
    "/instruments/{symbol}",
    response_model=Instrument,
)
async def get_instrument(
    symbol: str,
    service: MarketDataServiceDependency,
) -> Instrument:
    """Return a normalized instrument by symbol."""

    instrument = await service.get_instrument(symbol)

    if instrument is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instrument not found.",
        )

    return instrument
