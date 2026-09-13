from app.company_impact.models import CompanyImpact
from app.events.models import MarketEvent
from app.market_impact.analyzer import MarketImpactAnalyzer
from app.market_impact.models import MarketImpact


class MarketImpactService:
    """Application service for market impact intelligence."""

    def __init__(self) -> None:
        self._analyzer = MarketImpactAnalyzer()

    def analyze(
        self,
        event: MarketEvent,
        company_impact: CompanyImpact,
    ) -> MarketImpact:
        """Analyze economic market impact for a company."""

        return self._analyzer.analyze(
            event=event,
            company_impact=company_impact,
        )
