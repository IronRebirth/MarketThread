from uuid import UUID, uuid4

from app.company_impact.models import CompanyImpactDirection, ImpactType
from app.market_impact.models import ImpactFactor, MarketImpact, TimeHorizon
from app.risk.models import (
    ConfidenceLevel,
    RiskFactor,
    RiskLevel,
)
from app.risk.service import RiskConfidenceService
from app.signals.models import (
    MarketSignal,
    SignalDirection,
    SignalOpportunity,
    SignalStrength,
)


def make_signal(
    confidence: float = 0.84,
    risk_score: float = 0.16,
    direction: SignalDirection = SignalDirection.POSITIVE,
    time_horizon: str = "medium_term",
) -> MarketSignal:
    """Create a market signal for risk and confidence tests."""

    return MarketSignal(
        event_id=uuid4(),
        company_name="NVIDIA",
        direction=direction,
        strength=SignalStrength.STRONG,
        opportunity=SignalOpportunity.OPPORTUNITY,
        confidence=confidence,
        risk_score=risk_score,
        time_horizon=time_horizon,
        supporting_factors=("Demand remains strong.",),
        contradicting_factors=(),
        evidence_article_ids=(uuid4(),),
        invalidation_conditions=("Underlying event is reversed.",),
        rationale="Structured signal assessment.",
    )


def make_market_impact(
    event_id: UUID,
    confidence: float = 0.84,
    impact_type: ImpactType = ImpactType.DIRECT,
    time_horizon: TimeHorizon = TimeHorizon.MEDIUM_TERM,
) -> MarketImpact:
    """Create market impact data for risk and confidence tests."""

    return MarketImpact(
        event_id=event_id,
        company_name="NVIDIA",
        impact_type=impact_type,
        direction=CompanyImpactDirection.POSITIVE,
        factor=ImpactFactor.DEMAND,
        time_horizon=time_horizon,
        confidence=confidence,
        evidence_article_ids=(uuid4(),),
        rationale="Structured market impact assessment.",
    )


def test_assesses_high_confidence_and_low_risk() -> None:
    signal = make_signal()
    market_impact = make_market_impact(
        signal.event_id,
        confidence=signal.confidence,
    )

    assessment = RiskConfidenceService().analyze(
        signal,
        market_impact,
    )

    assert assessment.event_id == signal.event_id
    assert assessment.company_name == "NVIDIA"
    assert assessment.confidence.score == 0.84
    assert assessment.confidence.level == ConfidenceLevel.HIGH
    assert assessment.risk.score == 0.16
    assert assessment.risk.level == RiskLevel.LOW


def test_assesses_moderate_confidence() -> None:
    signal = make_signal(
        confidence=0.7,
        risk_score=0.3,
    )
    market_impact = make_market_impact(
        signal.event_id,
        confidence=signal.confidence,
    )

    assessment = RiskConfidenceService().analyze(
        signal,
        market_impact,
    )

    assert assessment.confidence.level == ConfidenceLevel.MODERATE
    assert assessment.risk.level == RiskLevel.MODERATE
    assert RiskFactor.LIMITED_EVIDENCE in assessment.risk.factors


def test_indirect_uncertain_exposure_adds_risk_factors() -> None:
    signal = make_signal(
        confidence=0.7,
        risk_score=0.65,
        time_horizon="uncertain",
    )
    market_impact = make_market_impact(
        signal.event_id,
        confidence=signal.confidence,
        impact_type=ImpactType.INDIRECT,
        time_horizon=TimeHorizon.UNCERTAIN,
    )

    assessment = RiskConfidenceService().analyze(
        signal,
        market_impact,
    )

    assert assessment.risk.level == RiskLevel.HIGH
    assert RiskFactor.INDIRECT_EXPOSURE in assessment.risk.factors
    assert RiskFactor.HORIZON_UNCERTAINTY in assessment.risk.factors
    assert "indirect" in assessment.confidence.limitations[0].lower()


def test_uncertain_direction_adds_event_uncertainty() -> None:
    signal = make_signal(
        confidence=0.55,
        risk_score=0.85,
        direction=SignalDirection.UNCERTAIN,
    )
    market_impact = make_market_impact(
        signal.event_id,
        confidence=signal.confidence,
    )

    assessment = RiskConfidenceService().analyze(
        signal,
        market_impact,
    )

    assert assessment.confidence.level == ConfidenceLevel.LOW
    assert assessment.risk.level == RiskLevel.CRITICAL
    assert RiskFactor.EVENT_UNCERTAINTY in assessment.risk.factors


def test_insufficient_confidence_is_explicit() -> None:
    signal = make_signal(
        confidence=0.4,
        risk_score=0.8,
    )
    market_impact = make_market_impact(
        signal.event_id,
        confidence=signal.confidence,
    )

    assessment = RiskConfidenceService().analyze(
        signal,
        market_impact,
    )

    assert assessment.confidence.level == ConfidenceLevel.INSUFFICIENT
    assert assessment.risk.level == RiskLevel.CRITICAL


def test_invalidation_conditions_are_preserved_and_deduplicated() -> None:
    signal = make_signal()
    signal = signal.model_copy(
        update={
            "invalidation_conditions": (
                "Underlying event is reversed.",
                "New evidence materially changes the underlying interpretation.",
            ),
        },
    )
    market_impact = make_market_impact(
        signal.event_id,
        confidence=signal.confidence,
    )

    assessment = RiskConfidenceService().analyze(
        signal,
        market_impact,
    )

    assert assessment.invalidation_conditions == (
        "Underlying event is reversed.",
        "New evidence materially changes the underlying interpretation.",
    )
    assert assessment.evidence_article_ids == signal.evidence_article_ids
