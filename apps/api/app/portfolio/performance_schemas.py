from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.portfolio.models import Portfolio

PerformanceQuality = Literal[
    "sufficient",
    "insufficient",
    "unavailable",
    "empty",
]


class PortfolioPerformancePointResponse(BaseModel):
    """API representation of one historical value observation."""

    model_config = ConfigDict(from_attributes=True)

    observed_on: date
    value: Decimal


class PortfolioCurrencyPerformanceResponse(BaseModel):
    """API representation of one currency performance series."""

    model_config = ConfigDict(from_attributes=True)

    currency: str
    position_count: int
    quality: PerformanceQuality
    first_observed_on: date | None
    last_observed_on: date | None
    observation_count: int
    return_count: int
    initial_value: Decimal | None
    latest_value: Decimal | None
    period_return: Decimal | None
    points: tuple[PortfolioPerformancePointResponse, ...]
    sources: tuple[str, ...]
    notes: tuple[str, ...]


class PortfolioPerformanceResponse(BaseModel):
    """API representation of historical portfolio performance."""

    model_config = ConfigDict(from_attributes=True)

    portfolio: Portfolio
    assessed_at: datetime
    lookback_start: datetime
    lookback_end: datetime
    lookback_days: int
    position_count: int
    quality: PerformanceQuality
    methodology: str
    currencies: tuple[PortfolioCurrencyPerformanceResponse, ...]
