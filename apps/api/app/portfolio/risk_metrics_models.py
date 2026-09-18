from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.portfolio.models import Portfolio

RiskMetricsQuality = Literal[
    "sufficient",
    "insufficient",
    "unavailable",
    "empty",
]


class PortfolioCurrencyRiskMetrics(BaseModel):
    """Historical volatility and drawdown metrics for one currency bucket."""

    model_config = ConfigDict(frozen=True)

    currency: str
    position_count: int = Field(ge=1)
    quality: RiskMetricsQuality
    first_observed_on: date | None
    last_observed_on: date | None
    observation_count: int = Field(ge=0)
    return_count: int = Field(ge=0)
    annualized_volatility: float | None = Field(
        default=None,
        ge=0.0,
    )
    maximum_drawdown: float | None = Field(
        default=None,
        le=0.0,
    )
    drawdown_peak_on: date | None
    drawdown_trough_on: date | None
    sources: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class PortfolioRiskMetrics(BaseModel):
    """Quality-aware historical volatility and drawdown analysis."""

    model_config = ConfigDict(frozen=True)

    portfolio: Portfolio
    assessed_at: datetime
    lookback_start: datetime
    lookback_end: datetime
    lookback_days: int = Field(gt=0)
    annualization_factor: int = Field(gt=0)
    position_count: int = Field(ge=0)
    quality: RiskMetricsQuality
    methodology: str = Field(min_length=1)
    currencies: tuple[PortfolioCurrencyRiskMetrics, ...]
