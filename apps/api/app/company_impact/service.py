from app.company_impact.analyzer import CompanyImpactAnalyzer
from app.company_impact.models import CompanyImpact
from app.events.models import MarketEvent


class CompanyImpactService:
    """Application service for company impact intelligence."""

    def __init__(self) -> None:
        self._analyzer = CompanyImpactAnalyzer()

    def analyze(
        self,
        event: MarketEvent,
    ) -> tuple[CompanyImpact, ...]:
        """Analyze companies affected by a market event."""

        return self._analyzer.analyze(event)
