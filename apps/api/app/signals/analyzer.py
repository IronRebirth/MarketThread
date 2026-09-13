from app.company_impact.models import CompanyImpactDirection, ImpactType
from app.market_impact.models import MarketImpact
from app.signals.models import (
    MarketSignal,
    SignalDirection,
    SignalOpportunity,
    SignalStrength,
)


class SignalAnalyzer:
    """Generate a baseline market signal from structured intelligence."""

    def analyze(
        self,
        market_impact: MarketImpact,
    ) -> MarketSignal:
        """Produce a structured signal without forecasting returns."""

        direction = self._map_direction(
            market_impact.direction,
        )

        strength = self._classify_strength(
            market_impact.confidence,
        )

        opportunity = self._classify_opportunity(
            direction=direction,
            strength=strength,
        )

        risk_score = self._calculate_risk(
            market_impact=market_impact,
            strength=strength,
        )

        supporting_factors = self._build_supporting_factors(
            market_impact,
        )

        contradicting_factors = self._build_contradicting_factors(
            market_impact,
        )

        invalidation_conditions = self._build_invalidation_conditions(
            market_impact,
        )

        rationale = self._build_rationale(
            direction=direction,
            strength=strength,
            opportunity=opportunity,
            risk_score=risk_score,
        )

        return MarketSignal(
            event_id=market_impact.event_id,
            company_name=market_impact.company_name,
            direction=direction,
            strength=strength,
            opportunity=opportunity,
            confidence=market_impact.confidence,
            risk_score=risk_score,
            time_horizon=market_impact.time_horizon.value,
            supporting_factors=supporting_factors,
            contradicting_factors=contradicting_factors,
            evidence_article_ids=market_impact.evidence_article_ids,
            invalidation_conditions=invalidation_conditions,
            rationale=rationale,
        )

    @staticmethod
    def _map_direction(
        direction: CompanyImpactDirection,
    ) -> SignalDirection:
        """Map company impact direction to signal direction."""

        mapping = {
            CompanyImpactDirection.POSITIVE: SignalDirection.POSITIVE,
            CompanyImpactDirection.NEGATIVE: SignalDirection.NEGATIVE,
            CompanyImpactDirection.NEUTRAL: SignalDirection.NEUTRAL,
            CompanyImpactDirection.UNCERTAIN: SignalDirection.UNCERTAIN,
        }

        return mapping[direction]

    @staticmethod
    def _classify_strength(confidence: float) -> SignalStrength:
        """Classify evidence strength from the upstream confidence score."""

        if confidence >= 0.8:
            return SignalStrength.STRONG

        if confidence >= 0.65:
            return SignalStrength.MODERATE

        if confidence >= 0.5:
            return SignalStrength.WEAK

        return SignalStrength.INSUFFICIENT

    @staticmethod
    def _classify_opportunity(
        direction: SignalDirection,
        strength: SignalStrength,
    ) -> SignalOpportunity:
        """Map evidence strength and direction to an opportunity state."""

        if strength == SignalStrength.INSUFFICIENT:
            return SignalOpportunity.INSUFFICIENT_EVIDENCE

        if direction == SignalDirection.UNCERTAIN:
            return SignalOpportunity.INSUFFICIENT_EVIDENCE

        if strength == SignalStrength.STRONG:
            if direction == SignalDirection.POSITIVE:
                return SignalOpportunity.OPPORTUNITY

            if direction == SignalDirection.NEGATIVE:
                return SignalOpportunity.REDUCE

        if strength == SignalStrength.MODERATE:
            return SignalOpportunity.WATCH

        return SignalOpportunity.HOLD

    @staticmethod
    def _calculate_risk(
        market_impact: MarketImpact,
        strength: SignalStrength,
    ) -> float:
        """Calculate a baseline risk score from uncertainty and evidence."""

        risk = 1.0 - market_impact.confidence

        if market_impact.time_horizon.value == "uncertain":
            risk += 0.15

        if market_impact.impact_type == ImpactType.INDIRECT:
            risk += 0.15

        if strength == SignalStrength.INSUFFICIENT:
            risk += 0.2

        return min(round(risk, 4), 1.0)

    @staticmethod
    def _build_supporting_factors(
        market_impact: MarketImpact,
    ) -> tuple[str, ...]:
        """Describe factors supporting the signal."""

        return (
            f"Economic factor: {market_impact.factor.value.replace('_', ' ')}",
            (
                "Evidence is linked to the source article set "
                "associated with the market event."
            ),
        )

    @staticmethod
    def _build_contradicting_factors(
        market_impact: MarketImpact,
    ) -> tuple[str, ...]:
        """Describe factors that limit interpretation."""

        factors: list[str] = []

        if market_impact.time_horizon.value == "uncertain":
            factors.append("The expected timing of the impact is uncertain.")

        if market_impact.impact_type == ImpactType.INDIRECT:
            factors.append("The company exposure is indirect.")

        if market_impact.confidence < 0.8:
            factors.append("Evidence strength is below the strong threshold.")

        return tuple(factors)

    @staticmethod
    def _build_invalidation_conditions(
        market_impact: MarketImpact,
    ) -> tuple[str, ...]:
        """Define conditions that would weaken the signal."""

        return (
            "New evidence contradicting the event interpretation.",
            ("Material changes to the underlying economic transmission mechanism."),
            "A reversal or cancellation of the underlying event.",
        )

    @staticmethod
    def _build_rationale(
        direction: SignalDirection,
        strength: SignalStrength,
        opportunity: SignalOpportunity,
        risk_score: float,
    ) -> str:
        """Build a concise explanation of the signal."""

        return (
            f"The signal is {direction.value} with {strength.value} "
            f"evidence strength and an opportunity state of "
            f"{opportunity.value}; baseline risk score is {risk_score:.2f}. "
            "Confidence reflects evidence support, not probability of profit."
        )
