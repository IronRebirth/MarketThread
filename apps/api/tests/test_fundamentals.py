from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.market_data import get_market_data_service
from app.main import app
from app.market_data.models import (
    Bar,
    Fundamentals,
    Instrument,
    MarketDataProviderHealth,
    Quote,
)
from app.market_data.service import MarketDataService


class FundamentalsProvider:
    name = "fundamentals-test"

    def __init__(self) -> None:
        self.instrument = Instrument(
            id=uuid4(),
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
            asset_class="equity",
            currency="USD",
        )

    async def health_check(self) -> MarketDataProviderHealth:
        return MarketDataProviderHealth(
            provider=self.name,
            status="healthy",
            checked_at=datetime.now(UTC),
            latency_ms=1,
        )

    async def get_instrument(self, symbol: str) -> Instrument | None:
        return self.instrument if symbol == "AAPL" else None

    async def get_quote(self, instrument_id: UUID) -> Quote | None:
        return None

    async def get_bars(
        self,
        instrument_id: UUID,
        start: datetime,
        end: datetime,
    ) -> list[Bar]:
        return []

    async def get_fundamentals(
        self,
        instrument_id: UUID,
    ) -> Fundamentals | None:
        if instrument_id != self.instrument.id:
            return None

        return Fundamentals(
            instrument_id=instrument_id,
            period_end=date(2026, 6, 30),
            revenue_growth=Decimal("0.08"),
            earnings_growth=Decimal("0.12"),
            gross_margin=Decimal("0.47"),
            operating_margin=Decimal("0.30"),
            net_margin=Decimal("0.25"),
            roe=Decimal("1.45"),
            roic=Decimal("0.48"),
            debt_to_equity=Decimal("1.20"),
            debt_to_ebitda=Decimal("1.10"),
            operating_cash_flow=Decimal("100000000"),
            free_cash_flow=Decimal("90000000"),
            pe_ratio=Decimal("28.5"),
            ps_ratio=Decimal("7.1"),
            ev_to_ebitda=Decimal("22.4"),
            dividend_yield=Decimal("0.004"),
            source=self.name,
        )


async def test_provider_fundamentals_are_retrievable() -> None:
    provider = FundamentalsProvider()
    service = MarketDataService(provider)

    result = await service.get_fundamentals(provider.instrument.id)

    assert result is not None
    assert result.period_end == date(2026, 6, 30)
    assert result.revenue_growth == Decimal("0.08")
    assert result.pe_ratio == Decimal("28.5")


def test_api_get_fundamentals_uses_market_data_service() -> None:
    provider = FundamentalsProvider()
    service = MarketDataService(provider)

    app.dependency_overrides[get_market_data_service] = lambda: service

    try:
        with TestClient(app) as client:
            response = client.get("/market-data/instruments/AAPL/fundamentals")
    finally:
        app.dependency_overrides.pop(get_market_data_service, None)

    assert response.status_code == 200
    payload = response.json()

    assert payload["instrument_id"] == str(provider.instrument.id)
    assert payload["period_end"] == "2026-06-30"
    assert Decimal(str(payload["revenue_growth"])) == Decimal("0.08")
    assert Decimal(str(payload["pe_ratio"])) == Decimal("28.5")
    assert payload["source"] == "fundamentals-test"


def test_api_get_fundamentals_returns_not_found() -> None:
    provider = FundamentalsProvider()
    service = MarketDataService(provider)

    app.dependency_overrides[get_market_data_service] = lambda: service

    try:
        with TestClient(app) as client:
            response = client.get("/market-data/instruments/MSFT/fundamentals")
    finally:
        app.dependency_overrides.pop(get_market_data_service, None)

    assert response.status_code == 404
    assert response.json()["detail"] == "Instrument not found."
