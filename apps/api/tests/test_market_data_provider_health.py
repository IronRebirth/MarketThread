import pytest

from app.market_data.models import MarketDataProviderHealth
from app.market_data.providers.errors import MarketDataProviderError
from app.market_data.service import MarketDataService


class HealthyProvider:
    name = "test-provider"

    async def health_check(self) -> MarketDataProviderHealth:
        return MarketDataProviderHealth(
            provider=self.name,
            status="healthy",
            checked_at="2026-01-01T00:00:00Z",
            latency_ms=12.5,
            detail="Provider health check succeeded.",
        )


class UnavailableProvider:
    name = "test-provider"

    async def health_check(self) -> MarketDataProviderHealth:
        return MarketDataProviderHealth(
            provider=self.name,
            status="unavailable",
            checked_at="2026-01-01T00:00:00Z",
            latency_ms=2000.0,
            detail="Provider health check request failed.",
        )


@pytest.mark.asyncio
async def test_service_returns_provider_health() -> None:
    service = MarketDataService(
        provider=HealthyProvider(),
    )

    result = await service.check_provider_health()

    assert result.status == "healthy"
    assert result.provider == "test-provider"
    assert result.latency_ms == 12.5


@pytest.mark.asyncio
async def test_service_returns_unavailable_provider_health() -> None:
    service = MarketDataService(
        provider=UnavailableProvider(),
    )

    result = await service.check_provider_health()

    assert result.status == "unavailable"


@pytest.mark.asyncio
async def test_service_rejects_health_check_without_provider() -> None:
    service = MarketDataService()

    with pytest.raises(
        MarketDataProviderError,
        match="No persisted market data is available",
    ):
        await service.check_provider_health()
