from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.portfolio.models import Portfolio, PortfolioPosition

AllocationRangeQuality = Literal[
    "sufficient",
    "partial",
    "none",
    "empty",
]

AllocationRangeItemQuality = Literal[
    "current",
    "unavailable",
]


class PortfolioAllocationRangeItem(BaseModel):
    """Allocation range benchmark for one current portfolio position."""

    model_config = ConfigDict(frozen=True)

    position: PortfolioPosition
    currency: str = Field(min_length=3, max_length=3)
    position_count: int = Field(ge=1)
    quality: AllocationRangeItemQuality

    current_market_value: Decimal | None
    current_weight: Decimal | None

    minimum_weight: Decimal = Field(ge=0, le=1)
    target_weight: Decimal = Field(gt=0, le=1)
    maximum_weight: Decimal = Field(gt=0, le=1)

    minimum_market_value: Decimal | None
    target_market_value: Decimal | None
    maximum_market_value: Decimal | None

    within_range: bool | None
    notes: tuple[str, ...]


class PortfolioAllocationCurrencyRange(BaseModel):
    """Allocation range benchmark summary for one currency."""

    model_config = ConfigDict(frozen=True)

    currency: str = Field(min_length=3, max_length=3)
    position_count: int = Field(ge=1)
    quality: AllocationRangeItemQuality
    current_market_value: Decimal | None

    minimum_weight: Decimal = Field(ge=0, le=1)
    target_weight: Decimal = Field(gt=0, le=1)
    maximum_weight: Decimal = Field(gt=0, le=1)

    minimum_market_value: Decimal | None
    target_market_value: Decimal | None
    maximum_market_value: Decimal | None


class PortfolioAllocationRanges(BaseModel):
    """Quality-aware allocation ranges built from reference sizing."""

    model_config = ConfigDict(frozen=True)

    portfolio: Portfolio
    assessed_at: datetime
    maximum_quote_age_seconds: float
    range_tolerance: Decimal = Field(gt=0, le=1)
    quality: AllocationRangeQuality
    positions: tuple[PortfolioAllocationRangeItem, ...]
    currencies: tuple[PortfolioAllocationCurrencyRange, ...]
    methodology: str
    notes: tuple[str, ...]
