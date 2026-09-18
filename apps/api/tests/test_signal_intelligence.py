from uuid import uuid4

from app.company_impact.models import (
    CompanyImpactDirection,
    ImpactType,
)
from app.market_impact.models import ImpactFactor, MarketImpact, TimeHorizon
from app.news.intelligence.models import ImpactDirection
from app.signals.models import (
    SignalDirection,
    SignalOpportunity,
    SignalStrength,
)
from app.signals.service import SignalIntelligenceService


def make_market_impact(
    confidence: float = 0.84,
    direction: ImpactDirection = ImpactDirection.POSITIVE,
    impact_type: ImpactType = ImpactType.DIRECT,
    time_horizon: TimeHorizon = TimeHorizon.MEDIUM_TERM,
) -> MarketImpact:
    """Create market impact data for signal tests."""

    article_id = uuid4()
    event_id = uuid4()

    return MarketImpact(
        event_id=event_id,
        company_name="NVIDIA",
        ticker="NVDA",
        impact_type=impact_type,
        direction=CompanyImpactDirection(direction.value),
        factor=ImpactFactor.DEMAND,
        time_horizon=time_horizon,
        confidence=confidence,
        evidence_article_ids=(article_id,),
        rationale="Structured market impact assessment.",
    )


def test_generates_strong_positive_opportunity() -> None:
    market_impact = make_market_impact(confidence=0.84)

    signal = SignalIntelligenceService().analyze(market_impact)

    assert signal.event_id == market_impact.event_id
    assert signal.company_name == "NVIDIA"
    assert signal.ticker == "NVDA"
    assert signal.direction == SignalDirection.POSITIVE
    assert signal.strength == SignalStrength.STRONG
    assert signal.opportunity == SignalOpportunity.OPPORTUNITY
    assert signal.confidence == 0.84
    assert signal.risk_score == 0.16
    assert signal.time_horizon == "medium_term"


def test_generates_strong_negative_reduce_signal() -> None:
    market_impact = make_market_impact(
        confidence=0.85,
        direction=ImpactDirection.NEGATIVE,
    )

    signal = SignalIntelligenceService().analyze(market_impact)

    assert signal.direction == SignalDirection.NEGATIVE
    assert signal.strength == SignalStrength.STRONG
    assert signal.opportunity == SignalOpportunity.REDUCE


def test_generates_watch_signal_for_moderate_evidence() -> None:
    market_impact = make_market_impact(confidence=0.7)

    signal = SignalIntelligenceService().analyze(market_impact)

    assert signal.strength == SignalStrength.MODERATE
    assert signal.opportunity == SignalOpportunity.WATCH


def test_generates_insufficient_evidence_signal() -> None:
    market_impact = make_market_impact(confidence=0.4)

    signal = SignalIntelligenceService().analyze(market_impact)

    assert signal.strength == SignalStrength.INSUFFICIENT
    assert signal.opportunity == SignalOpportunity.INSUFFICIENT_EVIDENCE


def test_uncertain_direction_cannot_become_opportunity() -> None:
    market_impact = make_market_impact(
        confidence=0.9,
        direction=ImpactDirection.UNCERTAIN,
    )

    signal = SignalIntelligenceService().analyze(market_impact)

    assert signal.direction == SignalDirection.UNCERTAIN
    assert signal.strength == SignalStrength.STRONG
    assert signal.opportunity == SignalOpportunity.INSUFFICIENT_EVIDENCE


def test_indirect_uncertain_horizon_increases_risk() -> None:
    market_impact = make_market_impact(
        confidence=0.7,
        impact_type=ImpactType.INDIRECT,
        time_horizon=TimeHorizon.UNCERTAIN,
    )

    signal = SignalIntelligenceService().analyze(market_impact)

    assert signal.risk_score == 0.6
    assert signal.opportunity == SignalOpportunity.WATCH


def test_signal_retains_evidence_and_invalidation_conditions() -> None:
    market_impact = make_market_impact()

    signal = SignalIntelligenceService().analyze(market_impact)

    assert signal.evidence_article_ids == market_impact.evidence_article_ids
    assert signal.invalidation_conditions
    assert signal.supporting_factors
    assert "profit" in signal.rationale.lower()
