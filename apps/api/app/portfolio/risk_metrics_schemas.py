from datetime import date, datetime

from pydantic import BaseModel

from app.portfolio.schemas import PortfolioResponse


class PortfolioCurrencyRiskMetricsResponse(BaseModel):
    """API representation of historical risk metrics for one currency."""

    currency: str
    position_count: int
    quality: str
    first_observed_on: date | None
    last_observed_on: date | None
    observation_count: int
    return_count: int
    annualized_volatility: float | None
    maximum_drawdown: float | None
    drawdown_peak_on: date | None
    drawdown_trough_on: date | None
    sources: tuple[str, ...]
    notes: tuple[str, ...]


class PortfolioRiskMetricsResponse(BaseModel):
    """API representation of portfolio volatility and drawdown analysis."""

    portfolio: PortfolioResponse
    assessed_at: datetime
    lookback_start: datetime
    lookback_end: datetime
    lookback_days: int
    annualization_factor: int
    position_count: int
    quality: str
    methodology: str
    currencies: tuple[PortfolioCurrencyRiskMetricsResponse, ...]
