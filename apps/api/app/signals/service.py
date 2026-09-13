from app.market_impact.models import MarketImpact
from app.signals.analyzer import SignalAnalyzer
from app.signals.models import MarketSignal


class SignalIntelligenceService:
    """Application service for signal intelligence."""

    def __init__(self) -> None:
        self._analyzer = SignalAnalyzer()

    def analyze(
        self,
        market_impact: MarketImpact,
    ) -> MarketSignal:
        """Generate a structured market signal."""

        return self._analyzer.analyze(market_impact)
