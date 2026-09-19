from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.portfolio.performance_models import PerformanceQuality
from app.portfolio.schemas import PortfolioResponse


class PortfolioPerformancePointResponse(BaseModel):
    """API representation of one historical portfolio value observation."""

    model_config = ConfigDict(frozen=True)

    observed_on: date
    value: Decimal


class PortfolioCurrencyPerformanceResponse(BaseModel):
    """API representation of historical performance for one currency."""

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
    external_cash_flow_adjusted_period_return: Decimal | None
    external_cash_flow_count: int = Field(ge=0)
    external_net_cash_flow: Decimal = Decimal("0")
    points: tuple[PortfolioPerformancePointResponse, ...] = ()
    sources: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class PortfolioPerformanceResponse(BaseModel):
    """API representation of quality-aware historical performance."""

    model_config = ConfigDict(frozen=True)

    portfolio: PortfolioResponse
    assessed_at: datetime
    lookback_start: datetime
    lookback_end: datetime
    lookback_days: int = Field(gt=0)
    position_count: int = Field(ge=0)
    quality: PerformanceQuality
    methodology: str = Field(min_length=1)
    currencies: tuple[PortfolioCurrencyPerformanceResponse, ...]
