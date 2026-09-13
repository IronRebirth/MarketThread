from datetime import UTC, datetime
from uuid import uuid4

from app.company_impact.models import (
    CompanyImpact,
    CompanyImpactDirection,
    ImpactType,
)
from app.events.models import MarketEvent
from app.events.types import EventCatalyst, EventType
from app.market_impact.models import ImpactFactor, TimeHorizon
from app.market_impact.service import MarketImpactService
from app.news.intelligence.models import ImpactDirection, MarketRelevance


def make_event(
    event_type: EventType,
    catalyst: EventCatalyst,
) -> MarketEvent:
    """Create a market event for market impact tests."""

    timestamp = datetime.now(UTC)

    return MarketEvent(
        event_id=uuid4(),
        event_type=event_type,
        title="Market-moving event",
        summary="A market-moving event has occurred.",
        catalyst=catalyst,
        market_relevance=MarketRelevance.HIGH,
        impact_direction=ImpactDirection.NEGATIVE,
        affected_entities=("NVIDIA",),
        affected_sectors=("Technology",),
        source_article_ids=(uuid4(),),
        first_seen_at=timestamp,
        last_seen_at=timestamp,
        confidence=0.84,
    )


def make_company_impact(
    event: MarketEvent,
) -> CompanyImpact:
    """Create a company impact for market impact tests."""

    return CompanyImpact(
        event_id=event.event_id,
        company_name="NVIDIA",
        ticker="NVDA",
        impact_type=ImpactType.DIRECT,
        direction=CompanyImpactDirection.NEGATIVE,
        mechanism="Potential exposure through trade restrictions.",
        confidence=0.84,
        evidence_article_ids=event.source_article_ids,
        rationale="The company has direct exposure to the event.",
    )


def test_detects_trade_policy_market_access_impact() -> None:
    event = make_event(
        EventType.TRADE_POLICY,
        EventCatalyst.TARIFF,
    )
    company_impact = make_company_impact(event)

    impact = MarketImpactService().analyze(
        event,
        company_impact,
    )

    assert impact.event_id == event.event_id
    assert impact.company_name == "NVIDIA"
    assert impact.impact_type == ImpactType.DIRECT
    assert impact.direction == CompanyImpactDirection.NEGATIVE
    assert impact.factor == ImpactFactor.MARKET_ACCESS
    assert impact.time_horizon == TimeHorizon.MEDIUM_TERM
    assert impact.confidence == 0.84
    assert impact.evidence_article_ids == event.source_article_ids


def test_detects_monetary_policy_financing_impact() -> None:
    event = make_event(
        EventType.MONETARY_POLICY,
        EventCatalyst.RATE_CUT,
    )
    company_impact = make_company_impact(event)

    impact = MarketImpactService().analyze(
        event,
        company_impact,
    )

    assert impact.factor == ImpactFactor.FINANCING
    assert impact.time_horizon == TimeHorizon.MEDIUM_TERM


def test_detects_earnings_revenue_impact() -> None:
    event = make_event(
        EventType.EARNINGS,
        EventCatalyst.EARNINGS_SURPRISE,
    )
    company_impact = make_company_impact(event)

    impact = MarketImpactService().analyze(
        event,
        company_impact,
    )

    assert impact.factor == ImpactFactor.REVENUE
    assert impact.time_horizon == TimeHorizon.SHORT_TERM


def test_detects_regulatory_burden() -> None:
    event = make_event(
        EventType.REGULATION,
        EventCatalyst.REGULATORY_CHANGE,
    )
    company_impact = make_company_impact(event)

    impact = MarketImpactService().analyze(
        event,
        company_impact,
    )

    assert impact.factor == ImpactFactor.REGULATORY_BURDEN
    assert impact.time_horizon == TimeHorizon.LONG_TERM


def test_preserves_evidence_and_confidence() -> None:
    event = make_event(
        EventType.GEOPOLITICAL,
        EventCatalyst.SANCTION,
    )
    company_impact = make_company_impact(event)

    impact = MarketImpactService().analyze(
        event,
        company_impact,
    )

    assert impact.evidence_article_ids == company_impact.evidence_article_ids
    assert impact.confidence == company_impact.confidence
    assert impact.time_horizon == TimeHorizon.UNCERTAIN
