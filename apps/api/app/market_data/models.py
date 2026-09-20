from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Instrument(BaseModel):
    """Normalized representation of a tradeable market instrument."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    symbol: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    exchange: str = Field(min_length=1, max_length=64)
    asset_class: str = Field(min_length=1, max_length=32)
    currency: str = Field(min_length=3, max_length=3)
    is_active: bool = True


class Quote(BaseModel):
    """Normalized latest quote for a market instrument."""

    model_config = ConfigDict(frozen=True)

    instrument_id: UUID
    timestamp: datetime
    price: Decimal
    bid: Decimal | None = None
    ask: Decimal | None = None
    volume: Decimal | None = None
    source: str = Field(min_length=1, max_length=64)


class Bar(BaseModel):
    """Normalized OHLCV market-data bar."""

    model_config = ConfigDict(frozen=True)

    instrument_id: UUID
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None = None
    source: str = Field(min_length=1, max_length=64)


class Fundamentals(BaseModel):
    """Normalized fundamental metrics for one reporting period."""

    model_config = ConfigDict(frozen=True)

    instrument_id: UUID
    period_end: date
    revenue_growth: Decimal | None = None
    earnings_growth: Decimal | None = None
    gross_margin: Decimal | None = None
    operating_margin: Decimal | None = None
    net_margin: Decimal | None = None
    roe: Decimal | None = None
    roic: Decimal | None = None
    debt_to_equity: Decimal | None = None
    debt_to_ebitda: Decimal | None = None
    operating_cash_flow: Decimal | None = None
    free_cash_flow: Decimal | None = None
    pe_ratio: Decimal | None = None
    ps_ratio: Decimal | None = None
    ev_to_ebitda: Decimal | None = None
    dividend_yield: Decimal | None = None
    source: str = Field(min_length=1, max_length=64)


class QuoteFreshness(BaseModel):
    """Freshness assessment for the latest available quote."""

    model_config = ConfigDict(frozen=True)

    status: Literal["fresh", "stale", "unavailable"]
    observed_at: datetime | None
    assessed_at: datetime
    age_seconds: float | None
    maximum_age_seconds: float
    source: str | None = None


class HistoricalDataCompleteness(BaseModel):
    """Coverage assessment for a requested historical market-data range."""

    model_config = ConfigDict(frozen=True)

    status: Literal["sufficient", "insufficient", "unavailable"]
    start: datetime
    end: datetime
    expected_interval_seconds: float
    minimum_coverage: float
    expected_bars: int
    observed_bars: int
    missing_bars: int
    coverage_ratio: float
    first_observed_at: datetime | None
    last_observed_at: datetime | None
    sources: tuple[str, ...] = ()


class MarketDataProviderHealth(BaseModel):
    """Operational health status for a market-data provider."""

    model_config = ConfigDict(frozen=True)

    provider: str = Field(min_length=1, max_length=64)
    status: Literal["healthy", "degraded", "unavailable"]
    checked_at: datetime
    latency_ms: float | None
    detail: str | None = None


class MarketDataIngestionRequest(BaseModel):
    """Request to ingest market data for an instrument."""

    start: datetime
    end: datetime
    include_quote: bool = True


class MarketDataIngestionResult(BaseModel):
    """Summary of a completed market-data ingestion operation."""

    instrument_id: UUID
    symbol: str
    exchange: str
    bars_received: int
    bars_persisted: int
    quote_received: bool
    quote_persisted: bool


class FundamentalsIngestionResult(BaseModel):
    """Summary of a completed fundamental-data ingestion operation."""

    instrument_id: UUID
    symbol: str
    exchange: str
    period_end: date
    source: str
    persisted: bool
