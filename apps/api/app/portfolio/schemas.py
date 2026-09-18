from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.portfolio.models import (
    PortfolioPosition,
)


class PortfolioCreateRequest(BaseModel):
    """Request to create a new portfolio."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Reject names that contain only whitespace."""

        normalized = value.strip()

        if not normalized:
            raise ValueError("Portfolio name must not be blank.")

        return normalized


class PortfolioResponse(BaseModel):
    """API representation of a persisted portfolio."""

    model_config = ConfigDict(from_attributes=True)

    portfolio_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    position_count: int


class PortfolioPositionUpsertRequest(BaseModel):
    """Request to replace the current position for an instrument."""

    model_config = ConfigDict(extra="forbid")

    quantity: Decimal = Field(gt=0)
    average_cost: Decimal = Field(ge=0)


class PortfolioPositionResponse(PortfolioPosition):
    """API representation of a persisted portfolio position."""

    model_config = ConfigDict(from_attributes=True)


class PortfolioDetailResponse(BaseModel):
    """API representation of a portfolio and its positions."""

    portfolio_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    position_count: int
    positions: tuple[PortfolioPositionResponse, ...]


class PortfolioQuoteResponse(BaseModel):
    """API representation of the quote used for valuation."""

    model_config = ConfigDict(from_attributes=True)

    instrument_id: UUID
    timestamp: datetime
    price: Decimal
    bid: Decimal | None
    ask: Decimal | None
    volume: Decimal | None
    source: str


class PortfolioQuoteQualityResponse(BaseModel):
    """API representation of quote freshness."""

    status: str
    observed_at: datetime | None
    assessed_at: datetime
    age_seconds: float | None
    maximum_age_seconds: float
    source: str | None


class PortfolioPositionValuationResponse(BaseModel):
    """API representation of a quality-aware position valuation."""

    model_config = ConfigDict(from_attributes=True)

    position: PortfolioPositionResponse
    cost_basis: Decimal
    quote: PortfolioQuoteResponse | None
    quote_quality: PortfolioQuoteQualityResponse
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_pnl_percent: Decimal | None


class PortfolioCurrencyValuationResponse(BaseModel):
    """API representation of one currency's portfolio valuation."""

    currency: str
    position_count: int
    quality: str
    cost_basis: Decimal
    market_value: Decimal | None
    unrealized_pnl: Decimal | None


class PortfolioValuationResponse(BaseModel):
    """API representation of a complete portfolio valuation."""

    portfolio: PortfolioResponse
    assessed_at: datetime
    maximum_quote_age_seconds: float
    quality: str
    positions: tuple[PortfolioPositionValuationResponse, ...]
    currencies: tuple[PortfolioCurrencyValuationResponse, ...]
