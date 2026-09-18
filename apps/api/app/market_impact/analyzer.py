from app.company_impact.models import CompanyImpact
from app.events.models import MarketEvent
from app.market_impact.models import (
    ImpactFactor,
    MarketImpact,
    TimeHorizon,
)


class MarketImpactAnalyzer:
    """Analyze the economic transmission path of a company impact."""

    def analyze(
        self,
        event: MarketEvent,
        company_impact: CompanyImpact,
    ) -> MarketImpact:
        """Produce a structured market impact assessment."""

        factor = self._detect_factor(
            event_type=event.event_type.value,
            catalyst=event.catalyst.value,
        )

        time_horizon = self._detect_time_horizon(
            event_type=event.event_type.value,
            catalyst=event.catalyst.value,
        )

        rationale = self._build_rationale(
            company_name=company_impact.company_name,
            factor=factor,
            time_horizon=time_horizon,
            impact_type=company_impact.impact_type.value,
        )

        return MarketImpact(
            event_id=company_impact.event_id,
            company_name=company_impact.company_name,
            ticker=company_impact.ticker,
            impact_type=company_impact.impact_type,
            direction=company_impact.direction,
            factor=factor,
            time_horizon=time_horizon,
            confidence=company_impact.confidence,
            evidence_article_ids=company_impact.evidence_article_ids,
            rationale=rationale,
        )

    @staticmethod
    def _detect_factor(
        event_type: str,
        catalyst: str,
    ) -> ImpactFactor:
        """Identify the primary economic transmission factor."""

        if event_type == "monetary_policy":
            return ImpactFactor.FINANCING

        if event_type == "inflation":
            return ImpactFactor.INPUT_COSTS

        if event_type == "trade_policy":
            if catalyst == "tariff":
                return ImpactFactor.MARKET_ACCESS

            return ImpactFactor.SUPPLY_CHAIN

        if event_type == "geopolitical":
            return ImpactFactor.OPERATING_RISK

        if event_type == "corporate_action":
            return ImpactFactor.COMPETITIVE_POSITION

        if event_type == "earnings":
            return ImpactFactor.REVENUE

        if event_type == "regulation":
            return ImpactFactor.REGULATORY_BURDEN

        if event_type == "macroeconomic":
            return ImpactFactor.DEMAND

        return ImpactFactor.OTHER

    @staticmethod
    def _detect_time_horizon(
        event_type: str,
        catalyst: str,
    ) -> TimeHorizon:
        """Estimate the primary impact horizon from event characteristics."""

        if event_type == "monetary_policy":
            return TimeHorizon.MEDIUM_TERM

        if event_type == "inflation":
            return TimeHorizon.MEDIUM_TERM

        if event_type == "trade_policy":
            return TimeHorizon.MEDIUM_TERM

        if event_type == "geopolitical":
            return TimeHorizon.UNCERTAIN

        if event_type == "corporate_action":
            return TimeHorizon.LONG_TERM

        if event_type == "earnings":
            return TimeHorizon.SHORT_TERM

        if event_type == "regulation":
            return TimeHorizon.LONG_TERM

        if event_type == "macroeconomic":
            return TimeHorizon.MEDIUM_TERM

        return TimeHorizon.UNCERTAIN

    @staticmethod
    def _build_rationale(
        company_name: str,
        factor: ImpactFactor,
        time_horizon: TimeHorizon,
        impact_type: str,
    ) -> str:
        """Build a concise explanation of the transmission assessment."""

        return (
            f"{company_name} has a {impact_type} exposure to this event. "
            f"The primary economic transmission factor is "
            f"{factor.value.replace('_', ' ')}, with the main potential "
            f"effects developing over a {time_horizon.value.replace('_', ' ')} "
            "horizon."
        )
