from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.portfolio.allocation_ranges_models import (
    AllocationRangeItemQuality,
    AllocationRangeQuality,
)
from app.portfolio.schemas import (
    PortfolioPositionResponse,
    PortfolioResponse,
)


class PortfolioAllocationRangeItemResponse(BaseModel):
    """API representation of one portfolio allocation range."""

    model_config = ConfigDict(frozen=True)

    position: PortfolioPositionResponse
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


class PortfolioAllocationCurrencyRangeResponse(BaseModel):
    """API representation of allocation ranges for one currency."""

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


class PortfolioAllocationRangesResponse(BaseModel):
    """API representation of portfolio allocation ranges."""

    model_config = ConfigDict(frozen=True)

    portfolio: PortfolioResponse
    assessed_at: datetime
    maximum_quote_age_seconds: float
    range_tolerance: Decimal = Field(gt=0, le=1)
    quality: AllocationRangeQuality
    positions: tuple[PortfolioAllocationRangeItemResponse, ...]
    currencies: tuple[PortfolioAllocationCurrencyRangeResponse, ...]
    methodology: str = Field(min_length=1)
    notes: tuple[str, ...]
