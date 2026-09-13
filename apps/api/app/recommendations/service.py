from app.recommendations.analyzer import RecommendationAnalyzer
from app.recommendations.models import Recommendation
from app.risk.models import RiskConfidenceAssessment
from app.signals.models import MarketSignal


class RecommendationIntelligenceService:
    """Application service for recommendation intelligence."""

    def __init__(self) -> None:
        self._analyzer = RecommendationAnalyzer()

    def analyze(
        self,
        signal: MarketSignal,
        risk_confidence: RiskConfidenceAssessment,
    ) -> Recommendation:
        """Generate a research-oriented recommendation."""

        return self._analyzer.analyze(
            signal=signal,
            risk_confidence=risk_confidence,
        )
