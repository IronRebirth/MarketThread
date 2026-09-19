from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.portfolio.models import Portfolio, PortfolioPosition

ReferencePositionSizingQuality = Literal[
    "sufficient",
    "partial",
    "none",
    "empty",
]

ReferenceCurrencySizingQuality = Literal[
    "current",
    "unavailable",
]


class PortfolioReferencePositionSizingItem(BaseModel):
    """Reference sizing for one current portfolio position."""

    model_config = ConfigDict(frozen=True)

    position: PortfolioPosition
    currency: str = Field(min_length=3, max_length=3)
    position_count: int = Field(ge=1)
    quality: ReferenceCurrencySizingQuality

    current_market_value: Decimal | None
    current_weight: Decimal | None

    reference_weight: Decimal = Field(gt=0, le=1)
    reference_market_value: Decimal | None
    reference_quantity: Decimal | None
    quantity_delta: Decimal | None

    quote_price: Decimal | None
    notes: tuple[str, ...]


class PortfolioReferenceCurrencySizing(BaseModel):
    """Reference sizing totals for one portfolio currency."""

    model_config = ConfigDict(frozen=True)

    currency: str = Field(min_length=3, max_length=3)
    position_count: int = Field(ge=1)
    quality: ReferenceCurrencySizingQuality
    current_market_value: Decimal | None
    reference_weight: Decimal
    reference_market_value: Decimal | None


class PortfolioReferencePositionSizing(BaseModel):
    """Quality-aware equal-reference position sizing for a portfolio."""

    model_config = ConfigDict(frozen=True)

    portfolio: Portfolio
    assessed_at: datetime
    maximum_quote_age_seconds: float
    quality: ReferencePositionSizingQuality
    positions: tuple[PortfolioReferencePositionSizingItem, ...]
    currencies: tuple[PortfolioReferenceCurrencySizing, ...]
    methodology: str
    notes: tuple[str, ...]
