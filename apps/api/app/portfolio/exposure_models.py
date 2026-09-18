from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.portfolio.models import Portfolio, PortfolioPosition

ExposureQuality = Literal[
    "current",
    "stale",
    "unavailable",
    "empty",
]


class PortfolioCurrencyExposure(BaseModel):
    """Exposure totals for one currency without FX conversion."""

    model_config = ConfigDict(frozen=True)

    currency: str
    position_count: int
    quality: ExposureQuality
    cost_basis: Decimal
    market_value: Decimal | None


class PortfolioAssetClassExposure(BaseModel):
    """Exposure for one asset class within one currency."""

    model_config = ConfigDict(frozen=True)

    currency: str
    asset_class: str
    position_count: int
    quality: ExposureQuality
    cost_basis: Decimal
    market_value: Decimal | None
    market_value_weight: Decimal | None


class PortfolioPositionExposure(BaseModel):
    """Exposure and concentration for one persisted position."""

    model_config = ConfigDict(frozen=True)

    position: PortfolioPosition
    cost_basis: Decimal
    market_value: Decimal | None
    market_value_weight: Decimal | None
    quality: str


class PortfolioExposure(BaseModel):
    """Quality-aware portfolio exposure analysis."""

    model_config = ConfigDict(frozen=True)

    portfolio: Portfolio
    assessed_at: datetime
    maximum_quote_age_seconds: float
    quality: ExposureQuality
    currencies: tuple[PortfolioCurrencyExposure, ...]
    asset_classes: tuple[PortfolioAssetClassExposure, ...]
    positions: tuple[PortfolioPositionExposure, ...]
