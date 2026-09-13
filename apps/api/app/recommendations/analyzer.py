from app.recommendations.models import Recommendation, RecommendationState
from app.risk.models import RiskConfidenceAssessment
from app.signals.models import MarketSignal


class RecommendationAnalyzer:
    """Generate research-oriented recommendations from signal assessments."""

    def analyze(
        self,
        signal: MarketSignal,
        risk_confidence: RiskConfidenceAssessment,
    ) -> Recommendation:
        """Produce an explainable recommendation state."""

        state = self._classify_state(
            signal=signal,
            risk_confidence=risk_confidence,
        )

        assumptions = self._build_assumptions(signal)

        rationale = self._build_rationale(
            state=state,
            signal=signal,
            risk_confidence=risk_confidence,
        )

        return Recommendation(
            event_id=signal.event_id,
            company_name=signal.company_name,
            ticker=signal.ticker,
            state=state,
            signal_direction=signal.direction.value,
            confidence_score=risk_confidence.confidence.score,
            risk_score=risk_confidence.risk.score,
            confidence_level=risk_confidence.confidence.level.value,
            risk_level=risk_confidence.risk.level.value,
            time_horizon=signal.time_horizon,
            supporting_factors=signal.supporting_factors,
            contradicting_factors=signal.contradicting_factors,
            assumptions=assumptions,
            invalidation_conditions=risk_confidence.invalidation_conditions,
            evidence_article_ids=risk_confidence.evidence_article_ids,
            rationale=rationale,
        )

    @staticmethod
    def _classify_state(
        signal: MarketSignal,
        risk_confidence: RiskConfidenceAssessment,
    ) -> RecommendationState:
        """Determine the recommendation state from evidence and risk."""

        confidence = risk_confidence.confidence.score
        risk = risk_confidence.risk.score
        direction = signal.direction.value

        if confidence < 0.5:
            return RecommendationState.INSUFFICIENT_EVIDENCE

        if direction == "uncertain":
            return RecommendationState.INSUFFICIENT_EVIDENCE

        if risk >= 0.8:
            return RecommendationState.INSUFFICIENT_EVIDENCE

        if direction == "positive":
            if confidence >= 0.8 and risk < 0.4:
                return RecommendationState.CONSIDER

            if confidence >= 0.65:
                return RecommendationState.WATCH

            return RecommendationState.HOLD

        if direction == "negative":
            if confidence >= 0.8 and risk < 0.4:
                return RecommendationState.REDUCE

            if confidence >= 0.65:
                return RecommendationState.WATCH

            return RecommendationState.HOLD

        return RecommendationState.HOLD

    @staticmethod
    def _build_assumptions(
        signal: MarketSignal,
    ) -> tuple[str, ...]:
        """Identify assumptions underlying the recommendation state."""

        assumptions = [
            "The identified market event remains materially relevant.",
            "The economic transmission mechanism remains applicable.",
        ]

        if signal.time_horizon == "uncertain":
            assumptions.append(
                "The timing of the expected impact remains uncertain.",
            )

        return tuple(assumptions)

    @staticmethod
    def _build_rationale(
        state: RecommendationState,
        signal: MarketSignal,
        risk_confidence: RiskConfidenceAssessment,
    ) -> str:
        """Build an explanation of the recommendation state."""

        return (
            f"Recommendation state is {state.value} for {signal.company_name}. "
            f"The underlying signal is {signal.direction.value} with "
            f"{risk_confidence.confidence.level.value} evidence confidence "
            f"and {risk_confidence.risk.level.value} interpretation risk. "
            "This is a research-oriented assessment and not a guarantee "
            "of investment performance."
        )
