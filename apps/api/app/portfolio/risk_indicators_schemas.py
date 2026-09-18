from datetime import datetime

from pydantic import BaseModel

from app.portfolio.schemas import PortfolioResponse


class PortfolioRiskIndicatorResponse(BaseModel):
    """API representation of one portfolio risk observation."""

    kind: str
    level: str
    currency: str | None
    title: str
    rationale: str
    position_count: int
    asset_class: str | None


class PortfolioRiskIndicatorsResponse(BaseModel):
    """API representation of portfolio risk observations."""

    portfolio: PortfolioResponse
    assessed_at: datetime
    maximum_quote_age_seconds: float
    quality: str
    indicators: tuple[PortfolioRiskIndicatorResponse, ...]
