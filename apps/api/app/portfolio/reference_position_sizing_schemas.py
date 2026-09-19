from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.portfolio.reference_position_sizing_models import (
    ReferenceCurrencySizingQuality,
    ReferencePositionSizingQuality,
)
from app.portfolio.schemas import PortfolioPositionResponse, PortfolioResponse


class PortfolioReferencePositionSizingItemResponse(BaseModel):
    """API representation of one reference-sized portfolio position."""

    model_config = ConfigDict(frozen=True)

    position: PortfolioPositionResponse
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


class PortfolioReferenceCurrencySizingResponse(BaseModel):
    """API representation of reference sizing for one currency."""

    model_config = ConfigDict(frozen=True)

    currency: str = Field(min_length=3, max_length=3)
    position_count: int = Field(ge=1)
    quality: ReferenceCurrencySizingQuality
    current_market_value: Decimal | None
    reference_weight: Decimal
    reference_market_value: Decimal | None


class PortfolioReferencePositionSizingResponse(BaseModel):
    """API representation of portfolio reference position sizing."""

    model_config = ConfigDict(frozen=True)

    portfolio: PortfolioResponse
    assessed_at: datetime
    maximum_quote_age_seconds: float
    quality: ReferencePositionSizingQuality
    positions: tuple[PortfolioReferencePositionSizingItemResponse, ...]
    currencies: tuple[PortfolioReferenceCurrencySizingResponse, ...]
    methodology: str = Field(min_length=1)
    notes: tuple[str, ...]
