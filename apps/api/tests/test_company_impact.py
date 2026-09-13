from datetime import UTC, datetime
from uuid import uuid4

from app.company_impact.models import (
    CompanyImpactDirection,
    ImpactType,
)
from app.company_impact.service import CompanyImpactService
from app.events.models import MarketEvent
from app.events.types import EventCatalyst, EventType
from app.news.intelligence.models import ImpactDirection, MarketRelevance


def make_event(
    affected_entities: tuple[str, ...],
    event_type: EventType = EventType.TRADE_POLICY,
    catalyst: EventCatalyst = EventCatalyst.TARIFF,
) -> MarketEvent:
    """Create a market event for company impact tests."""

    timestamp = datetime.now(UTC)

    return MarketEvent(
        event_id=uuid4(),
        event_type=event_type,
        title="New semiconductor trade restrictions announced",
        summary="New trade restrictions affect the semiconductor industry.",
        catalyst=catalyst,
        market_relevance=MarketRelevance.HIGH,
        impact_direction=ImpactDirection.NEGATIVE,
        affected_entities=affected_entities,
        affected_sectors=("Technology",),
        source_article_ids=(uuid4(),),
        first_seen_at=timestamp,
        last_seen_at=timestamp,
        confidence=0.84,
    )


def test_analyzes_direct_company_impact() -> None:
    event = make_event(("NVIDIA",))

    impacts = CompanyImpactService().analyze(event)

    assert len(impacts) == 1

    impact = impacts[0]

    assert impact.event_id == event.event_id
    assert impact.company_name == "NVIDIA"
    assert impact.impact_type == ImpactType.DIRECT
    assert impact.direction == CompanyImpactDirection.NEGATIVE
    assert impact.confidence == 0.84
    assert impact.evidence_article_ids == event.source_article_ids
    assert "tariffs" in impact.mechanism.lower()
    assert "market access" in impact.mechanism.lower()
    assert "supply-chain" in impact.mechanism.lower()


def test_analyzes_multiple_companies() -> None:
    event = make_event(("NVIDIA", "Microsoft"))

    impacts = CompanyImpactService().analyze(event)

    assert {impact.company_name for impact in impacts} == {
        "NVIDIA",
        "Microsoft",
    }


def test_returns_no_impacts_when_event_has_no_companies() -> None:
    event = make_event(())

    impacts = CompanyImpactService().analyze(event)

    assert impacts == ()


def test_preserves_uncertain_direction() -> None:
    event = make_event(("Apple",))
    event = event.model_copy(
        update={
            "impact_direction": ImpactDirection.UNCERTAIN,
        },
    )

    impacts = CompanyImpactService().analyze(event)

    assert impacts[0].direction == CompanyImpactDirection.UNCERTAIN
