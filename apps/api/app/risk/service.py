from app.market_impact.models import MarketImpact
from app.risk.analyzer import RiskConfidenceAnalyzer
from app.risk.models import RiskConfidenceAssessment
from app.signals.models import MarketSignal


class RiskConfidenceService:
    """Application service for risk and confidence assessment."""

    def __init__(self) -> None:
        self._analyzer = RiskConfidenceAnalyzer()

    def analyze(
        self,
        signal: MarketSignal,
        market_impact: MarketImpact,
    ) -> RiskConfidenceAssessment:
        """Assess risk and confidence for a market signal."""

        return self._analyzer.analyze(
            signal=signal,
            market_impact=market_impact,
        )
