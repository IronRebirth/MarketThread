from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.portfolio.schemas import PortfolioPositionResponse, PortfolioResponse


class PortfolioCurrencyExposureResponse(BaseModel):
    """API representation of one currency's exposure."""

    currency: str
    position_count: int
    quality: str
    cost_basis: Decimal
    market_value: Decimal | None


class PortfolioAssetClassExposureResponse(BaseModel):
    """API representation of one currency and asset-class exposure bucket."""

    currency: str
    asset_class: str
    position_count: int
    quality: str
    cost_basis: Decimal
    market_value: Decimal | None
    market_value_weight: Decimal | None


class PortfolioPositionExposureResponse(BaseModel):
    """API representation of position-level exposure."""

    model_config = ConfigDict(from_attributes=True)

    position: PortfolioPositionResponse
    cost_basis: Decimal
    market_value: Decimal | None
    market_value_weight: Decimal | None
    quality: str


class PortfolioExposureResponse(BaseModel):
    """API representation of complete portfolio exposure."""

    portfolio: PortfolioResponse
    assessed_at: datetime
    maximum_quote_age_seconds: float
    quality: str
    currencies: tuple[PortfolioCurrencyExposureResponse, ...]
    asset_classes: tuple[PortfolioAssetClassExposureResponse, ...]
    positions: tuple[PortfolioPositionExposureResponse, ...]
