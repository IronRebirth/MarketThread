from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.market_data.models import Quote, QuoteFreshness


class Portfolio(BaseModel):
    """Normalized user-owned investment portfolio."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    name: str = Field(min_length=1, max_length=100)
    created_at: datetime
    updated_at: datetime
    position_count: int = Field(ge=0)


class PortfolioPosition(BaseModel):
    """Current position held inside a user-owned portfolio."""

    model_config = ConfigDict(frozen=True)

    position_id: UUID
    portfolio_id: UUID
    instrument_id: UUID
    quantity: Decimal = Field(gt=0)
    average_cost: Decimal = Field(ge=0)
    created_at: datetime
    updated_at: datetime

    symbol: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    exchange: str = Field(min_length=1, max_length=64)
    asset_class: str = Field(min_length=1, max_length=32)
    currency: str = Field(min_length=3, max_length=3)
    is_active: bool


class PortfolioDetail(Portfolio):
    """Portfolio with its persisted current positions."""

    positions: tuple[PortfolioPosition, ...] = ()


class PortfolioPositionValuation(BaseModel):
    """Quality-aware derived valuation for a single portfolio position."""

    model_config = ConfigDict(frozen=True)

    position: PortfolioPosition
    cost_basis: Decimal
    quote: Quote | None
    quote_quality: QuoteFreshness
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_pnl_percent: Decimal | None


class PortfolioCurrencyValuation(BaseModel):
    """Portfolio totals for one currency."""

    model_config = ConfigDict(frozen=True)

    currency: str = Field(min_length=3, max_length=3)
    position_count: int = Field(ge=1)
    quality: Literal["current", "stale", "unavailable"]
    cost_basis: Decimal
    market_value: Decimal | None
    unrealized_pnl: Decimal | None


class PortfolioValuation(BaseModel):
    """Complete quality-aware valuation of a portfolio."""

    model_config = ConfigDict(frozen=True)

    portfolio: Portfolio
    assessed_at: datetime
    maximum_quote_age_seconds: float
    quality: Literal["current", "stale", "unavailable", "empty"]
    positions: tuple[PortfolioPositionValuation, ...]
    currencies: tuple[PortfolioCurrencyValuation, ...]
