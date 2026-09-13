from uuid import uuid4

from app.recommendations.models import RecommendationState
from app.recommendations.service import RecommendationIntelligenceService
from app.risk.models import (
    ConfidenceAssessment,
    ConfidenceLevel,
    RiskAssessment,
    RiskConfidenceAssessment,
    RiskLevel,
)
from app.signals.models import (
    MarketSignal,
    SignalDirection,
    SignalOpportunity,
    SignalStrength,
)


def make_signal(
    confidence: float = 0.84,
    direction: SignalDirection = SignalDirection.POSITIVE,
    risk_score: float = 0.16,
) -> MarketSignal:
    """Create a signal for recommendation tests."""

    return MarketSignal(
        event_id=uuid4(),
        company_name="NVIDIA",
        ticker="NVDA",
        direction=direction,
        strength=SignalStrength.STRONG,
        opportunity=SignalOpportunity.OPPORTUNITY,
        confidence=confidence,
        risk_score=risk_score,
        time_horizon="medium_term",
        supporting_factors=("Demand remains strong.",),
        contradicting_factors=(),
        evidence_article_ids=(uuid4(),),
        invalidation_conditions=("Event interpretation changes.",),
        rationale="Structured signal assessment.",
    )


def make_risk_confidence(
    signal: MarketSignal,
    confidence: float | None = None,
    risk_score: float | None = None,
) -> RiskConfidenceAssessment:
    """Create a risk-confidence assessment for recommendation tests."""

    confidence_value = signal.confidence if confidence is None else confidence
    risk_value = signal.risk_score if risk_score is None else risk_score

    confidence_level = (
        ConfidenceLevel.HIGH if confidence_value >= 0.8 else ConfidenceLevel.MODERATE
    )

    risk_level = RiskLevel.LOW if risk_value < 0.3 else RiskLevel.MODERATE

    return RiskConfidenceAssessment(
        event_id=signal.event_id,
        company_name=signal.company_name,
        confidence=ConfidenceAssessment(
            score=confidence_value,
            level=confidence_level,
            supporting_factors=("Traceable evidence.",),
            limitations=(),
            rationale="Evidence assessment.",
        ),
        risk=RiskAssessment(
            score=risk_value,
            level=risk_level,
            factors=(),
            rationale="Risk assessment.",
        ),
        evidence_article_ids=signal.evidence_article_ids,
        invalidation_conditions=signal.invalidation_conditions,
    )


def test_generates_consider_state_for_strong_positive_signal() -> None:
    signal = make_signal()
    risk_confidence = make_risk_confidence(signal)

    recommendation = RecommendationIntelligenceService().analyze(
        signal,
        risk_confidence,
    )

    assert recommendation.state == RecommendationState.CONSIDER
    assert recommendation.company_name == "NVIDIA"
    assert recommendation.ticker == "NVDA"
    assert recommendation.confidence_score == 0.84
    assert recommendation.risk_score == 0.16


def test_generates_reduce_state_for_strong_negative_signal() -> None:
    signal = make_signal(
        direction=SignalDirection.NEGATIVE,
    )
    risk_confidence = make_risk_confidence(signal)

    recommendation = RecommendationIntelligenceService().analyze(
        signal,
        risk_confidence,
    )

    assert recommendation.state == RecommendationState.REDUCE


def test_generates_watch_state_for_moderate_confidence() -> None:
    signal = make_signal(
        confidence=0.7,
        risk_score=0.3,
    )
    risk_confidence = make_risk_confidence(signal)

    recommendation = RecommendationIntelligenceService().analyze(
        signal,
        risk_confidence,
    )

    assert recommendation.state == RecommendationState.WATCH


def test_generates_insufficient_evidence_for_high_risk() -> None:
    signal = make_signal(
        confidence=0.9,
        risk_score=0.82,
    )
    risk_confidence = make_risk_confidence(signal)

    recommendation = RecommendationIntelligenceService().analyze(
        signal,
        risk_confidence,
    )

    assert recommendation.state == RecommendationState.INSUFFICIENT_EVIDENCE


def test_generates_insufficient_evidence_for_uncertain_direction() -> None:
    signal = make_signal(
        direction=SignalDirection.UNCERTAIN,
    )
    risk_confidence = make_risk_confidence(signal)

    recommendation = RecommendationIntelligenceService().analyze(
        signal,
        risk_confidence,
    )

    assert recommendation.state == RecommendationState.INSUFFICIENT_EVIDENCE


def test_preserves_evidence_and_invalidation_conditions() -> None:
    signal = make_signal()
    risk_confidence = make_risk_confidence(signal)

    recommendation = RecommendationIntelligenceService().analyze(
        signal,
        risk_confidence,
    )

    assert recommendation.evidence_article_ids == (risk_confidence.evidence_article_ids)
    assert recommendation.invalidation_conditions == (
        risk_confidence.invalidation_conditions
    )
    assert recommendation.assumptions
    assert "research-oriented" in recommendation.rationale.lower()
