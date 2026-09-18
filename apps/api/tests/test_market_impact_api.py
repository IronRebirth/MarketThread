from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.company_impact.models import (
    CompanyImpact,
    CompanyImpactDirection,
    ImpactType,
)
from app.company_impact.persistence import CompanyImpactPersistenceService
from app.db.models.company_impact import CompanyImpactRecord
from app.db.models.event import EventRecord
from app.db.models.market_impact import MarketImpactRecord
from app.events.models import MarketEvent
from app.events.persistence import EventPersistenceService
from app.events.types import EventCatalyst, EventType
from app.main import app
from app.news.intelligence.models import ImpactDirection, MarketRelevance


def make_event() -> MarketEvent:
    timestamp = datetime.now(UTC).replace(microsecond=0)

    return MarketEvent(
        event_id=uuid4(),
        event_type=EventType.TRADE_POLICY,
        title="New semiconductor trade restrictions announced",
        summary="New trade restrictions affect the semiconductor industry.",
        catalyst=EventCatalyst.TARIFF,
        market_relevance=MarketRelevance.HIGH,
        impact_direction=ImpactDirection.NEGATIVE,
        affected_entities=("NVIDIA", "Microsoft"),
        affected_sectors=("Technology",),
        source_article_ids=(uuid4(),),
        first_seen_at=timestamp,
        last_seen_at=timestamp,
        confidence=0.84,
    )


def make_company_impact(
    event: MarketEvent,
    company_name: str,
) -> CompanyImpact:
    return CompanyImpact(
        event_id=event.event_id,
        company_name=company_name,
        impact_type=ImpactType.DIRECT,
        direction=CompanyImpactDirection.NEGATIVE,
        mechanism="Potential exposure through tariffs and market access.",
        confidence=0.84,
        evidence_article_ids=event.source_article_ids,
        rationale="The company is directly associated with the event.",
    )


async def cleanup(
    db_session,
    event_id: UUID,
) -> None:
    await db_session.execute(
        delete(MarketImpactRecord).where(
            MarketImpactRecord.event_id == event_id,
        ),
    )
    await db_session.execute(
        delete(CompanyImpactRecord).where(
            CompanyImpactRecord.event_id == event_id,
        ),
    )
    await db_session.execute(
        delete(EventRecord).where(
            EventRecord.id == event_id,
        ),
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_create_get_and_list_market_impacts(
    db_session,
) -> None:
    event = make_event()

    await EventPersistenceService().persist(
        db_session,
        event,
    )

    company_service = CompanyImpactPersistenceService()

    await company_service.persist(
        db_session,
        make_company_impact(event, "NVIDIA"),
    )
    await company_service.persist(
        db_session,
        make_company_impact(event, "Microsoft"),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/market-impacts/from-event/{event.event_id}",
        )

        assert response.status_code == 201

        payload = response.json()

        assert len(payload) == 2
        assert {item["company_name"] for item in payload} == {
            "NVIDIA",
            "Microsoft",
        }

        impact_id = UUID(payload[0]["impact_id"])

        get_response = await client.get(
            f"/market-impacts/{impact_id}",
        )

        assert get_response.status_code == 200
        assert get_response.json()["impact_id"] == str(impact_id)

        list_response = await client.get(
            "/market-impacts",
            params={
                "event_id": str(event.event_id),
                "factor": "market_access",
                "time_horizon": "medium_term",
            },
        )

        assert list_response.status_code == 200
        assert len(list_response.json()) == 2

    await cleanup(
        db_session,
        event.event_id,
    )


@pytest.mark.asyncio
async def test_create_market_impacts_is_idempotent(
    db_session,
) -> None:
    event = make_event()

    await EventPersistenceService().persist(
        db_session,
        event,
    )

    company_service = CompanyImpactPersistenceService()

    await company_service.persist(
        db_session,
        make_company_impact(event, "NVIDIA"),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        first_response = await client.post(
            f"/market-impacts/from-event/{event.event_id}",
        )
        second_response = await client.post(
            f"/market-impacts/from-event/{event.event_id}",
        )

        assert first_response.status_code == 201
        assert second_response.status_code == 201
        assert first_response.json() == second_response.json()

        records = (
            (
                await db_session.execute(
                    select(MarketImpactRecord).where(
                        MarketImpactRecord.event_id == event.event_id,
                    ),
                )
            )
            .scalars()
            .all()
        )

        assert len(records) == 1

    await cleanup(
        db_session,
        event.event_id,
    )


@pytest.mark.asyncio
async def test_missing_event_returns_404() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/market-impacts/from-event/{uuid4()}",
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_missing_market_impact_returns_404() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/market-impacts/{uuid4()}",
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reversed_time_range_returns_422() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/market-impacts",
            params={
                "start_at": "2027-01-02T00:00:00Z",
                "end_at": "2027-01-01T00:00:00Z",
            },
        )

    assert response.status_code == 422
