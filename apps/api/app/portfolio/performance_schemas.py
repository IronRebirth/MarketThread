from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.portfolio.schemas import PortfolioResponse

PerformanceQuality = Literal[
    "sufficient",
    "insufficient",
    "unavailable",
    "empty",
]


class PortfolioPerformancePointResponse(BaseModel):
    """Historical portfolio value at one observed date."""

    model_config = ConfigDict(from_attributes=True)

    observed_on: date
    value: Decimal


class PortfolioCurrencyPerformanceResponse(BaseModel):
    """Historical performance for one currency bucket."""

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
    """API response for historical portfolio performance."""

    model_config = ConfigDict(from_attributes=True)

    portfolio: PortfolioResponse
    assessed_at: datetime
    lookback_start: datetime
    lookback_end: datetime
    lookback_days: int
    position_count: int
    quality: PerformanceQuality
    methodology: str
    currencies: tuple[PortfolioCurrencyPerformanceResponse, ...]
