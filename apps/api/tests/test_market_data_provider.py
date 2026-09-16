from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest

from app.market_data.providers.errors import (
    MarketDataInvalidResponseError,
    MarketDataUnavailableError,
)
from app.market_data.providers.http import HttpMarketDataProvider

INSTRUMENT_ID = uuid4()


@pytest.mark.asyncio
async def test_provider_health_check_reports_healthy(monkeypatch) -> None:
    provider = HttpMarketDataProvider(
        base_url="https://provider.example",
        api_key="test-key",
    )

    class HealthyResponse:
        status_code = 200

    class HealthyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            return HealthyResponse()

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: HealthyClient(),
    )

    result = await provider.health_check()

    assert result.provider == "http"
    assert result.status == "healthy"
    assert result.latency_ms is not None
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_provider_health_check_reports_degraded_for_client_error(
    monkeypatch,
) -> None:
    provider = HttpMarketDataProvider(
        base_url="https://provider.example",
    )

    class DegradedResponse:
        status_code = 429

    class DegradedClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            return DegradedResponse()

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: DegradedClient(),
    )

    result = await provider.health_check()

    assert result.status == "degraded"
    assert result.latency_ms is not None


@pytest.mark.asyncio
async def test_provider_health_check_reports_unavailable_for_server_error(
    monkeypatch,
) -> None:
    provider = HttpMarketDataProvider(
        base_url="https://provider.example",
    )

    class UnavailableResponse:
        status_code = 503

    class UnavailableClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            return UnavailableResponse()

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: UnavailableClient(),
    )

    result = await provider.health_check()

    assert result.status == "unavailable"
    assert result.latency_ms is not None


@pytest.mark.asyncio
async def test_provider_health_check_translates_connection_failure(
    monkeypatch,
) -> None:
    provider = HttpMarketDataProvider(
        base_url="https://provider.example",
    )

    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            raise httpx.ConnectError("connection failed")

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: FailingClient(),
    )

    result = await provider.health_check()

    assert result.status == "unavailable"
    assert result.latency_ms is not None


@pytest.mark.asyncio
async def test_provider_returns_normalized_instrument(
    monkeypatch,
) -> None:
    provider = HttpMarketDataProvider(
        base_url="https://provider.example",
        api_key="test-key",
    )

    async def fake_get(*args, **kwargs):
        return {
            "id": str(INSTRUMENT_ID),
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "exchange": "NASDAQ",
            "asset_class": "equity",
            "currency": "USD",
            "is_active": True,
        }

    monkeypatch.setattr(provider, "_get", fake_get)

    instrument = await provider.get_instrument("AAPL")

    assert instrument is not None
    assert instrument.symbol == "AAPL"


@pytest.mark.asyncio
async def test_provider_returns_normalized_quote(
    monkeypatch,
) -> None:
    provider = HttpMarketDataProvider(
        base_url="https://provider.example",
        api_key="test-key",
    )

    async def fake_get(*args, **kwargs):
        return {
            "instrument_id": str(INSTRUMENT_ID),
            "timestamp": datetime.now(UTC).isoformat(),
            "price": "200.12",
            "bid": "200.10",
            "ask": "200.14",
            "volume": "1000",
            "source": "test-provider",
        }

    monkeypatch.setattr(provider, "_get", fake_get)

    quote = await provider.get_quote(INSTRUMENT_ID)

    assert quote is not None
    assert quote.price == Decimal("200.12")
    assert quote.bid == Decimal("200.10")
    assert quote.ask == Decimal("200.14")
    assert quote.volume == Decimal("1000")
    assert quote.source == "test-provider"


@pytest.mark.asyncio
async def test_provider_returns_normalized_bars(
    monkeypatch,
) -> None:
    provider = HttpMarketDataProvider(
        base_url="https://provider.example",
        api_key="test-key",
    )

    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 2, tzinfo=UTC)

    async def fake_get(*args, **kwargs):
        return {
            "data": [
                {
                    "instrument_id": str(INSTRUMENT_ID),
                    "timestamp": start.isoformat(),
                    "open": "198.00",
                    "high": "201.00",
                    "low": "197.50",
                    "close": "200.00",
                    "volume": "5000",
                    "source": "test-provider",
                },
            ],
        }

    monkeypatch.setattr(provider, "_get", fake_get)

    bars = await provider.get_bars(
        INSTRUMENT_ID,
        start,
        end,
    )

    assert isinstance(bars, Sequence)
    assert len(bars) == 1
    assert bars[0].open == Decimal("198.00")
    assert bars[0].high == Decimal("201.00")
    assert bars[0].low == Decimal("197.50")
    assert bars[0].close == Decimal("200.00")
    assert bars[0].volume == Decimal("5000")


@pytest.mark.asyncio
async def test_provider_rejects_invalid_instrument(
    monkeypatch,
) -> None:
    provider = HttpMarketDataProvider(
        base_url="https://provider.example",
    )

    async def fake_get(*args, **kwargs):
        return {"symbol": "AAPL"}

    monkeypatch.setattr(provider, "_get", fake_get)

    with pytest.raises(MarketDataInvalidResponseError):
        await provider.get_instrument("AAPL")


@pytest.mark.asyncio
async def test_provider_translates_connection_failures(
    monkeypatch,
) -> None:
    provider = HttpMarketDataProvider(
        base_url="https://provider.example",
    )

    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            raise httpx.ConnectError("connection failed")

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: FailingClient(),
    )

    with pytest.raises(MarketDataUnavailableError):
        await provider._get("/v1/instruments")
