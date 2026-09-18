from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.portfolio.models import Portfolio

PerformanceQuality = Literal[
    "sufficient",
    "insufficient",
    "unavailable",
    "empty",
]


class PortfolioPerformancePoint(BaseModel):
    """One historical portfolio value observation."""

    model_config = ConfigDict(frozen=True)

    observed_on: date
    value: Decimal


class PortfolioCurrencyPerformance(BaseModel):
    """Historical performance for one portfolio currency."""

    model_config = ConfigDict(frozen=True)

    currency: str
    position_count: int = Field(ge=1)
    quality: PerformanceQuality
    first_observed_on: date | None
    last_observed_on: date | None
    observation_count: int = Field(ge=0)
    return_count: int = Field(ge=0)
    initial_value: Decimal | None = Field(
        default=None,
        ge=0,
    )
    latest_value: Decimal | None = Field(
        default=None,
        ge=0,
    )
    period_return: Decimal | None
    points: tuple[PortfolioPerformancePoint, ...] = ()
    sources: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class PortfolioPerformance(BaseModel):
    """Quality-aware historical portfolio performance."""

    model_config = ConfigDict(frozen=True)

    portfolio: Portfolio
    assessed_at: datetime
    lookback_start: datetime
    lookback_end: datetime
    lookback_days: int = Field(gt=0)
    position_count: int = Field(ge=0)
    quality: PerformanceQuality
    methodology: str = Field(min_length=1)
    currencies: tuple[PortfolioCurrencyPerformance, ...]
