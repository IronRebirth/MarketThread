from app.company_impact.models import (
    CompanyImpact,
    CompanyImpactDirection,
    ImpactType,
)
from app.events.models import MarketEvent


class CompanyImpactAnalyzer:
    """Analyze company exposure to a normalized market event."""

    def analyze(
        self,
        event: MarketEvent,
    ) -> tuple[CompanyImpact, ...]:
        """Produce company-level impact assessments."""

        impacts: list[CompanyImpact] = []

        for company_name in event.affected_entities:
            impacts.append(
                self._build_impact(
                    event=event,
                    company_name=company_name,
                ),
            )

        return tuple(impacts)

    @staticmethod
    def _build_impact(
        event: MarketEvent,
        company_name: str,
    ) -> CompanyImpact:
        """Build a baseline company impact assessment."""

        direction = CompanyImpactAnalyzer._map_direction(
            event.impact_direction.value,
        )

        impact_type = ImpactType.DIRECT

        mechanism = CompanyImpactAnalyzer._build_mechanism(
            event_type=event.event_type.value,
            catalyst=event.catalyst.value,
        )

        rationale = (
            f"{company_name} is identified as a directly affected company "
            f"because the event contains an explicit company-level entity "
            f"association."
        )

        return CompanyImpact(
            event_id=event.event_id,
            company_name=company_name,
            impact_type=impact_type,
            direction=direction,
            mechanism=mechanism,
            confidence=event.confidence,
            evidence_article_ids=event.source_article_ids,
            rationale=rationale,
        )

    @staticmethod
    def _map_direction(direction: str) -> CompanyImpactDirection:
        """Map event-level impact direction to company-level direction."""

        mapping = {
            "positive": CompanyImpactDirection.POSITIVE,
            "neutral": CompanyImpactDirection.NEUTRAL,
            "negative": CompanyImpactDirection.NEGATIVE,
            "uncertain": CompanyImpactDirection.UNCERTAIN,
        }

        return mapping[direction]

    @staticmethod
    def _build_mechanism(
        event_type: str,
        catalyst: str,
    ) -> str:
        """Describe the baseline economic transmission mechanism."""

        mechanisms = {
            "monetary_policy": (
                "Potential exposure through financing conditions, "
                "demand, and valuation changes."
            ),
            "inflation": (
                "Potential exposure through input costs, pricing power, "
                "and consumer demand."
            ),
            "trade_policy": (
                "Potential exposure through tariffs, market access, "
                "and supply-chain costs."
            ),
            "geopolitical": (
                "Potential exposure through market access, supply chains, "
                "operations, and geopolitical risk."
            ),
            "corporate_action": (
                "Potential exposure through ownership changes, "
                "business combinations, or strategic restructuring."
            ),
            "earnings": (
                "Potential exposure through changes in operating results, "
                "guidance, and investor expectations."
            ),
            "regulation": (
                "Potential exposure through compliance requirements, "
                "operating constraints, or market access."
            ),
            "macroeconomic": (
                "Potential exposure through changes in economic activity "
                "and aggregate demand."
            ),
        }

        return mechanisms.get(
            event_type,
            f"Potential exposure associated with the {catalyst} catalyst.",
        )
