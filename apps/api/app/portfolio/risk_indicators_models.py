from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.portfolio.models import Portfolio

RiskIndicatorKind = Literal[
    "valuation_data_quality",
    "single_instrument_currency_exposure",
    "single_asset_class_currency_exposure",
]

RiskIndicatorLevel = Literal[
    "attention",
    "information",
]


class PortfolioRiskIndicator(BaseModel):
    """One deterministic portfolio risk observation."""

    model_config = ConfigDict(frozen=True)

    kind: RiskIndicatorKind
    level: RiskIndicatorLevel
    currency: str | None
    title: str
    rationale: str
    position_count: int
    asset_class: str | None


class PortfolioRiskIndicators(BaseModel):
    """Quality-aware portfolio risk observations without a risk score."""

    model_config = ConfigDict(frozen=True)

    portfolio: Portfolio
    assessed_at: datetime
    maximum_quote_age_seconds: float
    quality: str
    indicators: tuple[PortfolioRiskIndicator, ...]
