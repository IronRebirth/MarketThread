from datetime import datetime
from decimal import Decimal
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
