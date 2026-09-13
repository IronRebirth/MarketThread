from app.core.config import Settings
from app.market_data.providers.base import MarketDataProvider
from app.market_data.providers.errors import MarketDataProviderError
from app.market_data.providers.http import HttpMarketDataProvider


def create_market_data_provider(
    settings: Settings,
) -> MarketDataProvider:
    """Create the configured market-data provider."""

    if not settings.market_data_base_url:
        raise MarketDataProviderError(
            "MARKET_DATA_BASE_URL is not configured.",
        )

    return HttpMarketDataProvider(
        base_url=settings.market_data_base_url,
        api_key=settings.market_data_api_key,
    )
