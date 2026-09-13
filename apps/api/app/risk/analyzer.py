from app.market_impact.models import MarketImpact
from app.risk.models import (
    ConfidenceAssessment,
    ConfidenceLevel,
    RiskAssessment,
    RiskConfidenceAssessment,
    RiskFactor,
    RiskLevel,
)
from app.signals.models import MarketSignal


class RiskConfidenceAnalyzer:
    """Assess confidence and risk for a structured market signal."""

    def analyze(
        self,
        signal: MarketSignal,
        market_impact: MarketImpact,
    ) -> RiskConfidenceAssessment:
        """Produce an explainable risk and confidence assessment."""

        confidence = self._assess_confidence(
            signal=signal,
            market_impact=market_impact,
        )

        risk = self._assess_risk(
            signal=signal,
            market_impact=market_impact,
            confidence=confidence,
        )

        invalidation_conditions = (
            *signal.invalidation_conditions,
            "New evidence materially changes the underlying interpretation.",
        )

        return RiskConfidenceAssessment(
            event_id=signal.event_id,
            company_name=signal.company_name,
            confidence=confidence,
            risk=risk,
            evidence_article_ids=signal.evidence_article_ids,
            invalidation_conditions=tuple(
                dict.fromkeys(invalidation_conditions),
            ),
        )

    @staticmethod
    def _assess_confidence(
        signal: MarketSignal,
        market_impact: MarketImpact,
    ) -> ConfidenceAssessment:
        """Assess evidence support without interpreting it as profit probability."""

        supporting_factors: list[str] = [
            "The signal has traceable source article references.",
            (
                "The signal is derived from structured event, company, "
                "and market impact analysis."
            ),
        ]

        limitations: list[str] = []

        if market_impact.impact_type.value == "indirect":
            limitations.append("Company exposure is indirect.")

        if market_impact.time_horizon.value == "uncertain":
            limitations.append("The expected impact horizon is uncertain.")

        level = RiskConfidenceAnalyzer._confidence_level(
            signal.confidence,
        )

        rationale = (
            f"Evidence confidence is {level.value} with a score of "
            f"{signal.confidence:.2f}. This score represents support for the "
            "interpretation, not the probability of a profitable outcome."
        )

        return ConfidenceAssessment(
            score=signal.confidence,
            level=level,
            supporting_factors=tuple(supporting_factors),
            limitations=tuple(limitations),
            rationale=rationale,
        )

    @staticmethod
    def _assess_risk(
        signal: MarketSignal,
        market_impact: MarketImpact,
        confidence: ConfidenceAssessment,
    ) -> RiskAssessment:
        """Assess interpretation risk from observable uncertainty factors."""

        factors: list[RiskFactor] = []

        if confidence.score < 0.8:
            factors.append(RiskFactor.LIMITED_EVIDENCE)

        if market_impact.impact_type.value == "indirect":
            factors.append(RiskFactor.INDIRECT_EXPOSURE)

        if market_impact.time_horizon.value == "uncertain":
            factors.append(RiskFactor.HORIZON_UNCERTAINTY)

        if signal.direction.value == "uncertain":
            factors.append(RiskFactor.EVENT_UNCERTAINTY)

        if not signal.evidence_article_ids:
            factors.append(RiskFactor.LIMITED_EVIDENCE)

        level = RiskConfidenceAnalyzer._risk_level(
            signal.risk_score,
        )

        rationale = (
            f"Interpretation risk is {level.value} with a score of "
            f"{signal.risk_score:.2f}. Risk reflects uncertainty in the "
            "analytical chain and does not represent a forecasted loss "
            "percentage."
        )

        return RiskAssessment(
            score=signal.risk_score,
            level=level,
            factors=tuple(dict.fromkeys(factors)),
            rationale=rationale,
        )

    @staticmethod
    def _confidence_level(score: float) -> ConfidenceLevel:
        """Map confidence score to a qualitative level."""

        if score >= 0.8:
            return ConfidenceLevel.HIGH

        if score >= 0.65:
            return ConfidenceLevel.MODERATE

        if score >= 0.5:
            return ConfidenceLevel.LOW

        return ConfidenceLevel.INSUFFICIENT

    @staticmethod
    def _risk_level(score: float) -> RiskLevel:
        """Map risk score to a qualitative level."""

        if score >= 0.8:
            return RiskLevel.CRITICAL

        if score >= 0.6:
            return RiskLevel.HIGH

        if score >= 0.3:
            return RiskLevel.MODERATE

        return RiskLevel.LOW
